"""El modelo de detección se carga una vez por proceso, no en cada inicio.

Medido en este equipo: construir P2PNet (leer el checkpoint y armar la red)
tarda varios segundos. Ese costo no depende de la sesion que se esta iniciando, asi que
pagarlo en cada "Iniciar" -incluida cada prueba rapida de una camara durante la
configuracion- era tiempo perdido: eso es lo que describia el reporte "al
cargar el modelo p2pnet me sale con delay, demora mucho tiempo en cargar".
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path('proyecto_lap_prototipo').resolve()))
sys.path.insert(0, str(Path('proyecto_lap_prototipo/src').resolve()))
sys.path.insert(0, str(Path('proyecto_lap_prototipo/external/P2PNet').resolve()))

import live_server  # noqa: E402


class DetectorCacheTests(unittest.TestCase):
    def setUp(self):
        self.engine = live_server.Engine.__new__(live_server.Engine)
        self.engine.detector_cache = None
        self.engine.detector_cache_key = None

    def test_modo_invalido_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.engine.load_detector("otro", {})

    def test_p2pnet_se_carga_una_vez_y_la_segunda_vez_es_mucho_mas_rapido(self):
        primera = time.perf_counter()
        detector_a = self.engine.load_detector("p2pnet", {})
        tiempo_primera = time.perf_counter() - primera

        segunda = time.perf_counter()
        detector_b = self.engine.load_detector("p2pnet", {})
        tiempo_segunda = time.perf_counter() - segunda

        self.assertIs(detector_a, detector_b, "la segunda llamada reconstruyó el modelo en vez de reutilizarlo")
        # con margen generoso: lo que importa es el orden de magnitud, no un
        # numero exacto que varia segun la maquina
        self.assertLess(tiempo_segunda, tiempo_primera / 3,
                        f"reutilizar el detector no fue claramente mas rapido "
                        f"(primera vez {tiempo_primera:.2f}s, segunda {tiempo_segunda:.2f}s)")
        self.assertLess(tiempo_segunda, 1.0, f"reutilizar el detector tomó {tiempo_segunda:.2f}s, debería ser casi instantáneo")

    def test_p2pnet_ajusta_el_tamano_de_analisis_sin_recargar_los_pesos(self):
        detector_a = self.engine.load_detector("p2pnet", {"inferenceSize": 640})
        detector_b = self.engine.load_detector("p2pnet", {"inferenceSize": 512})
        self.assertIs(detector_a, detector_b)
        self.assertEqual(detector_b.lado_max, 512)

    def test_p2pnet_de_verdad_detecta_igual_con_el_detector_reutilizado(self):
        # No basta con que sea el mismo objeto: tiene que seguir funcionando.
        import cv2
        frame = cv2.imread(str(Path('external/P2PNet/vis/demo1.jpg')))
        self.assertIsNotNone(frame)

        self.engine.load_detector("p2pnet", {})  # primera carga, se descarta
        detector = self.engine.load_detector("p2pnet", {})  # reutilizado
        detecciones = detector.detectar(frame)
        self.assertGreater(len(detecciones), 100, "el detector reutilizado no detectó la multitud de la imagen oficial")

    def test_p2pnet_procesa_dos_camaras_en_un_solo_lote(self):
        import cv2
        frame = cv2.imread(str(Path('external/P2PNet/vis/demo1.jpg')))
        detector = self.engine.load_detector("p2pnet", {"inferenceSize": 128})
        batches = detector.detectar_lote([frame, frame])
        self.assertEqual(len(batches), 2)
        self.assertTrue(all(len(detections) > 100 for detections in batches))


if __name__ == '__main__':
    unittest.main()
