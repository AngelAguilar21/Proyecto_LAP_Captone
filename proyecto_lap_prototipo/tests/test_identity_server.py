"""Servidor: motor de identidad elegible, borrado inmediato, insights al cerrar y avisos en los reportes."""
import copy
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import business_data  # noqa: E402
from live_core import validate_config  # noqa: E402
from live_reports import identity_note  # noqa: E402
from live_server import Engine, default_config  # noqa: E402
from test_insights import AnalisisCompleto, DesdeReplayYVentas  # noqa: E402


def config_valida(**cambios):
    c = default_config()
    c.update(cambios)
    return c


class ValidacionDeConfiguracion(unittest.TestCase):
    def test_valores_validos(self):
        validate_config(config_valida(identityGroupCrops=True, appearanceMemory=False, identityFinalize=True,
                                      identityV2={"threshold": 0.7, "mutual_best": True}))
        validate_config(config_valida())

    def test_claves_de_motores_retirados_se_limpian(self):
        c = config_valida(identityEngine="legacy", identityAlign=True, identityRetentionHours=48, reidModel="yolo26s-reid")
        validate_config(c)
        for clave in ("identityEngine", "identityAlign", "reidModel"):
            self.assertNotIn(clave, c)
        self.assertEqual(c["identityRetentionHours"], 48)     # la retención de la memoria de apariencia se conserva

    def test_banderas_deben_ser_booleanas(self):
        for clave in ("appearanceMemory", "identityFinalize", "identityGroupCrops"):
            with self.assertRaises(ValueError, msg=clave):
                validate_config(config_valida(**{clave: "si"}))

    def test_parametros_del_asociador(self):
        for cambios in ({"identityRetentionHours": 0}, {"identityRetentionHours": 500}, {"identityV2": {"threshold": "alto"}}, {"identityV2": [1]}):
            with self.assertRaises(ValueError, msg=str(cambios)):
                validate_config(config_valida(**cambios))


class Reportes(unittest.TestCase):
    def test_sin_informacion_no_agrega_nada(self):
        self.assertEqual(identity_note({}), "")

    def test_modo_visual(self):
        nota = identity_note({"identity": {"engine": "reid_v2", "mode": "visual_temporal", "camaras_sin_calibracion": ["B"]}})
        for texto in ("tracklets + OSNet", "modo visual y temporal", "sin calibrar: B", "no validados en campo"):
            self.assertIn(texto, nota)

    def test_modo_calibrado(self):
        nota = identity_note({"identity": {"engine": "reid_v2", "mode": "calibrado", "geometria_validada": True}})
        self.assertIn("geometría calibrada", nota)


class MotorDelServidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.engine = Engine(self.raiz / "live.json")

    def tearDown(self):
        self.engine.stop()
        if self.engine.worker:
            self.engine.worker.join(timeout=10)
        self.tmp.cleanup()

    def test_recorte_en_grupos_activo_por_defecto_y_elegible_al_iniciar(self):
        self.engine.config["clocksVerified"] = True
        self.engine.start({"detector": "demo"})
        self.assertTrue(self.engine.runtime_config["identityGroupCrops"])
        self.engine.stop()
        self.engine.worker.join(timeout=10)
        self.engine.start({"detector": "demo", "identityGroupCrops": False})
        self.assertFalse(self.engine.runtime_config["identityGroupCrops"])
        self.assertNotIn("identityGroupCrops", self.engine.config)

    def test_una_opcion_invalida_al_iniciar_se_rechaza(self):
        with self.assertRaisesRegex(ValueError, "identityGroupCrops"):
            self.engine.start({"detector": "demo", "identityGroupCrops": "si"})
        with self.assertRaisesRegex(ValueError, "Detector"):
            self.engine.start({"detector": "p2pnet"})

    def test_las_camaras_se_relacionan_solo_con_personas_marcadas(self):
        self.engine.config["clocksVerified"] = True
        for camara in self.engine.config["cameras"]:
            camara["links"] = []
        self.engine.start({"detector": "demo"})
        self.assertTrue(all(not c["links"] for c in self.engine.runtime_config["cameras"]))
        self.engine.stop()
        self.engine.worker.join(timeout=10)
        a, b = (c["id"] for c in self.engine.config["cameras"][:2])
        self.engine.config["personPairs"] = [{"id": f"p{i}", "t": float(i), "a": {"camera": a, "point": [.5, .8]},
                                              "b": {"camera": b, "point": [.4, .7]}} for i in range(4)]
        self.engine.start({"detector": "demo"})
        vecinas = {c["id"]: c["links"] for c in self.engine.runtime_config["cameras"]}
        self.assertEqual(vecinas[a], [b])
        self.assertEqual(vecinas[b], [a])

    def crear_bases(self, nombre):
        carpeta = self.raiz / "data" / "identidad"
        carpeta.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(carpeta / nombre)
        con.executescript("CREATE TABLE IF NOT EXISTS identity_observations (session TEXT, pid TEXT);"
                          "CREATE TABLE IF NOT EXISTS appearance_people (id INTEGER PRIMARY KEY, suma BLOB);"
                          "CREATE TABLE IF NOT EXISTS appearance_views (persona INTEGER, tramo TEXT);"
                          "INSERT INTO identity_observations VALUES ('s','P1'); INSERT INTO appearance_people VALUES (1, x'00'); INSERT INTO appearance_views VALUES (1,'t');")
        con.commit()
        con.close()

    def contar(self, nombre, tabla):
        con = sqlite3.connect(self.raiz / "data" / "identidad" / nombre)
        try:
            return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        finally:
            con.close()

    def test_borrado_inmediato_solo_del_proyecto_abierto(self):
        self.engine.project_id = "p-1"
        for nombre in ("p-1.sqlite", "p-1_apariencia.sqlite", "p-12.sqlite"):
            self.crear_bases(nombre)
        borradas = self.engine.purge_identities()
        self.assertGreaterEqual(borradas, 3)
        self.assertEqual(self.contar("p-1.sqlite", "identity_observations"), 0)
        self.assertEqual(self.contar("p-1_apariencia.sqlite", "appearance_people"), 0)
        self.assertEqual(self.contar("p-1_apariencia.sqlite", "appearance_views"), 0)
        self.assertEqual(self.contar("p-12.sqlite", "identity_observations"), 1, "otro proyecto con prefijo parecido no se toca")
        self.assertTrue(any(a["action"] == "Identidad" for a in self.engine.audit))

    def test_borrado_sin_bases_no_falla(self):
        self.assertEqual(self.engine.purge_identities(), 0)

    def test_borrado_vacia_tambien_la_memoria_viva(self):
        from identity import MemoriaApariencia
        memoria = MemoriaApariencia(None, {})
        memoria.nueva(time.time())
        self.engine.appearance_memory_live = memoria
        self.engine.purge_identities()
        self.assertEqual(memoria.personas, {})
        self.assertEqual(memoria.epoca, 1)

    def preparar_replay(self, sid="abcdef12", proyecto=None):
        DesdeReplayYVentas().crear_replay(self.raiz, sid)
        ruta = self.raiz / "data" / "replays" / sid / "manifest.json"
        meta = json.loads(ruta.read_text(encoding="utf-8"))
        meta["projectId"] = proyecto
        ruta.write_text(json.dumps(meta), encoding="utf-8")
        self.engine.config = {**self.engine.config, **copy.deepcopy(AnalisisCompleto.CONFIG), "cameras": []}
        return sid

    def test_calcula_y_lee_insights_de_una_sesion(self):
        sid = self.preparar_replay()
        with self.assertRaises(FileNotFoundError):
            self.engine.insights_data(sid)
        resultado = self.engine.compute_insights(sid)
        self.assertIsNotNone(resultado)
        datos = self.engine.insights_data(sid)
        self.assertEqual(datos["sesion"], sid)
        self.assertEqual(datos["dataset"], "demo")
        self.assertIn("ventas", datos)
        self.assertEqual(datos["resumen"]["personas"], 2)
        con = business_data.connect(self.engine.config_path)
        try:
            self.assertGreater(con.execute("SELECT COUNT(*) FROM insights_events").fetchone()[0], 0)
        finally:
            con.close()

    def test_los_insights_de_otro_proyecto_no_se_exponen(self):
        sid = self.preparar_replay(proyecto="p-otro")
        self.engine.project_id = "p-mio"
        with self.assertRaisesRegex(ValueError, "no pertenece"):
            self.engine.insights_data(sid)

    def test_un_fallo_de_insights_no_rompe_el_cierre(self):
        self.assertIsNone(self.engine.compute_insights("deadbeef"))   # la sesión no existe
        self.assertTrue(any(a["action"] == "Insights" for a in self.engine.audit))

    def test_sesion_invalida_es_error_claro(self):
        with self.assertRaises(ValueError):
            self.engine.insights_data("../../etc")


if __name__ == "__main__":
    unittest.main()
