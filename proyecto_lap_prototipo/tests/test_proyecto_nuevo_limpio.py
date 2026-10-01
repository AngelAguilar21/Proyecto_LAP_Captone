"""Un proyecto nuevo no muestra datos ni rótulos de otro espacio.

Los archivos de cada proyecto ya estaban aislados; lo que se colaba era la
identidad de LAP escrita en el código: la configuración por defecto traía
«Aeropuerto LAP / Terminal A · Nivel 1» y un proyecto recién creado heredaba ese
nivel y lo mostraba en su vista general como si fuera suyo.
"""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path('proyecto_lap_prototipo').resolve()))
sys.path.insert(0, str(Path('proyecto_lap_prototipo/src').resolve()))
from live_server import Engine, default_config

CLIENTE = ("LAP", "Aeropuerto LAP", "Terminal A", "Lima Airport")


class ProyectoNuevoTests(unittest.TestCase):
    def test_la_configuracion_por_defecto_no_nombra_a_ningun_cliente(self):
        config = default_config()
        for campo in ("airport", "floor"):
            for marca in CLIENTE:
                self.assertNotIn(marca, str(config.get(campo, "")),
                                 f"{campo} trae la identidad de un cliente: {config.get(campo)!r}")

    def test_el_espacio_y_el_nivel_empiezan_vacios(self):
        # Vacío, no un texto de ejemplo: la interfaz ya pone su propio rótulo
        # neutro cuando no hay nombre, y así nadie confunde un resto con un dato.
        config = default_config()
        self.assertEqual(config["airport"], "")
        self.assertEqual(config["floor"], "")

    def test_la_configuracion_por_defecto_no_trae_plano(self):
        config = default_config()
        self.assertEqual(config["zones"], [])
        self.assertFalse(config["setupComplete"])
        self.assertFalse(config["mapConfigured"])
        for campo in ("background", "planLines", "mapAsset", "plans", "workArea"):
            self.assertIn(config.get(campo, None), (None, "", [], {}),
                          f"{campo} viene con contenido heredado: {config.get(campo)!r}")

    def test_crear_un_proyecto_vacia_camaras_y_nivel(self):
        # default_config() sí trae las cámaras de demostración que describe el
        # camaras.json heredado (los videos del aeropuerto). Crear un proyecto
        # tiene que dejarlas fuera: si no, el proyecto nuevo abre con cámaras y
        # videos de otro espacio.
        import inspect
        from live_server import Engine
        fuente = inspect.getsource(Engine.new_project)
        cuerpo = fuente[fuente.index("if not copy_current"):]
        self.assertIn('config["cameras"] = []', cuerpo)
        self.assertIn('config["floor"] = ""', cuerpo)
        self.assertIn('config["airport"] = name.strip()', cuerpo)

    def test_un_proyecto_creado_de_verdad_no_ofrece_niveles_del_lap(self):
        # Reproduce el caso real: "Plano asociado" al editar una cámara lista
        # Object.keys(config.plans). Si new_project() no deja plans vacío, un
        # proyecto nuevo ofrece "LAP · Nivel 1" en ese desplegable aunque nunca
        # se haya tocado nada del LAP.
        import live_server
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config" / "projects").mkdir(parents=True)
            original_root, original_config = live_server.ROOT, live_server.CONFIG_PATH
            try:
                live_server.ROOT = root
                live_server.CONFIG_PATH = root / "config" / "live.local.json"
                engine = Engine()
                engine.new_project("Universidad de prueba")
                guardado = json.loads((root / "config" / "projects" / f"{engine.project_id}.json").read_text(encoding="utf-8"))
                planes = guardado.get("plans") or {}
                self.assertEqual([k for k in planes if k.startswith("lap-")], [],
                                 f"el proyecto nuevo trae niveles del LAP en plans: {list(planes)}")
                self.assertIn(guardado.get("planId"), (None, "custom"))
            finally:
                live_server.ROOT, live_server.CONFIG_PATH = original_root, original_config

    def test_el_reporte_no_queda_sin_titulo_con_el_nombre_vacio(self):
        # Al vaciar el nombre por defecto, el reporte no puede quedar mostrando
        # un separador suelto donde iba el espacio.
        import live_reports, inspect
        fuente = inspect.getsource(live_reports)
        self.assertNotIn('config.get("airport","Aeropuerto")', fuente)
        self.assertIn('config.get("airport") or', fuente)


if __name__ == '__main__':
    unittest.main()
