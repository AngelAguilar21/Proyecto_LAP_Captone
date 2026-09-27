"""Durable notifications with synthetic mail and temporary SQLite only."""
import sqlite3
import smtplib
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine
import business_data
import notifier
from incident_notifications import IncidentNotifications


class IncidentNotificationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="delivery-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "project.json"
        self.config = dict(enabled=True, host="smtp.example.invalid", port=465,
                           user="sender@example.invalid", password="synthetic-secret",
                           recipients=["recipient@example.invalid"])
        notifier.save(self.root, self.config.copy())
        self.smtp = self.enterContext(patch.object(notifier, "_send"))
        self.clock = self.enterContext(patch.object(notifier, "time", Mock()))
        self.clock.time.return_value = 1000
        self.mailer = notifier.Mailer(self.root)
        self.service = IncidentNotifications(self.mailer, clock=lambda: self.clock.time(), process_id="boot-a")
        self.incident("session-a:bag:1")

    def incident(self, iid):
        with closing(business_data.connect(self.path)) as db:
            business_data.registrar_incidente(db, iid, "equipaje", "maleta", "C", 0)

    def send(self, iid="session-a:bag:1", kind="original", service=None):
        return (service or self.service).send(self.path, iid, "Aviso sintético", "Sin datos reales",
                                              kind=kind, blocking=True)

    def test_new_incident_sends_once_and_repeated_call_is_suppressed(self):
        self.assertIsNone(self.service.get(self.path, "session-a:bag:1"))
        self.assertTrue(self.send())
        self.clock.time.return_value = 2000  # Beyond the defensive cooldown.
        self.assertFalse(self.send())
        self.smtp.assert_called_once()
        row = self.service.get(self.path, "session-a:bag:1")
        self.assertEqual((row["status"], row["attempts"], row["sent_at"]), ("sent", 1, 1000))

    def test_restart_does_not_resend_success(self):
        self.assertTrue(self.send())
        restarted = IncidentNotifications(notifier.Mailer(self.root), process_id="boot-b")
        restarted.recover(self.path)
        self.assertFalse(self.send(service=restarted))
        self.smtp.assert_called_once()

    def test_distinct_sessions_with_similar_keys_both_send(self):
        self.incident("session-b:bag:1")
        self.assertTrue(self.send())
        self.assertTrue(self.send("session-b:bag:1"))
        self.assertEqual(self.smtp.call_count, 2)

    def test_confirmed_failure_is_retryable_and_later_success_is_durable(self):
        self.smtp.side_effect = smtplib.SMTPDataError(550, b"synthetic-secret rejected")
        self.assertFalse(self.send())
        row = self.service.get(self.path, "session-a:bag:1")
        self.assertEqual(row["status"], "failed")
        self.assertIsNone(row["sent_at"])
        self.assertNotIn("synthetic-secret", str(row))
        self.smtp.side_effect = None
        self.clock.time.return_value += notifier.COOLDOWN
        self.assertTrue(self.send())
        row = self.service.get(self.path, "session-a:bag:1")
        self.assertEqual((row["status"], row["attempts"], row["sent_at"]), ("sent", 2, 1120))

    def test_cooldown_suppression_after_failure_never_counts_as_success(self):
        self.smtp.side_effect = smtplib.SMTPDataError(550, b"rejected")
        self.assertFalse(self.send())
        self.smtp.side_effect = None
        self.assertFalse(self.send())
        self.smtp.assert_called_once()
        row = self.service.get(self.path, "session-a:bag:1")
        self.assertEqual(row["status"], "failed")
        self.assertIsNone(row["sent_at"])

    def test_uncertain_delivery_is_never_retried_even_after_restart(self):
        self.smtp.side_effect = TimeoutError("may have been accepted")
        self.assertFalse(self.send())
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["status"], "uncertain")
        restarted = IncidentNotifications(notifier.Mailer(self.root), process_id="boot-b")
        self.assertFalse(self.send(service=restarted))
        self.smtp.assert_called_once()
        self.assertIsNone(restarted.get(self.path, "session-a:bag:1")["sent_at"])

    def test_interrupted_attempt_is_reconciled_as_uncertain(self):
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("INSERT INTO incident_notifications "
                       "(incident_id,notification_kind,status,attempted_at,owner) "
                       "VALUES (?,'original','attempting',1000,'old-process')", ("session-a:bag:1",))
        self.service.recover(self.path)
        self.assertFalse(self.send())
        row = self.service.get(self.path, "session-a:bag:1")
        self.assertEqual(row["status"], "uncertain")
        self.assertIsNone(row["sent_at"])
        self.smtp.assert_not_called()

    def test_original_and_escalation_are_independent(self):
        self.assertTrue(self.send())
        self.assertTrue(self.send(kind="escalation"))
        self.assertFalse(self.send(kind="escalation"))
        self.assertEqual(self.smtp.call_count, 2)
        for kind in ("original", "escalation"):
            self.assertEqual(self.service.get(self.path, "session-a:bag:1", kind)["status"], "sent")

    def test_two_simultaneous_calls_cannot_deliver_twice(self):
        entered, release = threading.Event(), threading.Event()
        def transport(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test barrier")
        self.smtp.side_effect = transport
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.send)
            try:
                self.assertTrue(entered.wait(5))
                peer = IncidentNotifications(notifier.Mailer(self.root), process_id="boot-a")
                self.assertFalse(self.send(service=peer))
            finally:
                release.set()
            self.assertTrue(future.result(5))
        self.smtp.assert_called_once()

    def test_existing_database_migration_is_repeatable_and_preserves_incident(self):
        # Recreate the pre-migration shape without the new notification table.
        with closing(sqlite3.connect(business_data.path_for(self.path))) as db, db:
            db.execute("DROP TABLE incident_notifications")
        for _ in range(3):
            with closing(business_data.connect(self.path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM incident_notifications").fetchone()[0], 0)
        self.assertTrue(self.send())

    def test_engine_dispatch_uses_durable_incident_identity(self):
        engine = Engine(self.path)
        engine.state.update(session="session-a", t=10)
        data = {"C": {"luggage": {"items": [{"id": "B0001", "alert": True,
                                              "duration": 10, "since": 0, "kind": "maleta"}]}}}
        engine.dispatch_alerts(data, {})
        engine.notifications.join()
        engine.dispatch_alerts(data, {})
        engine.notifications.join()
        restarted = Engine(self.path)
        restarted.state.update(session="session-a", t=10)
        restarted.dispatch_alerts(data, {})
        restarted.notifications.join()
        self.smtp.assert_called_once()
        row = restarted.notifications.get(self.path, "session-a:equipaje:C:B0001")
        self.assertEqual(row["status"], "sent")


    def test_shutdown_keeps_accepted_blocking_delivery_active_until_persisted(self):
        entered, release = threading.Event(), threading.Event()
        write = self.service._write_result
        result = []
        def delayed_write(identity, outcome):
            entered.set()
            if not release.wait(5):
                raise AssertionError("Synthetic writer was not released")
            return write(identity, outcome)
        with patch.object(self.service, "_write_result", side_effect=delayed_write):
            worker = threading.Thread(target=lambda: result.append(self.send()))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.service.stop_event.set()
                self.assertTrue(self.service.has_writers())
                self.assertFalse(self.service.join(timeout=0))
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [True])
        self.assertFalse(self.service.has_writers())
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["status"], "sent")
        self.smtp.assert_called_once()

    def test_accepted_delivery_retries_persistence_only_and_keeps_acceptance_time(self):
        write = self.service._write_result
        results = []
        def unavailable_once(identity, result):
            results.append(result)
            self.clock.time.return_value = 2000
            if len(results) == 1:
                raise sqlite3.OperationalError("synthetic disk busy")
            return write(identity, result)
        with patch.object(self.service, "_write_result", side_effect=unavailable_once):
            self.assertTrue(self.send())
        self.assertEqual(results, [("sent", 1000, None)] * 2)
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["sent_at"], 1000)
        self.smtp.assert_called_once()

    def test_persistence_outage_is_observable_and_later_recovery_never_resends(self):
        with patch.object(self.service, "_write_result", side_effect=sqlite3.OperationalError("disk")) as write:
            self.assertFalse(self.send())
            self.assertEqual(write.call_count, 3)
            self.assertEqual(self.service.diagnostics()["pending_results"], 1)
            self.assertEqual(self.service.diagnostics()["error"], "notification_result_persistence_failed")
            self.assertFalse(self.send())
        self.service.recover(self.path)
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["status"], "sent")
        self.assertEqual(self.service.diagnostics()["pending_results"], 0)
        self.smtp.assert_called_once()

    def test_restart_after_lost_confirmation_becomes_uncertain_not_failed(self):
        import incident_notifications as delivery
        with patch.object(self.service, "_write_result", side_effect=OSError("disk")):
            self.assertFalse(self.send())
        identity = self.service._identity(self.path, "session-a:bag:1", "original")
        # Simulate loss of volatile results on process exit; persisted claim remains.
        delivery.PENDING.pop(identity)
        restarted = IncidentNotifications(notifier.Mailer(self.root), process_id="boot-b")
        restarted.recover(self.path)
        self.assertFalse(self.send(service=restarted))
        row = restarted.get(self.path, "session-a:bag:1")
        self.assertEqual(row["status"], "uncertain")
        self.assertIsNone(row["sent_at"])
        self.smtp.assert_called_once()

    def test_async_accepted_delivery_keeps_pending_result_after_worker_exits(self):
        with patch.object(self.service, "_write_result", side_effect=OSError("disk")):
            self.service.send(self.path, "session-a:bag:1", "Test", "Test")
            self.service.join()
        self.service.recover(self.path)
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["status"], "sent")
        self.smtp.assert_called_once()

    def test_commit_acknowledgement_failure_does_not_repeat_delivery_or_change_timestamp(self):
        write = self.service._write_result
        calls = []
        def lost_ack(identity, result):
            write(identity, result)
            calls.append(result)
            if len(calls) == 1:
                raise sqlite3.OperationalError("commit acknowledgement lost")
        with patch.object(self.service, "_write_result", side_effect=lost_ack):
            self.assertTrue(self.send())
        self.assertEqual(len(calls), 2)
        self.smtp.assert_called_once()
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["attempts"], 1)

    def test_same_process_orphan_is_uncertain_but_live_claim_is_not_stolen(self):
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("INSERT INTO incident_notifications "
                       "(incident_id,notification_kind,status,attempted_at,owner) "
                       "VALUES (?,'original','attempting',1000,'boot-a')", ("session-a:bag:1",))
        self.service.recover(self.path)
        self.assertEqual(self.service.get(self.path, "session-a:bag:1")["status"], "uncertain")
        self.assertFalse(self.send())
        self.smtp.assert_not_called()

    def test_shutdown_does_not_claim_or_send_new_notification(self):
        self.service.stop_event.set()
        self.assertFalse(self.send())
        self.assertIsNone(self.service.get(self.path, "session-a:bag:1"))
        self.smtp.assert_not_called()

    def test_notification_join_uses_one_deadline_for_all_workers(self):
        first, second = Mock(), Mock()
        first.is_alive.return_value = second.is_alive.return_value = True
        self.service.workers = [first, second]
        with patch("incident_notifications.time.monotonic", side_effect=[10., 12., 15.]):
            self.assertFalse(self.service.join(timeout=5))
        first.join.assert_called_once_with(3.)
        second.join.assert_called_once_with(0.)


class SMTPOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.transport = self.enterContext(patch.object(notifier.smtplib, "SMTP_SSL"))
        self.server = self.transport.return_value.__enter__.return_value
        self.server.send_message.return_value = {}
        self.config = dict(user="sender@example.invalid", password="synthetic",
                           recipients=["recipient@example.invalid"], port=465)

    def test_login_failure_is_confirmed_not_accepted(self):
        self.server.login.side_effect = OSError("offline")
        with self.assertRaises(notifier.DeliveryError) as caught:
            notifier._send(self.config, "Test", "Test")
        self.assertFalse(caught.exception.uncertain)
        self.server.send_message.assert_not_called()

    def test_timeout_during_data_is_uncertain(self):
        self.server.send_message.side_effect = TimeoutError()
        with self.assertRaises(notifier.DeliveryError) as caught:
            notifier._send(self.config, "Test", "Test")
        self.assertTrue(caught.exception.uncertain)

    def test_partial_recipient_acceptance_is_uncertain(self):
        self.server.send_message.return_value = {"other@example.invalid": (550, b"refused")}
        with self.assertRaises(notifier.DeliveryError) as caught:
            notifier._send(self.config, "Test", "Test")
        self.assertTrue(caught.exception.uncertain)

    def test_quit_failure_does_not_undo_confirmed_acceptance(self):
        self.transport.return_value.__exit__.side_effect = OSError("quit failed")
        notifier._send(self.config, "Test", "Test")
        self.server.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
