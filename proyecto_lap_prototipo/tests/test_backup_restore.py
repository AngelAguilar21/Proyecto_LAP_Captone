import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import default_config, Engine
from automation_backups import ProjectBackups
from automation_store import AutomationStore
from backup_restore import restore_backup, resume_restore, release_hold, cancel_preparation, journal
from restore_guard import blocked, storage_lease
from operational_history import provenance
from incident_notifications import IncidentNotifications
from automation_cleanup import RetentionCleanup
import business_data
import notifier


class RestoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="restore-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.path = self.projects / "p-a.json"
        self.config = default_config()
        self.config.update(cameras=[], airport="Before")
        self.path.write_text(json.dumps(self.config), encoding="utf-8")
        self.index = dict(active="p-a", projects=[dict(id="p-a", name="Synthetic")])
        (self.projects / "index.json").write_text(json.dumps(self.index), encoding="utf-8")
        self.engine = SimpleNamespace(settings_root=self.root, lock=threading.RLock())
        self.store = AutomationStore(self.root / "automation.sqlite")
        self.now = datetime(2026,9,26,18,tzinfo=timezone.utc)
        notifier.save(self.root, dict(enabled=True, user="sender@example.invalid", password="fake",
                                     recipients=["receiver@example.invalid"]))
        self.smtp = self.enterContext(patch.object(notifier, "_send"))
        self.delivery = IncidentNotifications(notifier.Mailer(self.root))
        with closing(business_data.connect(self.path)) as db:
            business_data.registrar_incidente(db, "incident", "equipaje", "z", None, 0,
                                              detalle={"sesion": "aaaaaaaa"})

    def backup(self):
        ProjectBackups(self.engine, self.store)(self.now, dict(time="00:00", retention=7))
        return self.root / "backups" / "projects-2026-09-26.zip"

    def test_restoring_config_keeps_later_sent_review_and_new_rows(self):
        archive = self.backup()
        self.assertTrue(self.delivery.send(self.path, "incident", "test", "test", blocking=True))
        with closing(business_data.connect(self.path)) as db:
            business_data.actualizar_estado_incidente(db, "incident", "revisado")
            business_data.registrar_incidente(db, "later", "equipaje", "z", None, 0)
            business_data.crear_negocio(db, "shop", "Synthetic")
            business_data.cargar_ventas(db, [("shop","2026-09-26",10,12.5)])
            before = db.execute("SELECT * FROM incidentes ORDER BY id").fetchall()
            history = db.execute("SELECT * FROM operational_events ORDER BY seq").fetchall()
        self.config["airport"] = "After"
        self.path.write_text(json.dumps(self.config))
        result = restore_backup(self.root, archive, "test-operator")
        self.assertEqual(result["held_projects"], [])
        self.assertEqual(json.loads(self.path.read_text())["airport"], "Before")
        with closing(business_data.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT * FROM incidentes ORDER BY id").fetchall(), before)
            self.assertEqual(db.execute("SELECT * FROM operational_events ORDER BY seq").fetchall(), history)
            self.assertEqual(db.execute("SELECT monto FROM ventas").fetchone()[0], 12.5)
        self.assertFalse(self.delivery.send(self.path, "incident", "test", "test", blocking=True))
        self.smtp.assert_called_once()

    def test_later_legacy_validation_and_attendance_never_roll_back(self):
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("UPDATE incidentes SET review_history_known=0")
        archive = self.backup()
        with closing(business_data.connect(self.path)) as db:
            business_data.validar_historial_incidente(db, "incident", True)
            validation = business_data.listar_incidentes(db)[0]["history_validated_at"]
            business_data.actualizar_estado_incidente(db, "incident", "revisado")
        restore_backup(self.root, archive, "test-operator")
        with closing(business_data.connect(self.path)) as db:
            row = business_data.listar_incidentes(db)[0]
            self.assertEqual(row["history_validated_at"], validation)
            self.assertIsNotNone(row["reviewed_at"])

    def test_lost_operational_state_is_restored_with_durable_hold(self):
        archive = self.backup()
        business_data.path_for(self.path).unlink()  # Synthetic loss, only in this TemporaryDirectory.
        result = restore_backup(self.root, archive, "test-operator")
        self.assertEqual(result["held_projects"], ["p-a"])
        self.assertTrue(blocked(self.root, self.path))
        self.assertFalse(blocked(self.root, maintenance_only=True))
        for kind in ("original", "escalation"):
            self.assertFalse(self.delivery.send(self.path, "incident", "test", "test", kind=kind, blocking=True))
        self.smtp.assert_not_called()
        with self.assertRaises(ValueError):
            release_hold(self.root, "p-a", "operator", "")
        release_hold(self.root, "p-a", "operator", "Synthetic reconciliation documented")
        self.assertFalse(blocked(self.root, self.path))

    def test_unrelated_lineage_preserves_current_database_but_blocks_delivery(self):
        archive = self.backup()
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("UPDATE operational_identity SET storage_id='other-installation'")
        result = restore_backup(self.root, archive, "test-operator")
        self.assertEqual(result["held_projects"], ["p-a"])
        with closing(business_data.connect(self.path)) as db:
            self.assertEqual(provenance(db)["storage_id"], "other-installation")

    def test_publication_interruption_stays_blocked_and_can_resume(self):
        archive = self.backup()
        import backup_restore
        actual = backup_restore.os.replace
        calls = []
        def interrupt(source, target):
            calls.append(str(source))
            if len(calls) == 2:
                raise OSError("synthetic power loss")
            return actual(source, target)
        with patch.object(backup_restore.os, "replace", side_effect=interrupt):
            with self.assertRaises(OSError):
                restore_backup(self.root, archive, "test-operator")
        self.assertTrue(blocked(self.root, maintenance_only=True))
        with journal(self.root) as db:
            run = db.execute("SELECT id FROM restores").fetchone()[0]
        resume_restore(self.root, run)
        resume_restore(self.root, run)
        self.assertTrue(self.path.exists())
        self.assertFalse(blocked(self.root, maintenance_only=True))

    def test_new_projects_and_global_automation_state_survive_restore(self):
        archive = self.backup()
        other = self.projects / "p-b.json"
        other.write_text(json.dumps(self.config))
        self.index["projects"].append(dict(id="p-b", name="Later"))
        (self.projects / "index.json").write_text(json.dumps(self.index))
        with closing(business_data.connect(other)) as db:
            business_data.registrar_incidente(db, "new", "equipaje", "z", None, 0)
        self.store.record("reports", "p-a", "2026-09-26", "succeeded", self.now)
        restore_backup(self.root, archive, "test-operator")
        self.assertTrue(other.exists())
        self.assertIn("p-b", [p["id"] for p in json.loads((self.projects / "index.json").read_text())["projects"]])
        self.assertEqual(self.store.get("reports", "p-a", "2026-09-26")["status"], "succeeded")

    def test_server_lease_prevents_restore(self):
        archive = self.backup()
        with storage_lease(self.root):
            with self.assertRaises(OSError):
                restore_backup(self.root, archive, "test-operator")
        self.assertFalse((self.root / "restore.sqlite").exists())

    def test_unsafe_archive_never_changes_current_configuration(self):
        archive = self.backup()
        with zipfile.ZipFile(archive, "a") as output:
            output.writestr("projects/../../escape.json", "{}")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            restore_backup(self.root, archive, "test-operator")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.root / "restore.sqlite").exists())

    def test_journal_migration_is_idempotent_and_records_facts_transactionally(self):
        with closing(business_data.connect(self.path)) as db:
            initial = db.execute("SELECT count(*) FROM operational_events").fetchone()[0]
        for _ in range(3):
            with closing(business_data.connect(self.path)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM operational_events").fetchone()[0], initial)
                db.execute("UPDATE incidentes SET estado='resuelto'")
                db.rollback()
                self.assertEqual(db.execute("SELECT count(*) FROM operational_events").fetchone()[0], initial)
        self.assertFalse(blocked(self.root))

    def test_future_backup_schema_is_rejected_before_maintenance_or_publication(self):
        archive = self.backup()
        with zipfile.ZipFile(archive) as original:
            entries = {name: original.read(name) for name in original.namelist()}
        manifest = json.loads(entries["backup-manifest.json"])
        manifest["schema_version"] = 999
        entries["backup-manifest.json"] = json.dumps(manifest).encode()
        with zipfile.ZipFile(archive, "w") as modified:
            for name, data in entries.items():
                modified.writestr(name, data)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            restore_backup(self.root, archive, "test-operator")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.root / "restore.sqlite").exists())

    def test_restore_hold_blocks_cleanup_apply(self):
        archive = self.backup()
        business_data.path_for(self.path).unlink()
        restore_backup(self.root, archive, "test-operator")
        engine = Engine(self.root / "temporary-config.json")
        task = RetentionCleanup(engine, self.store)
        from automation_cleanup import CleanupPlan, Decision
        plan = CleanupPlan(self.root, self.root, self.now, 30,
                           (Decision("data/replays/aaaaaaaa", "candidate", "expired_unreferenced"),))
        self.assertEqual(task.apply_cleanup(plan)[0]["reason"], "restore_hold")

    def test_crash_after_directory_publication_resumes_without_overwriting_again(self):
        archive = self.backup()
        import backup_restore
        actual = backup_restore.os.replace
        def interrupt(source, target):
            actual(source, target)
            if Path(source).name == "stage":
                raise OSError("published, journal not completed")
        with patch.object(backup_restore.os, "replace", side_effect=interrupt):
            with self.assertRaises(OSError):
                restore_backup(self.root, archive, "test-operator")
        before = self.path.read_bytes()
        with journal(self.root) as db:
            run = db.execute("SELECT id FROM restores").fetchone()[0]
        resume_restore(self.root, run)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(blocked(self.root, maintenance_only=True))

    def test_preparation_failure_keeps_current_data_and_can_be_cancelled(self):
        archive = self.backup()
        before = self.path.read_bytes()
        with patch("backup_restore.snapshot", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                restore_backup(self.root, archive, "test-operator")
        self.assertTrue(blocked(self.root, maintenance_only=True))
        self.assertEqual(self.path.read_bytes(), before)
        with journal(self.root) as db:
            run = db.execute("SELECT id FROM restores").fetchone()[0]
        cancel_preparation(self.root, run, "test-operator", "Synthetic failure investigated")
        self.assertFalse(blocked(self.root, maintenance_only=True))

    def test_legacy_backup_without_lineage_keeps_delivery_held(self):
        with closing(business_data.connect(self.path)) as db, db:
            db.execute("DROP TABLE operational_identity")
        archive = self.backup()
        restore_backup(self.root, archive, "test-operator")
        self.assertTrue(blocked(self.root, self.path))
        self.assertFalse(self.delivery.send(self.path, "incident", "test", "test", blocking=True))
        self.smtp.assert_not_called()

    def test_corrupt_guard_and_pending_restore_stop_automation_ticks(self):
        from automation import AutomationService
        callback = Mock()
        (self.root / "restore.sqlite").write_bytes(b"corrupt")
        service = AutomationService(self.engine, tasks={"reports": callback})
        self.assertEqual(service.run_due_tasks(self.now), {})
        self.assertTrue(blocked(self.root, self.path))
        callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
