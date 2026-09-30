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
# Shared by service instances in this process, including synchronous deliveries.
# Values contain delivery facts only, never recipients, message bodies or secrets.
ATTEMPT_LOCK = threading.RLock()
ACTIVE = set()
PENDING = {}


class IncidentNotifications:
    def __init__(self, mailer, clock=time.time, process_id=PROCESS_ID):
        self.mailer = mailer
        self.clock = clock
        self.process_id = process_id
        self.workers = set()
        self.lock = threading.Lock()
        self.error = None
        self.stop_event = threading.Event()

    def _identity(self, path, incident_id, kind):
        return (self.process_id, str(business_data.path_for(path).resolve()), incident_id, kind)

    def _write_result(self, identity, result):
        owner, path, iid, kind = identity
        status, sent_at, reason = result
        # The claim already created/migrated this database. Do not create a new
        # database after a storage loss, or hold migrations during retries.
        from pathlib import Path
        with closing(sqlite3.connect(Path(path).as_uri() + "?mode=rw", uri=True, timeout=0.2)) as db, db:
            cursor = db.execute("UPDATE incident_notifications SET status=?,sent_at=?,last_error=? "
                "WHERE incident_id=? AND notification_kind=? AND status='attempting' AND owner=?",
                (status, sent_at, reason, iid, kind, owner))
            if cursor.rowcount != 1:
                row = db.execute("SELECT status,sent_at,last_error FROM incident_notifications "
                                 "WHERE incident_id=? AND notification_kind=? AND owner=?", (iid, kind, owner)).fetchone()
                if row != result:
                    raise sqlite3.DatabaseError("Delivery claim no longer matches")

    def _persist(self, identity, result):
        for _ in range(3):
            try:
                self._write_result(identity, result)
                self.error = None
                return True
            except (sqlite3.Error, OSError):
                self.error = "notification_result_persistence_failed"
        return False

    def _finish(self, identity, result):
        with ATTEMPT_LOCK:
            PENDING[identity] = result
            try:
                persisted = self._persist(identity, result)
                if persisted:
                    PENDING.pop(identity, None)
                return persisted
            finally:
                # Synchronous accepted deliveries are writers until persistence
                # finishes, even when cancellation has already been requested.
                ACTIVE.discard(identity)

    def recover(self, project_path):
        """Persist known outcomes; orphaned claims become uncertain, never resent."""
        path = str(business_data.path_for(project_path).resolve())
        with ATTEMPT_LOCK:
            for identity, result in list(PENDING.items()):
                if identity[:2] == (self.process_id, path) and self._persist(identity, result):
                    PENDING.pop(identity, None)
            with closing(business_data.connect(project_path)) as db, db:
                for iid, kind, owner in db.execute("SELECT incident_id,notification_kind,owner "
                                                   "FROM incident_notifications WHERE status='attempting'").fetchall():
                    identity = (owner, path, iid, kind)
                    if owner == self.process_id and (identity in ACTIVE or identity in PENDING):
                        continue
                    db.execute("UPDATE incident_notifications SET status='uncertain',sent_at=NULL, "
                               "last_error='process_interrupted' WHERE incident_id=? AND notification_kind=? "
                               "AND status='attempting'", (iid, kind))

    def diagnostics(self):
        with ATTEMPT_LOCK:
            return {"error": self.error, "pending_results": sum(k[0] == self.process_id for k in PENDING)}

    def get(self, project_path, incident_id, kind="original"):
        with closing(business_data.connect(project_path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM incident_notifications "
                             "WHERE incident_id=? AND notification_kind=?",
                             (incident_id, kind)).fetchone()
            return dict(row) if row else None

    def send(self, project_path, incident_id, subject, body, kind="original", blocking=False,
             recipients=None):
        if self.stop_event.is_set():
            return False
        if kind not in ("original", "escalation"):
            raise ValueError("Unknown notification kind")
        mail_options = {"recipients": recipients} if recipients is not None else {}
        if not self.mailer.ready(**mail_options):
            return False
        identity = self._identity(project_path, incident_id, kind)
        with ATTEMPT_LOCK:
            if self.stop_event.is_set():
                return False
            self.recover(project_path)
            claimed = self._claim(project_path, incident_id, kind)
            if claimed:
                ACTIVE.add(identity)
        if not claimed:
            return False

        def deliver():
            status, reason = "failed", "not_sent"
            accepted_at = None
            try:
                key = json.dumps([str(project_path), incident_id, kind])
                if self.stop_event.is_set():
                    reason = "cancelled_before_smtp"
                elif self.mailer.send(subject, body, key=key, blocking=True, **mail_options):
                    status, reason = "sent", None
                    accepted_at = self.clock()
            except DeliveryError as exc:
                status = "uncertain" if exc.uncertain else "failed"
                reason = str(exc)
            except Exception:
                status, reason = "uncertain", "delivery_exception"
            try:
                persisted = self._finish(identity, (status, accepted_at, reason))
            finally:
                with self.lock:
                    self.workers.discard(threading.current_thread())
            return persisted and status == "sent"

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
            self._finish(identity, ("failed", None, "worker_start_failed"))
            raise
        return True

    def _claim(self, project_path, incident_id, kind):
        # SQLite serializes claims; Python locks alone are not the durable guard.
        with closing(business_data.connect(project_path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "INSERT INTO incident_notifications "
                "(incident_id,notification_kind,status,attempted_at,owner) "
                "VALUES (?,?,'attempting',?,?) "
                "ON CONFLICT(incident_id,notification_kind) DO UPDATE SET "
                "status='attempting',attempts=attempts+1,attempted_at=excluded.attempted_at,"
                "last_error=NULL,owner=excluded.owner "
                "WHERE incident_notifications.status='failed'",
                (incident_id, kind, self.clock(), self.process_id))
            return cursor.rowcount == 1

    def has_writers(self):
        # Snapshot without waiting behind a database write during bounded shutdown.
        return any(k[0] == self.process_id for k in tuple(ACTIVE)) or any(w.is_alive() for w in tuple(self.workers))

    def join(self, timeout=30):
        deadline = time.monotonic() + max(0, timeout)
        with self.lock:
            workers = list(self.workers)
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        return not self.has_writers()
