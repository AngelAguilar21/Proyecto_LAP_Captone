"""Durable execution outcomes, separate from preferences and mail secrets."""
import sqlite3
import json
from contextlib import contextmanager


class AutomationStore:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS executions (task TEXT, scope TEXT, date TEXT, "
                       "status TEXT NOT NULL, attempted_at REAL NOT NULL, attempts INTEGER NOT NULL, "
                       "artifact TEXT, error TEXT, PRIMARY KEY(task,scope,date))")
            db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, "
                       "at REAL NOT NULL, task TEXT NOT NULL, detail TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS artifact_health (task TEXT,scope TEXT,date TEXT,"
                       "sha256 TEXT,size INTEGER,status TEXT NOT NULL,checked_at REAL NOT NULL,error TEXT,"
                       "PRIMARY KEY(task,scope,date))")
            with db:
                yield db
        finally:
            db.close()

    def get(self, task, scope, date):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM executions WHERE task=? AND scope=? AND date=?",
                             (task, scope, date)).fetchone()
            return dict(row) if row else None

    def record(self, task, scope, date, status, now, artifact=None, error=None, fingerprint=None):
        with self.connect() as db:
            db.execute("INSERT INTO executions VALUES (?,?,?,?,?,1,?,?) "
                       "ON CONFLICT(task,scope,date) DO UPDATE SET status=excluded.status,"
                       "attempted_at=excluded.attempted_at,attempts=attempts+1,"
                       "artifact=excluded.artifact,error=excluded.error",
                       (task, scope, date, status, now.timestamp(), artifact, error))
            if fingerprint is not None:
                db.execute("INSERT INTO artifact_health VALUES (?,?,?,?,?,'healthy',?,NULL) "
                           "ON CONFLICT(task,scope,date) DO UPDATE SET sha256=excluded.sha256,size=excluded.size,"
                           "status='healthy',checked_at=excluded.checked_at,error=NULL",
                           (task, scope, date, *fingerprint, now.timestamp()))

    def successes(self, task):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM executions WHERE task=? AND status='succeeded'",
                                                   (task,))]

    def health(self, task, scope, date):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM artifact_health WHERE task=? AND scope=? AND date=?",
                             (task, scope, date)).fetchone()
            return dict(row) if row else None

    def set_health(self, task, scope, date, status, now, error=None):
        # Preserve both original success and its original fingerprint. Missing
        # fingerprints are never invented from potentially replaced legacy files.
        with self.connect() as db:
            prior = db.execute("SELECT status,error FROM artifact_health WHERE task=? AND scope=? AND date=?",
                               (task, scope, date)).fetchone()
            db.execute("INSERT INTO artifact_health VALUES (?,?,?,NULL,NULL,?,?,?) "
                       "ON CONFLICT(task,scope,date) DO UPDATE SET status=excluded.status,"
                       "checked_at=excluded.checked_at,error=excluded.error",
                       (task, scope, date, status, now.timestamp(), error))
            if prior != (status, error):
                db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)", (now.timestamp(), task,
                    json.dumps(dict(scope=scope, date=date, artifact_health=status, reason=error))))

    def audit(self, task, detail, now):
        with self.connect() as db:
            db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)",
                       (now.timestamp(), task, detail))
