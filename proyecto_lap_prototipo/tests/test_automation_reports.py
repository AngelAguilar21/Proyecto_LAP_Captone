"""Scheduled reports use synthetic aggregates/PDFs and temporary files only."""
import copy
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from reportlab.pdfgen.canvas import Canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
from automation import AutomationService, LIMA
from automation_reports import ScheduledReports
from automation_artifacts import fingerprint, verify_pdf
from automation_store import AutomationStore
from live_reports import business_report_data
from task_control import budget, Cancelled
import automation_settings


def synthetic_pdf(label="Synthetic report", pages=1):
    output = io.BytesIO()
    canvas = Canvas(output, invariant=1)
    for page in range(pages):
        canvas.drawString(30, 100, f"{label} {page}")
        canvas.showPage()
    canvas.save()
    return output.getvalue()


class ScheduledReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.engine = Engine(self.root / "project.json")
        self.engine.project_id = "synthetic-project"
        self.engine.config.update(airport="Synthetic site", unit="relative", cameras=[])
        self.valid_session()
        self.store = AutomationStore(self.root / "automation.sqlite")
        self.renderer = Mock(return_value=synthetic_pdf())
        self.task = ScheduledReports(self.engine, self.store, self.renderer)
        self.now = datetime(2026, 10, 1, 18, tzinfo=LIMA)
        self.settings = {"enabled": True, "time": "18:00"}

    def valid_session(self):
        self.engine.state.update(session="synthetic-session", status="ended", t=10, mode="hybrid", testRun=False,
            analytics={"zones": []}, cameraAnalytics={},
            totals={"meanObservedSeconds": 5, "alerts": 0}, series=[{"t": 10, "count": 2}])

    def row(self, pid="synthetic-project", date="2026-10-01"):
        return self.store.get("reports", pid, date)

    def health(self):
        return self.store.health("reports", "synthetic-project", "2026-10-01")

    def target(self):
        return self.root / "data/reports/synthetic-project/business-2026-10-01.pdf"

    def test_disabled_direct_call_does_not_capture_render_or_write(self):
        with patch.object(self.engine, "automation_snapshot") as capture:
            self.assertEqual(self.task(self.now, {**self.settings, "enabled": False}), "disabled")
        capture.assert_not_called()
        self.renderer.assert_not_called()
        self.assertFalse(self.store.path.exists())

    def test_absent_configuration_does_not_activate_injected_reports(self):
        service = AutomationService(self.engine, {"reports": self.task})
        self.assertEqual(service.run_due_tasks(self.now), {})
        self.renderer.assert_not_called()
        self.assertFalse(self.store.path.exists())

    def test_before_configured_time_is_not_due(self):
        self.assertEqual(self.task(self.now - timedelta(seconds=1), self.settings), "not_due")
        self.renderer.assert_not_called()
        self.assertFalse(self.store.path.exists())

    def test_exact_time_publishes_valid_pdf_fingerprint_and_project_execution(self):
        self.assertEqual(self.task(self.now, self.settings), "succeeded")
        row = self.row()
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(Path(row["artifact"]), self.target())
        data = self.target().read_bytes()
        self.assertTrue(verify_pdf(data))
        self.assertEqual(data, self.renderer.return_value)
        self.assertEqual((self.health()["sha256"], self.health()["size"]), fingerprint(data))
        self.assertEqual(self.health()["status"], "healthy")
        self.assertEqual(self.renderer.call_args.args[0]["generated"], self.now.isoformat())

    def test_repeat_ticks_and_restarted_task_do_not_duplicate(self):
        self.task(self.now, self.settings)
        before = self.row()
        modified = self.target().stat().st_mtime_ns
        restarted = ScheduledReports(self.engine, AutomationStore(self.store.path), self.renderer)
        for minute in (1, 2, 30):
            self.assertEqual(restarted(self.now + timedelta(minutes=minute), self.settings), "already_done")
        self.renderer.assert_called_once()
        self.assertEqual(self.row(), before)
        self.assertEqual(self.target().stat().st_mtime_ns, modified)
        with self.store.connect() as db:
            statuses = [json.loads(r[0]) for r in db.execute("SELECT detail FROM audit WHERE task='reports'")]
        self.assertEqual(sum(r.get("status") == "succeeded" for r in statuses), 1)

    def test_new_lima_day_and_other_project_have_independent_scope(self):
        self.task(self.now, self.settings)
        self.assertEqual(self.task(self.now + timedelta(days=1), self.settings), "succeeded")
        self.engine.project_id = "another-project"
        self.assertEqual(self.task(self.now, self.settings), "succeeded")
        self.assertEqual(self.renderer.call_count, 3)
        self.assertEqual(len(list(self.task.root.rglob("*.pdf"))), 3)
        self.assertEqual(self.row(date="2026-10-02")["status"], "succeeded")
        self.assertEqual(self.row(pid="another-project")["status"], "succeeded")

    def test_utc_input_uses_lima_day_without_backfilling_missed_days(self):
        utc = datetime(2026, 10, 2, 1, tzinfo=timezone.utc)
        self.assertEqual(self.task(utc, self.settings), "succeeded")
        self.assertEqual(self.row()["status"], "succeeded")
        self.assertIsNone(self.row(date="2026-10-02"))
        self.assertIsNone(self.row(date="2026-09-30"))

    def test_configurable_schedule_and_naive_datetime_rejection(self):
        self.assertEqual(self.task(self.now, {**self.settings, "time": "20:00"}), "not_due")
        with self.assertRaises(ValueError):
            self.task(self.now.replace(tzinfo=None), self.settings)
        self.renderer.assert_not_called()

    def test_no_data_cases_are_recorded_and_can_be_retried(self):
        original = copy.deepcopy(self.engine.state)
        cases = [{"session": None}, {"status": "idle"}, {"status": "error"}, {"t": 0},
                 {"series": []}, {"totals": {}}, {"series": [{"t": 1}]},
                 {"analytics": {"zones": [{"name": "incomplete"}]}}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.engine.state = {**copy.deepcopy(original), **changes}
                self.assertEqual(self.task(self.now, self.settings), "no_data")
                self.assertEqual(self.row()["status"], "no_data")
                self.assertFalse(self.target().exists())
        self.renderer.assert_not_called()
        self.engine.state = original
        self.assertEqual(self.task(self.now, self.settings), "succeeded")

    def test_unmanaged_snapshot_has_no_data_without_invented_project_scope(self):
        self.engine.project_id = None
        self.assertEqual(self.task(self.now, self.settings), "no_data")
        self.renderer.assert_not_called()
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM executions").fetchone()[0], 0)
            self.assertIn('"status": "no_data"', db.execute("SELECT detail FROM audit").fetchone()[0])

    def test_observed_zero_is_reportable(self):
        self.engine.state["series"] = [{"t": 10, "count": 0}]
        self.engine.state["totals"]["meanObservedSeconds"] = 0
        self.assertEqual(self.task(self.now, self.settings), "succeeded")
        self.assertEqual(self.renderer.call_args.args[0]["kpis"][0][1], "0")

    def test_test_run_and_demo_are_explicitly_marked(self):
        self.engine.state["testRun"] = True
        self.task(self.now, self.settings)
        self.assertEqual(self.renderer.call_args.args[0]["mode"], "VIDEOS DE PRUEBA - PLANO ILUSTRATIVO")
        self.engine.state["mode"] = "demo"
        self.task(self.now + timedelta(days=1), self.settings)
        self.assertEqual(self.renderer.call_args.args[0]["mode"], "SIMULACIÓN SINTÉTICA")

    def test_only_whitelisted_snapshot_reaches_formatter_and_renderer(self):
        forbidden = {"people": [{"id": "INDIVIDUAL-SECRET"}], "history": "SECRET", "appearance": "SECRET",
                     "frames": "SECRET", "source": "rtsp://user:SECRET@invalid", "password": "SECRET"}
        self.engine.state.update(forbidden)
        self.engine.config.update(forbidden)
        self.engine.config["cameras"] = [{"id": "C", "name": "synthetic", **forbidden}]
        self.engine.state["cameraAnalytics"] = {"C": {**forbidden, "dense": {"count": 8, "points": [forbidden]},
                                                     "avie": {"tracks": 4, **forbidden}}}
        captured = self.engine.automation_snapshot()
        def render(data):
            self.assertNotIn("SECRET", json.dumps(data))
            self.assertGreater(self.engine.resource_users, 0)
            # Any later Engine access to fill the report would now be invalid.
            self.engine.config.clear()
            self.engine.state.clear()
            self.engine.project_id = "changed-project"
            return self.renderer.return_value
        self.renderer.side_effect = render
        with patch("automation_reports.business_report_data", wraps=business_report_data) as formatter, \
             patch.object(self.engine, "automation_snapshot", wraps=self.engine.automation_snapshot) as snapshot:
            self.task(self.now, self.settings)
        snapshot.assert_called_once()
        self.assertEqual(formatter.call_args.args, (captured["config"], captured["state"]))
        self.assertNotIn("SECRET", json.dumps(formatter.call_args.args))
        self.assertEqual(self.row()["status"], "succeeded")
        self.assertIsNone(self.row(pid="changed-project"))

    def test_running_snapshot_reports_unknown_camera_coverage_not_zero(self):
        self.engine.state["status"] = "running"
        self.engine.config["cameras"] = [{"id": "C"}]
        self.task(self.now, self.settings)
        recommendations = " ".join(self.renderer.call_args.args[0]["recommendations"])
        self.assertIn("no se puede determinar", recommendations)
        self.assertNotIn("Solo 0", recommendations)

    def test_atomic_publication_uses_synced_temporary_in_final_directory(self):
        replaced, events = os.replace, []
        fsync = os.fsync
        def sync(fd):
            fsync(fd)
            events.append("fsync")
        def replace(source, target):
            self.assertEqual(Path(source).parent, self.target().parent)
            self.assertEqual(Path(target), self.target())
            self.assertEqual(Path(source).read_bytes(), self.renderer.return_value)
            self.assertFalse(self.target().exists())
            self.assertTrue(self.engine.resources.protected(source))
            events.append("replace")
            replaced(source, target)
        with patch("automation_reports.os.fsync", side_effect=sync), patch("automation_reports.os.replace", side_effect=replace):
            self.task(self.now, self.settings)
        self.assertEqual(events, ["fsync", "replace"])
        self.assertEqual(list(self.task.root.rglob("*.tmp")), [])
        self.assertEqual(self.engine.resource_users, 0)

    def test_invalid_renderer_pdf_is_not_published(self):
        self.renderer.return_value = b"%PDF-1.4\n%%EOF"
        with self.assertRaises(ValueError):
            self.task(self.now, self.settings)
        self.assertFalse(self.target().exists())
        self.assertEqual(self.row()["status"], "failed")

    def test_fsync_or_replace_failure_removes_only_temporary_artifact(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation), patch("automation_reports.os." + operation, side_effect=OSError("synthetic")):
                with self.assertRaises(OSError):
                    self.task(self.now, self.settings)
            self.assertFalse(self.target().exists())
            self.assertEqual(list(self.task.root.rglob("*.tmp")), [])
            self.assertEqual(self.engine.resource_users, 0)

    def test_existing_invalid_final_is_preserved_for_human_review(self):
        self.target().parent.mkdir(parents=True)
        self.target().write_bytes(b"existing synthetic evidence")
        with self.assertRaises(ValueError):
            self.task(self.now, self.settings)
        self.renderer.assert_not_called()
        self.assertEqual(self.target().read_bytes(), b"existing synthetic evidence")

    def test_published_pdf_recovers_after_failure_before_success_commit(self):
        with patch.object(self.store, "publish_success", side_effect=OSError("synthetic database failure")):
            with self.assertRaises(OSError):
                self.task(self.now, self.settings)
        data = self.target().read_bytes()
        self.assertNotEqual(self.row()["status"], "succeeded")
        self.engine.state.clear()  # Recovery does not need to recreate the session.
        self.assertEqual(self.task(self.now, self.settings), "recovered")
        self.renderer.assert_called_once()
        self.assertEqual(self.target().read_bytes(), data)
        self.assertEqual(self.row()["status"], "succeeded")
        self.assertEqual((self.health()["sha256"], self.health()["size"]), fingerprint(data))

    def test_cancel_after_render_does_not_publish(self):
        event = threading.Event()
        def render(data):
            event.set()
            return self.renderer.return_value
        self.renderer.side_effect = render
        with self.assertRaises(Cancelled), budget(event, 60):
            self.task(self.now, self.settings)
        self.assertFalse(self.target().exists())
        self.assertEqual(self.row()["status"], "cancelled")

    def test_historical_missing_stays_succeeded_without_regeneration(self):
        self.task(self.now, self.settings)
        before, digest = self.row(), self.health()["sha256"]
        self.target().unlink()
        for _ in range(2):
            self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.row(), before)
        self.assertEqual((self.health()["status"], self.health()["sha256"]), ("missing", digest))
        self.renderer.assert_called_once()
        self.assertFalse(self.target().exists())

    def test_historical_corrupt_stays_succeeded_without_replacement(self):
        self.task(self.now, self.settings)
        before = self.row()
        bad = b"%PDF-1.4\nsynthetic invalid objects\n%%EOF"
        self.target().write_bytes(bad)
        self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.row(), before)
        self.assertEqual(self.health()["status"], "corrupt")
        self.assertEqual(self.target().read_bytes(), bad)
        self.renderer.assert_called_once()

    def test_different_structurally_valid_pdf_fails_fingerprint(self):
        self.task(self.now, self.settings)
        original = self.health()["sha256"]
        self.target().write_bytes(synthetic_pdf("Different PDF"))
        self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual((self.health()["status"], self.health()["error"]), ("corrupt", "fingerprint_mismatch"))
        self.assertEqual(self.health()["sha256"], original)
        self.renderer.assert_called_once()

    def test_legacy_success_without_fingerprint_is_unverifiable(self):
        self.task(self.now, self.settings)
        with self.store.connect() as db:
            db.execute("DELETE FROM artifact_health")
        for _ in range(2):
            self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.health()["status"], "unverifiable")
        self.assertIsNone(self.health()["sha256"])
        self.assertIsNone(self.health()["size"])
        self.assertEqual(self.row()["status"], "succeeded")
        self.renderer.assert_called_once()

    def test_old_dates_and_other_projects_are_verified_without_regenerating_them(self):
        self.task(self.now, self.settings)
        self.target().unlink()
        self.engine.project_id = "another-project"
        self.task(self.now + timedelta(days=1), self.settings)
        self.assertEqual(self.health()["status"], "missing")
        self.assertEqual(self.row()["status"], "succeeded")
        self.assertEqual(self.renderer.call_count, 2)

    def test_current_publication_precedes_long_history_scan(self):
        def cancelled(*args):
            self.assertTrue(self.target().exists())
            self.assertEqual(self.row()["status"], "succeeded")
            raise Cancelled("synthetic budget consumed by history")
        with patch("automation_reports.check_successes", side_effect=cancelled):
            with self.assertRaises(Cancelled):
                self.task(self.now, self.settings)
        self.assertEqual(self.row()["status"], "succeeded")

    def test_service_records_project_outcome_without_false_service_success(self):
        automation_settings.save(self.root, {"reports": self.settings})
        self.engine.state["session"] = None
        service = AutomationService(self.engine, {"reports": self.task})
        self.assertEqual(service.run_due_tasks(self.now), {"reports": "no_data"})
        self.assertEqual(self.row()["status"], "no_data")
        self.assertIsNone(self.row(pid="service"))
        self.valid_session()
        self.assertEqual(service.run_due_tasks(self.now), {"reports": "succeeded"})
        self.assertEqual(self.row()["status"], "succeeded")
        self.assertIsNone(self.row(pid="service"))

    def test_two_instances_publish_only_one_final_with_shared_sqlite(self):
        barrier = threading.Barrier(2)
        calls, outcomes, errors = [], [], []
        def render(data):
            barrier.wait(3)
            return self.renderer.return_value
        other = ScheduledReports(self.engine, AutomationStore(self.store.path), render)
        self.task.renderer = render
        original = os.replace
        def replace(source, target):
            calls.append(str(target))
            original(source, target)
        def run(task):
            try:
                outcomes.append(task(self.now, self.settings))
            except BaseException as exc:
                errors.append(exc)
        # Initialize the schema before concurrent connections start.
        with self.store.connect():
            pass
        with patch("automation_reports.os.replace", side_effect=replace):
            workers = [threading.Thread(target=run, args=(task,)) for task in (self.task, other)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(5)
        self.assertTrue(all(not w.is_alive() for w in workers))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(outcomes), ["already_done", "succeeded"])
        self.assertEqual(calls, [str(self.target())])
        self.assertEqual(self.row()["status"], "succeeded")

    def test_persistence_failure_is_visible_to_runtime_without_publishing(self):
        automation_settings.save(self.root, {"reports": self.settings})
        service = AutomationService(self.engine, {"reports": self.task})
        with patch.object(self.store, "publication", side_effect=sqlite3.OperationalError("synthetic")):
            self.assertEqual(service.run_due_tasks(self.now), {"reports": "failed"})
        self.assertEqual(service.error, "OperationalError")
        self.assertEqual(self.row()["status"], "failed")
        self.renderer.assert_not_called()
        self.assertFalse(self.target().exists())

    def test_real_modern_business_renderer_produces_valid_marked_pdf(self):
        self.engine.state["testRun"] = True
        task = ScheduledReports(self.engine, self.store)
        self.assertEqual(task(self.now, self.settings), "succeeded")
        pdf = self.target().read_bytes()
        self.assertTrue(verify_pdf(pdf))
        import pypdfium2 as pdfium
        from contextlib import closing
        from pdf_runtime import PDFIUM_LOCK
        with PDFIUM_LOCK, closing(pdfium.PdfDocument(pdf)) as document:
            text = []
            for index in range(len(document)):
                with closing(document[index]) as page, closing(page.get_textpage()) as contents:
                    text.append(contents.get_text_bounded())
        self.assertIn("VIDEOS DE PRUEBA", " ".join(text))

    def test_startup_registers_reports_backups_escalation_and_keeps_default_inert(self):
        import live_server
        def serve():
            from automation_backups import ProjectBackups
            from automation_escalation import AlertEscalation
            self.assertEqual(set(self.engine.automation.tasks), {"reports", "backups", "escalation"})
            self.assertIsInstance(self.engine.automation.tasks["reports"], ScheduledReports)
            self.assertIsInstance(self.engine.automation.tasks["backups"], ProjectBackups)
            self.assertIsInstance(self.engine.automation.tasks["escalation"], AlertEscalation)
            self.assertEqual(self.engine.automation.run_due_tasks(self.now), {})
        server = SimpleNamespace(socket=Mock(), server_bind=Mock(), server_activate=Mock(), server_close=Mock(), serve_forever=serve)
        with patch.object(live_server, "ManagedHTTPServer", return_value=server), \
             patch.object(live_server, "Engine", return_value=self.engine), \
             patch.object(self.engine, "warm_detector_async"), patch.object(sys, "argv", ["live_server.py"]):
            live_server.main()
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.task.root.exists())
        server.server_close.assert_called_once()
