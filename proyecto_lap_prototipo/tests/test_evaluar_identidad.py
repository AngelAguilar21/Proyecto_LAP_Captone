"""Métricas de identidad: IDF1, cambios de ID, fragmentación y personas contadas."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import evaluar_identidad as ev


def fila(cam, t, x, ident):
    return {"camara": cam, "t": t, "caja": (x, .2, x + .1, .6), "id": ident}


def escena(ids_sistema):
    """Dos personas reales (P en x=.1, Q en x=.6) vistas 6 instantes; ids_sistema decide qué ID recibe cada una."""
    gt, sistema = [], []
    for k in range(6):
        t = k * .2
        for real, x in (("P", .1), ("Q", .6)):
            gt.append(fila("A", t, x, real))
            sistema.append(fila("A", t, x, ids_sistema(real, k)))
    return gt, sistema


class MetricasTests(unittest.TestCase):
    def test_perfect_identities(self):
        gt, sistema = escena(lambda real, k: "s" + real)
        r = ev.metricas(gt, sistema)
        self.assertEqual((r["IDF1"], r["cambios_de_id"], r["fragmentos"]), (1., 0, 0))
        self.assertEqual((r["personas_reales"], r["ids_sistema_que_siguen_a_alguien"], r["exceso_de_ids"]), (2, 2, 0))

    def test_id_switch_is_counted_and_lowers_idf1(self):
        gt, sistema = escena(lambda real, k: "s" + real if real == "Q" or k < 3 else "otro")
        r = ev.metricas(gt, sistema)
        self.assertEqual(r["cambios_de_id"], 1)
        self.assertLess(r["IDF1"], 1.)
        self.assertEqual(r["exceso_de_ids"], 1)

    def test_one_person_split_across_cameras_counts_as_two_ids(self):
        gt = [fila("A", k * .2, .1, "P") for k in range(5)] + [fila("B", k * .2, .1, "P") for k in range(5)]
        sistema = [fila("A", k * .2, .1, "a1") for k in range(5)] + [fila("B", k * .2, .1, "b1") for k in range(5)]
        r = ev.metricas(gt, sistema)
        self.assertAlmostEqual(r["IDF1"], .5)
        self.assertEqual((r["personas_reales"], r["ids_sistema_que_siguen_a_alguien"]), (1, 2))
        self.assertEqual((r["cambios_de_id"], r["ids_por_persona"]), (0, 2.0))  # sin cambios dentro de cada cámara

    def test_fragmentation_counts_lost_then_recovered(self):
        gt = [fila("A", k * .2, .1, "P") for k in range(6)]
        sistema = [fila("A", k * .2, .1, "s1") for k in (0, 1, 4, 5)]
        r = ev.metricas(gt, sistema)
        self.assertEqual((r["fragmentos"], r["cambios_de_id"]), (1, 0))
        self.assertAlmostEqual(r["recall_deteccion"], 4 / 6, places=3)

    def test_purity_drops_when_one_id_mixes_two_people(self):
        gt, sistema = escena(lambda real, k: "mezcla" if k < 3 else "s" + real)
        self.assertLess(ev.metricas(gt, sistema)["pureza_media"], 1.)


class EtiquetasTests(unittest.TestCase):
    def test_track_labels_expand_to_boxes(self):
        obs = [{"camara": "A", "local": 3, "t": k * .2, "caja": (.1, .2, .2, .6), "id": "g1"} for k in range(5)]
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "e.csv"
            with open(ruta, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["camara", "local_id", "t_ini", "t_fin", "id_real"])
                w.writerow(["A", 3, 0.0, 0.4, "P"])
                w.writerow(["A", 9, 0.0, 1.0, ""])
            gt = ev.expandir_etiquetas(ruta, obs)
        self.assertEqual(len(gt), 3)
        self.assertEqual({g["id"] for g in gt}, {"P"})


if __name__ == "__main__":
    unittest.main()
