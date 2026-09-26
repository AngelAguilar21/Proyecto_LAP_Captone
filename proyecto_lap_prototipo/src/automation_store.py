"""Durable execution outcomes, separate from preferences and mail secrets."""
import sqlite3
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

    def record(self, task, scope, date, status, now, artifact=None, error=None):
        with self.connect() as db:
            db.execute("INSERT INTO executions VALUES (?,?,?,?,?,1,?,?) "
                       "ON CONFLICT(task,scope,date) DO UPDATE SET status=excluded.status,"
                       "attempted_at=excluded.attempted_at,attempts=attempts+1,"
                       "artifact=excluded.artifact,error=excluded.error",
                       (task, scope, date, status, now.timestamp(), artifact, error))

    def audit(self, task, detail, now):
        with self.connect() as db:
            db.execute("INSERT INTO audit(at,task,detail) VALUES (?,?,?)",
                       (now.timestamp(), task, detail))
