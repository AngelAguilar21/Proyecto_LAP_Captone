"""Escalation uses temporary SQLite/config, controlled clocks and no SMTP."""
import smtplib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
from automation import AutomationService, LIMA
from automation_escalation import AlertEscalation
from incident_notifications import IncidentNotifications
import automation_settings
import business_data
import notifier


class EscalationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="escalation-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "project.json"
        self.created = datetime(2026, 9, 26, 10, tzinfo=LIMA)
        self.now = self.created
        self.enterContext(patch.object(business_data, "time", Mock(time=lambda: self.now.timestamp())))
        self.enterContext(patch.object(notifier, "time", Mock(time=lambda: self.now.timestamp())))
        self.smtp = self.enterContext(patch.object(notifier, "_send"))
        # Defense in depth: an accidental bypass of _send must not reach a socket.
        self.enterContext(patch.object(notifier.smtplib, "SMTP", side_effect=AssertionError("Real SMTP forbidden")))
        self.enterContext(patch.object(notifier.smtplib, "SMTP_SSL", side_effect=AssertionError("Real SMTP forbidden")))
        notifier.save(self.root, dict(enabled=True, host="smtp.example.invalid", port=465,
                                     user="sender@example.invalid", password="synthetic-secret",
                                     recipients=["normal@example.invalid"]))
        self.engine = Engine(self.path)
        self.restart_notifications("boot-a")
        self.task = AlertEscalation(self.engine)
        self.settings = dict(enabled=True, delay_minutes=15, recipients=["supervisor@example.invalid"])

    def restart_notifications(self, owner):
        self.engine.notifications = IncidentNotifications(notifier.Mailer(self.root),
            clock=lambda: self.now.timestamp(), process_id=owner)

    def create(self, iid="incident", path=None):
        with closing(business_data.connect(path or self.path)) as db:
            business_data.registrar_incidente(db, iid, "equipaje", "Zona sintética", "C", 2)

    def legacy(self, states=("pendiente",)):
        # Authentic old schema: ESQUEMA intentionally has no history columns.
        with closing(sqlite3.connect(business_data.path_for(self.path))) as db, db:
            db.executescript(business_data.ESQUEMA)
            for i, state in enumerate(states):
                db.execute("INSERT INTO incidentes "
                           "(id,tipo,inicio,estado,creado,actualizado) VALUES (?,'equipaje',0,?,?,?)",
                           (f"legacy-{i}", state, self.created.timestamp(), self.created.timestamp() + 9999))

    def tick(self, seconds=900):
        self.now = self.created + timedelta(seconds=seconds)
        return self.task(self.now, self.settings)

    def incident(self, iid="incident"):
        return next(i for i in self.engine.incidents()["incidentes"] if i["id"] == iid)

    def notification(self, iid="incident", kind="escalation"):
        return self.engine.notifications.get(self.path, iid, kind)

    def test_migration_repeated_preserves_all_legacy_states_as_unknown(self):
        states = ("pendiente", "revisado", "falsa_alarma", "resuelto")
        self.legacy(states)
        for _ in range(3):
            rows = self.engine.incidents()["incidentes"]
            self.assertEqual(len(rows), 4)
            for i, state in enumerate(states):
                row = next(r for r in rows if r["id"] == f"legacy-{i}")
                self.assertEqual(row["estado"], state)
                self.assertFalse(row["review_history_known"])
                self.assertIsNone(row["reviewed_at"])
                self.assertIsNone(row["history_validated_at"])
                self.assertIsNone(row["escalated_at"])
        self.assertEqual(self.tick(99999)["candidates"], 0)
        self.smtp.assert_not_called()

    def test_migration_failure_rolls_back_all_added_columns(self):
        self.legacy()
        with closing(sqlite3.connect(business_data.path_for(self.path))) as db:
            before = db.execute("PRAGMA table_info(incidentes)").fetchall()
            alterations = []
            def authorize(action, *args):
                if action == sqlite3.SQLITE_ALTER_TABLE:
                    alterations.append(action)
                    if len(alterations) == 2:
                        return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            db.set_authorizer(authorize)
            with self.assertRaises(sqlite3.DatabaseError):
                business_data.migrate_incident_history(db)
            db.set_authorizer(None)
            self.assertEqual(db.execute("PRAGMA table_info(incidentes)").fetchall(), before)
            self.assertEqual(db.execute("SELECT id FROM incidentes").fetchall(), [("legacy-0",)])

    def test_new_incident_is_known_and_exact_delay_uses_created_not_source_or_updated(self):
        self.create()
        self.assertTrue(self.incident()["review_history_known"])
        self.assertIsNone(self.incident()["reviewed_at"])
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("UPDATE incidentes SET inicio=-999999, actualizado=?", (self.created.timestamp()+99999,))
        self.assertEqual(self.tick(899.999), {"candidates": 0, "sent": 0})
        self.smtp.assert_not_called()
        self.assertEqual(self.tick(900), {"candidates": 1, "sent": 1})
        row = self.notification()
        self.assertEqual((row["status"], row["sent_at"]), ("sent", self.now.timestamp()))
        self.assertEqual(self.incident()["escalated_at"], self.now.timestamp())
        self.smtp.assert_called_once()

    def test_all_attended_states_permanently_exclude_even_if_returned_to_pending(self):
        for state in ("revisado", "falsa_alarma", "resuelto"):
            with self.subTest(state=state):
                self.create(state)
                self.engine.update_incident(state, state)
                first_review = self.incident(state)["reviewed_at"]
                self.assertEqual(first_review, self.now.timestamp())
                self.engine.update_incident(state, "pendiente")
                self.assertEqual(self.incident(state)["reviewed_at"], first_review)
        self.assertEqual(self.tick()["candidates"], 0)
        self.smtp.assert_not_called()

    def test_legacy_only_explicit_never_attended_confirmation_enables_escalation(self):
        self.legacy()
        self.engine.update_incident("legacy-0", "pendiente")
        self.assertEqual(self.tick()["sent"], 0)
        result = self.engine.validate_incident_history("legacy-0", True)["incidentes"][0]
        self.assertTrue(result["review_history_known"])
        self.assertIsNone(result["reviewed_at"])
        self.assertEqual(result["estado"], "pendiente")
        self.assertEqual(result["history_validated_at"], self.now.timestamp())
        self.assertEqual(self.tick()["sent"], 1)
        self.smtp.assert_called_once()

    def test_human_attendance_during_legacy_validation_permanently_excludes(self):
        self.legacy()
        result = self.engine.validate_incident_history("legacy-0", False)["incidentes"][0]
        self.assertEqual(result["estado"], "revisado")
        self.assertEqual(result["reviewed_at"], self.now.timestamp())
        self.assertTrue(result["review_history_known"])
        self.engine.update_incident("legacy-0", "pendiente")
        with self.assertRaises(ValueError):
            self.engine.validate_incident_history("legacy-0", True)
        self.assertEqual(self.tick()["sent"], 0)
        self.smtp.assert_not_called()

    def test_validation_requires_explicit_boolean_and_cannot_validate_nonpending(self):
        self.legacy(("pendiente", "resuelto"))
        for invalid in (None, 1, "true"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.engine.validate_incident_history("legacy-0", invalid)
        with self.assertRaises(ValueError):
            self.engine.validate_incident_history("legacy-1", True)
        self.assertFalse(self.incident("legacy-0")["review_history_known"])

    def test_success_is_not_repeated_after_cooldown_or_restart(self):
        self.create()
        self.assertEqual(self.tick()["sent"], 1)
        self.restart_notifications("boot-b")
        self.task = AlertEscalation(self.engine)
        self.assertEqual(self.tick(99999)["sent"], 0)
        self.assertEqual(self.notification()["attempts"], 1)
        self.smtp.assert_called_once()

    def test_confirmed_failure_is_retryable_and_success_timestamp_is_written_after_send(self):
        self.create()
        self.smtp.side_effect = smtplib.SMTPDataError(550, b"synthetic rejection")
        self.assertEqual(self.tick()["sent"], 0)
        self.assertEqual(self.notification()["status"], "failed")
        self.assertIsNone(self.incident()["escalated_at"])
        self.assertIsNone(self.notification()["sent_at"])
        def accepted(*args):
            self.assertEqual(self.notification()["status"], "attempting")
            self.assertIsNone(self.incident()["escalated_at"])
        self.smtp.side_effect = accepted
        self.assertEqual(self.tick(1020)["sent"], 1)
        self.assertEqual(self.notification()["attempts"], 2)
        self.assertEqual(self.incident()["escalated_at"], self.now.timestamp())

    def test_uncertain_delivery_is_never_retried_after_restart(self):
        self.create()
        self.smtp.side_effect = TimeoutError("unknown result")
        self.assertEqual(self.tick()["sent"], 0)
        self.restart_notifications("boot-b")
        self.assertEqual(self.tick(99999)["sent"], 0)
        self.assertEqual(self.notification()["status"], "uncertain")
        self.assertIsNone(self.incident()["escalated_at"])
        self.smtp.assert_called_once()

    def test_attempting_from_old_process_is_reconciled_without_sending(self):
        self.create()
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("INSERT INTO incident_notifications "
                       "(incident_id,notification_kind,status,attempted_at,owner) "
                       "VALUES ('incident','escalation','attempting',?,'old-boot')", (self.now.timestamp(),))
        self.assertEqual(self.tick()["sent"], 0)
        self.assertEqual(self.notification()["status"], "uncertain")
        self.assertIsNone(self.notification()["sent_at"])
        self.smtp.assert_not_called()

    def test_supervisor_recipients_and_original_delivery_are_independent(self):
        self.create()
        before = notifier.path_for(self.root).read_bytes()
        self.assertTrue(self.engine.notifications.send(self.path, "incident", "Original", "Synthetic", blocking=True))
        self.assertEqual(self.tick()["sent"], 1)
        self.assertEqual([call.args[0]["recipients"] for call in self.smtp.call_args_list],
                         [["normal@example.invalid"], ["supervisor@example.invalid"]])
        self.assertEqual(notifier.path_for(self.root).read_bytes(), before)
        self.assertEqual(self.notification(kind="original")["status"], "sent")
        self.assertEqual(self.notification()["status"], "sent")
        self.assertNotIn("synthetic-secret", str(self.notification()))

    def test_invalid_override_is_rejected_without_changing_config(self):
        before = notifier.path_for(self.root).read_bytes()
        for recipients in ([], ["invalid"], "a@example.invalid", [None]):
            with self.subTest(recipients=recipients), self.assertRaises(ValueError):
                self.engine.mailer.send("Test", "Test", blocking=True, recipients=recipients)
        self.assertEqual(notifier.path_for(self.root).read_bytes(), before)
        self.smtp.assert_not_called()

    def test_review_between_selection_and_claim_prevents_smtp(self):
        self.create()
        send = self.engine.notifications.send
        def review_then_send(*args, **kwargs):
            self.engine.update_incident("incident", "revisado")
            return send(*args, **kwargs)
        with patch.object(self.engine.notifications, "send", side_effect=review_then_send):
            self.assertEqual(self.tick()["sent"], 0)
        self.assertIsNone(self.notification())
        self.smtp.assert_not_called()

    def test_smtp_runs_outside_engine_lock_and_keeps_captured_project(self):
        self.create()
        other = self.root / "other.json"
        self.create(path=other)
        class Lock:
            held = False
            def __enter__(lock): lock.held = True
            def __exit__(lock, *args): lock.held = False
        self.engine.lock = Lock()
        def send(*args):
            self.assertFalse(self.engine.lock.held)
            self.engine.config_path = other
        self.smtp.side_effect = send
        self.assertEqual(self.tick()["sent"], 1)
        self.assertEqual(self.notification()["status"], "sent")
        self.assertIsNone(self.engine.notifications.get(other, "incident", "escalation"))

    def test_service_registers_task_without_starting_threads_and_disabled_is_inert(self):
        self.create()
        with patch("threading.Thread", side_effect=AssertionError("No worker in direct ticks")):
            service = AutomationService(self.engine)
            self.assertEqual(service.run_due_tasks(self.created), {})
            automation_settings.save(self.root, {"escalation": self.settings})
            self.now = self.created + timedelta(minutes=15)
            self.assertEqual(service.run_due_tasks(self.now)["escalation"]["sent"], 1)
        self.smtp.assert_called_once()

    def test_no_incidents_does_not_create_business_database(self):
        self.assertEqual(self.tick(), "no_incidents")
        self.assertFalse(business_data.path_for(self.path).exists())
        self.smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
