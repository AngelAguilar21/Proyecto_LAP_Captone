import json
import hashlib
import sqlite3
import sys
import tempfile
import threading
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from automation import LIMA
from automation_backups import ProjectBackups, verify_backup
from automation_store import AutomationStore


class BackupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        (self.projects / "index.json").write_text(json.dumps({"active": "p-test", "projects": [{"id": "p-test"}]}))
        (self.projects / "p-test.json").write_text('{"airport":"Synthetic"}')
        self.engine = SimpleNamespace(settings_root=self.root, lock=threading.RLock())
        self.store = AutomationStore(self.root / "automation.sqlite")
        self.task = ProjectBackups(self.engine, self.store)
        self.now = datetime(2026, 9, 25, 2, tzinfo=LIMA)
        self.settings = {"time": "02:00", "retention": 2}

    def target(self, now=None):
        return self.root / "backups" / f"projects-{(now or self.now).date()}.zip"

    def test_before_time_has_no_archive(self):
        self.assertEqual(self.task(self.now - timedelta(seconds=1), self.settings), "not_due")
        self.assertFalse(self.target().exists())

    def test_json_index_and_open_wal_database_are_restorable(self):
        path = self.projects / "p-test.negocios.sqlite"
        with closing(sqlite3.connect(path)) as live:
            live.execute("PRAGMA journal_mode=WAL")
            live.execute("CREATE TABLE sample (value TEXT)")
            live.execute("INSERT INTO sample VALUES ('synthetic')")
            live.commit()
            self.assertEqual(self.task(self.now, self.settings), "succeeded")
        self.assertTrue(verify_backup(self.target()))
        with zipfile.ZipFile(self.target()) as archive:
            self.assertEqual(json.loads(archive.read("projects/index.json"))["active"], "p-test")
            self.assertEqual(json.loads(archive.read("projects/p-test.json"))["airport"], "Synthetic")
            self.assertFalse(any(n.endswith(("-wal", "-shm", "-journal")) for n in archive.namelist()))
            restored = self.root / "restored.sqlite"
            restored.write_bytes(archive.read("projects/p-test.negocios.sqlite"))
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "synthetic")

    def test_restart_and_repeated_tick_do_not_duplicate(self):
        self.task(self.now, self.settings)
        before = self.target().read_bytes()
        restarted = ProjectBackups(self.engine, AutomationStore(self.store.path))
        self.assertEqual(restarted(self.now, self.settings), "already_done")
        self.assertEqual(self.target().read_bytes(), before)

    def test_retention_only_removes_verified_final_archives(self):
        self.task(self.now, self.settings)
        bad = self.root / "backups" / "projects-2000-01-01.zip"
        bad.write_bytes(b"not a zip")
        partial = self.root / "backups" / "projects-2000-01-02.zip.tmp"
        partial.write_bytes(b"partial")
        self.task(self.now + timedelta(days=1), self.settings)
        self.task(self.now + timedelta(days=2), self.settings)
        self.assertFalse(self.target().exists())
        self.assertTrue(bad.exists())
        self.assertTrue(partial.exists())
        self.assertTrue(self.target(self.now + timedelta(days=1)).exists())
        self.assertTrue(self.target(self.now + timedelta(days=2)).exists())

    def test_failed_zip_verification_never_publishes(self):
        with patch("automation_backups.verify_backup", return_value=False):
            with self.assertRaises(ValueError):
                self.task(self.now, self.settings)
        self.assertFalse(self.target().exists())
        self.assertEqual(list((self.root / "backups").iterdir()), [])

    def test_missing_index_member_fails_before_publication(self):
        (self.projects / "p-test.json").unlink()
        with self.assertRaises(ValueError):
            self.task(self.now, self.settings)
        self.assertFalse(self.target().exists())

    def test_json_cut_holds_lock_but_zip_does_not(self):
        class Lock:
            held = False
            def __enter__(lock): lock.held = True
            def __exit__(lock, *args): lock.held = False
        self.engine.lock = Lock()
        original = zipfile.ZipFile
        def archive(*args, **kwargs):
            self.assertFalse(self.engine.lock.held)
            return original(*args, **kwargs)
        with patch("automation_backups.zipfile.ZipFile", side_effect=archive):
            self.task(self.now, self.settings)
        self.assertTrue(self.target().exists())

    def test_crash_after_publication_is_reconciled(self):
        with patch.object(self.store, "record", side_effect=OSError()):
            with self.assertRaises(OSError):
                self.task(self.now, self.settings)
        self.assertEqual(self.task(self.now, self.settings), "recovered")

    def test_cancel_during_archive_creation_never_publishes(self):
        from task_control import budget, Cancelled
        event = threading.Event()
        write = zipfile.ZipFile.writestr
        def cancelled(archive, *args, **kwargs):
            result = write(archive, *args, **kwargs)
            event.set()
            return result
        with budget(event, 60), patch.object(zipfile.ZipFile, "writestr", cancelled):
            with self.assertRaises(Cancelled):
                self.task(self.now, self.settings)
        self.assertFalse(self.target().exists())

    def test_missing_successful_backup_keeps_history_without_recreation(self):
        self.task(self.now, self.settings)
        before = self.store.get("backups", "projects", "2026-09-25")
        self.target().unlink()
        with patch.object(self.task, "capture", side_effect=AssertionError("No regeneration")):
            self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.store.get("backups", "projects", "2026-09-25"), before)
        self.assertEqual(self.store.health("backups", "projects", "2026-09-25")["status"], "missing")
        self.assertFalse(self.target().exists())

    def test_corrupt_successful_backup_is_not_overwritten(self):
        self.task(self.now, self.settings)
        self.target().write_bytes(b"broken zip")
        self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.store.health("backups", "projects", "2026-09-25")["status"], "corrupt")
        self.assertEqual(self.target().read_bytes(), b"broken zip")

    def test_valid_replacement_zip_is_detected_even_with_matching_internal_hashes(self):
        self.task(self.now, self.settings)
        with zipfile.ZipFile(self.target()) as original:
            entries = {name: original.read(name) for name in original.namelist()}
        entries["projects/p-test.json"] = b'{"airport":"Replaced"}'
        manifest = json.loads(entries["backup-manifest.json"])
        manifest["sha256"]["projects/p-test.json"] = hashlib.sha256(entries["projects/p-test.json"]).hexdigest()
        entries["backup-manifest.json"] = json.dumps(manifest).encode()
        with zipfile.ZipFile(self.target(), "w") as modified:
            for name, data in entries.items():
                modified.writestr(name, data)
        self.assertTrue(verify_backup(self.target()))
        self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.store.health("backups", "projects", "2026-09-25")["error"], "fingerprint_mismatch")

    def test_retention_is_distinguished_from_unexpected_loss_and_keeps_history(self):
        self.settings["retention"] = 1
        self.task(self.now, self.settings)
        original = self.store.get("backups", "projects", "2026-09-25")
        self.task(self.now + timedelta(days=1), self.settings)
        self.task(self.now + timedelta(days=1), self.settings)
        self.assertEqual(self.store.health("backups", "projects", "2026-09-25")["status"], "retired")
        self.assertEqual(self.store.get("backups", "projects", "2026-09-25"), original)

    def test_old_corruption_is_detected_and_preserved_on_next_day(self):
        self.task(self.now, self.settings)
        self.target().write_bytes(b"broken zip")
        self.settings["retention"] = 1
        self.task(self.now + timedelta(days=1), self.settings)
        self.assertEqual(self.store.health("backups", "projects", "2026-09-25")["status"], "corrupt")
        self.assertTrue(self.target().exists())

    def test_interrupted_retention_reconciles_expected_missing_file(self):
        self.task(self.now, self.settings)
        self.store.set_health("backups", "projects", "2026-09-25", "retention_pending", self.now, "retention")
        self.target().unlink()
        self.assertEqual(self.task(self.now, self.settings), "artifact_problem")
        self.assertEqual(self.store.health("backups", "projects", "2026-09-25")["status"], "retired")


if __name__ == "__main__":
    unittest.main()
