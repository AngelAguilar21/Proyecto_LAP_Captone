"""Durable delivery identity. No message body, addresses or secrets are stored."""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing

import business_data
from notifier import DeliveryError


PROCESS_ID = uuid.uuid4().hex


class IncidentNotifications:
    def __init__(self, mailer, clock=time.time, process_id=PROCESS_ID):
        self.mailer = mailer
        self.clock = clock
        self.process_id = process_id
        self.workers = set()
        self.lock = threading.Lock()

    def recover(self, project_path):
        """Reconcile another process's attempts; never steal a live local claim."""
        with closing(business_data.connect(project_path)) as db, db:
            db.execute("UPDATE incident_notifications SET status='uncertain', "
                       "last_error='process_interrupted' "
                       "WHERE status='attempting' AND owner<>?", (self.process_id,))

    def get(self, project_path, incident_id, kind="original"):
        with closing(business_data.connect(project_path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM incident_notifications "
                             "WHERE incident_id=? AND notification_kind=?",
                             (incident_id, kind)).fetchone()
            return dict(row) if row else None

    def send(self, project_path, incident_id, subject, body, kind="original", blocking=False,
             recipients=None, escalation_due_before=None):
        if kind not in ("original", "escalation"):
            raise ValueError("Unknown notification kind")
        mail_options = {"recipients": recipients} if recipients is not None else {}
        if not self.mailer.ready(**mail_options):
            return False
        self.recover(project_path)
        with closing(business_data.connect(project_path)) as db, db:
            # Selection can become stale while a human reviews an incident.
            # Serialize eligibility and the durable claim, then release SQLite
            # before SMTP. A delivery already claimed may finish during review.
            db.execute("BEGIN IMMEDIATE")
            if escalation_due_before is not None:
                if kind != "escalation":
                    raise ValueError("Eligibility cutoff is only valid for escalation")
                eligible = db.execute(
                    "SELECT 1 FROM incidentes WHERE id=? AND estado='pendiente' "
                    "AND review_history_known=1 AND reviewed_at IS NULL AND creado<=?",
                    (incident_id, escalation_due_before)).fetchone()
                if not eligible:
                    return False
            cursor = db.execute(
                "INSERT INTO incident_notifications "
                "(incident_id,notification_kind,status,attempted_at,owner) "
                "VALUES (?,?,'attempting',?,?) "
                "ON CONFLICT(incident_id,notification_kind) DO UPDATE SET "
                "status='attempting',attempts=attempts+1,attempted_at=excluded.attempted_at,"
                "last_error=NULL,owner=excluded.owner "
                "WHERE incident_notifications.status='failed'",
                (incident_id, kind, self.clock(), self.process_id))
            claimed = cursor.rowcount == 1
        if not claimed:
            return False

        def deliver():
            status, reason = "failed", "not_sent"
            try:
                key = json.dumps([str(project_path), incident_id, kind])
                if self.mailer.send(subject, body, key=key, blocking=True, **mail_options):
                    status, reason = "sent", None
            except DeliveryError as exc:
                status = "uncertain" if exc.uncertain else "failed"
                reason = str(exc)
            except Exception:
                status, reason = "uncertain", "delivery_exception"
            try:
                with closing(business_data.connect(project_path)) as db, db:
                    db.execute("UPDATE incident_notifications SET status=?,sent_at=?,last_error=? "
                               "WHERE incident_id=? AND notification_kind=? AND status='attempting' AND owner=?",
                               (status, self.clock() if status == "sent" else None, reason,
                                incident_id, kind, self.process_id))
            finally:
                with self.lock:
                    self.workers.discard(threading.current_thread())
            return status == "sent"

        if blocking:
            return deliver()
        worker = threading.Thread(target=deliver, name="incident-mail", daemon=True)
        with self.lock:
            self.workers.add(worker)
        try:
            worker.start()
        except Exception:
            with self.lock:
                self.workers.discard(worker)
            # No SMTP was started. Leave a safe, auditable failed attempt.
            with closing(business_data.connect(project_path)) as db, db:
                db.execute("UPDATE incident_notifications SET status='failed',last_error='worker_start_failed' "
                           "WHERE incident_id=? AND notification_kind=? AND status='attempting' AND owner=?",
                           (incident_id, kind, self.process_id))
            raise
        return True

    def join(self):
        with self.lock:
            workers = list(self.workers)
        for worker in workers:
            worker.join()
