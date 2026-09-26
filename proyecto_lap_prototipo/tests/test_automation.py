"""Deterministic scheduling infrastructure; no background worker is started."""
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
from automation import AutomationService
from automation_store import AutomationStore
import automation_settings


class AutomationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.engine = SimpleNamespace(settings_root=self.root, lock=threading.RLock(), record=Mock())
        self.now = datetime(2026, 9, 25, 23, tzinfo=timezone.utc)

    def test_constructor_and_disabled_tasks_have_no_side_effects(self):
        callback, factory = Mock(), Mock()
        service = AutomationService(self.engine, {"reports": callback}, thread_factory=factory)
        self.assertEqual(service.run_due_tasks(self.now), {})
        callback.assert_not_called()
        factory.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_task_failure_is_persisted_and_does_not_block_next_task(self):
        automation_settings.save(self.root, {"reports": {"enabled": True}, "backups": {"enabled": True}})
        report, backup = Mock(side_effect=ValueError("synthetic")), Mock(return_value="done")
        service = AutomationService(self.engine, {"reports": report, "backups": backup})
        self.assertEqual(service.run_due_tasks(self.now), {"reports": "failed", "backups": "done"})
        self.assertEqual(backup.call_args.args[0].hour, 18)
        restarted = AutomationStore(self.root / "automation.sqlite")
        self.assertEqual(restarted.get("reports", "service", "2026-09-25")["status"], "failed")

    def test_start_stop_are_idempotent_with_separate_event(self):
        factory = Mock()
        worker = factory.return_value
        worker.is_alive.return_value = True
        service = AutomationService(self.engine, thread_factory=factory)
        service.start()
        service.start()
        factory.assert_called_once()
        worker.start.assert_called_once()
        service.stop()
        self.assertTrue(service.stop_event.is_set())
        worker.join.assert_called_once()

    def test_overlapping_tick_is_not_executed_twice(self):
        automation_settings.save(self.root, {"reports": {"enabled": True}})
        service = AutomationService(self.engine)
        nested = []
        service.tasks["reports"] = lambda *args: nested.append(service.run_due_tasks(self.now))
        service.run_due_tasks(self.now)
        self.assertEqual(nested, [{}])

    def test_stop_between_tasks_prevents_next_task(self):
        automation_settings.save(self.root, {"reports": {"enabled": True}, "backups": {"enabled": True}})
        service = AutomationService(self.engine)
        second = Mock()
        service.tasks = {"reports": lambda *args: service.stop_event.set(), "backups": second}
        service.run_due_tasks(self.now)
        second.assert_not_called()

    def test_invalid_preferences_do_not_overwrite_previous_configuration(self):
        automation_settings.save(self.root, {})
        path = self.root / "automation.local.json"
        before = path.read_bytes()
        for value in ({"reports": {"time": "25:00"}}, {"cleanup": {"retention_days": 0}},
                      {"backups": {"enabled": "yes"}}, {"timezone": "UTC"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                automation_settings.save(self.root, value)
            self.assertEqual(path.read_bytes(), before)

    def test_malformed_file_and_naive_time_do_not_run_tasks(self):
        callback = Mock()
        service = AutomationService(self.engine, {"reports": callback})
        with self.assertRaises(ValueError):
            service.run_due_tasks(datetime(2026, 9, 25))
        (self.root / "automation.local.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            service.run_due_tasks(self.now)
        callback.assert_not_called()

    def test_snapshot_is_detached_and_excludes_individual_data(self):
        engine = Engine(self.root / "project.json")
        engine.report_config = {"airport": "Synthetic", "cameras": []}
        engine.state.update(session="test", people=[{"id": "P1"}],
                            analytics={"zones": [{"name": "Zone", "count": 3}]})
        snapshot = engine.automation_snapshot()
        engine.state["analytics"]["zones"][0]["count"] = 9
        engine.report_config["airport"] = "Changed"
        self.assertEqual(snapshot["state"]["analytics"]["zones"][0]["count"], 3)
        self.assertEqual(snapshot["config"]["airport"], "Synthetic")
        self.assertNotIn("people", snapshot["state"])


if __name__ == "__main__":
    unittest.main()
