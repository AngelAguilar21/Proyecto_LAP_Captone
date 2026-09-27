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
from task_control import budget, checkpoint, Cancelled
from restore_guard import storage_lease
from shutdown_control import stop_server, quiescent
import automation_settings


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def server(self):
        notifications = SimpleNamespace(stop_event=threading.Event(), has_writers=lambda: False)
        engine = SimpleNamespace(settings_root=self.root, stop_event=threading.Event(),
            pause_event=threading.Event(), preview_stop_event=threading.Event(), notifications=notifications,
            worker=None, preview_worker=None, resource_users=0)
        return SimpleNamespace(engine=engine, _threads=[])

    def test_limits_are_positive_finite_and_defaults_do_not_enable_tasks(self):
        settings = automation_settings.validate({})
        for task in ("reports", "backups", "escalation", "cleanup"):
            self.assertFalse(settings[task]["enabled"])
        for invalid in (0, -1, True, "30", float("nan"), float("inf")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                automation_settings.validate({"runtime": {"shutdown_timeout_seconds": invalid}})

    def test_deadline_is_exact_and_context_does_not_leak(self):
        event = threading.Event()
        now = [10.]
        with budget(event, 5, clock=lambda: now[0]):
            now[0] = 14.999
            checkpoint()
            now[0] = 15.
            with self.assertRaises(Cancelled):
                checkpoint()
        checkpoint()

    def test_cancellation_between_tasks_does_not_start_next_one(self):
        engine = self.server().engine
        automation_settings.save(self.root, {"reports": {"enabled": True}, "backups": {"enabled": True}})
        service = AutomationService(engine, tasks={})
        later = Mock()
        def first(*args):
            service.stop_event.set()
            checkpoint()
        service.tasks = {"reports": first, "backups": later}
        self.assertEqual(service.run_due_tasks(datetime.now(timezone.utc)), {"reports": "cancelled"})
        later.assert_not_called()

    def test_stop_returns_incomplete_and_keeps_running_worker_reference(self):
        service = AutomationService(self.server().engine, tasks={})
        worker = Mock()
        worker.is_alive.return_value = True
        service.worker = worker
        with patch("automation.time.monotonic", side_effect=[100., 102.]):
            self.assertFalse(service.stop(timeout=5))
        worker.join.assert_called_once_with(3.)
        self.assertIs(service.worker, worker)

    def test_global_shutdown_budget_signals_all_before_waiting(self):
        server = self.server()
        service = AutomationService(server.engine, tasks={})
        writer = Mock()
        writer.is_alive.return_value = True
        server.engine.worker = writer
        now = [0.]
        def wait(seconds):
            self.assertTrue(server.engine.stop_event.is_set())
            self.assertTrue(server.engine.notifications.stop_event.is_set())
            self.assertTrue(service.stop_event.is_set())
            now[0] += seconds
        self.assertFalse(stop_server(server, service, .12, clock=lambda: now[0], wait=wait))
        self.assertAlmostEqual(now[0], .12)
        self.assertIs(server.engine.worker, writer)
        writer.is_alive.return_value = False
        self.assertTrue(quiescent(server, service))

    def test_storage_lease_and_cleanup_are_deferred_until_writer_finishes(self):
        ready = threading.Event()
        cleaned = threading.Event()
        with storage_lease(self.root) as lease:
            lease.defer_until(ready.is_set, cleaned.set)
        try:
            self.assertFalse(cleaned.is_set())
            with self.assertRaises(OSError):
                with storage_lease(self.root):
                    pass
        finally:
            ready.set()
            lease.worker.join(5)
        self.assertFalse(lease.worker.is_alive())
        self.assertTrue(cleaned.is_set())
        with storage_lease(self.root):
            pass

    def test_active_request_prevents_resource_release(self):
        server = self.server()
        service = AutomationService(server.engine, tasks={})
        request = Mock()
        request.is_alive.return_value = True
        server._threads.append(request)
        self.assertFalse(stop_server(server, service, 0))
        request.is_alive.return_value = False
        self.assertTrue(stop_server(server, service, 0))


if __name__ == "__main__":
    unittest.main()
