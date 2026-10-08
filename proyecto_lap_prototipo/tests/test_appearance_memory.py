"""Memoria de apariencia (portada de AeroVision, test_memoria_identidades) con personas sintéticas y SQLite local.

La persistencia se prueba contra un archivo temporal: sin servidor, sin video, sin modelo.
"""
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from identity import AsociadorConMemoria, AsociadorMulticamara, MemoriaApariencia  # noqa: E402
from identity import memory as memoria_mod  # noqa: E402
from identity.engine import ASOCIACION_DEFECTO  # noqa: E402
from test_identity_core import (A, B, C, DIM, Escena, ReIDFalso, registro, unitario)  # noqa: E402


def bases():
    rng = np.random.default_rng(3)
    a = unitario(rng.normal(size=DIM))
    ortogonal = unitario(rng.normal(size=DIM) - a * (a @ rng.normal(size=DIM)))
    return {
        A: a,
        B: unitario(rng.normal(size=DIM)),
        C: unitario(0.5 * a + np.sqrt(0.75) * ortogonal),     # se parece a A (0,5), pero no es A
        (100, 100, 100): unitario(0.66 * a + np.sqrt(1 - 0.66 ** 2) * unitario(rng.normal(size=DIM))),  # D: 0,66 con A
        (0, 180, 180): unitario(0.65 * a + np.sqrt(1 - 0.65 ** 2) * unitario(rng.normal(size=DIM))),   # A de espaldas
    }


D, A_ESPALDAS = (100, 100, 100), (0, 180, 180)


def memoria_ram():
    return MemoriaApariencia(None, ASOCIACION_DEFECTO)


def asociador(memoria, camaras=("c1",), **cfg):
    config = registro(camaras=camaras, **cfg)
    reid = ReIDFalso(bases())
    return AsociadorConMemoria(reid, config, memoria) if memoria is not None else AsociadorMulticamara(reid, config)


class PruebasMemoria(unittest.TestCase):
    def test_quien_vuelve_tarde_conserva_su_id(self):
        # Sin memoria: pasado el regreso máximo de la sesión, la misma persona recibe otro ID.
        escena = Escena(asociador(None, transiciones=[]))
        antes = escena.ver(4, {"c1": [(1, A, 300)]})[("c1", 1)]
        escena.esperar(300)
        despues = escena.ver(4, {"c1": [(7, A, 600)]})[("c1", 7)]
        self.assertIsNotNone(antes)
        self.assertNotEqual(antes, despues, "el asociador solo debería olvidar sin la memoria")

        escena = Escena(asociador(memoria_ram()))
        primero = escena.ver(4, {"c1": [(1, A, 300)]})[("c1", 1)]
        escena.esperar(300)
        self.assertEqual(escena.ver(4, {"c1": [(7, A, 600)]})[("c1", 7)], primero)
        self.assertEqual(escena.asociador.reconocidas, set(), "300 s de sesión no son 30 s de reloj: no cuenta como regreso")

    def test_sobrevive_a_reiniciar_la_sesion(self):
        memoria = memoria_ram()
        uno = Escena(asociador(memoria)).ver(4, {"c1": [(1, A, 300)]})[("c1", 1)]
        memoria.personas[uno].ultima_vez -= 120
        escena = Escena(asociador(memoria, camaras=("c1",)))
        self.assertEqual(escena.ver(4, {"c1": [(1, A, 500)]})[("c1", 1)], uno)
        self.assertEqual(escena.asociador.reconocidas, {uno})
        self.assertEqual(memoria.personas[uno].apariciones, 2)

    def test_personas_distintas_no_se_mezclan(self):
        memoria = memoria_ram()
        escena = Escena(asociador(memoria))
        ids = escena.ver(4, {"c1": [(1, A, 100), (2, B, 500), (3, C, 900)]})
        self.assertEqual(len({ids[("c1", 1)], ids[("c1", 2)], ids[("c1", 3)]}), 3)
        escena.esperar(300)
        self.assertEqual(escena.ver(4, {"c1": [(9, C, 700)]})[("c1", 9)], ids[("c1", 3)], "C se parece a A pero no le roba el ID")
        self.assertEqual(escena.ver(4, {"c1": [(10, A, 200)]})[("c1", 10)], ids[("c1", 1)])

    def test_un_id_nuevo_que_era_alguien_ya_visto_se_corrige(self):
        memoria = memoria_ram()
        escena = Escena(asociador(memoria))
        antiguo = escena.ver(4, {"c1": [(1, A, 300)]})[("c1", 1)]
        escena.esperar(300)
        nuevo = escena.ver(4, {"c1": [(2, A_ESPALDAS, 600)]})[("c1", 2)]
        self.assertIsNotNone(nuevo)
        self.assertNotEqual(nuevo, antiguo)
        final = escena.ver(12, {"c1": [(2, A, 600)]})[("c1", 2)]
        self.assertEqual(final, antiguo)
        self.assertNotIn(nuevo, memoria.personas)

    def test_pasa_de_una_camara_a_otra_con_memoria(self):
        memoria = memoria_ram()
        escena = Escena(asociador(memoria, camaras=("c1", "c2"), solapes=[("c1", "c2")],
                                  transiciones=[("c1", "c2", 0, 30), ("c2", "c1", 0, 30)]))
        primero = escena.ver(4, {"c1": [(1, A, 300)], "c2": []})[("c1", 1)]
        escena.esperar(5)
        self.assertEqual(escena.ver(4, {"c1": [], "c2": [(4, A, 600)]})[("c2", 4)], primero)
        ids = escena.ver(6, {"c1": [(5, A, 300)], "c2": [(6, A, 600)]})
        self.assertEqual(ids[("c1", 5)], primero)
        self.assertEqual(ids[("c2", 6)], primero)
        self.assertEqual(escena.asociador.personas_contadas(), 1)


class PruebasPrimerSegundo(unittest.TestCase):
    """A 10 fps."""

    def cuando_tiene_id(self, escena, segundos, personas, clave, fps=10):
        inicio = escena.t
        for _ in range(int(segundos * fps)):
            ids = escena.ver(1 / fps, personas, fps=fps)
            if ids.get(clave) is not None:
                return escena.t - inicio, ids[clave]
        return None, None

    def test_una_persona_nueva_recibe_id_en_un_segundo(self):
        escena = Escena(asociador(memoria_ram()))
        segundos, pid = self.cuando_tiene_id(escena, 3, {"c1": [(1, A, 300)]}, ("c1", 1))
        self.assertIsNotNone(pid)
        self.assertLessEqual(segundos, 1.2)

    def test_quien_ya_se_vio_se_reconoce_en_menos_de_un_segundo(self):
        escena = Escena(asociador(memoria_ram()))
        _, primero = self.cuando_tiene_id(escena, 3, {"c1": [(1, A, 300)]}, ("c1", 1))
        escena.ver(2, {"c1": [(1, A, 300)]})
        escena.esperar(300)
        segundos, pid = self.cuando_tiene_id(escena, 3, {"c1": [(5, A, 600)]}, ("c1", 5))
        self.assertEqual(pid, primero)
        self.assertLessEqual(segundos, 0.6)

    def test_si_se_parece_a_alguien_espera_antes_de_darle_un_id_nuevo(self):
        escena = Escena(asociador(memoria_ram()))
        _, de_a = self.cuando_tiene_id(escena, 3, {"c1": [(1, A, 300)]}, ("c1", 1))
        escena.ver(2, {"c1": [(1, A, 300)]})
        escena.esperar(300)
        segundos, pid = self.cuando_tiene_id(escena, 5, {"c1": [(6, D, 600)]}, ("c1", 6))
        self.assertIsNotNone(pid)
        self.assertNotEqual(pid, de_a)
        self.assertGreaterEqual(segundos, 2.9)
        self.assertLessEqual(segundos, 3.3)


class PruebasPersistencia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "identidad.sqlite"
        self.viejo = memoria_mod.ESCRIBIR_CADA_S
        memoria_mod.ESCRIBIR_CADA_S = 0.05

    def tearDown(self):
        memoria_mod.ESCRIBIR_CADA_S = self.viejo
        self.tmp.cleanup()

    def abrir(self, **kw):
        return MemoriaApariencia(self.ruta, ASOCIACION_DEFECTO, **kw)

    def test_la_memoria_sobrevive_a_reiniciar_y_se_puede_borrar(self):
        memoria = self.abrir()
        self.assertTrue(memoria.persistente)
        uno = Escena(asociador(memoria)).ver(4, {"c1": [(1, A, 300)]})[("c1", 1)]
        memoria.cerrar()
        con = sqlite3.connect(self.ruta)
        muestras, vistas = con.execute("SELECT muestras FROM appearance_people WHERE id=?", (uno,)).fetchone()[0], \
            con.execute("SELECT COUNT(*) FROM appearance_views WHERE persona=?", (uno,)).fetchone()[0]
        con.close()
        self.assertGreaterEqual(muestras, 5)
        self.assertEqual(vistas, 1)

        # Reinicio del modelo: carga la memoria y reconoce a la misma persona con el mismo ID.
        memoria = self.abrir()
        self.assertEqual(set(memoria.personas), {uno})
        self.assertEqual(Escena(asociador(memoria, camaras=("c1",))).ver(4, {"c1": [(3, A, 500)]})[("c1", 3)], uno)

        # Borrado inmediato: la RAM y el disco quedan vacíos y los IDs vuelven a empezar en 1.
        self.assertEqual(memoria.purgar_todo(), 1)
        self.assertEqual(memoria.personas, {})
        escena = Escena(asociador(memoria, camaras=("y",)))
        self.assertEqual(escena.ver(4, {"y": [(8, B, 900)]})[("y", 8)], 1)
        memoria.cerrar()
        con = sqlite3.connect(self.ruta)
        ids = [r[0] for r in con.execute("SELECT id FROM appearance_people")]
        con.close()
        self.assertEqual(ids, [1])

    def test_la_retencion_borra_a_quien_no_se_vio_a_tiempo(self):
        memoria = self.abrir(retencion_horas=1)
        uno = Escena(asociador(memoria)).ver(4, {"c1": [(1, A, 300)]})[("c1", 1)]
        memoria.personas[uno].ultima_vez -= 2 * 3600  # se vio hace 2 h con retención de 1 h
        self.assertEqual(memoria.purgar(), 1)
        self.assertEqual(memoria.personas, {})
        memoria.cerrar()
        memoria = self.abrir(retencion_horas=1)
        self.assertEqual(memoria.personas, {})
        memoria.cerrar()

    def test_la_retencion_se_acota_entre_1_y_168_horas(self):
        for pedido, esperado in ((0, 3600), (9999, 168 * 3600), ("x", 24 * 3600)):
            memoria = self.abrir(retencion_horas=pedido)
            self.assertEqual(memoria.retencion_s, esperado)
            memoria.cerrar()

    def test_un_encoder_distinto_no_mezcla_vectores(self):
        memoria = self.abrir(encoder="osnet")
        Escena(asociador(memoria)).ver(4, {"c1": [(1, A, 300)]})
        memoria.cerrar()
        otra = self.abrir(encoder="yolo26s-reid")
        self.assertEqual(otra.personas, {})
        otra.cerrar()

    def test_nunca_se_guardan_imagenes_ni_rostros(self):
        memoria = self.abrir()
        Escena(asociador(memoria)).ver(4, {"c1": [(1, A, 300)]})
        memoria.cerrar()
        con = sqlite3.connect(self.ruta)
        columnas = {fila[1]: fila[2] for t in ("appearance_people", "appearance_views")
                    for fila in con.execute(f"PRAGMA table_info({t})")}
        blob = con.execute("SELECT length(suma) FROM appearance_people").fetchone()[0]
        con.close()
        self.assertEqual(blob, DIM * 4, "solo el vector de apariencia (512 float32)")
        self.assertFalse({"imagen", "foto", "rostro", "face", "image"} & set(columnas))

    def test_un_fallo_de_la_base_no_detiene_el_monitoreo(self):
        memoria = self.abrir()
        escena = Escena(asociador(memoria))
        escena.ver(2, {"c1": [(1, A, 300)]})
        memoria._con.close()  # el disco "falla"
        ids = escena.ver(3, {"c1": [(1, A, 300)]})
        self.assertIsNotNone(ids[("c1", 1)])
        deadline = time.time() + 3
        while memoria.persistente and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(memoria.persistente)
        self.assertIn("solo en RAM", memoria.error)

    def test_ruta_imposible_deja_la_memoria_en_ram(self):
        (Path(self.tmp.name) / "archivo.txt").write_text("no es un directorio")
        memoria = MemoriaApariencia(Path(self.tmp.name) / "archivo.txt" / "dentro" / "x.sqlite", ASOCIACION_DEFECTO)
        self.assertFalse(memoria.persistente)
        self.assertIsNotNone(memoria.error)
        self.assertEqual(Escena(asociador(memoria)).ver(4, {"c1": [(1, A, 300)]})[("c1", 1)], 1)


if __name__ == "__main__":
    unittest.main()
