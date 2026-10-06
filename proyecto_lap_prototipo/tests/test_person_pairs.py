"""La misma persona marcada en dos cámaras: validación, desfase de tiempo, concordancia de homografías y fotogramas."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from live_core import calibration, validate_config  # noqa: E402
from live_server import Engine, ajuste_de_relojes, source_time_offset  # noqa: E402

DEMO = json.loads((ROOT / "config" / "ejemplos" / "demo_camaras_A_B.json").read_text(encoding="utf-8"))
H = {c["id"]: calibration(c["pairs"]) for c in DEMO["cameras"]}


def imagen_de(camara, punto):
    """Punto normalizado de la imagen cuyo suelo cae en `punto` del plano (inversa de la homografía de esa cámara)."""
    v = np.linalg.inv(H[camara]) @ np.array([punto[0], punto[1], 1.0])
    return [float(v[0] / v[2]), float(v[1] / v[2])]


def pareja(i, plano, desfase_b=(0.0, 0.0), t=None):
    """La misma persona en `plano` vista por A y por B, con la proyección de B corrida `desfase_b`."""
    return {"id": f"p{i}", "t": float(i if t is None else t),
            "a": {"camera": "A", "point": imagen_de("A", plano)},
            "b": {"camera": "B", "point": imagen_de("B", (plano[0] + desfase_b[0], plano[1] + desfase_b[1]))}}


PUNTOS = [(3.2, 3.4), (3.8, 3.6), (4.4, 3.5), (5.0, 3.9), (5.6, 3.3), (6.1, 3.8), (4.0, 4.4), (5.3, 4.5)]


def config(**cambios):
    c = copy.deepcopy(DEMO)
    c.update(cambios)
    return c


class Motor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.tmp.name) / "live.json")
        self.engine.config = {**self.engine.config, **copy.deepcopy(DEMO)}

    def tearDown(self):
        self.tmp.cleanup()


class Validacion(unittest.TestCase):
    def test_parejas_validas(self):
        validate_config(config(personPairs=[pareja(1, PUNTOS[0])]))

    def test_pareja_invalida(self):
        malas = [{"id": "x", "t": 1, "a": {"camera": "A", "point": [0.5, 0.5]}, "b": {"camera": "A", "point": [0.5, 0.5]}},    # misma cámara
                 {"id": "x", "t": 1, "a": {"camera": "A", "point": [0.5, 0.5]}, "b": {"camera": "Z", "point": [0.5, 0.5]}},    # cámara inexistente
                 {"id": "x", "t": 1, "a": {"camera": "A", "point": [1.5, 0.5]}, "b": {"camera": "B", "point": [0.5, 0.5]}},    # fuera de la imagen
                 {"id": "x", "t": -3, "a": {"camera": "A", "point": [0.5, 0.5]}, "b": {"camera": "B", "point": [0.5, 0.5]}}]  # tiempo inválido
        for mala in malas:
            with self.assertRaises(ValueError, msg=str(mala)):
                validate_config(config(personPairs=[mala]))


class Concordancia(Motor):
    """Con puntos del suelo en las dos cámaras se mide cuánto separa el plano a la misma persona: diagnóstico, no corrección."""

    def test_calibraciones_que_no_concuerdan_se_avisan_sin_corregir_nada(self):
        r = self.engine.person_pairs_check("A", "B", [pareja(i, p, (-2.4, -0.1)) for i, p in enumerate(PUNTOS)])
        self.assertTrue(r["suficiente"])
        self.assertAlmostEqual(r["espacial"]["mediana"], 2.4, delta=0.2)
        self.assertFalse(r["espacial"]["concuerdan"])
        self.assertTrue(any("no concuerdan" in a["texto"] for a in r["avisos"]))
        self.assertNotIn("entrada", r)       # ya no se propone una corrección estimada

    def test_calibraciones_que_concuerdan(self):
        r = self.engine.person_pairs_check("A", "B", [pareja(i, p, (0.05, 0.0)) for i, p in enumerate(PUNTOS)])
        self.assertTrue(r["espacial"]["concuerdan"])
        self.assertLess(r["espacial"]["mediana"], 0.2)
        self.assertFalse(any("no concuerdan" in a["texto"] for a in r["avisos"]))

    def test_detecta_desfase_temporal_consistente(self):
        pares = []
        for i, p in enumerate(PUNTOS):
            item = pareja(i, p, (0.0, 0.0), t=i)
            item["ta"], item["tb"] = float(i), float(i) + 0.8
            pares.append(item)
        r = self.engine.person_pairs_check("A", "B", pares)
        self.assertTrue(r["temporal"]["necesita"])
        # El suceso está 0,8 s más adelante en el video de B: B se lee 0,8 s después.
        self.assertAlmostEqual(r["temporal"]["offset"], 0.8, delta=0.01)
        self.assertEqual(r["temporal"]["syncBase"], 0.0)
        self.assertEqual(r["temporal"]["syncDestino"], 0.8)

    def test_con_pocas_parejas_no_calcula(self):
        r = self.engine.person_pairs_check("A", "B", [pareja(i, p) for i, p in enumerate(PUNTOS[:3])])
        self.assertFalse(r["suficiente"])
        self.assertIn("4 como mínimo", r["avisos"][0]["texto"])

    def test_una_pareja_con_otro_instante_se_senala_y_no_cuenta_en_la_distancia(self):
        pares = [pareja(i, p, t=2.0 + i) | {"ta": 2.0 + i, "tb": 2.0 + i} for i, p in enumerate(PUNTOS)]
        pares[3]["tb"] += 3.0
        r = self.engine.person_pairs_check("A", "B", pares)
        self.assertTrue(r["temporal"]["verificada"])
        self.assertEqual([f["id"] for f in r["pares"] if f["fueraDeTiempo"]], ["p3"])
        self.assertIsNone(next(f for f in r["pares"] if f["id"] == "p3")["distancia"])
        self.assertEqual(r["espacial"]["n"], len(PUNTOS) - 1)

    def test_ignora_parejas_de_otras_camaras_y_exige_dos_camaras_distintas(self):
        r = self.engine.person_pairs_check("B", "A", [pareja(i, p) for i, p in enumerate(PUNTOS)])
        self.assertEqual(r["n"], len(PUNTOS))
        with self.assertRaises(ValueError):
            self.engine.person_pairs_check("A", "A", [])


class SinPuntosDelSuelo(Motor):
    """Los puntos del suelo son opcionales: las personas marcadas bastan para el desfase de tiempo."""

    def setUp(self):
        super().setUp()
        for camara in self.engine.config["cameras"]:
            camara["pairs"] = []

    def parejas(self, n, desfase=0.0):
        def una(i):
            return {"id": f"p{i}", "t": 3.0 + i, "ta": 3.0 + i + desfase, "tb": 3.0 + i,
                    "a": {"camera": "A", "point": [0.2 + 0.05 * (i % 9), 0.5]}, "b": {"camera": "B", "point": [0.3, 0.2 + 0.05 * (i % 9)]}}
        return [una(i) for i in range(n)]

    def test_calcula_el_desfase_sin_geometria(self):
        r = self.engine.person_pairs_check("A", "B", self.parejas(6, 0.4))
        self.assertTrue(r["suficiente"])
        self.assertIsNone(r["espacial"])
        self.assertTrue(r["temporal"]["necesita"] and r["temporal"]["verificada"])
        # La persona está 0,4 s más atrás en el video de B: B no puede leerse antes del inicio, así que se retrasa A.
        self.assertAlmostEqual(r["temporal"]["offset"], -0.4, delta=0.01)
        self.assertAlmostEqual(r["temporal"]["syncBase"], 0.4, delta=0.01)
        self.assertEqual(r["temporal"]["syncDestino"], 0.0)
        self.assertTrue(any("Sin puntos del suelo" in a["texto"] for a in r["avisos"]))

    def test_relojes_ya_sincronizados_quedan_verificados_sin_corregir(self):
        r = self.engine.person_pairs_check("A", "B", self.parejas(5, 0.0))
        self.assertTrue(r["temporal"]["verificada"])
        self.assertFalse(r["temporal"]["necesita"])

    def test_tiempos_incoherentes_no_se_verifican(self):
        pares = self.parejas(6)
        for i, par in enumerate(pares):
            par["ta"] += (i % 3) * 0.6        # tres desfases distintos: no hay un desfase consistente
        r = self.engine.person_pairs_check("A", "B", pares)
        self.assertFalse(r["temporal"]["verificada"])
        self.assertTrue(any("no coinciden en el tiempo" in a["texto"] for a in r["avisos"]))

    def test_iniciar_sin_sincronizar_se_bloquea_por_el_tiempo(self):
        self.engine.config["clocksVerified"] = False
        with self.assertRaisesRegex(ValueError, "personas de apoyo"):
            self.engine.start({"detector": "yolo", "requireUnified": True, "testRun": False})


class Fotogramas(Motor):
    def test_info_y_fotograma_de_un_video(self):
        info = self.engine.camera_frame_info("A")
        self.assertGreater(info["duration"], 10)
        self.assertGreater(info["width"], 100)
        jpeg = self.engine.camera_frame_at("A", 5.0)
        self.assertEqual(jpeg[:2], b"\xff\xd8")
        self.assertNotEqual(jpeg, self.engine.camera_frame_at("A", 12.0), "otro instante, otra imagen")

    def test_el_desfase_de_la_camara_mueve_el_fotograma(self):
        self.engine.config["cameras"][0]["offset"] = 3.0
        self.assertEqual(self.engine.camera_frame_at("A", 0.0), self.engine.camera_frame_at("A", 0.0))
        self.assertAlmostEqual(self.engine.camera_frame_info("A")["offset"], 3.0)

    def test_instante_fuera_del_video_y_fuentes_en_vivo(self):
        with self.assertRaisesRegex(ValueError, "fuera del video"):
            self.engine.camera_frame_at("A", 99999)
        self.engine.config["cameras"][1]["source"] = "rtsp://127.0.0.1/x"
        with self.assertRaisesRegex(ValueError, "videos grabados"):
            self.engine.camera_frame_info("B")
        with self.assertRaisesRegex(ValueError, "desconocida"):
            self.engine.camera_frame_info("Z")


class DesfaseDeLectura(Motor):
    """El desfase calculado con personas debe dejar a la misma persona en el mismo instante común al leer los videos."""

    def setUp(self):
        super().setUp()
        for camara in self.engine.config["cameras"]:
            camara["pairs"] = []

    def camara(self, cid):
        return next(c for c in self.engine.config["cameras"] if c["id"] == cid)

    def parejas(self, adelanto_b, n=6):
        """El mismo suceso está `adelanto_b` s más adelante en el video de B que en el de A (los dos sin desfase aplicado)."""
        return [{"id": f"p{i}", "t": 3.0 + i, "ta": 3.0 + i, "tb": 3.0 + i + adelanto_b,
                 "a": {"camera": "A", "point": [0.2 + 0.05 * i, 0.5]}, "b": {"camera": "B", "point": [0.3, 0.2 + 0.05 * i]}} for i in range(n)]

    def aplicar(self, r):
        t = r["temporal"]
        self.camara("A")["syncOffset"], self.camara("B")["syncOffset"] = t["syncBase"], t["syncDestino"]

    def test_ajuste_de_relojes_con_desfase_positivo_negativo_y_sin_cambio(self):
        a, b = {"id": "A"}, {"id": "B"}
        positivo = ajuste_de_relojes(a, b, [1.5] * 5)
        self.assertEqual((positivo["sync_destino"], positivo["sync_base"], positivo["necesita"]), (1.5, 0.0, True))
        negativo = ajuste_de_relojes(a, b, [-1.5] * 5)
        self.assertEqual((negativo["sync_destino"], negativo["sync_base"], negativo["necesita"]), (0.0, 1.5, True))
        self.assertFalse(ajuste_de_relojes(a, b, [0.05] * 5)["necesita"])
        self.assertFalse(ajuste_de_relojes(a, b, [1.5] * 3)["necesita"], "con menos de 4 parejas no se corrige")
        self.assertFalse(ajuste_de_relojes(a, b, [1.5, -1.0, 2.5, 0.0, 3.0])["necesita"], "diferencias incoherentes no se corrigen")

    def test_el_desfase_deja_a_la_persona_en_el_mismo_instante(self):
        for adelanto in (1.5, -1.5, 0.8):
            self.camara("A").pop("syncOffset", None)
            self.camara("B").pop("syncOffset", None)
            pares = self.parejas(adelanto)
            r = self.engine.person_pairs_check("A", "B", pares)
            self.assertTrue(r["temporal"]["necesita"], adelanto)
            self.aplicar(r)
            for par in pares:
                ta = par["ta"] - source_time_offset(self.camara("A"))
                tb = par["tb"] - source_time_offset(self.camara("B"))
                self.assertAlmostEqual(ta, tb, delta=0.01, msg=f"adelanto {adelanto}")
            self.assertGreaterEqual(min(source_time_offset(self.camara("A")), source_time_offset(self.camara("B"))), 0.0)

    def test_recalcular_despues_de_aplicar_es_estable(self):
        pares = self.parejas(1.5)
        for par in pares:
            par["pa"], par["pb"] = par["ta"], par["tb"]        # lo que guarda el panel: instante en el archivo
        r = self.engine.person_pairs_check("A", "B", pares)
        self.aplicar(r)
        otra = self.engine.person_pairs_check("A", "B", pares)
        self.assertFalse(otra["temporal"]["necesita"])
        self.assertAlmostEqual(otra["temporal"]["offset"], 1.5, delta=0.01)
        self.assertEqual(otra["temporal"]["syncDestino"], r["temporal"]["syncDestino"])

    def test_pa_y_pb_deben_ser_numeros_validos(self):
        par = self.parejas(0.5, n=1)[0]
        validate_config(config(personPairs=[{**par, "pa": 3.0, "pb": 3.5}]))
        with self.assertRaises(ValueError):
            validate_config(config(personPairs=[{**par, "pa": -1.0, "pb": 3.5}]))


if __name__ == "__main__":
    unittest.main()
