"""Escalation through real SQLite and Mailer; transport is always synthetic."""
import json
import smtplib
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
import automation_settings
import business_data
import notifier
from automation_escalation import AlertEscalation
from incident_notifications import IncidentNotifications
from task_control import budget, Cancelled


class AutomationEscalationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="escalation-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "project.json"
        self.now = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
        self.options = {"enabled": True, "delay_minutes": 15, "recipients": ["supervisor@example.invalid"]}
        self.cutoff = self.now.timestamp() - 900
        notifier.save(self.root, {"enabled": True, "host": "smtp.example.invalid", "port": 465,
                                 "user": "sender@example.invalid", "password": "synthetic-secret",
                                 "recipients": ["normal@example.invalid"]})
        self.smtp = self.enterContext(patch.object(notifier, "_send"))
        for name in ("SMTP", "SMTP_SSL"):
            guard = self.enterContext(patch.object(notifier.smtplib, name, side_effect=AssertionError("Real SMTP forbidden")))
            self.addCleanup(guard.assert_not_called)
        self.clock = self.enterContext(patch.object(notifier, "time", Mock()))
        self.clock.time.return_value = self.now.timestamp()
        self.engine = Engine(self.path)
        self.engine.project_id = "project-a"
        self.engine.notifications = IncidentNotifications(self.engine.mailer, clock=lambda: self.clock.time())
        self.task = AlertEscalation(self.engine)

    def incident(self, iid="incident", created=None, state="pendiente", path=None, known=True):
        with closing(business_data.connect(path or self.path)) as db, db:
            business_data.registrar_incidente(db, iid, "aglomeracion", "Synthetic zone", "C", 0,
                                              detalle={"people": [{"id": "SECRET-PERSON", "point": [12, 34]}],
                                                       "appearance": "SECRET-SIGNATURE", "frame": "SECRET-FRAME",
                                                       "source": "rtsp://user:SECRET-PASSWORD@example.invalid/video"})
            db.execute("UPDATE incidentes SET creado=?,review_history_known=? WHERE id=?",
                       (self.cutoff if created is None else created, int(known), iid))
            if state != "pendiente":
                business_data.actualizar_estado_incidente(db, iid, state)

    def result(self, iid="incident", kind="escalation"):
        return self.engine.notifications.get(self.path, iid, kind)

    def test_defaults_disabled_and_direct_disabled_task_does_not_create_database(self):
        self.assertFalse(automation_settings.load(self.root)["escalation"]["enabled"])
        self.assertTrue(all(not automation_settings.load(self.root)[k]["enabled"] for k in ("reports", "backups", "escalation", "cleanup")))
        self.assertEqual(self.task(self.now, {**self.options, "enabled": False}),
                         {"candidates": 0, "sent": 0, "status": "disabled"})
        self.assertFalse(business_data.path_for(self.path).exists())
        self.smtp.assert_not_called()

    def test_settings_validate_delay_recipients_and_reject_secrets(self):
        for delay in (0, -1, True, 1.5, "15", 3651):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                automation_settings.validate({"escalation": {**self.options, "delay_minutes": delay}})
        for recipients in ([], "a@example.invalid", ["bad"], ["@"], ["a@"], ["@b"], ["a@b\r\nBcc:x@y"],
                           ["a b@example.invalid"], [None], ["a@b@c"], ["x" * 201 + "@b"], ["a@b"] * 21):
            with self.subTest(recipients=recipients), self.assertRaises(ValueError):
                automation_settings.validate({"escalation": {**self.options, "recipients": recipients}})
        with self.assertRaises(ValueError):
            automation_settings.validate({"escalation": {**self.options, "password": "synthetic"}})
        config = automation_settings.save(self.root, {"escalation": {**self.options, "recipients": ["a@b"] * 20}})
        self.assertEqual(automation_settings.load(self.root), config)

    def test_project_without_business_sqlite_is_not_created(self):
        self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0, "status": "no_incidents"})
        self.assertFalse(business_data.path_for(self.path).exists())
        self.smtp.assert_not_called()

    def test_age_boundary_is_inclusive_and_selection_order_is_stable(self):
        self.incident("young", self.cutoff + .001)
        self.incident("equal-b")
        self.incident("older", self.cutoff - 1)
        self.incident("equal-a")
        sent = self.task(self.now, self.options)
        self.assertEqual(sent, {"candidates": 3, "sent": 3})
        self.assertEqual([c.args[2].splitlines()[0] for c in self.smtp.call_args_list],
                         ["Incidente: older", "Incidente: equal-a", "Incidente: equal-b"])
        self.assertIsNone(self.result("young"))

    def test_reviewed_resolved_false_alarm_and_return_to_pending_are_excluded(self):
        for state in ("revisado", "resuelto", "falsa_alarma"):
            self.incident(state, state=state)
        self.incident("returned", state="revisado")
        with closing(business_data.connect(self.path)) as db:
            business_data.actualizar_estado_incidente(db, "returned", "pendiente")
        self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0})
        self.smtp.assert_not_called()

    def test_legacy_unknown_requires_explicit_never_attended_validation(self):
        # Construct an actual pre-migration row, not a known new incident.
        with closing(sqlite3.connect(business_data.path_for(self.path))) as db, db:
            db.executescript(business_data.ESQUEMA)
            db.execute("INSERT INTO incidentes VALUES ('legacy','aglomeracion','zone','C',0,8,10,'pendiente','{}',?,?)",
                       (self.cutoff, self.cutoff))
        self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0})
        with closing(business_data.connect(self.path)) as db:
            business_data.validar_historial_incidente(db, "legacy", True)
        self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 1})
        self.assertEqual(self.result("legacy")["status"], "sent")

    def test_success_is_durable_across_ticks_and_restart(self):
        self.incident()
        self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 1})
        self.clock.time.return_value += 86400
        self.assertEqual(self.task(self.now + timedelta(days=1), self.options), {"candidates": 0, "sent": 0})
        self.engine.notifications = IncidentNotifications(notifier.Mailer(self.root), process_id="restart")
        self.assertEqual(self.task(self.now + timedelta(days=2), self.options), {"candidates": 0, "sent": 0})
        row = self.result()
        self.assertEqual((row["notification_kind"], row["status"], row["attempts"], row["sent_at"]),
                         ("escalation", "sent", 1, self.now.timestamp()))
        self.smtp.assert_called_once()

    def test_uncertain_never_retries_after_restart(self):
        self.incident()
        self.smtp.side_effect = TimeoutError("synthetic ambiguous result")
        self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 0})
        self.assertEqual(self.result()["status"], "uncertain")
        self.assertIsNone(self.result()["sent_at"])
        self.engine.notifications = IncidentNotifications(notifier.Mailer(self.root), process_id="restart")
        self.assertEqual(self.task(self.now + timedelta(days=1), self.options), {"candidates": 0, "sent": 0})
        self.smtp.assert_called_once()

    def test_failed_escalation_can_retry_after_defensive_cooldown(self):
        self.incident()
        self.smtp.side_effect = smtplib.SMTPDataError(550, b"synthetic")
        self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 0})
        self.assertEqual(self.result()["status"], "failed")
        self.assertIsNone(self.result()["sent_at"])
        self.smtp.side_effect = None
        self.clock.time.return_value += notifier.COOLDOWN
        self.assertEqual(self.task(self.now + timedelta(seconds=notifier.COOLDOWN), self.options), {"candidates": 1, "sent": 1})
        self.assertEqual((self.result()["status"], self.result()["attempts"]), ("sent", 2))

    def test_escalation_is_independent_of_original_sent_failed_or_absent(self):
        for state in ("sent", "failed", "absent"):
            self.incident(state)
            if state != "absent":
                self.smtp.side_effect = smtplib.SMTPDataError(550, b"synthetic") if state == "failed" else None
                self.engine.notifications.send(self.path, state, "Original", "Synthetic", blocking=True)
                self.assertEqual(self.result(state, "original")["status"], state)
        self.smtp.reset_mock(side_effect=True)
        self.assertEqual(self.task(self.now, self.options), {"candidates": 3, "sent": 3})
        self.assertEqual(self.result("sent", "original")["status"], "sent")
        self.assertEqual(self.result("failed", "original")["status"], "failed")
        self.assertIsNone(self.result("absent", "original"))

    def test_recovery_reconciles_orphan_attempt_as_uncertain(self):
        self.incident()
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("INSERT INTO incident_notifications(incident_id,notification_kind,status,attempted_at,owner) "
                       "VALUES ('incident','escalation','attempting',1,'old-process')")
        self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0})
        self.assertEqual(self.result()["status"], "uncertain")
        self.smtp.assert_not_called()

    def test_human_review_between_selection_and_claim_rejects_without_transport(self):
        self.incident()
        claim = self.engine.notifications._claim
        def reviewed(*args):
            with closing(business_data.connect(self.path)) as db:
                business_data.actualizar_estado_incidente(db, "incident", "revisado")
            return claim(*args)
        with patch.object(self.engine.notifications, "_claim", side_effect=reviewed):
            self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 0})
        self.assertIsNone(self.result())
        self.smtp.assert_not_called()

    def test_final_claim_rechecks_cutoff_using_captured_timestamp(self):
        self.incident()
        claim = self.engine.notifications._claim
        def younger(path, iid, kind, cutoff):
            self.assertEqual(cutoff, self.cutoff)
            self.clock.time.return_value += 3600  # Delivery clock must not widen eligibility.
            with closing(business_data.connect(path)) as db, db:
                db.execute("UPDATE incidentes SET creado=? WHERE id=?", (cutoff + .001, iid))
            return claim(path, iid, kind, cutoff)
        with patch.object(self.engine.notifications, "_claim", side_effect=younger):
            self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 0})
        self.assertIsNone(self.result())
        self.smtp.assert_not_called()

    def test_claim_also_rechecks_history_known_and_irreversible_review(self):
        claim = self.engine.notifications._claim
        for field, value in (("review_history_known", 0), ("reviewed_at", 100)):
            self.incident(field)
            with closing(business_data.connect(self.path)) as db, db:
                db.execute(f"UPDATE incidentes SET {field}=? WHERE id=?", (value, field))
            self.assertFalse(claim(self.path, field, "escalation", self.cutoff))
            self.assertIsNone(self.result(field))
        self.smtp.assert_not_called()

    def test_sqlite_serializes_escalation_claims_without_python_attempt_lock(self):
        self.incident()
        gate = threading.Barrier(2)
        def claim(owner):
            service = IncidentNotifications(notifier.Mailer(self.root), process_id=owner)
            gate.wait(5)
            return service._claim(self.path, "incident", "escalation", self.cutoff)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ["worker-a", "worker-b"]))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual((self.result()["status"], self.result()["attempts"]), ("attempting", 1))
        self.smtp.assert_not_called()

    def test_two_tasks_select_same_incident_but_only_one_sends(self):
        self.incident()
        gate = threading.Barrier(2)
        select = business_data.incidentes_para_escalar
        def simultaneous(db, cutoff):
            result = select(db, cutoff)
            gate.wait(5)
            return result
        with patch.object(business_data, "incidentes_para_escalar", side_effect=simultaneous), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.task(self.now, self.options), range(2)))
        self.assertEqual([r["candidates"] for r in results], [1, 1])
        self.assertEqual(sum(r["sent"] for r in results), 1)
        self.assertEqual(self.result()["attempts"], 1)
        self.smtp.assert_called_once()

    def test_active_delivery_is_not_reconciled_or_sent_twice(self):
        self.incident()
        entered, release = threading.Event(), threading.Event()
        def transport(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("synthetic gate")
        self.smtp.side_effect = transport
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.task, self.now, self.options)
            try:
                self.assertTrue(entered.wait(5))
                self.assertTrue(self.engine.notifications.has_writers())
                self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0})
                self.assertEqual(self.result()["status"], "attempting")
            finally:
                release.set()
            self.assertEqual(future.result(5)["sent"], 1)
        self.smtp.assert_called_once()

    def test_project_switch_after_capture_keeps_entire_task_on_original_project(self):
        self.incident("first")
        self.incident("second")
        other = self.root / "other.json"
        self.incident("other", path=other)
        select = business_data.incidentes_para_escalar
        def switch(db, cutoff):
            result = select(db, cutoff)
            with self.engine.lock:
                self.engine.config_path = other
                self.engine.project_id = "project-b"
            return result
        with patch.object(business_data, "incidentes_para_escalar", side_effect=switch):
            self.assertEqual(self.task(self.now, self.options), {"candidates": 2, "sent": 2})
        self.assertIsNone(self.engine.notifications.get(other, "other", "escalation"))
        for call in self.smtp.call_args_list:
            self.assertIn("Proyecto: project-a", call.args[2])
            self.assertNotIn("project-b", call.args[2])

    def test_supervisor_recipients_and_allowlisted_aggregate_body(self):
        self.incident()
        mail_before = (self.root / "correo.local.json").read_bytes()
        self.task(self.now, self.options)
        config, subject, body = self.smtp.call_args.args
        self.assertEqual(config["recipients"], ["supervisor@example.invalid"])
        self.assertEqual((self.root / "correo.local.json").read_bytes(), mail_before)
        self.assertEqual(notifier.load(self.root)["recipients"], ["normal@example.invalid"])
        self.assertIn("Incidente: incident", body)
        self.assertIn("15.0 minutos", body)
        self.assertIn("revisión humana", body)
        for secret in ("SECRET-PERSON", "SECRET-SIGNATURE", "SECRET-FRAME", "SECRET-PASSWORD", "synthetic-secret", "rtsp://", "point", "appearance"):
            self.assertNotIn(secret, subject + body)
            self.assertNotIn(secret, json.dumps(self.result()))

    def test_misplaced_source_url_in_zone_is_not_sent(self):
        self.incident()
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("UPDATE incidentes SET zona='rtsp://user:SECRET-PASSWORD@example.invalid/video'")
        self.task(self.now, self.options)
        self.assertIn("Zona: [omitido]", self.smtp.call_args.args[2])
        self.assertNotIn("SECRET-PASSWORD", self.smtp.call_args.args[2])

    def test_public_escalated_at_comes_only_from_successful_escalation(self):
        self.incident()
        self.engine.notifications.send(self.path, "incident", "Original", "Synthetic", blocking=True)
        self.assertIsNone(self.engine.incidents()["incidentes"][0]["escalated_at"])
        self.smtp.side_effect = TimeoutError("uncertain")
        self.task(self.now, self.options)
        self.assertIsNone(self.engine.incidents()["incidentes"][0]["escalated_at"])
        self.incident("success")
        self.smtp.side_effect = None
        self.task(self.now, self.options)
        row = next(r for r in self.engine.incidents()["incidentes"] if r["id"] == "success")
        self.assertEqual(row["escalated_at"], self.now.timestamp())

    def test_stop_between_candidates_preserves_first_delivery_and_skips_second(self):
        self.incident("first")
        self.incident("second")
        stopped = threading.Event()
        self.smtp.side_effect = lambda *args: stopped.set()
        with self.assertRaises(Cancelled), budget(stopped, 60):
            self.task(self.now, self.options)
        self.assertEqual(self.result("first")["status"], "sent")
        self.assertIsNone(self.result("second"))
        self.assertFalse(self.engine.notifications.has_writers())
        self.assertEqual(self.engine.resource_users, 0)
        self.smtp.assert_called_once()

    def test_deadline_expiring_during_claim_does_not_start_smtp(self):
        self.incident()
        elapsed = [0.]
        claim = self.engine.notifications._claim
        def slow_claim(*args):
            result = claim(*args)
            elapsed[0] = 60.
            return result
        with patch.object(self.engine.notifications, "_claim", side_effect=slow_claim):
            with self.assertRaises(Cancelled), budget(threading.Event(), 60, clock=lambda: elapsed[0]):
                self.task(self.now, self.options)
        self.assertEqual(self.result()["status"], "failed")
        self.assertIsNone(self.result()["sent_at"])
        self.assertFalse(self.engine.notifications.has_writers())
        self.smtp.assert_not_called()

    def test_notification_stop_event_blocks_claim_and_smtp(self):
        self.incident()
        self.engine.notifications.stop_event.set()
        self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 0})
        self.assertIsNone(self.result())
        self.smtp.assert_not_called()

    def test_engine_lock_released_and_writers_tracked_through_smtp(self):
        self.incident()
        with ThreadPoolExecutor(max_workers=1) as pool:
            def transport(*args):
                def take_lock():
                    with self.engine.lock:
                        return True
                self.assertTrue(pool.submit(take_lock).result(3))
                self.assertTrue(self.engine.resources.protected(business_data.path_for(self.path)))
                self.assertTrue(self.engine.notifications.has_writers())
                self.assertEqual(self.engine.notifications.workers, set())  # blocking; no own thread
            self.smtp.side_effect = transport
            self.assertEqual(self.task(self.now, self.options)["sent"], 1)
        self.assertEqual(self.engine.resource_users, 0)

    def test_accepted_result_persistence_failure_retries_only_sqlite(self):
        self.incident()
        with patch.object(self.engine.notifications, "_write_result", side_effect=sqlite3.OperationalError("synthetic disk")):
            self.assertEqual(self.task(self.now, self.options), {"candidates": 1, "sent": 0})
            self.assertEqual(self.result()["status"], "attempting")
            self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0})
        self.assertEqual(self.task(self.now, self.options), {"candidates": 0, "sent": 0})
        self.assertEqual((self.result()["status"], self.result()["sent_at"]), ("sent", self.now.timestamp()))
        self.smtp.assert_called_once()

    def test_service_runs_injected_task_and_records_task_not_individual_email(self):
        self.incident()
        self.engine.automation.tasks = {"escalation": self.task}
        self.assertEqual(self.engine.automation.run_due_tasks(self.now), {})
        self.smtp.assert_not_called()
        automation_settings.save(self.root, {"escalation": self.options})
        self.assertEqual(self.engine.automation.run_due_tasks(self.now), {"escalation": {"candidates": 1, "sent": 1}})
        with closing(sqlite3.connect(self.engine.automation.store.path)) as db:
            rows = db.execute("SELECT task,scope,status FROM executions").fetchall()
        self.assertEqual(rows, [("escalation", "service", "succeeded")])


if __name__ == "__main__":
    unittest.main()
