"""Retention planning/execution is exercised exclusively inside TemporaryDirectory."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation_cleanup import plan_cleanup, RetentionCleanup, Decision
from automation_store import AutomationStore
from automation import AutomationService
from live_server import Engine
import automation_settings


class CleanupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="cleanup-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.settings = self.root / "config"
        self.settings.mkdir()
        self.now = datetime(2026, 9, 26, tzinfo=timezone.utc)
        self.old = self.now.timestamp() - 31 * 86400

    def replay(self, sid="aaaaaaaa", status="ended", recent=False):
        path = self.root / "data" / "replays" / sid
        path.mkdir(parents=True)
        (path / "manifest.json").write_text(json.dumps(dict(session=sid, status=status,
            created="2026-01-01T00:00:00+00:00", cameras=[], config={})), encoding="utf-8")
        (path / "samples.jsonl").write_text('{"t": 0}\n', encoding="utf-8")
        for child in path.iterdir():
            os.utime(child, (self.old, self.now.timestamp() if recent else self.old))
        return path

    def plan(self, **kwargs):
        return plan_cleanup(self.root, self.settings, self.now, 30, **kwargs)

    def test_plan_identifies_expired_replay_without_mutating_any_files(self):
        path = self.replay()
        before = {p.name: p.read_bytes() for p in path.iterdir()}
        plan = self.plan()
        self.assertEqual([(d.disposition, d.reason) for d in plan.decisions],
                         [("candidate", "expired_unreferenced")])
        self.assertEqual({p.name: p.read_bytes() for p in path.iterdir()}, before)

    def test_running_active_recent_and_in_use_resources_are_preserved(self):
        self.replay("aaaaaaaa", "running")
        self.replay("bbbbbbbb")
        self.replay("cccccccc", recent=True)
        self.replay("dddddddd")
        decisions = self.plan(active_sessions={"bbbbbbbb"}, busy=True).decisions
        self.assertEqual([d.reason for d in decisions],
            ["active_session", "active_session", "recent_resource", "resources_in_use"])
        self.assertTrue(all(d.disposition != "candidate" for d in decisions))

    def test_corrupt_manifest_omits_other_candidates_conservatively(self):
        self.replay()
        bad = self.replay("bbbbbbbb")
        (bad / "manifest.json").write_text("{", encoding="utf-8")
        self.assertTrue(all(d.disposition == "omitted" for d in self.plan().decisions))

    def test_all_projects_including_orphans_protect_references(self):
        self.replay()
        other = self.replay("bbbbbbbb")
        directory = self.settings / "projects"
        directory.mkdir()
        (directory / "index.json").write_text(json.dumps({"projects": [{"id": "p-a"}]}))
        (directory / "p-a.json").write_text(json.dumps({"replay": "data/replays/aaaaaaaa"}))
        (directory / "orphan.json").write_text(json.dumps({"source": str(other / "samples.jsonl")}))
        self.assertEqual([d.reason for d in self.plan().decisions], ["referenced_resource"] * 2)

    def test_corrupt_or_missing_indexed_project_omits_candidate(self):
        self.replay()
        directory = self.settings / "projects"
        directory.mkdir()
        index = directory / "index.json"
        for text in ("{", json.dumps({"projects": [{"id": "missing"}]})):
            with self.subTest(text=text):
                index.write_text(text)
                self.assertEqual(self.plan().decisions[0].reason, "uncertain_references")

    def test_counting_history_beyond_ui_limit_protects_session(self):
        self.replay()
        with closing(sqlite3.connect(self.settings / "counting.sqlite")) as db, db:
            db.execute("CREATE TABLE sessions (id TEXT, payload TEXT)")
            db.executemany("INSERT INTO sessions VALUES (?,?)", [(str(i), '{}') for i in range(40)])
            db.execute("INSERT INTO sessions VALUES ('old', ?)", ('{"session": "aaaaaaaa"}',))
        self.assertEqual(self.plan().decisions[0].reason, "referenced_resource")

    def test_upload_without_completion_evidence_is_always_omitted(self):
        uploads = self.root / "data" / "uploads"
        uploads.mkdir(parents=True)
        video = uploads / "synthetic.mp4"
        video.write_bytes(b"synthetic")
        os.utime(video, (self.old, self.old))
        self.assertEqual(self.plan().decisions[0].reason, "upload_completion_unknown")
        self.assertEqual(video.read_bytes(), b"synthetic")

    def test_junction_or_symlink_is_not_traversed(self):
        path = self.replay()
        original = Path.is_junction
        with patch.object(Path, "is_junction", lambda p: p == path or original(p)):
            self.assertEqual(self.plan().decisions[0].disposition, "omitted")
        self.assertTrue((path / "samples.jsonl").exists())

    def test_ambiguous_path_and_unreadable_file_are_omitted(self):
        self.replay()
        self.assertEqual(self.plan(documents=[{"source": "data/replays/../replays/aaaaaaaa"}]).decisions[0].reason,
                         "uncertain_references")
        with patch.object(Path, "read_text", side_effect=PermissionError("synthetic")):
            self.assertEqual(self.plan().decisions[0].disposition, "omitted")

    def test_unknown_extra_content_prevents_recursive_deletion(self):
        path = self.replay()
        (path / "unexpected.txt").write_text("keep")
        self.assertEqual(self.plan().decisions[0].disposition, "omitted")

    def task(self):
        engine = Engine(self.settings / "project.json")
        engine.data_root = self.root
        engine.config = {"cameras": []}
        store = AutomationStore(self.settings / "automation.sqlite")
        return RetentionCleanup(engine, store)

    def test_apply_deletes_only_candidate_and_persists_audit(self):
        path = self.replay()
        recent = self.replay("bbbbbbbb", recent=True)
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        self.assertTrue(path.exists())
        result = task.apply_cleanup(plan)
        self.assertEqual([d["decision"] for d in result], ["deleted", "protected"])
        self.assertFalse(path.exists())
        self.assertTrue(recent.exists())
        with task.store.connect() as db:
            audit = [json.loads(row[0]) for row in db.execute("SELECT detail FROM audit ORDER BY id")]
        self.assertEqual([row["decision"] for row in audit], ["delete_planned", "deleted", "protected"])

    def test_new_reference_after_planning_prevents_deletion(self):
        path = self.replay()
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        task.engine.config["replay"] = str(path)
        self.assertEqual(task.apply_cleanup(plan)[0]["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_changed_file_after_planning_prevents_deletion(self):
        path = self.replay()
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        (path / "samples.jsonl").write_text("new synthetic data")
        self.assertEqual(task.apply_cleanup(plan)[0]["decision"], "omitted")
        self.assertTrue(path.exists())

    def test_active_request_and_workers_block_apply_without_waiting(self):
        path = self.replay()
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        with task.engine.resource_use():
            self.assertEqual(task.apply_cleanup(plan)[0]["decision"], "omitted")
        self.assertEqual(task.engine.resource_users, 0)
        for worker in ("worker", "preview_worker"):
            with self.subTest(worker=worker):
                setattr(task.engine, worker, Mock(is_alive=Mock(return_value=True)))
                self.assertEqual(task.apply_cleanup(plan)[0]["decision"], "omitted")
                setattr(task.engine, worker, None)
        self.assertTrue(path.exists())

    def test_request_guard_releases_on_exception(self):
        task = self.task()
        with self.assertRaises(ValueError):
            with task.engine.resource_use():
                self.assertEqual(task.engine.resource_users, 1)
                raise ValueError("synthetic")
        self.assertEqual(task.engine.resource_users, 0)

    def test_forged_outside_root_candidate_cannot_delete_file(self):
        path = self.root / "keep.txt"
        path.write_text("keep")
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        forged = replace(plan, decisions=(Decision("../../keep.txt", "candidate", "expired_unreferenced"),))
        self.assertEqual(task.apply_cleanup(forged)[0]["decision"], "omitted")
        self.assertEqual(path.read_text(), "keep")

    def test_audit_failure_prevents_deletion(self):
        path = self.replay()
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        with patch.object(task.store, "audit", side_effect=sqlite3.OperationalError("disk unavailable")):
            with self.assertRaises(sqlite3.OperationalError):
                task.apply_cleanup(plan)
        self.assertTrue((path / "samples.jsonl").exists())

    def test_permission_failure_is_logged_and_not_reported_deleted(self):
        path = self.replay()
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        with patch.object(Path, "unlink", side_effect=PermissionError("file in use")):
            self.assertEqual(task.apply_cleanup(plan)[0]["reason"], "delete_failed_or_changed")
        self.assertTrue((path / "manifest.json").exists())

    def test_link_replacing_candidate_after_plan_is_omitted(self):
        path = self.replay()
        task = self.task()
        plan = task.plan_cleanup(self.now, 30)
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda p: p == path or original(p)):
            self.assertEqual(task.apply_cleanup(plan)[0]["decision"], "omitted")
        self.assertTrue((path / "samples.jsonl").exists())

    def test_counting_worker_blocks_cleanup(self):
        path = self.replay()
        task = self.task()
        import threading
        task.engine.counting = Mock(lock=threading.RLock(), config={}, state={})
        task.engine.counting.active.return_value = True
        self.assertEqual(task.plan_cleanup(self.now, 30).decisions[0].reason, "resources_in_use")
        self.assertTrue(path.exists())

    def test_corrupt_counting_database_or_manifest_date_excludes_candidate(self):
        path = self.replay()
        db_path = self.settings / "counting.sqlite"
        db_path.write_bytes(b"not sqlite")
        self.assertEqual(self.plan().decisions[0].reason, "uncertain_references")
        db_path.unlink()
        meta = json.loads((path / "manifest.json").read_text())
        meta["created"] = "unknown"
        (path / "manifest.json").write_text(json.dumps(meta))
        self.assertEqual(self.plan().decisions[0].disposition, "omitted")

    def test_cleanup_service_disabled_by_default_and_runs_only_on_temporary_data(self):
        path = self.replay()
        task = self.task()
        service = AutomationService(task.engine)
        self.assertEqual(service.run_due_tasks(self.now), {})
        self.assertTrue(path.exists())
        automation_settings.save(self.settings, {"cleanup": {"enabled": True, "retention_days": 30}})
        self.assertEqual(service.run_due_tasks(self.now)["cleanup"][0]["decision"], "deleted")
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
