"""Motor de identidad entre cámaras: registro desde la configuración y filas que entrega al servidor."""
import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from identity import MotorIdentidadV2, crear_motor_identidad, registro_desde_config  # noqa: E402

DEMO = json.loads((ROOT / "config" / "ejemplos" / "demo_camaras_A_B.json").read_text(encoding="utf-8"))
DIM = 512


def unitario(v):
    return v / np.linalg.norm(v)


def config(**cambios):
    c = copy.deepcopy(DEMO)
    c.update(cambios)
    return c


def vector(semilla):
    return unitario(np.random.default_rng(semilla).normal(size=DIM)).astype(np.float32)


def obs(camara, local, x, y, vec, caja_x=300, score=0.9):
    """Observación como la arma live_server: caja en píxeles, punto en el plano y vector de apariencia."""
    return {"camera": camara, "local": local, "point": (x, y), "pixel": [caja_x + 30., 460.], "score": score,
            "box": [caja_x, 300., caja_x + 60., 460.], "color": None, "embedding": vec, "embeddingFresh": True, "height": None}


TAMANOS = {"A": (1280, 720), "B": (1280, 720)}


def correr(motor, pasos, dt=0.2, **extra):
    """Alimenta `pasos` instantes (lista de listas de observaciones) y devuelve la salida del último."""
    salida = []
    for i, observaciones in enumerate(pasos):
        salida = motor.update(copy.deepcopy(observaciones), round(i * dt, 3), **extra)
    return salida


class RegistroDesdeConfig(unittest.TestCase):
    def test_links_y_handoff_pasan_a_transiciones_dirigidas(self):
        registro = registro_desde_config(config(handoffSeconds=9))
        pares = {(t["from"], t["to"]) for t in registro["transitions"]}
        self.assertEqual(pares, {("A", "B"), ("B", "A")})
        self.assertTrue(all(t["t_min_s"] == 0 and t["t_max_s"] == 9 for t in registro["transitions"]))

    def test_un_enlace_en_un_solo_sentido_es_una_sola_transicion(self):
        c = config()
        c["cameras"][1]["links"] = []
        registro = registro_desde_config(c)
        self.assertEqual({(t["from"], t["to"]) for t in registro["transitions"]}, {("A", "B")})

    def test_camaras_de_planos_distintos_no_se_enlazan(self):
        c = config()
        c["cameras"][1]["planId"] = "lap-1"
        self.assertEqual(registro_desde_config(c)["transitions"], [])

    def test_camaras_inactivas_no_entran(self):
        c = config()
        c["cameras"][1]["active"] = False
        registro = registro_desde_config(c)
        self.assertEqual(set(registro["cameras"]), {"A"})
        self.assertEqual(registro["transitions"], [])

    def test_modo_calibrado_solo_con_relojes_verificados_y_homografia(self):
        self.assertEqual(registro_desde_config(config())["mode"], "calibrado")
        sin_relojes = registro_desde_config(config(clocksVerified=False))
        self.assertEqual(sin_relojes["mode"], "visual_temporal")
        self.assertEqual((sin_relojes["transitions"], sin_relojes["overlaps"]), ([], []), "sin relojes verificados no se unen cámaras")
        sin = config()
        for c in sin["cameras"]:
            c["pairs"] = []
        registro = registro_desde_config(sin)
        self.assertEqual(registro["mode"], "visual_temporal")
        self.assertTrue(all(not c["calibrada"] for c in registro["cameras"].values()))

    def test_sin_calibracion_el_solape_se_permite(self):
        sin = config()
        for c in sin["cameras"]:
            c["pairs"] = []
        self.assertEqual(registro_desde_config(sin)["overlaps"], [["A", "B"]])

    def test_coberturas_separadas_en_el_plano_no_se_solapan(self):
        c = config()
        # Se mueve la cobertura de B lejos de la de A en el plano.
        c["cameras"][1]["pairs"] = [[p[0], p[1], p[2] + 50, p[3] + 50] for p in c["cameras"][1]["pairs"]]
        self.assertEqual(registro_desde_config(c)["overlaps"], [])

    def test_las_distancias_salen_de_matchDistance(self):
        a = registro_desde_config(config(matchDistance=1.0))["association"]
        b = registro_desde_config(config(matchDistance=2.0))["association"]
        self.assertAlmostEqual(b["overlap_distance_m"], 2 * a["overlap_distance_m"])
        self.assertAlmostEqual(b["max_speed_m_s"], 2 * a["max_speed_m_s"])

    def test_recorte_en_grupos_solo_si_se_pide(self):
        self.assertNotIn("min_visible", registro_desde_config(config())["association"])
        self.assertEqual(registro_desde_config(config(identityGroupCrops=True))["association"]["min_visible"], 0.6)
        self.assertEqual(registro_desde_config(config(identityGroupCrops=True, identityV2={"min_visible": 0.8}))["association"]["min_visible"], 0.8)
        self.assertEqual(MotorIdentidadV2(config(identityGroupCrops=True)).min_visible, 0.6)
        self.assertIsNone(MotorIdentidadV2(config()).min_visible)

    def test_los_ajustes_sobrescriben_los_umbrales(self):
        registro = registro_desde_config(config(identityV2={"threshold": 0.5}), {"split_threshold": 0.3})
        self.assertEqual(registro["association"]["threshold"], 0.5)
        self.assertEqual(registro["association"]["split_threshold"], 0.3)


class Creacion(unittest.TestCase):
    def test_crea_el_motor_de_identidad(self):
        self.assertIsInstance(crear_motor_identidad(config()), MotorIdentidadV2)

    def test_las_claves_de_motores_retirados_no_cambian_nada(self):
        motor = crear_motor_identidad(config(identityEngine="legacy", identityAlign=True))
        self.assertIsInstance(motor, MotorIdentidadV2)
        self.assertNotIn("alineacion", motor.resumen())


class ContratoDeSalida(unittest.TestCase):
    """El motor devuelve las claves que live_server y el dashboard esperan."""

    def pasos(self, n):
        va = vector(1)
        return [[obs("A", 1, 5.0, 4.0, va)] for _ in range(n)]

    def test_claves_que_consume_el_servidor(self):
        salida = correr(MotorIdentidadV2(config()), self.pasos(1), tamanos=TAMANOS)
        for clave in ("id", "camera", "local", "point", "pixel", "box", "association", "history", "velocity", "predicted", "confirmed", "nextCamera"):
            self.assertIn(clave, salida[0])
        self.assertNotIn("embedding", salida[0])
        self.assertNotIn("color", salida[0])

    def test_id_provisional_y_luego_publico(self):
        motor = MotorIdentidadV2(config())
        primero = correr(motor, self.pasos(1), tamanos=TAMANOS)[0]
        self.assertFalse(primero["confirmed"])
        self.assertTrue(primero["id"].startswith("T"))
        despues = correr(MotorIdentidadV2(config()), self.pasos(40), tamanos=TAMANOS)[0]
        self.assertTrue(despues["confirmed"])
        self.assertEqual(despues["id"], "P00001")

    def test_la_misma_persona_en_dos_camaras_comparte_id_y_se_marca_estimated(self):
        va = vector(2)
        pasos = [[obs("A", 1, 5.0, 4.0, va), obs("B", 7, 5.1, 4.1, va, caja_x=600)] for _ in range(40)]
        salida = correr(MotorIdentidadV2(config()), pasos, tamanos=TAMANOS)
        self.assertEqual(salida[0]["id"], salida[1]["id"])
        self.assertEqual({p["association"] for p in salida}, {"estimated"})

    def test_dos_personas_lejanas_son_dos_ids(self):
        pasos = [[obs("A", 1, 2.0, 2.0, vector(3)), obs("A", 2, 9.0, 6.0, vector(4), caja_x=700)] for _ in range(40)]
        salida = correr(MotorIdentidadV2(config()), pasos, tamanos=TAMANOS)
        self.assertEqual(len({p["id"] for p in salida}), 2)

    def test_un_provisional_que_repite_a_otra_camara_no_se_dibuja(self):
        grande = obs("B", 7, 5.1, 4.1, vector(10), caja_x=600)
        grande["box"] = [600., 250., 700., 460.]                 # recuadro mayor: es el que se conserva
        salida = correr(MotorIdentidadV2(config()), [[obs("A", 1, 5.0, 4.0, vector(9)), grande]], tamanos=TAMANOS)
        por_camara = {p["camera"]: p for p in salida}
        self.assertFalse(por_camara["B"]["confirmed"] or por_camara["A"]["confirmed"])
        self.assertTrue(por_camara["A"]["duplicate"])
        self.assertFalse(por_camara["B"]["duplicate"])

    def test_provisionales_lejanos_o_de_la_misma_camara_se_dibujan_todos(self):
        lejos = correr(MotorIdentidadV2(config()), [[obs("A", 1, 2.0, 2.0, vector(9)), obs("B", 7, 9.0, 6.0, vector(10), caja_x=600)]], tamanos=TAMANOS)
        self.assertFalse(any(p["duplicate"] for p in lejos))
        juntos = correr(MotorIdentidadV2(config()), [[obs("A", 1, 5.0, 4.0, vector(9)), obs("A", 2, 5.1, 4.1, vector(10), caja_x=700)]], tamanos=TAMANOS)
        self.assertFalse(any(p["duplicate"] for p in juntos))

    def test_un_confirmado_nunca_se_oculta(self):
        va = vector(2)
        pasos = [[obs("A", 1, 5.0, 4.0, va), obs("B", 7, 5.1, 4.1, va, caja_x=600)] for _ in range(40)]
        salida = correr(MotorIdentidadV2(config()), pasos, tamanos=TAMANOS)
        self.assertTrue(all(p["confirmed"] and not p.get("duplicate") for p in salida))

    def test_el_historial_y_la_velocidad_se_llenan(self):
        va = vector(5)
        pasos = [[obs("A", 1, 3.0 + 0.1 * i, 4.0, va)] for i in range(30)]
        salida = correr(MotorIdentidadV2(config()), pasos, tamanos=TAMANOS)[0]
        self.assertGreater(len(salida["history"]), 10)
        self.assertGreater(salida["velocity"][0], 0.2)

    def test_instante_repetido_no_reprocesa(self):
        motor = MotorIdentidadV2(config())
        va = vector(6)
        for i in range(10):
            motor.update([obs("A", 1, 5, 4, va)], i * 0.2, tamanos=TAMANOS)
        uno = motor.update([obs("A", 1, 5, 4, va)], 1.8, tamanos=TAMANOS)
        self.assertEqual(motor.errores, 0)
        self.assertEqual(uno[0]["id"], motor.update([obs("A", 1, 5, 4, va)], 1.8, tamanos=TAMANOS)[0]["id"])

    def test_el_tiempo_hacia_atras_reinicia_sin_error(self):
        motor = MotorIdentidadV2(config())
        va = vector(7)
        for i in range(10):
            motor.update([obs("A", 1, 5, 4, va)], i * 0.2, tamanos=TAMANOS)
        salida = motor.update([obs("A", 1, 5, 4, va)], 0.0, tamanos=TAMANOS)
        self.assertEqual(motor.errores, 0)
        self.assertFalse(salida[0]["confirmed"])

    def test_un_error_interno_no_detiene_el_monitoreo(self):
        motor = MotorIdentidadV2(config())
        # Sin tamaño de cámara ni frame el asociador no puede evaluar la calidad: error controlado.
        salida = motor.update([obs("A", 1, 5, 4, vector(8))], 0.0)
        self.assertEqual(motor.errores, 1)
        self.assertIn("ValueError", motor.ultimo_error)
        self.assertEqual(len(salida), 1)
        self.assertFalse(salida[0]["confirmed"])
        # Y el motor sigue funcionando después.
        ok = motor.update([obs("A", 1, 5, 4, vector(8))], 0.2, tamanos=TAMANOS)
        self.assertEqual(len(ok), 1)

    def test_observacion_sin_caja_sale_con_id_provisional(self):
        motor = MotorIdentidadV2(config())
        o = obs("A", 1, 5, 4, vector(9))
        o["box"] = None
        salida = motor.update([o], 0.0, tamanos=TAMANOS)
        self.assertEqual(len(salida), 1)
        self.assertFalse(salida[0]["confirmed"])

    def test_necesita_vista_hasta_confirmar(self):
        motor = MotorIdentidadV2(config())
        self.assertTrue(motor.necesita_vista("A", 1))
        correr(motor, self.pasos(40), tamanos=TAMANOS)
        self.assertTrue(motor.resumen()["identidades_globales"] >= 1)

    def test_resumen_informa_geometria_y_camaras_sin_calibrar(self):
        motor = MotorIdentidadV2(config())
        resumen = motor.resumen()
        self.assertEqual(resumen["engine"], "reid_v2")
        self.assertTrue(resumen["geometria_validada"])
        sin = config()
        sin["cameras"][1]["pairs"] = []
        self.assertEqual(MotorIdentidadV2(sin).resumen()["camaras_sin_calibracion"], ["B"])
        self.assertFalse(MotorIdentidadV2(sin).resumen()["geometria_validada"])


if __name__ == "__main__":
    unittest.main()
