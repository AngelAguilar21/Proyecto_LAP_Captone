import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import automation_settings as settings


class AutomationSettingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_absent_settings_disable_every_task_without_writing(self):
        value = settings.load(self.root)
        self.assertEqual(value["timezone"], "America/Lima")
        self.assertTrue(all(value[t]["enabled"] is False for t in ("reports", "backups", "escalation", "cleanup")))
        value["reports"]["enabled"] = True
        self.assertFalse(settings.load(self.root)["reports"]["enabled"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_values_and_secrets_fail_closed(self):
        values = [[], {"reports": {"enabled": "false"}}, {"timezone": "UTC"},
                  {"password": "synthetic-secret"}, {"backups": {"retention": 0}},
                  {"escalation": {"enabled": True}}, {"reports": {"time": "24:00"}},
                  {"runtime": {"task_timeout_seconds": float("nan")}},
                  {"runtime": {"shutdown_timeout_seconds": True}}]
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings.save(self.root, value)
        self.assertFalse((self.root / "automation.local.json").exists())

    def test_malformed_file_raises_instead_of_enabling_defaults(self):
        (self.root / "automation.local.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            settings.load(self.root)

    def test_atomic_replace_failure_preserves_previous_configuration(self):
        previous = settings.save(self.root, {})
        with patch("projects.os.replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                settings.save(self.root, {"reports": {"enabled": True}})
        self.assertEqual(settings.load(self.root), previous)
        settings.save(self.root, {"runtime": {"task_timeout_seconds": 3, "shutdown_timeout_seconds": 2}})
        self.assertEqual(settings.load(self.root)["runtime"], {"task_timeout_seconds": 3, "shutdown_timeout_seconds": 2})
        self.assertEqual(json.loads((self.root / "automation.local.json").read_text()), settings.load(self.root))
