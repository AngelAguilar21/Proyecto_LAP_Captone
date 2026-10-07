import contextlib
import os
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import cv2

# Protege la variable de entorno global de FFmpeg mientras se abre una captura.
# Sin el candado, dos hilos que abren cámaras RTSP a la vez podrían pisarse la
# configuración de baja latencia entre sí.
_ffmpeg_lock = threading.Lock()


def is_youtube_url(source):
    if not isinstance(source, str):
        return False
    host = (urlparse(source).hostname or '').lower()
    return host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be') or host.endswith('.youtube.com')


def canonical_youtube_url(source):
    """Convierte también las URLs internas /api/stats de YouTube a un video."""
    parsed = urlparse(source)
    query = parse_qs(parsed.query)
    video_id = (query.get('v') or query.get('docid') or [None])[0]
    if not video_id and parsed.path.startswith('/embed/'):
        video_id = parsed.path.split('/embed/', 1)[1].split('/', 1)[0]
    if not video_id and parsed.netloc.lower() == 'youtu.be':
        video_id = parsed.path.strip('/').split('/', 1)[0]
    if not video_id:
        return source
    return f'https://www.youtube.com/watch?{urlencode({"v": video_id})}'


def resolve_stream_source(source):
    """Resuelve YouTube a una URL de medios que OpenCV/FFmpeg pueda leer."""
    if not is_youtube_url(source):
        return source
    try:
        import yt_dlp
    except ImportError as exc:
        raise ValueError('Para usar YouTube instala la dependencia yt-dlp y reinicia AeroTrack.') from exc
    target = canonical_youtube_url(source)
    # Para una fuente en vivo priorizamos 360p: las variantes HLS de 480/720p
    # suelen tardar más en entregar el primer segmento y algunas cámaras
    # públicas rechazan esa pista aunque el video siga disponible.
    options = {'format': 'bestvideo[height<=360]/bestvideo[height<=480]/bestvideo[height<=720]/bestvideo/best', 'quiet': True, 'no_warnings': True, 'noplaylist': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(target, download=False)
    except Exception as exc:
        raise ValueError(f'No se pudo resolver el video de YouTube: {exc}') from exc
    media_url = info.get('url')
    if not media_url:
        formats = [item for item in info.get('formats', []) if item.get('url') and item.get('vcodec') not in (None, 'none')]
        if formats:
            media_url = formats[-1]['url']
    if not media_url:
        raise ValueError('YouTube no entregó una URL de video reproducible para esta transmisión.')
    return media_url


@contextlib.contextmanager
def low_latency_ffmpeg(allow_all_extensions=False):
    """Evita que FFmpeg acumule segundos de video en un stream en vivo.

    Sin estas banderas, el demuxer de FFmpeg guarda varios segundos de cuadros
    antes de entregarlos, y ese retraso crece sin parar aunque se lea al ritmo
    que llegan: el problema está dentro de FFmpeg, no en el bucle de lectura.
    `OPENCV_FFMPEG_CAPTURE_OPTIONS` solo se lee al abrir la captura, así que
    basta con que estas banderas estén puestas durante el `cv2.VideoCapture(...)`,
    y se restaura el valor anterior al salir porque es una variable de entorno
    del proceso, no de esta captura en particular.

    `allow_all_extensions` solo debe activarse para fuentes HLS ya resueltas
    por yt-dlp (YouTube): relaja una restriccion de seguridad de FFmpeg, por
    lo que RTSP y demas fuentes conservan el comportamiento estricto.
    """
    with _ffmpeg_lock:
        clave = "OPENCV_FFMPEG_CAPTURE_OPTIONS"
        previo = os.environ.get(clave)
        opciones = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0|reorder_queue_size;0"
        if allow_all_extensions:
            # YouTube Live entrega una playlist HLS cuyos segmentos pueden llevar
            # extensiones variables; FFmpeg los rechaza por defecto.
            opciones += "|allowed_extensions;ALL"
        os.environ[clave] = opciones
        try:
            yield
        finally:
            if previo is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = previo


class VideoSource:
    """Entrega frames y tiempo de contenido; admite archivos y streams locales autorizados."""

    def __init__(self, source, root):
        self.original_source = source
        self.hls = isinstance(source, str) and is_youtube_url(source)
        # YouTube serves ~5 s HLS segments. A 5 s open/read limit can expire
        # while the next segment is being published, especially over Wi-Fi.
        self.open_timeout_ms = 20000 if self.hls else 5000
        self.read_timeout_ms = 15000 if self.hls else 5000
        if self.hls:
            source = resolve_stream_source(source)
        self.media_source = source
        self.live = isinstance(source,int) or source.lower().startswith(("rtsp://", "http://", "https://", "rtmp://"))
        if isinstance(source,int):
            self.capture=cv2.VideoCapture(source)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
        elif self.live:
            with low_latency_ffmpeg(self.hls):
                self.capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG,
                    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.open_timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.read_timeout_ms])
            try:
                # Complementa las banderas de FFmpeg: sin esto OpenCV puede
                # quedarse con un cuadro más en su propia cola interna.
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except cv2.error:
                pass
        else:
            path = Path(source)
            path = path if path.is_absolute() else root/path
            if not path.is_file():
                raise ValueError("No se encontró el video. Cárgalo nuevamente o revisa su ruta.")
            self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            self.capture.release()
            raise ValueError("No se pudo abrir la fuente de video.")
        self.capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        if not 0 < self.fps <= 1000:
            self.fps = 25.
        self.frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT)) if not self.live else 0
        self.duration = self.frames/self.fps if self.frames > 0 else None
        self.index = -1
        self.started = time.monotonic()
        self.condition = threading.Condition()
        self.closed = threading.Event()
        self.latest = None
        self.failure = None
        self.reader = None
        if self.live:
            self.reader = threading.Thread(target=self._receive, daemon=True)
            self.reader.start()

    def _reconnect_live(self):
        """Reabre una fuente en vivo tras un corte transitorio de lectura."""
        source = self.original_source
        if isinstance(source, str) and is_youtube_url(source):
            source = resolve_stream_source(source)
        if isinstance(source, int):
            capture = cv2.VideoCapture(source)
        else:
            with low_latency_ffmpeg(self.hls):
                capture = cv2.VideoCapture(
                    source,
                    cv2.CAP_FFMPEG,
                    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.open_timeout_ms,
                     cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.read_timeout_ms],
                )
        if not capture.isOpened():
            capture.release()
            return False
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except cv2.error:
            pass
        old_capture = self.capture
        self.capture = capture
        self.media_source = source
        old_capture.release()
        return True

    def _receive(self):
        # Conserva solo el fotograma reciente para no acumular retraso durante inferencia.
        missed_reads = 0
        reconnect_failures = 0
        try:
            while not self.closed.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    missed_reads += 1
                    if missed_reads < 3:
                        time.sleep(.15)
                        continue
                    missed_reads = 0
                    reconnect_failures += 1
                    if reconnect_failures <= 5 and self._reconnect_live():
                        continue
                    if reconnect_failures <= 5:
                        time.sleep(.5)
                        continue
                    raise ValueError("Se interrumpió la señal después de varios reintentos. No se interpreta la pérdida de señal como cero personas.")
                missed_reads = 0
                reconnect_failures = 0
                with self.condition:
                    self.latest = (frame, time.monotonic()-self.started)
                    self.condition.notify_all()
        except Exception as exc:
            with self.condition:
                self.failure = exc
                self.condition.notify_all()
        finally:
            self.capture.release()

    def read(self, target=0):
        if self.live:
            with self.condition:
                self.condition.wait_for(lambda: self.latest is not None or self.failure is not None or self.closed.is_set(), timeout=35 if self.hls else 12)
                if self.failure:
                    raise self.failure
                if self.latest is None:
                    raise ValueError("La cámara no entregó una imagen dentro del tiempo esperado.")
                result, self.latest = self.latest, None
                return result
        wanted = int(round(target*self.fps))
        if self.frames > 0 and wanted >= self.frames:
            return None, target
        if self.index == -1 and wanted > 0:
            if not self.capture.set(cv2.CAP_PROP_POS_FRAMES, wanted):
                raise ValueError("No se pudo avanzar al instante de vista previa.")
            self.index = wanted-1
        while self.index < wanted-1:
            if not self.capture.grab():
                raise ValueError("La lectura del video se interrumpió antes del final esperado.")
            self.index += 1
        ok, frame = self.capture.read()
        self.index += 1
        if not ok:
            if self.frames > 0 and self.index < self.frames-1:
                raise ValueError("No se pudo decodificar una muestra del video.")
            return None, target
        return frame, self.index/self.fps

    def close(self):
        self.closed.set()
        if self.reader:
            with self.condition:
                self.condition.notify_all()
            self.reader.join(timeout=6)
        else:
            self.capture.release()
