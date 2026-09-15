from pathlib import Path
import threading
import time

import cv2


class VideoSource:
    """Entrega frames y tiempo de contenido; admite archivos y streams locales autorizados."""

    def __init__(self, source, root):
        self.live = isinstance(source,int) or source.lower().startswith(("rtsp://", "http://", "https://", "rtmp://"))
        if isinstance(source,int):
            self.capture=cv2.VideoCapture(source)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
        elif self.live:
            self.capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
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

    def _receive(self):
        # Conserva solo el fotograma reciente para no acumular retraso durante inferencia.
        try:
            while not self.closed.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    raise ValueError("Se interrumpió la señal. No se interpreta la pérdida de señal como cero personas.")
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
                self.condition.wait_for(lambda: self.latest is not None or self.failure is not None or self.closed.is_set(), timeout=6)
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
