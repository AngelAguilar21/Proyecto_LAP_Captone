import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine, default_config
from automation import AutomationService, LIMA
from automation_reports import ScheduledReports
from automation_store import AutomationStore
import automation_settings


class ReportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.engine = Engine(self.root / "project.json")
        self.engine.project_id = "p-test"
        self.store = AutomationStore(self.root / "automation.sqlite")
        self.render = Mock(return_value=b"%PDF-1.4\nsynthetic\n%%EOF")
        self.task = ScheduledReports(self.engine, self.store, self.render)
        self.now = datetime(2026, 9, 25, 18, tzinfo=LIMA)
        self.settings = {"enabled": True, "time": "18:00"}
        self.valid_session()

    def valid_session(self):
        self.engine.report_config = default_config()
        self.engine.report_config["cameras"] = []
        self.engine.state.update(session="synthetic", status="ended", t=10, mode="demo",
                                 analytics={"zones": []}, totals={}, series=[{"t": 10, "count": 2}])

    def test_before_scheduled_time_does_nothing(self):
        self.assertEqual(self.task(self.now - timedelta(seconds=1), self.settings), "not_due")
        self.render.assert_not_called()
        self.assertFalse((self.root / "data" / "reports").exists())

    def test_exact_time_publishes_and_records_once(self):
        self.assertEqual(self.task(self.now, self.settings), "succeeded")
        row = self.store.get("reports", "p-test", "2026-09-25")
        self.assertEqual(Path(row["artifact"]).read_bytes(), self.render.return_value)
        self.assertEqual(self.render.call_args.args[0]["generated"], self.now.isoformat())
        self.assertEqual(self.task(self.now, self.settings), "already_done")
        self.render.assert_called_once()

    def test_late_start_only_generates_current_day(self):
        self.assertEqual(self.task(self.now + timedelta(hours=3), self.settings), "succeeded")
        self.assertIsNone(self.store.get("reports", "p-test", "2026-09-24"))
        self.assertEqual(len(list((self.root / "data" / "reports").rglob("*.pdf"))), 1)

    def test_no_session_can_be_retried_later_that_day(self):
        self.engine.state.pop("session")
        self.assertEqual(self.task(self.now, self.settings), "no_data")
        self.render.assert_not_called()
        self.assertEqual(self.store.get("reports", "p-test", "2026-09-25")["status"], "no_data")
        self.valid_session()
        self.assertEqual(self.task(self.now + timedelta(minutes=1), self.settings), "succeeded")

    def test_partial_recovery_is_not_reportable(self):
        self.engine.report_config = None
        self.assertEqual(self.task(self.now, self.settings), "no_data")
        self.render.assert_not_called()

    def test_restart_does_not_duplicate_report(self):
        self.task(self.now, self.settings)
        restarted = ScheduledReports(self.engine, AutomationStore(self.store.path), self.render)
        self.assertEqual(restarted(self.now, self.settings), "already_done")
        self.render.assert_called_once()

    def test_renderer_runs_outside_lock_and_keeps_captured_project(self):
        class Lock:
            held = False
            def __enter__(lock): lock.held = True
            def __exit__(lock, *args): lock.held = False
        self.engine.lock = Lock()
        def render(data):
            self.assertFalse(self.engine.lock.held)
            self.engine.project_id = "p-other"
            return b"%PDF-1.4\n%%EOF"
        self.render.side_effect = render
        self.task(self.now, self.settings)
        self.assertEqual(self.store.get("reports", "p-test", "2026-09-25")["status"], "succeeded")
        self.assertIsNone(self.store.get("reports", "p-other", "2026-09-25"))

    def test_render_failure_has_no_final_pdf_and_other_tasks_can_continue(self):
        automation_settings.save(self.root, {"reports": self.settings})
        self.render.side_effect = RuntimeError("synthetic failure")
        service = AutomationService(self.engine, {"reports": self.task})
        self.assertEqual(service.run_due_tasks(self.now), {"reports": "failed"})
        self.assertEqual(list(self.root.rglob("*.pdf")), [])
        self.assertIsNone(self.store.get("reports", "p-test", "2026-09-25"))

    def test_publication_failure_removes_temporary_file(self):
        with patch("automation_reports.os.replace", side_effect=PermissionError()):
            with self.assertRaises(PermissionError):
                self.task(self.now, self.settings)
        self.assertEqual(list((self.root / "data" / "reports").rglob("*.pdf")), [])
        self.assertEqual(list((self.root / "data" / "reports").rglob("*.tmp")), [])

    def test_published_file_is_reconciled_after_missing_success_commit(self):
        with patch.object(self.store, "record", side_effect=OSError("commit unavailable")):
            with self.assertRaises(OSError):
                self.task(self.now, self.settings)
        self.assertEqual(self.task(self.now, self.settings), "recovered")
        self.render.assert_called_once()

    def test_real_business_pdf_uses_synthetic_aggregates(self):
        task = ScheduledReports(self.engine, self.store)
        self.assertEqual(task(self.now, self.settings), "succeeded")
        row = self.store.get("reports", "p-test", "2026-09-25")
        self.assertTrue(Path(row["artifact"]).read_bytes().startswith(b"%PDF-"))

    def test_cancel_after_render_never_publishes(self):
        from task_control import budget, Cancelled
        import threading
        event = threading.Event()
        def render(data):
            event.set()
            return self.render.return_value
        self.render.side_effect = render
        with budget(event, 60), self.assertRaises(Cancelled):
            self.task(self.now, self.settings)
        self.assertEqual(list(self.root.rglob("*.pdf")), [])


if __name__ == "__main__":
    unittest.main()
