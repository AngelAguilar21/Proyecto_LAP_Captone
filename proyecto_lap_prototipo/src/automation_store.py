"""Execution metadata only, in a separate SQLite database; connections are scoped."""
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path


class AutomationStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=.2)
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

    def get(self, task, scope, date, connection=None):
        if connection is None:
            with self.connect() as db:
                return self.get(task, scope, date, connection=db)
        else:
            db = connection
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM executions WHERE task=? AND scope=? AND date=?",
                             (task, scope, date)).fetchone()
            return dict(row) if row else None

    def record(self, task, scope, date, status, now, artifact=None, error=None, preserve_success=False):
        with self.connect() as db:
            cursor = db.execute("INSERT INTO executions(task,scope,date,status,attempted_at,attempts,artifact,error) "
                       "VALUES (?,?,?,?,?,1,?,?) "
                       "ON CONFLICT(task,scope,date) DO UPDATE SET status=excluded.status,"
                       "attempted_at=excluded.attempted_at,attempts=attempts+1,"
                       "artifact=excluded.artifact,error=excluded.error " +
                       ("WHERE executions.status!='succeeded'" if preserve_success else ""),
                       (task, scope, date, status, now.timestamp(), artifact, error))
            if preserve_success and cursor.rowcount:
                db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)", (now.timestamp(), task,
                           json.dumps(dict(scope=scope, date=date, status=status, reason=error))))

    def finish(self, task, scope, date, status, now, error=None):
        with self.connect() as db:
            db.execute("UPDATE executions SET status=?,error=? WHERE task=? AND scope=? AND date=?",
                       (status, error, task, scope, date))
            db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)", (now.timestamp(), task, status))

    def audit(self, task, detail, now):
        with self.connect() as db:
            db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)", (now.timestamp(), task, detail))

    @contextmanager
    def publication(self):
        """Serialize final-file reconciliation/publication for a shared database."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def publish_success(self, db, task, scope, date, now, artifact, fingerprint):
        """Called inside publication(): history and its fingerprint commit together."""
        cursor = db.execute("INSERT INTO executions(task,scope,date,status,attempted_at,attempts,artifact,error) "
            "VALUES (?,?,?,'succeeded',?,1,?,NULL) ON CONFLICT(task,scope,date) DO UPDATE SET "
            "status='succeeded',artifact=excluded.artifact,error=NULL WHERE executions.status!='succeeded'",
            (task, scope, date, now.timestamp(), artifact))
        if not cursor.rowcount:
            return False
        db.execute("INSERT INTO artifact_health(task,scope,date,sha256,size,status,checked_at,error) "
            "VALUES (?,?,?,?,?,'healthy',?,NULL) ON CONFLICT(task,scope,date) DO UPDATE SET "
            "sha256=excluded.sha256,size=excluded.size,status='healthy',checked_at=excluded.checked_at,error=NULL",
            (task, scope, date, *fingerprint, now.timestamp()))
        db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)", (now.timestamp(), task,
                   json.dumps(dict(scope=scope, date=date, status="succeeded"))))
        return True

    def successes(self, task):
        # Close each read connection before health writes; don't retain a SQLite
        # reader lock over validation, and don't load the entire history at once.
        from task_control import checkpoint
        offset = 0
        while True:
            checkpoint()
            with self.connect() as db:
                db.row_factory = sqlite3.Row
                rows = [dict(r) for r in db.execute("SELECT * FROM executions WHERE task=? AND status='succeeded' "
                        "ORDER BY scope,date LIMIT 128 OFFSET ?", (task, offset))]
            yield from rows
            if len(rows) < 128:
                return
            offset += len(rows)

    def health(self, task, scope, date):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM artifact_health WHERE task=? AND scope=? AND date=?",
                             (task, scope, date)).fetchone()
            return dict(row) if row else None

    def set_health(self, task, scope, date, status, now, error=None):
        # Never derive a missing historical fingerprint from today's file.
        with self.connect() as db:
            prior = db.execute("SELECT status,error FROM artifact_health WHERE task=? AND scope=? AND date=?",
                               (task, scope, date)).fetchone()
            db.execute("INSERT INTO artifact_health(task,scope,date,sha256,size,status,checked_at,error) "
                "VALUES (?,?,?,NULL,NULL,?,?,?) ON CONFLICT(task,scope,date) DO UPDATE SET "
                "status=excluded.status,checked_at=excluded.checked_at,error=excluded.error",
                (task, scope, date, status, now.timestamp(), error))
            if prior != (status, error):
                db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)", (now.timestamp(), task,
                    json.dumps(dict(scope=scope, date=date, artifact_health=status, reason=error))))
