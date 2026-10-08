import sys
import sqlite3
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from automation_store import AutomationStore


class AutomationStoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "config" / "automation.sqlite"
        self.store = AutomationStore(self.path)
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_constructor_is_lazy_and_schema_separate(self):
        self.assertFalse(self.path.exists())
        with self.store.connect() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"executions", "audit", "artifact_health"})

    def test_repeated_initialization_preserves_history_and_additive_columns(self):
        self.store.record("reports", "p", "2026-01-01", "running", self.now)
        self.store.finish("reports", "p", "2026-01-01", "succeeded", self.now)
        with self.store.connect() as db:
            db.execute("ALTER TABLE executions ADD COLUMN future_field TEXT DEFAULT 'preserved'")
        reopened = AutomationStore(self.path)
        reopened.record("reports", "p", "2026-01-01", "running", self.now)
        row = reopened.get("reports", "p", "2026-01-01")
        self.assertEqual((row["attempts"], row["future_field"]), (2, "preserved"))
        with reopened.connect() as db:
            self.assertEqual(db.execute("SELECT detail FROM audit").fetchall(), [("succeeded",)])

    def test_transaction_failure_rolls_back_and_connection_closes(self):
        with self.assertRaises(RuntimeError):
            with self.store.connect() as db:
                db.execute("INSERT INTO audit VALUES (1,0,'reports','synthetic')")
                raise RuntimeError("synthetic")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)
        self.path.unlink()  # Windows also detects a leaked SQLite handle here.

    def test_phase_three_database_migrates_additively_and_idempotently(self):
        self.path.parent.mkdir()
        db = sqlite3.connect(self.path)
        try:
            db.execute("CREATE TABLE executions (task TEXT,scope TEXT,date TEXT,status TEXT NOT NULL,"
                       "attempted_at REAL NOT NULL,attempts INTEGER NOT NULL,artifact TEXT,error TEXT,"
                       "PRIMARY KEY(task,scope,date))")
            db.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY,at REAL NOT NULL,task TEXT NOT NULL,detail TEXT NOT NULL)")
            db.execute("INSERT INTO executions VALUES ('reports','p','2026-01-01','succeeded',1,2,'legacy.pdf',NULL)")
            db.execute("INSERT INTO audit VALUES (1,1,'reports','legacy')")
            db.commit()
        finally:
            db.close()
        for _ in range(2):
            reopened = AutomationStore(self.path)
            self.assertEqual(reopened.get("reports", "p", "2026-01-01")["attempts"], 2)
            self.assertIsNone(reopened.health("reports", "p", "2026-01-01"))
            with reopened.connect() as db:
                self.assertEqual(db.execute("SELECT * FROM audit").fetchall(), [(1, 1, "reports", "legacy")])

    def test_publication_rolls_back_history_fingerprint_and_audit_together(self):
        key = ("reports", "p", "2026-01-01")
        self.store.record(*key, "running", self.now)
        before = self.store.get(*key)
        with self.assertRaises(RuntimeError), self.store.publication() as db:
            self.store.publish_success(db, *key, self.now, "synthetic.pdf", ("abc", 42))
            raise RuntimeError("synthetic failure before commit")
        self.assertEqual(self.store.get(*key), before)
        self.assertIsNone(self.store.health(*key))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)

    def test_success_and_fingerprint_cannot_be_replaced_by_late_report_attempt(self):
        key = ("reports", "p", "2026-01-01")
        with self.store.publication() as db:
            self.assertTrue(self.store.publish_success(db, *key, self.now, "first.pdf", ("abc", 42)))
        before, health = self.store.get(*key), self.store.health(*key)
        self.store.record(*key, "failed", self.now, error="late failure", preserve_success=True)
        with self.store.publication() as db:
            self.assertFalse(self.store.publish_success(db, *key, self.now, "second.pdf", ("def", 99)))
        self.assertEqual(self.store.get(*key), before)
        self.assertEqual(self.store.health(*key), health)

    def test_health_changes_preserve_success_and_fingerprint_and_audit_only_transitions(self):
        key = ("reports", "p", "2026-01-01")
        with self.store.publication() as db:
            self.store.publish_success(db, *key, self.now, "synthetic.pdf", ("abc", 42))
        before = self.store.get(*key)
        for status in ("healthy", "missing", "missing", "corrupt", "healthy"):
            self.store.set_health(*key, status, self.now)
            health = self.store.health(*key)
            self.assertEqual((health["sha256"], health["size"]), ("abc", 42))
            self.assertEqual(self.store.get(*key), before)
        with self.store.connect() as db:
            rows = [json.loads(r[0]) for r in db.execute("SELECT detail FROM audit ORDER BY id")]
        self.assertEqual([r["artifact_health"] for r in rows if "artifact_health" in r], ["missing", "corrupt", "healthy"])
