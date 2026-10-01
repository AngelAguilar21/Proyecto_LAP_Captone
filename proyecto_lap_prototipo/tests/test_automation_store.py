import sys
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
        self.assertEqual(tables, {"executions", "audit"})

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
