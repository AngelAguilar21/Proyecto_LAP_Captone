"""Rendimiento del análisis: presets, un solo paso de OSNet para varias cámaras, vectores que el motor no descartaría y apertura de video."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import live_server  # noqa: E402
from following.reid import OSNetEmbedder  # noqa: E402
from identity.engine import MotorIdentidadV2  # noqa: E402


class Presets(unittest.TestCase):
    def test_auto_elige_por_numero_de_camaras_en_cpu_y_conserva_preciso_con_gpu(self):
        elegir = live_server.rendimiento_elegido
        self.assertEqual(elegir("auto", 1)[0], "precise")
        self.assertEqual(elegir("auto", 2)[0], "balanced")
        self.assertEqual(elegir("auto", 3)[0], "balanced")
        self.assertEqual(elegir("auto", 4)[0], "balanced")
        self.assertEqual(elegir("auto", 7)[0], "fast")
        self.assertEqual(elegir("auto", 7, tier="gpu_media")[0], "precise")
        self.assertEqual(elegir("fast", 1)[0], "fast")

    def test_los_presets_bajan_el_costo_y_uno_invalido_se_rechaza(self):
        pasos = [live_server.RENDIMIENTO[k]["step"] for k in ("precise", "balanced", "fast")]
        self.assertEqual(pasos, sorted(pasos))
        self.assertIsNone(live_server.RENDIMIENTO["precise"]["size"])
        self.assertLess(live_server.RENDIMIENTO["fast"]["size"], live_server.RENDIMIENTO["balanced"]["size"])
        with self.assertRaises(ValueError):
            live_server.rendimiento_elegido("turbo", 2)


class OSNetEnLote(unittest.TestCase):
    """OSNet con lote fijo de 16: cada llamada cobra un bloque entero aunque lleve un solo recorte."""

    def embedder(self):
        e = OSNetEmbedder.__new__(OSNetEmbedder)
        e.error, e.batch, e.dimension, e.size, e.input_name = None, 4, 8, (16, 32), "input"
        llamadas = []

        class Sesion:
            def run(self, _salidas, entradas):
                lote = entradas["input"]
                llamadas.append(len(lote))
                return [np.repeat(lote.reshape(len(lote), -1).mean(axis=1, keepdims=True), 8, axis=1) + np.arange(8)]

        e.session = Sesion()
        e.llamadas = llamadas
        return e

    def test_los_recortes_de_varias_camaras_van_juntos_y_vuelven_a_su_camara(self):
        e = self.embedder()
        a = np.full((100, 100, 3), 60, np.uint8)
        b = np.full((100, 100, 3), 200, np.uint8)
        cajas = [[0, 0, 40, 80], [10, 0, 50, 80]]
        resultado = e.embed_varios([(a, cajas, None), (b, cajas[:1], None), (a, [], None)])
        self.assertEqual([len(r) for r in resultado], [2, 1, 0])
        self.assertEqual(e.llamadas, [4], "3 recortes de 3 trabajos: una sola llamada de un bloque")
        self.assertTrue(np.allclose([np.linalg.norm(v) for r in resultado for v in r], 1.0))
        self.assertFalse(np.allclose(resultado[0][0], resultado[1][0]), "cada vector corresponde a su propio recorte")
        e2 = self.embedder()
        suelto = e2.embed(a, cajas)
        self.assertTrue(np.allclose(suelto[0], resultado[0][0]))

    def test_mas_de_un_bloque_se_divide_y_un_recorte_invalido_queda_en_none(self):
        e = self.embedder()
        frame = np.full((100, 100, 3), 90, np.uint8)
        cajas = [[0, 0, 40, 80]] * 9 + [[0, 0, 2, 2], None]
        resultado = e.embed_varios([(frame, cajas, None)])[0]
        self.assertEqual(e.llamadas, [4, 4, 4])
        self.assertIsNone(resultado[9])
        self.assertIsNone(resultado[10])
        self.assertTrue(all(v is not None for v in resultado[:9]))


class VectoresQueElMotorUsa(unittest.TestCase):
    def motor(self):
        cfg = {"cameras": [{"id": "A", "links": [], "pairs": [], "x": 0, "y": 0}], "width": 10, "height": 10, "clocksVerified": True,
               "handoffSeconds": 12}
        return MotorIdentidadV2(cfg)

    def fila(self, t, v):
        return {"camera": "A", "local": 1, "box": [100, 100, 160, 260], "pixel": [130, 260], "point": None, "embedding": v,
                "embeddingFresh": True, "partial": False, "score": 0.9, "height": None}

    def test_no_pide_vector_si_el_motor_lo_descartaria_por_muestrear_hace_poco(self):
        motor = self.motor()
        v = np.random.default_rng(1).normal(size=64)
        v /= np.linalg.norm(v)
        self.assertTrue(motor.necesita_vista("A", 1, 0.0), "track nuevo: sí")
        motor.update([self.fila(0.0, v)], 0.0, tamanos={"A": (1280, 720)})
        sample = motor.asociador.sample_s
        self.assertFalse(motor.necesita_vista("A", 1, sample / 2), "menos de sample_interval_s desde la última vista")
        self.assertTrue(motor.necesita_vista("A", 1, sample + 0.05))
        self.assertTrue(motor.necesita_vista("A", 1), "sin instante se comporta como antes")


class AbrirArchivo(unittest.TestCase):
    def test_si_la_aceleracion_falla_abre_en_modo_normal(self):
        import cv2
        llamadas = []

        class Falso:
            def __init__(self, abierto):
                self.abierto = abierto

            def isOpened(self):
                return self.abierto

            def read(self):
                return False, None

            def release(self):
                llamadas.append("release")

        def fabrica(*args):
            llamadas.append(len(args))
            return Falso(len(args) == 1)          # con aceleración (3 argumentos) no entrega cuadros; sin ella sí abre

        with mock.patch.object(cv2, "VideoCapture", side_effect=fabrica):
            cap = live_server.abrir_archivo("video.mp4")
        self.assertEqual(llamadas[0], 3)
        self.assertIn("release", llamadas)
        self.assertTrue(cap.isOpened())

    def test_pedir_un_modo_de_rendimiento_invalido_al_iniciar_falla(self):
        with tempfile.TemporaryDirectory() as d:
            motor = live_server.Engine(Path(d) / "live.json")
            with self.assertRaises(ValueError):
                motor.start({"detector": "yolo", "performance": "turbo"})


class RegionFiable(unittest.TestCase):
    """Fuera de la región donde hay referencias la homografía no se extrapola."""

    def camara(self):
        import json
        from live_core import calibration
        demo = json.loads((ROOT / "config" / "ejemplos" / "demo_camaras_A_B.json").read_text(encoding="utf-8"))
        cam = dict(demo["cameras"][0])
        cam.update(h=calibration(cam["pairs"]), projects=True)
        cam["fiable"] = live_server.region_fiable(cam)
        return cam

    def test_dentro_se_ubica_y_fuera_no(self):
        from live_core import calibration
        pares = [[0.4, 0.3, 2.0, 1.0], [0.6, 0.3, 4.0, 1.0], [0.6, 0.5, 4.0, 3.0], [0.4, 0.5, 2.0, 3.0]]
        cam = {"pairs": pares, "h": calibration(pares), "projects": True}
        cam["fiable"] = live_server.region_fiable(cam)
        punto, fiable = live_server.ubicar_en_plano(cam, 0.5, 0.4, 1.7)
        self.assertTrue(fiable)
        self.assertAlmostEqual(punto[0], 3.0, delta=0.05)
        for u, v in ((0.5, 0.9), (0.05, 0.4), (0.5, 0.05)):          # el primer plano, un lado y el horizonte: sin referencias cerca
            punto, fiable = live_server.ubicar_en_plano(cam, u, v, 1.7)
            self.assertFalse(fiable, (u, v))
            self.assertIsNone(punto)

    def test_sin_homografia_no_hay_posicion(self):
        cam = self.camara()
        self.assertEqual(live_server.ubicar_en_plano({**cam, "projects": False}, 0.5, 0.5, 1.7), (None, False))
        self.assertIsNone(live_server.region_fiable({"pairs": [[0, 0, 0, 0], [1, 0, 1, 0]]}), "con menos de 4 referencias no hay región")

    def test_la_region_es_el_casco_ampliado_y_queda_dentro_de_la_imagen(self):
        pares = [[0.4, 0.3, 0, 0], [0.6, 0.3, 1, 0], [0.6, 0.5, 1, 1], [0.4, 0.5, 0, 1]]
        region = live_server.region_fiable({"pairs": pares})
        self.assertTrue((region >= 0).all() and (region <= 1).all())
        self.assertAlmostEqual(float(region[:, 0].min()), 0.35, delta=0.01)
        self.assertAlmostEqual(float(region[:, 1].max()), 0.55, delta=0.01)


class PlanoRelativo(unittest.TestCase):
    def test_un_plano_relativo_no_se_filtra_con_el_limite_de_trabajo_del_plano_dibujado(self):
        from spatial_scope import accepts
        escala = {"workArea": [[0, 0], [10, 0], [10, 4], [0, 4]]}
        self.assertFalse(accepts({}, escala, 0.5, 0.5, (5, 7)), "con plano real, fuera del límite se descarta")
        self.assertTrue(accepts({}, escala, 0.5, 0.5, (5, 7), image_only=True), "un plano relativo se trata solo por la imagen")


if __name__ == "__main__":
    unittest.main()
