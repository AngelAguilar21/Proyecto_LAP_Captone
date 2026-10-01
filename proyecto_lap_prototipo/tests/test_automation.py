import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from automation import AutomationService
import automation_settings
from task_control import checkpoint


class AutomationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.engine = SimpleNamespace(settings_root=self.root, closing=False)
        self.now = datetime(2026, 1, 2, 1, tzinfo=timezone.utc)

    def enable(self, *tasks, **options):
        automation_settings.save(self.root, {**{t: {"enabled": True} for t in tasks}, **options})

    def test_empty_registry_is_inert_even_with_features_enabled(self):
        self.enable("reports", "backups", "cleanup", escalation={"enabled": True, "recipients": ["fake@example.invalid"]})
        service = AutomationService(self.engine)
        self.assertEqual(service.run_due_tasks(self.now), {})
        self.assertFalse(service.store.path.exists())
        self.assertEqual(service.tasks, {})

    def test_absent_settings_skip_injected_task(self):
        task = Mock()
        service = AutomationService(self.engine, {"reports": task})
        self.assertEqual(service.run_due_tasks(self.now), {})
        task.assert_not_called()
        self.assertFalse(service.store.path.exists())

    def test_invalid_settings_do_not_run_any_task(self):
        (self.root / "automation.local.json").write_text('{"reports":{"enabled":1}}')
        task = Mock()
        with self.assertRaises(ValueError):
            AutomationService(self.engine, {"reports": task}).run_due_tasks(self.now)
        task.assert_not_called()

    def test_tasks_are_sequential_and_failure_is_durable(self):
        self.enable("reports", "backups")
        order = []
        def first(now, settings):
            order.append("first")
            self.assertEqual(now.isoformat(), "2026-01-01T20:00:00-05:00")
            raise ValueError("synthetic-secret must not be stored")
        def second(now, settings):
            order.append("second")
            return "synthetic-success"
        service = AutomationService(self.engine, {"reports": first, "backups": second})
        self.assertEqual(service.run_due_tasks(self.now), {"reports": "failed", "backups": "synthetic-success"})
        self.assertEqual(order, ["first", "second"])
        failed = service.store.get("reports", "service", "2026-01-01")
        self.assertEqual((failed["status"], failed["error"]), ("failed", "ValueError"))
        with service.store.connect() as db:
            self.assertEqual(db.execute("SELECT task,detail FROM audit ORDER BY id").fetchall(),
                             [("reports", "failed"), ("backups", "succeeded")])
        self.assertEqual(service.store.get("backups", "service", "2026-01-01")["status"], "succeeded")

    def test_simultaneous_runs_admit_only_one_and_stop_retains_worker(self):
        self.enable("reports")
        entered, release = threading.Event(), threading.Event()
        def task(*_):
            entered.set()
            release.wait(3)
            checkpoint()
        service = AutomationService(self.engine, {"reports": task}, clock=lambda: self.now)
        service.start()
        try:
            self.assertTrue(entered.wait(2))
            worker = service.worker
            self.assertEqual(service.run_due_tasks(self.now), {})
            self.assertFalse(service.stop(timeout=0))
            self.assertIs(service.worker, worker)
            self.assertTrue(worker.is_alive())
        finally:
            release.set()
            service.stop(timeout=3)
        self.assertFalse(service.worker.is_alive())
        self.assertEqual(service.store.get("reports", "service", "2026-01-01")["status"], "cancelled")

    def test_fake_timeout_cancels_and_records_result(self):
        self.enable("reports", runtime={"task_timeout_seconds": 1})
        now = [0.]
        def task(*_):
            now[0] = 2.
            checkpoint()
        service = AutomationService(self.engine, {"reports": task}, monotonic=lambda: now[0])
        self.assertEqual(service.run_due_tasks(self.now), {"reports": "cancelled"})
        self.assertEqual(service.store.get("reports", "service", "2026-01-01")["status"], "cancelled")

    def test_missing_initial_durable_record_blocks_callback(self):
        self.enable("reports")
        task = Mock()
        service = AutomationService(self.engine, {"reports": task})
        with patch.object(service.store, "record", side_effect=OSError("synthetic")):
            self.assertEqual(service.run_due_tasks(self.now), {"reports": "failed"})
        task.assert_not_called()

    def test_background_loop_survives_invalid_config_and_can_stop(self):
        entered = threading.Event()
        service = AutomationService(self.engine, clock=lambda: self.now)
        def invalid(*_):
            entered.set()
            raise ValueError("synthetic")
        with patch.object(service, "run_due_tasks", side_effect=invalid):
            service.start()
            self.assertTrue(entered.wait(2))
            self.assertTrue(service.stop(2))
        self.assertEqual(service.error, "ValueError")
