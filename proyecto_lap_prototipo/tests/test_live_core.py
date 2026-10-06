"""Calibración, ocupación, validación y cámaras relacionadas por personas marcadas."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import default_config
from live_core import MIN_PAREJAS_RELACION, Occupancy, calibration, project, related_cameras, validate_config


def row(pid, x, y):
    return {"id": pid, "camera": "A", "point": [x, y], "predicted": False}


def pareja(i, a="A", b="B"):
    return {"id": f"p{i}", "t": float(i), "a": {"camera": a, "point": [.5, .8]}, "b": {"camera": b, "point": [.4, .7]}}


class LiveCoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = default_config()
        self.cfg["clocksVerified"] = True

    def test_ground_projection_and_degenerate_calibration(self):
        h = calibration([[0, 0, 0, 0], [1, 0, 12, 0], [1, 1, 12, 8], [0, 1, 0, 8]])
        p = project(h, .5, .5)
        self.assertAlmostEqual(p[0], 6)
        self.assertAlmostEqual(p[1], 4)
        with self.assertRaises(ValueError):
            calibration([[0, 0, 0, 0], [.2, 0, 1, 0], [.4, 0, 2, 0], [.6, 0, 3, 0]])

    def test_alert_requires_persistence_and_clears_when_empty(self):
        self.cfg.update(minPeople=2, dwell=2)
        occupancy = Occupancy(self.cfg)
        rows = [row("P1", 1, 1), row("P2", 1.1, 1)]
        self.assertFalse(occupancy.update(rows, 0)["clusters"][0]["alert"])
        self.assertTrue(occupancy.update(rows, 2)["clusters"][0]["alert"])
        self.assertEqual(occupancy.update([], 3)["clusters"], [])

    def test_predictions_do_not_inflate_occupancy(self):
        occupancy = Occupancy(self.cfg)
        self.assertEqual(occupancy.update([{**row("P1", 1, 1), "predicted": True}], 1)["mappedCount"], 0)

    def test_configuration_rejects_invalid_geometry_and_nonfinite_values(self):
        for patch in ({"radius": float("nan")}, {"width": 0}, {"minPeople": 2.5}, {"background": "javascript:bad"}):
            with self.assertRaises(ValueError):
                validate_config({**copy.deepcopy(self.cfg), **patch})

    def test_configuration_accepts_created_floors_and_business_context(self):
        config = copy.deepcopy(self.cfg)
        config["commercialContext"] = {"hasBusinesses": True}
        config["zones"] = [{"id":"shop-1","name":"Cafetería","kind":"commercial","source":"operator",
                            "shape":"rectangle","points":[[1,1],[3,1],[3,2],[1,2]],
                            "business":{"category":"food","widthM":2,"depthM":1,"areaM2":2,"capacity":8}}]
        validate_config(config)

        floor = {key: copy.deepcopy(config[key]) for key in ("width","height","unit","background","floor","zones","commercialContext")}
        config.update(planId="floor-a1b2c3d4", plans={"floor-a1b2c3d4":floor}, cameras=[])
        validate_config(config)

    def test_retired_fields_are_removed_and_people_calibration_restores_ground_points(self):
        config = copy.deepcopy(self.cfg)
        medidos = [[.1, .9, 1, 1], [.9, .9, 5, 1], [.9, .5, 5, 4], [.1, .5, 1, 4]]
        camara = config["cameras"][0]
        camara.update(pairs=[[.2, .8, 2, 2], [.8, .8, 4, 2], [.8, .6, 4, 3], [.2, .6, 2, 3]], heading=90, fov=60, coverageShape="free",
                      peopleCalibration={"base": "B", "replaced": medidos})
        config.update(alignment={"B": {}}, connections={"A|B": {}}, cameraRelations={}, identityEngine="legacy", identityAlign=True)
        validate_config(config)
        for campo in ("alignment", "connections", "cameraRelations", "identityEngine", "identityAlign"):
            self.assertNotIn(campo, config)
        self.assertNotIn("peopleCalibration", camara)
        self.assertNotIn("coverageShape", camara)
        self.assertEqual(camara["pairs"], medidos)

    def test_sin_puntos_medidos_guardados_se_conservan_los_actuales(self):
        config = copy.deepcopy(self.cfg)
        actuales = [[.2, .8, 2, 2], [.8, .8, 4, 2], [.8, .6, 4, 3]]
        config["cameras"][0].update(pairs=copy.deepcopy(actuales), peopleCalibration={"base": "B", "replaced": []})
        validate_config(config)
        self.assertEqual(config["cameras"][0]["pairs"], actuales)
        self.assertNotIn("peopleCalibration", config["cameras"][0])


class CamarasRelacionadas(unittest.TestCase):
    def config(self, parejas=(), links=None):
        c = default_config()
        for cam in c["cameras"]:
            cam["links"] = []
        c["cameras"].append({**copy.deepcopy(c["cameras"][0]), "id": "C"})
        if links:
            c["cameras"][0]["links"] = links
        c["personPairs"] = list(parejas)
        return c

    def test_sin_personas_marcadas_no_hay_relacion(self):
        self.assertEqual(related_cameras(self.config()), {"A": [], "B": [], "C": []})

    def test_la_misma_persona_marcada_suficientes_veces_relaciona_las_dos_camaras(self):
        pocas = related_cameras(self.config([pareja(i) for i in range(MIN_PAREJAS_RELACION - 1)]))
        self.assertEqual(pocas["A"], [])
        bastantes = related_cameras(self.config([pareja(i) for i in range(MIN_PAREJAS_RELACION)]))
        self.assertEqual(bastantes["A"], ["B"])
        self.assertEqual(bastantes["B"], ["A"])
        self.assertEqual(bastantes["C"], [])

    def test_los_enlaces_manuales_se_conservan(self):
        self.assertEqual(related_cameras(self.config(links=["C"]))["C"], ["A"])

    def test_una_camara_inactiva_no_se_relaciona(self):
        c = self.config([pareja(i) for i in range(MIN_PAREJAS_RELACION)])
        c["cameras"][1]["active"] = False
        self.assertNotIn("B", related_cameras(c))
        self.assertEqual(related_cameras(c)["A"], [])


if __name__ == "__main__":
    unittest.main()
