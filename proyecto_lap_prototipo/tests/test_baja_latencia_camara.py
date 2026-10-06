"""El video en vivo no debe acumular segundos de retraso.

Ya se habia corregido este mismo sintoma para la vista previa de calibracion
("Ver imagen en vivo"), con banderas de FFmpeg que evitan que el demuxer
acumule cuadros antes de entregarlos. Pero la sesion de analisis real usa un
camino de codigo distinto (VideoSource, en following/stream_source.py) que no tenia
esas banderas: por eso el retraso de 10 segundos volvio a aparecer al iniciar
seguimiento sobre una camara en vivo, aunque la vista previa ya estuviera bien.

Estas pruebas no necesitan una camara real: interceptan cv2.VideoCapture para
comprobar que la variable de entorno de FFmpeg tiene las banderas correctas en
el instante exacto en que se abre la captura, y que se restaura despues.
"""
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

CLAVE = "OPENCV_FFMPEG_CAPTURE_OPTIONS"
ESPERADAS = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0|reorder_queue_size;0"


class CapturaFalsa:
    """Sustituye a cv2.VideoCapture: no abre nada de verdad, solo registra con
    qué variable de entorno estaba puesta al construirse."""
    vistas = []

    def __init__(self, source, *args, **kwargs):
        CapturaFalsa.vistas.append(os.environ.get(CLAVE))
        self.source = source
        self.ajustes = []

    def isOpened(self):
        return True

    def get(self, prop):
        return 25.

    def set(self, prop, value=None):
        self.ajustes.append((prop, value))
        return True

    def read(self):
        return True, "frame-falso"

    def release(self):
        pass


class LowLatencyFfmpegTests(unittest.TestCase):
    def setUp(self):
        self.previo = os.environ.pop(CLAVE, None)

    def tearDown(self):
        if self.previo is None:
            os.environ.pop(CLAVE, None)
        else:
            os.environ[CLAVE] = self.previo

    def test_pone_las_banderas_y_las_quita_al_salir(self):
        from following.stream_source import low_latency_ffmpeg
        self.assertNotIn(CLAVE, os.environ)
        with low_latency_ffmpeg():
            self.assertEqual(os.environ[CLAVE], ESPERADAS)
        self.assertNotIn(CLAVE, os.environ)

    def test_restaura_el_valor_anterior_en_vez_de_borrarlo(self):
        from following.stream_source import low_latency_ffmpeg
        os.environ[CLAVE] = "algo_que_ya_habia"
        with low_latency_ffmpeg():
            self.assertEqual(os.environ[CLAVE], ESPERADAS)
        self.assertEqual(os.environ[CLAVE], "algo_que_ya_habia")

    def test_extensiones_hls_solo_se_permiten_cuando_se_piden(self):
        from following.stream_source import low_latency_ffmpeg
        with low_latency_ffmpeg():
            self.assertNotIn("allowed_extensions", os.environ[CLAVE])
        with low_latency_ffmpeg(allow_all_extensions=True):
            self.assertEqual(os.environ[CLAVE], ESPERADAS + "|allowed_extensions;ALL")
        self.assertNotIn(CLAVE, os.environ)

    def test_restaura_incluso_si_algo_falla_dentro(self):
        from following.stream_source import low_latency_ffmpeg
        with self.assertRaises(ValueError):
            with low_latency_ffmpeg():
                raise ValueError("fallo simulado")
        self.assertNotIn(CLAVE, os.environ)


class VideoSourceLatenciaTests(unittest.TestCase):
    def setUp(self):
        self.previo = os.environ.pop(CLAVE, None)
        CapturaFalsa.vistas = []

    def tearDown(self):
        if self.previo is None:
            os.environ.pop(CLAVE, None)
        else:
            os.environ[CLAVE] = self.previo

    def test_una_camara_rtsp_abre_con_las_banderas_de_baja_latencia(self):
        import following.stream_source as modulo
        with patch.object(modulo.cv2, "VideoCapture", CapturaFalsa):
            fuente = modulo.VideoSource("rtsp://camara.local/stream", Path("."))
            fuente.close()
        self.assertEqual(CapturaFalsa.vistas, [ESPERADAS],
                         "VideoSource no aplico las banderas de baja latencia al abrir")
        # y no debe quedar puesta para el resto del proceso
        self.assertNotIn(CLAVE, os.environ)

    def test_limita_el_buffer_interno_de_opencv_a_un_cuadro(self):
        import following.stream_source as modulo
        capturas = []

        class Registradora(CapturaFalsa):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                capturas.append(self)

        with patch.object(modulo.cv2, "VideoCapture", Registradora):
            fuente = modulo.VideoSource("rtsp://camara.local/stream", Path("."))
            fuente.close()
        self.assertEqual(len(capturas), 1)
        self.assertIn((modulo.cv2.CAP_PROP_BUFFERSIZE, 1), capturas[0].ajustes,
                      "no se limito CAP_PROP_BUFFERSIZE a 1 en la fuente en vivo")

    def test_un_archivo_local_no_toca_la_variable_de_entorno(self):
        # Un video grabado no pasa por FFmpeg en modo red: no debe alterar nada.
        import following.stream_source as modulo
        with patch.object(modulo.cv2, "VideoCapture", CapturaFalsa):
            with self.assertRaises(ValueError):
                modulo.VideoSource("no_existe.mp4", Path("."))
        self.assertEqual(CapturaFalsa.vistas, [])

    def test_dos_camaras_abiertas_a_la_vez_no_se_pisan(self):
        # Si dos hilos abren una camara en vivo al mismo tiempo, el candado de
        # low_latency_ffmpeg no debe dejar que uno vea la variable del otro a
        # medio restaurar.
        import following.stream_source as modulo
        vistos = []

        class LentaYRegistra(CapturaFalsa):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                import time
                time.sleep(.02)
                vistos.append(os.environ.get(CLAVE))

        # patch.object no es seguro entre hilos: se aplica una sola vez para
        # todo el grupo, y es low_latency_ffmpeg (con su propio candado) quien
        # tiene que evitar que un hilo vea la variable de entorno del otro.
        errores = []
        def abrir():
            try:
                modulo.VideoSource("rtsp://otra.local/stream", Path(".")).close()
            except Exception as exc:
                errores.append(exc)

        with patch.object(modulo.cv2, "VideoCapture", LentaYRegistra):
            hilos = [threading.Thread(target=abrir) for _ in range(4)]
            for h in hilos: h.start()
            for h in hilos: h.join(timeout=5)
        self.assertEqual(errores, [])
        self.assertTrue(all(v == ESPERADAS for v in vistos), vistos)
        self.assertNotIn(CLAVE, os.environ)


if __name__ == '__main__':
    unittest.main()
