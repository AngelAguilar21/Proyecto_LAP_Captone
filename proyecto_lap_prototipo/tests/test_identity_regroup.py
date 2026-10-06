"""Reagrupación al cerrar la sesión y reescritura de la grabación con IDs finales."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from identity import MotorIdentidadV2  # noqa: E402
from identity.closing import reescribir_replay  # noqa: E402
from identity.regroup import ReagrupadorPlano  # noqa: E402
from test_identity_engine import DEMO, TAMANOS, obs, vector  # noqa: E402

FPS = 5.0


def tracklet(uid, camara, gid, inicio, fin, muestras=10):
    return {"uid": uid, "camera": camara, "gid": gid, "inicio": inicio, "fin": fin, "muestras": muestras}


def serie(inicio, fin, x, y, vx=0.0):
    """Posiciones a 5 por segundo de alguien que camina a velocidad vx."""
    ticks = np.arange(inicio, fin + 1e-9, 1 / FPS)
    return [(float(t), x + vx * (t - inicio), y) for t in ticks]


class Reagrupacion(unittest.TestCase):
    def reagrupar(self, tracklets, series, prototipos=None, **kw):
        return ReagrupadorPlano(escala=1.6, fps=FPS, **kw)(tracklets, series, prototipos or {})

    def test_dos_camaras_juntas_en_el_plano_son_una_persona(self):
        r = self.reagrupar([tracklet("A/L1/T1", "A", 1, 0, 10), tracklet("B/L1/T1", "B", 2, 0, 10)],
                           {"A/L1/T1": serie(0, 10, 5, 5, 0.3), "B/L1/T1": serie(0, 10, 5.2, 5.1, 0.3)})
        self.assertEqual(r["personas"], 1)
        self.assertEqual(r["publico"]["A/L1/T1"], r["publico"]["B/L1/T1"])
        self.assertEqual(r["uniones_plano"], 1)

    def test_lejos_en_el_plano_no_se_unen_aunque_el_asociador_las_uniera(self):
        r = self.reagrupar([tracklet("A/L1/T1", "A", 1, 0, 10), tracklet("B/L1/T1", "B", 1, 0, 10)],
                           {"A/L1/T1": serie(0, 10, 2, 2), "B/L1/T1": serie(0, 10, 9, 7)})
        self.assertEqual(r["personas"], 2)
        self.assertEqual(r["separados"], 1)
        self.assertNotEqual(r["publico"]["A/L1/T1"], r["publico"]["B/L1/T1"])

    def test_dos_tramos_de_la_misma_camara_a_la_vez_nunca_son_la_misma_persona(self):
        r = self.reagrupar([tracklet("A/L1/T1", "A", 1, 0, 10), tracklet("A/L2/T1", "A", 1, 2, 12)],
                           {"A/L1/T1": serie(0, 10, 2, 2), "A/L2/T1": serie(2, 12, 2.1, 2)})
        self.assertEqual(r["personas"], 2)

    def test_un_grupo_apretado_no_se_une_por_el_plano(self):
        # Dos personas de A y dos de B caminan muy juntas (B1 y B2 a 5 cm): la posición no distingue a una de otra.
        tracklets = [tracklet(f"{c}/L{i}/T1", c, g, 0, 10) for c, i, g in (("A", 1, 1), ("A", 2, 2), ("B", 1, 3), ("B", 2, 4))]
        series = {"A/L1/T1": serie(0, 10, 5.0, 5), "A/L2/T1": serie(0, 10, 5.4, 5),
                  "B/L1/T1": serie(0, 10, 5.2, 5), "B/L2/T1": serie(0, 10, 5.25, 5)}
        r = self.reagrupar(tracklets, series)
        self.assertEqual(r["uniones_plano"], 0)
        self.assertEqual(r["personas"], 4)

    def test_un_tramo_cortado_por_oclusion_se_vuelve_a_unir_si_se_parece(self):
        tracklets = [tracklet("A/L1/T1", "A", 1, 0, 4), tracklet("A/L1/T2", "A", 2, 6, 12)]
        series = {"A/L1/T1": serie(0, 4, 3, 3, 0.5), "A/L1/T2": serie(6, 12, 6, 3, 0.5)}
        v = np.ones(8) / np.sqrt(8)
        r = self.reagrupar(tracklets, series, {"A/L1/T1": v, "A/L1/T2": v})
        self.assertEqual(r["personas"], 1, "gids distintos pero idénticos en apariencia y sin chocar: el agrupamiento global los junta")
        self.assertEqual(r["uniones_apariencia"], 1)
        mismo = [tracklet("A/L1/T1", "A", 1, 0, 4), tracklet("A/L1/T2", "A", 1, 6, 12)]
        r = self.reagrupar(mismo, series, {"A/L1/T1": v, "A/L1/T2": v})
        self.assertEqual(r["personas"], 1)

    def test_la_apariencia_junta_tramos_de_camaras_distintas_aunque_el_plano_no_diga_nada(self):
        v = np.ones(8) / np.sqrt(8)
        tracklets = [tracklet("A/L1/T1", "A", 1, 0, 6), tracklet("B/L1/T1", "B", 2, 20, 26), tracklet("C/L1/T1", "C", 3, 40, 46)]
        r = self.reagrupar(tracklets, {}, {u["uid"]: v for u in tracklets}, usar_posicion=False)
        self.assertEqual(r["personas"], 1)
        self.assertEqual(r["uniones_apariencia"], 2)

    def test_la_apariencia_distinta_no_se_junta_y_los_choques_mandan(self):
        a, b = np.array([1.0, 0, 0, 0]), np.array([0, 1.0, 0, 0])
        distintos = [tracklet("A/L1/T1", "A", 1, 0, 6), tracklet("B/L1/T1", "B", 2, 20, 26)]
        r = self.reagrupar(distintos, {}, {"A/L1/T1": a, "B/L1/T1": b}, usar_posicion=False)
        self.assertEqual(r["personas"], 2)
        # Iguales en apariencia pero a la vez en la misma cámara: son dos personas.
        iguales = [tracklet("A/L1/T1", "A", 1, 0, 10), tracklet("A/L2/T1", "A", 2, 2, 12)]
        r = self.reagrupar(iguales, {}, {"A/L1/T1": a, "A/L2/T1": a}, usar_posicion=False)
        self.assertEqual(r["personas"], 2)
        self.assertEqual(r["uniones_apariencia"], 0)

    def test_una_cadena_de_choques_impide_juntar_a_seis_personas_en_menos_de_seis(self):
        v = np.ones(8) / np.sqrt(8)       # todos idénticos en apariencia: lo único que los separa es estar a la vez en la misma cámara
        tracklets = [tracklet(f"A/L{i}/T1", "A", i, 0, 10) for i in range(1, 7)] + [tracklet("B/L1/T1", "B", 9, 30, 40)]
        r = self.reagrupar(tracklets, {}, {u["uid"]: v for u in tracklets}, usar_posicion=False)
        self.assertEqual(r["personas"], 6)

    def test_el_mismo_gid_con_apariencia_distinta_se_separa(self):
        mismo = [tracklet("A/L1/T1", "A", 1, 0, 4), tracklet("A/L1/T2", "A", 1, 6, 12)]
        series = {"A/L1/T1": serie(0, 4, 3, 3), "A/L1/T2": serie(6, 12, 6, 3)}
        r = self.reagrupar(mismo, series, {"A/L1/T1": np.array([1.0, 0, 0]), "A/L1/T2": np.array([0, 1.0, 0])}, min_parecido=0.5)
        self.assertEqual(r["personas"], 2)
        self.assertEqual(r["separados"], 1)

    def test_numeracion_por_orden_de_aparicion_y_pasadas_breves_sin_numero(self):
        tracklets = [tracklet("A/L1/T1", "A", 1, 10, 20), tracklet("A/L2/T1", "A", 2, 0, 8),
                     tracklet("A/L3/T1", "A", 3, 30, 30.4, muestras=1)]
        series = {u: serie(i, f, 2, 2) for u, i, f in (("A/L1/T1", 10, 20), ("A/L2/T1", 0, 8), ("A/L3/T1", 30, 30.4))}
        r = self.reagrupar(tracklets, series)
        self.assertEqual(r["publico"], {"A/L2/T1": 1, "A/L1/T1": 2})
        self.assertEqual(r["pasadas_breves"], 1)

    def test_sin_posicion_solo_actuan_apariencia_y_conteo(self):
        r = self.reagrupar([tracklet("A/L1/T1", "A", 1, 0, 10), tracklet("B/L1/T1", "B", 2, 0, 10)],
                           {"A/L1/T1": serie(0, 10, 5, 5), "B/L1/T1": serie(0, 10, 5.1, 5)}, usar_posicion=False)
        self.assertEqual(r["uniones_plano"], 0)
        self.assertEqual(r["personas"], 2)


def sesion_con_cierre():
    """Tres personas vistas por A y B (calibraciones coherentes); devuelve el motor ya recorrido."""
    config = copy.deepcopy(DEMO)
    motor = MotorIdentidadV2(config, ajustes={"threshold": 0.7, "average_threshold": 0.5, "same_camera_threshold": 0.75, "split_threshold": 0.5})
    vectores = [vector(21), vector(22), vector(23)]
    for i in range(120):
        t = round(i * 0.2, 3)
        a = [obs("A", k + 1, 2.0 + 3 * k + 0.25 * t, 2.0 + 2 * k, v, caja_x=100 + 350 * k) for k, v in enumerate(vectores)]
        b = [obs("B", k + 11, 2.0 + 3 * k + 0.25 * t, 2.0 + 2 * k, v, caja_x=100 + 350 * k) for k, v in enumerate(vectores)]
        motor.update(copy.deepcopy(a + b), t, tamanos=TAMANOS)
    return motor


class CierreDeSesion(unittest.TestCase):
    def test_el_cierre_numera_de_1_a_n_y_une_las_camaras(self):
        motor = sesion_con_cierre()
        cierre = motor.cierre()
        self.assertEqual(cierre.resultado["personas"], 3)
        ids = {cierre.id_final(c, l, 10.0) for c, l in (("A", 1), ("A", 2), ("A", 3), ("B", 11), ("B", 12), ("B", 13))}
        self.assertEqual(ids, {1, 2, 3})
        self.assertEqual(cierre.id_final("A", 1, 10.0), cierre.id_final("B", 11, 10.0))
        self.assertIsNone(cierre.id_final("Z", 1, 10.0))

    def test_resumen_sin_datos_personales(self):
        resumen = sesion_con_cierre().cierre().resumen()
        self.assertEqual(set(resumen), {"personas", "uniones_plano", "separados", "pasadas_breves", "geometria", "cambios"})

    def test_reescribir_replay_cambia_solo_el_id(self):
        motor = sesion_con_cierre()
        cierre = motor.cierre()
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / "manifest.json").write_text(json.dumps({"session": "x", "status": "ended"}), encoding="utf-8")
            muestra = {"t": 10.0, "cameras": [{"id": "A", "people": [
                {"id": "T00001", "local": 1, "box": None, "point": [1, 2], "association": "local"},
                {"id": "T00009", "local": 99, "box": None, "point": [3, 4], "association": "local"},
                {"id": "P00001", "box": None, "point": [5, 6], "association": "local"}]}]}
            (carpeta / "samples.jsonl").write_text(json.dumps(muestra) + "\n" + "no es json\n", encoding="utf-8")
            n = reescribir_replay(carpeta, cierre)
            lineas = (carpeta / "samples.jsonl").read_text(encoding="utf-8").splitlines()
            nueva = json.loads(lineas[0])["cameras"][0]["people"]
            self.assertEqual(n, 1)
            self.assertRegex(nueva[0]["id"], r"^P0000[123]$")
            self.assertTrue(nueva[0]["confirmed"])
            self.assertEqual(nueva[0]["point"], [1, 2])
            self.assertEqual(nueva[1]["id"], "T00009")
            self.assertFalse(nueva[1]["confirmed"])
            self.assertNotIn("confirmed", nueva[2])          # sin id local: grabación anterior, se deja igual
            self.assertEqual(lineas[1], "no es json")        # una línea dañada no se pierde ni detiene el cierre
            meta = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["identity"]["personas"], 3)
            self.assertTrue(meta["identity"]["finalizada"])


if __name__ == "__main__":
    unittest.main()
