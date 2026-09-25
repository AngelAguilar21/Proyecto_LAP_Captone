"""Project lifecycle through Engine, with all storage in temporary directories."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_server
from live_server import Engine
import projects


class ProjectTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="projects-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.legacy_path = self.root / "config" / "live.local.json"
        # An explicit Engine config_path disables project management. Redirect
        # its managed storage instead, without mocking project operations.
        self.enterContext(patch.object(live_server, "ROOT", self.root))
        self.enterContext(patch.object(live_server, "CONFIG_PATH", self.legacy_path))

    def test_create_project_adds_it_to_persisted_index(self):
        engine = Engine()
        original_id = engine.project_id

        listing = engine.new_project("Terminal de prueba")

        index = projects.read_index(self.root)
        created_id = listing["active"]
        self.assertNotEqual(created_id, original_id)
        self.assertEqual(len(index["projects"]), 2)
        self.assertEqual({item["id"] for item in index["projects"]},
                         {original_id, created_id})
        self.assertEqual(projects.entry(index, created_id)["name"],
                         "Terminal de prueba")
        self.assertEqual(index["active"], created_id)
        self.assertEqual(engine.project_id, created_id)
        saved = json.loads(projects.project_path(self.root, created_id)
                           .read_text(encoding="utf-8"))
        self.assertEqual(saved["airport"], "Terminal de prueba")

    def test_legacy_config_migrates_as_main_project(self):
        config = live_server.default_config()
        config.update(airport="Aeropuerto de prueba", floor="Nivel legacy")
        self.legacy_path.parent.mkdir(parents=True)
        legacy_text = json.dumps(config, ensure_ascii=False, indent=2)
        self.legacy_path.write_text(legacy_text, encoding="utf-8")

        engine = Engine()

        index = projects.read_index(self.root)
        self.assertEqual(len(index["projects"]), 1)
        self.assertEqual(index["projects"][0]["name"], "Proyecto principal")
        self.assertEqual(index["active"], engine.project_id)
        self.assertEqual(engine.config_path.read_text(encoding="utf-8"), legacy_text)
        self.assertEqual(self.legacy_path.read_text(encoding="utf-8"), legacy_text)
        self.assertIsNone(engine.config_error)
        self.assertEqual(engine.config["airport"], config["airport"])
        self.assertEqual(engine.config["floor"], config["floor"])
        self.assertEqual(Engine().project_id, engine.project_id)
        self.assertEqual(projects.read_index(self.root), index)

    def test_cannot_delete_only_project(self):
        engine = Engine()
        engine.configure(engine.config)
        index = projects.read_index(self.root)
        saved = engine.config_path.read_bytes()
        original_id = engine.project_id

        with self.assertRaisesRegex(ValueError, "único proyecto"):
            engine.delete_project(original_id)

        self.assertEqual(projects.read_index(self.root), index)
        self.assertEqual(engine.project_id, original_id)
        self.assertEqual(engine.config_path.read_bytes(), saved)

    def test_open_project_changes_active_project_and_loads_config(self):
        engine = Engine()
        first_id = engine.new_project("Terminal uno")["active"]
        second_id = engine.new_project("Terminal dos")["active"]
        self.assertEqual(engine.project_id, second_id)
        self.assertEqual(engine.config["airport"], "Terminal dos")

        listing = engine.open_project(first_id)

        self.assertEqual(listing["active"], first_id)
        self.assertEqual(projects.read_index(self.root)["active"], first_id)
        self.assertEqual(engine.project_id, first_id)
        self.assertEqual(engine.config_path, projects.project_path(self.root, first_id))
        self.assertIsNone(engine.config_error)
        self.assertEqual(engine.config["airport"], "Terminal uno")
        self.assertEqual(Engine().project_id, first_id)

    def test_new_project_rejects_empty_or_whitespace_name(self):
        engine = Engine()
        index = projects.read_index(self.root)
        files = set(projects.directory(self.root).iterdir())

        for name in ("", "   ", "\t\n"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "Escribe un nombre"):
                    engine.new_project(name)
                self.assertEqual(projects.read_index(self.root), index)
                self.assertEqual(engine.project_id, index["active"])
                self.assertEqual(set(projects.directory(self.root).iterdir()), files)


if __name__ == "__main__":
    unittest.main()
