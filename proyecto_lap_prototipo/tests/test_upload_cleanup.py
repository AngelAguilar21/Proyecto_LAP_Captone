"""Completed upload lifecycle and retention, exclusively with temporary data."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import Engine, Handler
from automation_cleanup import RetentionCleanup, plan_cleanup
from automation_store import AutomationStore
import uploads


class UploadCleanupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="upload-cleanup-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.settings = self.root / "config"
        self.settings.mkdir()
        self.engine = Engine(self.settings / "project.json")
        self.engine.data_root = self.root
        self.engine.config = {"cameras": []}
        self.store = AutomationStore(self.settings / "automation.sqlite")
        self.task = RetentionCleanup(self.engine, self.store)
        self.now = datetime(2026, 9, 27, tzinfo=timezone.utc)
        self.old = self.now.timestamp() - 31 * 86400

    def upload(self, completed_at=None):
        return uploads.receive(self.root, io.BytesIO(b"synthetic-video"), 15, ".mp4",
                               clock=lambda: self.old if completed_at is None else completed_at)

    def plan(self):
        return self.task.plan_cleanup(self.now, 30)

    def decision(self, plan, path):
        return next(d for d in plan.decisions if d.path == path.relative_to(self.root).as_posix())

    def outcome(self, result, path):
        return next(d for d in result if d["path"] == path.relative_to(self.root).as_posix())

    def change_metadata(self, upload_path, **changes):
        marker = uploads.metadata_path(upload_path)
        data = json.loads(marker.read_text())
        data.update(changes)
        marker.write_text(json.dumps(data), encoding="utf-8")

    def reference(self, path):
        (self.settings / "live.local.json").write_text(json.dumps({"source": str(path)}))

    def test_completed_expired_unreferenced_upload_is_candidate(self):
        path = self.upload()
        self.assertEqual(self.decision(self.plan(), path).disposition, "candidate")

    def test_apply_removes_exact_upload_and_metadata_and_audits(self):
        path = self.upload()
        result = self.outcome(self.task.apply_cleanup(self.plan()), path)
        self.assertEqual(result["decision"], "deleted")
        self.assertFalse(path.exists())
        self.assertFalse(uploads.metadata_path(path).exists())
        with self.store.connect() as db:
            rows = db.execute("SELECT at,detail FROM audit WHERE task='cleanup' ORDER BY id").fetchall()
        self.assertEqual([json.loads(row[1])["decision"] for row in rows], ["delete_planned", "deleted"])
        self.assertTrue(all(row[0] == self.now.timestamp() for row in rows))

    def test_recent_completed_upload_is_protected(self):
        path = self.upload(self.now.timestamp())
        self.assertEqual(self.decision(self.plan(), path).reason, "recent_resource")

    def test_legacy_without_evidence_remains_unknown(self):
        folder = self.root / "data" / "uploads"
        folder.mkdir(parents=True)
        path = folder / "legacy.mp4"
        path.write_bytes(b"legacy")
        os.utime(path, (self.old, self.old))
        self.assertEqual(self.decision(self.plan(), path).reason, "upload_completion_unknown")
        self.task.apply_cleanup(self.plan())
        self.assertEqual(path.read_bytes(), b"legacy")
        self.assertFalse(uploads.metadata_path(path).exists())

    def test_incomplete_upload_has_no_completion_evidence(self):
        with self.assertRaises(ValueError):
            uploads.receive(self.root, io.BytesIO(b"partial"), 20, ".mp4")
        files = list((self.root / "data" / "uploads").iterdir())
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.endswith(".part"))
        self.assertEqual(self.decision(self.plan(), files[0]).reason, "upload_completion_unknown")

    def test_configuration_reference_protects_upload(self):
        path = self.upload()
        self.reference(path)
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def replay(self, source=None):
        path = self.root / "data" / "replays" / "aaaaaaaa"
        path.mkdir(parents=True)
        cameras = [{"source": str(source)}] if source else []
        (path / "manifest.json").write_text(json.dumps(dict(session="aaaaaaaa", status="ended",
            created="2026-01-01T00:00:00+00:00", cameras=cameras, config={})))
        (path / "samples.jsonl").write_text('{"t":0}\n')
        for file in path.iterdir():
            os.utime(file, (self.old, self.old))
        return path

    def test_replay_reference_protects_upload(self):
        path = self.upload()
        self.replay(path)
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def test_active_request_after_plan_prevents_deletion(self):
        path = self.upload()
        plan = self.plan()
        with self.engine.resource_use():
            result = self.task.apply_cleanup(plan)
        self.assertEqual(self.outcome(result, path)["decision"], "omitted")
        self.assertTrue(path.exists())

    def test_file_changed_after_plan_is_omitted(self):
        path = self.upload()
        plan = self.plan()
        path.write_bytes(b"changed")
        self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_metadata_changed_after_plan_is_omitted(self):
        path = self.upload()
        plan = self.plan()
        self.change_metadata(path, completed_at=self.old - 1)
        self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_new_reference_after_plan_prevents_deletion(self):
        path = self.upload()
        plan = self.plan()
        self.reference(path)
        self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_links_or_junctions_after_plan_are_not_followed(self):
        path = self.upload()
        for method in ("is_symlink", "is_junction"):
            with self.subTest(method=method):
                plan = self.plan()
                original = getattr(Path, method)
                with patch.object(Path, method, lambda p: p == path or original(p)):
                    result = self.task.apply_cleanup(plan)
                self.assertEqual(self.outcome(result, path)["decision"], "omitted")
                self.assertTrue(path.exists())

    def test_reparse_point_is_omitted(self):
        path = self.upload()
        original = Path.lstat
        def reparse(p):
            if p == path:
                return SimpleNamespace(st_file_attributes=1024)
            return original(p)
        with patch.object(Path, "lstat", reparse):
            self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")
        self.assertTrue(path.exists())

    def test_corrupt_metadata_is_omitted(self):
        path = self.upload()
        uploads.metadata_path(path).write_text("{")
        self.assertEqual(self.decision(self.plan(), path).reason, "upload_completion_invalid")

    def test_metadata_size_mismatch_is_omitted(self):
        path = self.upload()
        self.change_metadata(path, final_size=100)
        self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")

    def test_unknown_version_status_or_identity_is_omitted(self):
        path = self.upload()
        marker = uploads.metadata_path(path)
        original = marker.read_bytes()
        for changes in ({"version": 2}, {"status": "writing"}, {"path": "../outside.mp4"},
                        {"completed_at": float("nan")}, {"identity": []}):
            with self.subTest(changes=changes):
                marker.write_bytes(original)
                self.change_metadata(path, **changes)
                self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")

    def test_runtime_and_counting_history_references_protect_upload(self):
        import sqlite3
        path = self.upload()
        self.engine.runtime_config = {"source": str(path)}
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")
        self.engine.runtime_config = None
        with closing(sqlite3.connect(self.settings / "counting.sqlite")) as db, db:
            db.execute("CREATE TABLE sessions (payload TEXT)")
            db.execute("INSERT INTO sessions VALUES (?)", (json.dumps({"source": str(path)}),))
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def test_orphan_project_reference_protects_upload(self):
        path = self.upload()
        directory = self.settings / "projects"
        directory.mkdir()
        (directory / "index.json").write_text(json.dumps({"projects": [{"id": "p-a"}]}))
        (directory / "p-a.json").write_text("{}")
        (directory / "orphan.json").write_text(json.dumps({"source": str(path)}))
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def test_retention_uses_completed_at_and_configured_days(self):
        path = self.upload()
        self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 32), path).disposition, "protected")
        self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), path).disposition, "candidate")

    def test_same_size_changed_bytes_cannot_reuse_completion(self):
        path = self.upload()
        path.write_bytes(b"different-video")
        # Even metadata with updated stat fields cannot authenticate different bytes.
        self.change_metadata(path, identity=uploads.identity(path))
        self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")

    def test_audit_failure_prevents_both_deletions(self):
        path = self.upload()
        plan = self.plan()
        with patch.object(self.store, "audit", side_effect=OSError("synthetic audit failure")):
            with self.assertRaises(OSError):
                self.task.apply_cleanup(plan)
        self.assertTrue(path.exists())
        self.assertTrue(uploads.metadata_path(path).exists())

    def test_unlink_failure_is_never_reported_deleted(self):
        path = self.upload()
        plan = self.plan()
        with patch.object(Path, "unlink", side_effect=PermissionError("synthetic")):
            result = self.task.apply_cleanup(plan)
        self.assertEqual(self.outcome(result, path)["reason"], "delete_failed_or_changed")
        self.assertTrue(path.exists())

    def test_metadata_unlink_failure_leaves_auditable_orphan(self):
        path = self.upload()
        marker = uploads.metadata_path(path)
        original = Path.unlink
        def unlink(p, *args, **kwargs):
            if p == marker:
                raise PermissionError("synthetic metadata failure")
            return original(p, *args, **kwargs)
        plan = self.plan()
        with patch.object(Path, "unlink", unlink):
            result = self.task.apply_cleanup(plan)
        self.assertEqual(self.outcome(result, path)["reason"], "delete_failed_or_changed")
        self.assertFalse(path.exists())
        self.assertTrue(marker.exists())
        self.assertEqual(self.decision(self.plan(), marker).disposition, "omitted")

    def handler(self, content, length):
        handler = Handler.__new__(Handler)
        handler.server = SimpleNamespace(engine=self.engine, closing=False)
        handler.path = "/api/upload?name=synthetic.mp4"
        handler.headers = {"Content-Length": str(length), "X-LAP-Token": self.engine.token}
        handler.rfile = io.BytesIO(content)
        handler.allowed = Mock(return_value=True)
        handler.send_data = Mock()
        return handler

    def test_endpoint_success_publishes_completed_evidence_before_response(self):
        handler = self.handler(b"synthetic", 9)
        def response(code, value):
            self.assertEqual(code, 200)
            path = Path(value["path"])
            completed_at, fingerprint = uploads.completed_fingerprint(path, self.root)
            self.assertGreater(completed_at, 0)
            self.assertEqual(fingerprint[0][2], 9)
            self.assertTrue(self.engine.resource_users)
        handler.send_data.side_effect = response
        with patch("live_server.auth.hay_usuarios", return_value=False):
            handler.do_POST()
        handler.send_data.assert_called_once()
        self.assertEqual(self.engine.resource_users, 0)

    def test_endpoint_interruption_never_publishes_completed(self):
        handler = self.handler(b"short", 10)
        with patch("live_server.auth.hay_usuarios", return_value=False):
            handler.do_POST()
        self.assertEqual(handler.send_data.call_args.args[0], 400)
        self.assertEqual(list(self.root.rglob("*" + uploads.MARKER)), [])
        self.assertTrue(all(d.disposition == "omitted" for d in self.plan().decisions))
        self.assertEqual(self.engine.resource_users, 0)

    def test_failure_after_publication_leaves_unknown_upload(self):
        replace = os.replace
        def fail_metadata(source, target):
            if str(target).endswith(uploads.MARKER):
                raise OSError("synthetic metadata publication failure")
            replace(source, target)
        with patch.object(uploads.os, "replace", side_effect=fail_metadata):
            with self.assertRaises(OSError):
                self.upload()
        path = next((self.root / "data" / "uploads").glob("*.mp4"))
        self.assertFalse(uploads.metadata_path(path).exists())
        self.assertEqual(self.decision(self.plan(), path).reason, "upload_completion_unknown")

    def test_repeated_planning_does_not_mutate_filesystem(self):
        self.upload()
        def snapshot():
            return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        before = snapshot()
        self.assertEqual(self.plan(), self.plan())
        self.assertEqual(snapshot(), before)

    def test_upload_cleanup_preserves_existing_replay_behavior(self):
        path = self.upload()
        replay = self.replay()
        result = self.task.apply_cleanup(self.plan())
        self.assertEqual(self.outcome(result, path)["decision"], "deleted")
        self.assertEqual(self.outcome(result, replay)["decision"], "deleted")
        self.assertFalse(replay.exists())

    def test_fsync_failure_never_publishes_completed(self):
        with patch.object(uploads.os, "fsync", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.upload()
        self.assertFalse(list(self.root.rglob("*" + uploads.MARKER)))
        self.assertTrue(all(d.disposition == "omitted" for d in self.plan().decisions))


if __name__ == "__main__":
    unittest.main()
