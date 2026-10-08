"""Project backups and retention use only synthetic data in temporary roots."""
import io
import json
import os
import sqlite3
import stat
import sys
import tempfile
import threading
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from automation import AutomationService, LIMA
from automation_artifacts import fingerprint
from automation_backups import ProjectBackups, InvalidBackup, sqlite_snapshot
from automation_backup_format import MANIFEST, verify_backup_bytes, write_archive
from automation_store import AutomationStore
from resource_control import ResourceRegistry
from task_control import budget, Cancelled
import automation_settings
import business_data
import commercial


class ProjectBackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "config"
        self.projects = self.config / "projects"
        self.projects.mkdir(parents=True)
        self.index = self.projects / "index.json"
        self.project = self.projects / "p-test.json"
        self.index.write_text(json.dumps({"active": "p-test", "projects": [{"id": "p-test", "name": "Synthetic"}]}))
        self.project.write_text('{"airport":"Synthetic", "cameras":[]}')
        self.resources = ResourceRegistry(self.root)
        self.engine = SimpleNamespace(settings_root=self.config, lock=threading.RLock(), resources=self.resources,
                                      resource_use=self.resources.use)
        self.store = AutomationStore(self.config / "automation.sqlite")
        self.task = ProjectBackups(self.engine, self.store)
        self.now = datetime(2026, 10, 1, 2, tzinfo=LIMA)
        self.settings = {"enabled": True, "time": "02:00", "retention": 7}

    def target(self, day=0):
        return self.task.root / f"projects-{(self.now + timedelta(days=day)).date()}.zip"

    def row(self, day=0):
        return self.store.get("backups", "projects", (self.now + timedelta(days=day)).date().isoformat())

    def health(self, day=0):
        return self.store.health("backups", "projects", (self.now + timedelta(days=day)).date().isoformat())

    def run_day(self, day=0, count=7):
        return self.task(self.now + timedelta(days=day), {**self.settings, "retention": count})

    def active_database(self):
        db = sqlite3.connect(business_data.path_for(self.project))
        self.addCleanup(db.close)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE sample(value TEXT)")
        db.execute("INSERT INTO sample VALUES ('committed synthetic')")
        db.commit()
        return db

    def test_disabled_does_not_capture_or_create_files(self):
        with patch.object(self.task, "capture") as capture:
            self.assertEqual(self.task(self.now, {**self.settings, "enabled": False}), "disabled")
        capture.assert_not_called()
        self.assertFalse(self.task.root.exists())
        self.assertFalse(self.store.path.exists())

    def test_absent_configuration_keeps_injected_task_inert(self):
        service = AutomationService(self.engine, {"backups": self.task})
        self.assertEqual(service.run_due_tasks(self.now), {})
        self.assertFalse(self.task.root.exists())
        self.assertFalse(self.store.path.exists())

    def test_before_time_is_not_due(self):
        self.assertEqual(self.task(self.now - timedelta(seconds=1), self.settings), "not_due")
        self.assertFalse(self.task.root.exists())

    def test_schedule_uses_lima_and_rejects_naive_time(self):
        self.assertEqual(self.task(datetime(2026, 10, 2, 1, tzinfo=timezone.utc), self.settings), "succeeded")
        self.assertTrue(self.target().exists())
        self.assertFalse(self.target(1).exists())
        with self.assertRaises(ValueError):
            self.task(self.now.replace(tzinfo=None), self.settings)

    def test_published_backup_has_manifest_exact_members_hashes_and_fingerprint(self):
        self.assertEqual(self.run_day(), "succeeded")
        data = self.target().read_bytes()
        self.assertTrue(verify_backup_bytes(data, "2026-10-01"))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read(MANIFEST))
            self.assertEqual(manifest["scope"], "projects")
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(set(archive.namelist()), {MANIFEST, "projects/index.json", "projects/p-test.json"})
            self.assertEqual(manifest["files"], sorted(manifest["sha256"]))
            for name, digest in manifest["sha256"].items():
                self.assertEqual(fingerprint(archive.read(name))[0], digest)
        self.assertEqual(self.row()["status"], "succeeded")
        self.assertEqual(self.health()["status"], "healthy")
        self.assertEqual((self.health()["sha256"], self.health()["size"]), fingerprint(data))

    def test_repeated_ticks_and_restarted_service_do_not_duplicate(self):
        self.run_day()
        before, data, modified = self.row(), self.target().read_bytes(), self.target().stat().st_mtime_ns
        restarted = ProjectBackups(self.engine, AutomationStore(self.store.path))
        with patch.object(restarted, "capture", side_effect=AssertionError("unexpected regeneration")):
            for minutes in (1, 2, 60):
                self.assertEqual(restarted(self.now + timedelta(minutes=minutes), self.settings), "already_done")
        self.assertEqual(self.target().read_bytes(), data)
        self.assertEqual(self.target().stat().st_mtime_ns, modified)
        self.assertEqual(self.row(), before)

    def test_new_day_publishes_independent_backup(self):
        self.run_day()
        self.assertEqual(self.run_day(1), "succeeded")
        self.assertEqual(len(list(self.task.root.glob("*.zip"))), 2)
        self.assertTrue(verify_backup_bytes(self.target(1).read_bytes(), "2026-10-02"))

    def test_no_projects_records_no_data_and_can_retry(self):
        original = self.project.read_bytes()
        self.project.unlink()
        self.index.write_text('{"active":null,"projects":[]}')
        self.assertEqual(self.run_day(), "no_data")
        self.assertEqual(self.row()["status"], "no_data")
        self.assertFalse(self.target().exists())
        self.index.write_text('{"active":"p-test","projects":[{"id":"p-test"}]}')
        self.project.write_bytes(original)
        self.assertEqual(self.run_day(), "succeeded")

    def test_missing_project_tree_records_no_data(self):
        self.project.unlink()
        self.index.unlink()
        self.projects.rmdir()
        self.assertEqual(self.run_day(), "no_data")
        self.assertFalse(self.target().exists())

    def test_invalid_index_does_not_publish(self):
        for value in ('invalid', '[]', '{"projects":[]}',
                      '{"active":"absent","projects":[{"id":"p-test"}]}',
                      '{"active":"p-test","projects":[{"id":"p-test"},{"id":"p-test"}]}'):
            with self.subTest(value=value):
                self.index.write_text(value)
                with self.assertRaises(ValueError):
                    self.run_day()
                self.assertFalse(self.target().exists())

    def test_missing_indexed_config_does_not_publish(self):
        self.project.unlink()
        with self.assertRaises(ValueError):
            self.run_day()
        self.assertFalse(self.target().exists())

    def test_invalid_project_json_does_not_publish(self):
        for value in ('{', '[]', '{"x":NaN}', '{"x":1,"x":2}'):
            with self.subTest(value=value):
                self.project.write_text(value)
                with self.assertRaises(ValueError):
                    self.run_day()
                self.assertFalse(self.target().exists())

    def test_unknown_project_store_fails_closed_without_expanding_scope(self):
        (self.projects / "unknown.db").write_bytes(b"SQLite format 3\x00")
        with self.assertRaises(ValueError):
            self.run_day()
        self.assertFalse(self.target().exists())

    def test_sqlite_extension_without_header_fails_closed(self):
        business_data.path_for(self.project).write_bytes(b"not SQLite")
        with self.assertRaises(ValueError):
            self.run_day()
        self.assertFalse(self.target().exists())

    def test_active_wal_database_uses_backup_api_and_includes_committed_rows_only(self):
        live = self.active_database()
        live.execute("INSERT INTO sample VALUES ('uncommitted synthetic')")
        original = sqlite3.connect
        calls = []
        class Source(sqlite3.Connection):
            def backup(connection, target, **kwargs):
                calls.append(kwargs["pages"])
                return super().backup(target, **kwargs)
        def connect(path, *args, **kwargs):
            if str(path).endswith("p-test.negocios.sqlite?mode=ro"):
                kwargs["factory"] = Source
            return original(path, *args, **kwargs)
        with patch("automation_backups.sqlite3.connect", side_effect=connect):
            self.run_day()
        self.assertEqual(calls, [128])
        with zipfile.ZipFile(self.target()) as archive:
            names = archive.namelist()
            self.assertFalse(any(n.endswith(("-wal", "-shm", "-journal")) for n in names))
            snapshot = self.root / "inspect.sqlite"
            snapshot.write_bytes(archive.read("projects/p-test.negocios.sqlite"))
        with closing(sqlite3.connect(snapshot)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(db.execute("SELECT * FROM sample").fetchall(), [("committed synthetic",)])

    def test_project_backup_excludes_other_stores_but_preserves_embedded_source_url(self):
        for name in ("correo.local.json", "usuarios.local.json", "counting.sqlite"):
            (self.config / name).write_text("OUTSIDE-SYNTHETIC-SECRET")
        source = "rtsp://synthetic:synthetic-password@example.invalid/test"
        self.project.write_text(json.dumps({"cameras": [{"source": source}]}))
        (self.projects / "p-test.json.tmp").write_text("temporary")
        for name in ("replays", "uploads", "reports", "identidad"):
            path = self.root / "data" / name
            path.mkdir(parents=True)
            (path / "synthetic.txt").write_text("outside")
        self.run_day()
        with zipfile.ZipFile(self.target()) as archive:
            self.assertEqual(set(archive.namelist()), {MANIFEST, "projects/index.json", "projects/p-test.json"})
            self.assertEqual(json.loads(archive.read("projects/p-test.json"))["cameras"][0]["source"], source)
            self.assertNotIn(b"OUTSIDE-SYNTHETIC-SECRET", b"".join(archive.read(n) for n in archive.namelist()))

    def test_modern_schema_columns_rows_and_notification_states_are_preserved(self):
        with closing(business_data.connect(self.project)) as db:
            commercial.setup(db)
            db.execute("INSERT INTO negocios VALUES ('b','Synthetic shop','c','l',1,'Synthetic company')")
            db.execute("INSERT INTO negocio_ubicaciones VALUES ('b','plan',1.5,2.5)")
            db.execute("INSERT INTO negocio_puertas VALUES ('b','c','l')")
            db.execute("INSERT INTO negocio_referencias VALUES ('b','synthetic-map','feature')")
            db.execute("INSERT INTO negocio_estados VALUES ('b','cerrado')")
            for n, status in enumerate(("sent", "uncertain", "failed", "attempting")):
                iid = f"incident-{n}"
                db.execute("INSERT INTO incidentes "
                           "(id,tipo,zona,camara_id,inicio,pico,duracion,estado,detalle,creado,actualizado,"
                           "review_history_known,reviewed_at,history_validated_at) "
                           "VALUES (?,'aglomeracion','zone','c',1,5,7,'revisado','{}',1,2,1,3,4)", (iid,))
                db.execute("INSERT INTO incident_notifications VALUES (?,'original',?,2,1,?,NULL,'synthetic-owner')",
                           (iid, status, 2 if status == 'sent' else None))
                db.execute("INSERT INTO incident_replay_links VALUES (?,'unknown',NULL)", (iid,))
            db.execute("INSERT INTO commercial_sales VALUES ('b','2026-10-01',1,12.5,2,'demo','i')")
            db.execute("INSERT INTO commercial_imports VALUES ('i','synthetic.csv','demo',1,'2026-10-01')")
            db.execute("INSERT INTO commercial_traffic VALUES ('s','b','2026-10-01',1,5,2,1,'demo')")
            db.execute("INSERT INTO commercial_incidents VALUES ('i','b','2026-10-01',3,5,'demo')")
            db.execute("INSERT INTO commercial_bags VALUES ('i','s','b',1,1,0,.7,'synthetic','demo')")
            db.commit()
            before = list(db.iterdump())
        self.run_day()
        with zipfile.ZipFile(self.target()) as archive:
            extracted = self.root / "schema-inspection.sqlite"
            extracted.write_bytes(archive.read("projects/p-test.negocios.sqlite"))
        with closing(sqlite3.connect(extracted)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(list(db.iterdump()), before)
            self.assertEqual(db.execute("SELECT empresa FROM negocios").fetchall(), [("Synthetic company",)])
            self.assertEqual(db.execute("SELECT review_history_known,reviewed_at,history_validated_at "
                                        "FROM incidentes ORDER BY id").fetchall(), [(1, 3., 4.)] * 4)
            self.assertEqual(db.execute("SELECT resolution,session_id FROM incident_replay_links").fetchall(),
                             [("unknown", None)] * 4)
            self.assertEqual(db.execute("SELECT status FROM incident_notifications ORDER BY incident_id").fetchall(),
                             [("sent",), ("uncertain",), ("failed",), ("attempting",)])

    def test_json_capture_holds_engine_lock_but_sqlite_and_compression_do_not(self):
        self.active_database()
        class ObservedLock:
            held = False
            def acquire(lock, timeout):
                self.assertFalse(lock.held)
                lock.held = True
                return True
            def release(lock):
                lock.held = False
        self.engine.lock = ObservedLock()
        from automation_backups import read_artifact
        def read(path, root):
            if path.parent == self.projects:
                self.assertTrue(self.engine.lock.held)
                self.assertTrue(self.resources.protected(path))
            return read_artifact(path, root)
        def snapshot(*args):
            self.assertFalse(self.engine.lock.held)
            self.assertTrue(self.resources.protected(args[0]))
            self.assertTrue(self.resources.protected(args[1]))
            return sqlite_snapshot(*args)
        def archive(*args):
            self.assertFalse(self.engine.lock.held)
            self.assertTrue(self.resources.protected(args[0]))
            return write_archive(*args)
        with patch("automation_backups.read_artifact", side_effect=read), \
             patch("automation_backups.sqlite_snapshot", side_effect=snapshot), \
             patch("automation_backups.write_archive", side_effect=archive):
            self.run_day()
        self.assertFalse(self.resources.busy())

    def test_publication_is_verified_synced_atomic_and_leased(self):
        replace, fsync, events = os.replace, os.fsync, []
        def sync(fd):
            fsync(fd)
            events.append("fsync")
        def publish(source, target):
            self.assertFalse(self.target().exists())
            self.assertEqual(Path(source).parent.parent, self.task.root)
            self.assertTrue(verify_backup_bytes(Path(source).read_bytes()))
            self.assertTrue(self.resources.protected(source))
            self.assertTrue(self.resources.protected(target))
            events.append("replace")
            replace(source, target)
        with patch("automation_backups.os.fsync", side_effect=sync), patch("automation_backups.os.replace", side_effect=publish):
            self.run_day()
        self.assertEqual(events, ["fsync", "replace"])
        self.assertEqual([p.name for p in self.task.root.iterdir()], [self.target().name])

    def test_failed_verification_does_not_publish(self):
        with patch.object(self.task, "verify", return_value=False):
            with self.assertRaises(InvalidBackup):
                self.run_day()
        self.assertFalse(self.target().exists())
        self.assertEqual(list(self.task.root.iterdir()), [])

    def test_fsync_and_replace_failure_leave_no_partial_final(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation), patch("automation_backups.os." + operation, side_effect=OSError("synthetic")):
                with self.assertRaises(OSError):
                    self.run_day()
            self.assertFalse(self.target().exists())
            self.assertEqual(list(self.task.root.iterdir()), [])

    def test_crash_after_publish_recovers_without_second_capture(self):
        with patch.object(self.store, "publish_success", side_effect=OSError("synthetic commit failure")):
            with self.assertRaises(OSError):
                self.run_day()
        before = self.target().read_bytes()
        with patch.object(self.task, "capture", side_effect=AssertionError("no second capture")):
            self.assertEqual(self.run_day(), "recovered")
        self.assertEqual(self.target().read_bytes(), before)
        self.assertEqual(self.row()["status"], "succeeded")

    def test_invalid_preexisting_final_is_marked_corrupt_and_preserved(self):
        self.task.root.mkdir()
        self.target().write_bytes(b"invalid synthetic zip evidence")
        with self.assertRaises(InvalidBackup):
            self.run_day()
        self.assertEqual(self.target().read_bytes(), b"invalid synthetic zip evidence")
        self.assertEqual(self.health()["status"], "corrupt")

    def test_missing_success_stays_succeeded_without_regeneration(self):
        self.run_day()
        before = self.row()
        self.target().unlink()
        with patch.object(self.task, "capture", side_effect=AssertionError("no regeneration")):
            self.assertEqual(self.run_day(), "artifact_problem")
        self.assertEqual(self.row(), before)
        self.assertEqual(self.health()["status"], "missing")
        self.assertFalse(self.target().exists())

    def test_corrupt_success_stays_succeeded_without_replacement(self):
        self.run_day()
        before = self.row()
        self.target().write_bytes(b"corrupt evidence")
        self.assertEqual(self.run_day(), "artifact_problem")
        self.assertEqual(self.row(), before)
        self.assertEqual(self.health()["status"], "corrupt")
        self.assertEqual(self.target().read_bytes(), b"corrupt evidence")

    def test_missing_fingerprint_is_unverifiable_and_never_adopted(self):
        self.run_day()
        with self.store.connect() as db:
            db.execute("DELETE FROM artifact_health")
        self.assertEqual(self.run_day(), "artifact_problem")
        self.assertEqual(self.health()["status"], "unverifiable")
        self.assertIsNone(self.health()["sha256"])

    def test_retention_one_with_three_days_keeps_only_latest(self):
        for day in range(3):
            self.run_day(day, 1)
        self.assertEqual(list(self.task.root.glob("*.zip")), [self.target(2)])
        self.assertEqual([self.health(day)["status"] for day in range(3)], ["retired", "retired", "healthy"])

    def test_retention_n_keeps_exactly_n_valid_backups(self):
        for day in range(5):
            self.run_day(day, 3)
        self.assertEqual(set(self.task.root.glob("*.zip")), {self.target(day) for day in (2, 3, 4)})

    def test_corrupt_newer_backup_does_not_count_and_is_not_deleted(self):
        for day in range(3):
            self.run_day(day)
        self.target(2).write_bytes(b"newer corrupt evidence")
        self.run_day(3, 2)
        self.assertFalse(self.target().exists())
        self.assertTrue(self.target(1).exists())
        self.assertTrue(self.target(2).exists())
        self.assertTrue(self.target(3).exists())
        self.assertEqual(self.health(2)["status"], "corrupt")

    def test_unknown_files_unowned_valid_zips_and_temporaries_are_preserved(self):
        self.run_day()
        protected = {}
        for name in ("unknown.zip", "projects-2000-01-01.zip.tmp", "projects-2000-01-02.zip", "projects-2026-99-99.zip"):
            path = self.task.root / name
            path.write_bytes(self.target().read_bytes())
            protected[path] = path.read_bytes()
        self.run_day(1, 1)
        for path, data in protected.items():
            self.assertEqual(path.read_bytes(), data)

    def test_valid_zip_with_different_fingerprint_is_corrupt_and_not_retained_as_useful(self):
        self.run_day()
        self.run_day(1)
        with zipfile.ZipFile(self.target(1)) as archive:
            files = {name: archive.read(name) for name in archive.namelist() if name != MANIFEST}
        files["projects/p-test.json"] = b'{"airport":"different synthetic data"}'
        write_archive(self.target(1), files, self.now + timedelta(days=1))
        self.assertTrue(verify_backup_bytes(self.target(1).read_bytes()))
        self.run_day(2, 2)
        self.assertEqual(self.health(1)["status"], "corrupt")
        self.assertTrue(self.target().exists())
        self.assertTrue(self.target(1).exists())
        self.assertTrue(self.target(2).exists())

    def test_retention_audit_is_durable_before_unlink_and_history_is_unchanged(self):
        self.run_day()
        before = self.row()
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == self.target():
                self.assertTrue(self.resources.protected(path))
                self.assertEqual(self.health()["status"], "retention_pending")
                with self.store.connect() as db:
                    audit = [json.loads(r[0]) for r in db.execute("SELECT detail FROM audit")]
                self.assertTrue(any(r.get("event") == "retention_planned" for r in audit))
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", new=unlink):
            self.run_day(1, 1)
        self.assertEqual(self.row(), before)
        self.assertEqual(self.health()["status"], "retired")
        self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "retired")
        with self.store.connect() as db:
            audit = [json.loads(r[0]) for r in db.execute("SELECT detail FROM audit")]
        self.assertEqual([r["event"] for r in audit if "event" in r], ["retention_planned", "retention_deleted"])

    def test_unlink_failure_keeps_pending_error_then_retries_prudently(self):
        self.run_day()
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == self.target():
                raise PermissionError("synthetic open file")
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", new=unlink):
            with self.assertRaises(PermissionError):
                self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "retention_pending")
        self.assertIn("PermissionError", self.health()["error"])
        self.assertTrue(self.target().exists())
        self.assertEqual(self.row()["status"], "succeeded")
        self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "retired")

    def test_crash_after_unlink_reconciles_pending_to_retired(self):
        self.run_day()
        original = self.store.set_health
        def health(*args, **kwargs):
            if args[3] == "retired":
                raise sqlite3.OperationalError("synthetic commit failure")
            return original(*args, **kwargs)
        with patch.object(self.store, "set_health", side_effect=health):
            with self.assertRaises(sqlite3.OperationalError):
                self.run_day(1, 1)
        self.assertFalse(self.target().exists())
        self.assertEqual(self.health()["status"], "retention_pending")
        self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "retired")

    def test_reader_lease_prevents_retention_until_released(self):
        self.run_day()
        with self.resources.use(self.target()):
            self.run_day(1, 1)
            self.assertTrue(self.target().exists())
        self.run_day(1, 1)
        self.assertFalse(self.target().exists())

    def test_hard_link_backup_is_unverifiable_and_never_deleted(self):
        self.run_day()
        copy = self.root / "linked.zip"
        os.link(self.target(), copy)
        self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "unverifiable")
        self.assertTrue(self.target().exists())
        self.assertEqual(self.target().read_bytes(), copy.read_bytes())

    def test_symlink_or_junction_metadata_is_not_followed_or_deleted(self):
        self.run_day()
        original = Path.lstat
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400)):
            def lstat(path, *args, **kwargs):
                if path == self.target():
                    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                return original(path, *args, **kwargs)
            with self.subTest(mode=mode), patch.object(Path, "lstat", new=lstat):
                self.run_day(1, 1)
                self.assertEqual(self.health()["status"], "unverifiable")
            self.assertTrue(self.target().exists())

    def test_cancellation_in_sqlite_backup_removes_scratch_and_no_final(self):
        self.active_database()
        event, original, callbacks = threading.Event(), sqlite3.connect, []
        class Source(sqlite3.Connection):
            def backup(connection, target, **kwargs):
                progress = kwargs["progress"]
                def cancel(*args):
                    callbacks.append(args)
                    event.set()
                    progress(*args)
                kwargs["progress"] = cancel
                return super().backup(target, **kwargs)
        def connect(path, *args, **kwargs):
            if str(path).endswith("p-test.negocios.sqlite?mode=ro"):
                kwargs["factory"] = Source
            return original(path, *args, **kwargs)
        with patch("automation_backups.sqlite3.connect", side_effect=connect):
            with self.assertRaises(Cancelled), budget(event, 60):
                self.run_day()
        self.assertTrue(callbacks)
        self.assertFalse(self.target().exists())
        self.assertEqual(list(self.task.root.iterdir()), [])
        self.assertFalse(self.resources.busy())

    def test_cancellation_during_zip_compression_leaves_no_final(self):
        event = threading.Event()
        original = zipfile._ZipWriteFile.write
        def write(stream, data):
            result = original(stream, data)
            event.set()
            return result
        with patch.object(zipfile._ZipWriteFile, "write", new=write):
            with self.assertRaises(Cancelled), budget(event, 60):
                self.run_day()
        self.assertFalse(self.target().exists())
        self.assertEqual(list(self.task.root.iterdir()), [])
        self.assertFalse(self.resources.busy())

    def test_cancellation_after_fsync_does_not_publish(self):
        event, original = threading.Event(), os.fsync
        def sync(fd):
            original(fd)
            event.set()
        with patch("automation_backups.os.fsync", side_effect=sync):
            with self.assertRaises(Cancelled), budget(event, 60):
                self.run_day()
        self.assertFalse(self.target().exists())
        self.assertEqual(list(self.task.root.iterdir()), [])

    def test_runtime_owns_no_service_scoped_false_success(self):
        automation_settings.save(self.config, {"backups": self.settings})
        service = AutomationService(self.engine, {"backups": self.task})
        self.assertEqual(service.run_due_tasks(self.now), {"backups": "succeeded"})
        self.assertIsNone(self.store.get("backups", "service", "2026-10-01"))
        self.assertFalse(self.resources.busy())

    def test_unindexed_json_is_not_silently_treated_as_project_data(self):
        (self.projects / "unknown.json").write_text('{"synthetic":"private"}')
        with self.assertRaises(ValueError):
            self.run_day()
        self.assertFalse(self.target().exists())

    def test_retained_business_database_of_removed_project_is_preserved(self):
        orphan = self.projects / "p-removed.negocios.sqlite"
        with closing(sqlite3.connect(orphan)) as db:
            db.execute("CREATE TABLE historical(value TEXT)")
            db.execute("INSERT INTO historical VALUES ('synthetic retained business data')")
            db.commit()
        self.run_day()
        with zipfile.ZipFile(self.target()) as archive:
            self.assertIn("projects/p-removed.negocios.sqlite", archive.namelist())
        self.assertTrue(verify_backup_bytes(self.target().read_bytes()))

    def test_cancellation_after_replace_preserves_success_and_does_not_duplicate(self):
        event, original = threading.Event(), os.replace
        def replace(source, target):
            original(source, target)
            event.set()
        with patch("automation_backups.os.replace", side_effect=replace):
            with self.assertRaises(Cancelled), budget(event, 60):
                self.run_day()
        self.assertEqual(self.row()["status"], "succeeded")
        with patch.object(self.task, "capture", side_effect=AssertionError("no second capture")):
            self.assertEqual(self.run_day(), "already_done")

    def test_cancellation_after_retention_plan_leaves_file_pending_until_retry(self):
        self.run_day()
        event, original = threading.Event(), self.store.set_health
        def health(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[3] == "retention_pending":
                event.set()
            return result
        with patch.object(self.store, "set_health", side_effect=health):
            with self.assertRaises(Cancelled), budget(event, 60):
                self.run_day(1, 1)
        self.assertTrue(self.target().exists())
        self.assertEqual(self.health()["status"], "retention_pending")
        self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "retired")

    def test_retired_file_that_reappears_is_preserved_without_deletion_authority(self):
        self.run_day()
        evidence = self.target().read_bytes()
        self.run_day(1, 1)
        self.target().write_bytes(evidence)
        self.run_day(2, 1)
        self.assertEqual(self.target().read_bytes(), evidence)
        self.assertEqual(self.health()["status"], "retired")

    def test_wrong_artifact_identity_is_unverifiable_and_never_deleted(self):
        self.run_day()
        before = self.target().read_bytes()
        with self.store.connect() as db:
            db.execute("UPDATE executions SET artifact=?", (str(self.task.root / 'different.zip'),))
        (self.task.root / "different.zip").write_bytes(before)
        self.run_day(1, 1)
        self.assertEqual(self.health()["status"], "unverifiable")
        self.assertEqual(self.target().read_bytes(), before)

    def test_two_instances_share_durable_success_without_duplicate_publication(self):
        other = ProjectBackups(self.engine, AutomationStore(self.store.path))
        started, release, outcomes, errors = threading.Event(), threading.Event(), [], []
        original = self.task.capture
        def capture():
            started.set()
            if not release.wait(3):
                raise RuntimeError("synthetic test timeout")
            return original()
        def run(task):
            try:
                outcomes.append(task(self.now, self.settings))
            except BaseException as exc:
                errors.append(exc)
        with patch.object(self.task, "capture", side_effect=capture), \
             patch.object(other, "capture", side_effect=AssertionError("no duplicate capture")):
            first = threading.Thread(target=run, args=(self.task,))
            second = threading.Thread(target=run, args=(other,))
            first.start()
            try:
                self.assertTrue(started.wait(3))
                second.start()
            finally:
                release.set()
                first.join(5)
                if second.ident is not None:
                    second.join(5)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(sorted(outcomes), ["already_done", "succeeded"])
        self.assertEqual(list(self.task.root.glob("*.zip")), [self.target()])
