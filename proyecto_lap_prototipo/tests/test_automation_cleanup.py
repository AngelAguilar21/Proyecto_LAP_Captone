"""Deletion tests operate exclusively on synthetic temporary fixtures."""
import json
import os
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cleanup_fixtures import CleanupFixture
from automation_cleanup import Decision
import automation_settings
from task_control import budget, Cancelled
import uploads


class AutomationCleanupTests(CleanupFixture, unittest.TestCase):
    def test_finished_replay_is_candidate_and_plan_is_readonly(self):
        path = self.replay()
        before = self.snapshot()
        self.assertEqual(self.decision(self.plan(), path).disposition, "candidate")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.store.path.exists())

    def test_recent_replay_and_all_active_states_are_protected(self):
        self.replay("aaaaaaaa", when=self.now.timestamp())
        for i, state in enumerate(("starting", "running", "paused", "stopping")):
            self.replay(f"{i:08x}", state)
        self.assertTrue(all(d.disposition == "protected" for d in self.plan().decisions))

    def test_retention_boundary_is_strict_for_replay_and_upload(self):
        boundary = self.now.timestamp() - 30 * 86400
        path = self.replay(when=boundary)
        upload = self.upload(boundary)
        self.assertEqual(self.decision(self.plan(), path).reason, "recent_resource")
        self.assertEqual(self.decision(self.plan(), upload).reason, "recent_resource")
        expired = self.upload(boundary - .01)
        self.assertEqual(self.decision(self.plan(), expired).disposition, "candidate")

    def test_ended_stopped_and_error_replays_are_potential_candidates(self):
        for i, status in enumerate(("ended", "stopped", "error")):
            self.replay(f"{i:08x}", status)
        self.assertTrue(all(d.disposition == "candidate" for d in self.plan().decisions))

    def test_completed_upload_recent_or_expired_uses_completion_timestamp(self):
        recent = self.upload(self.now.timestamp())
        old = self.upload()
        self.assertEqual(self.decision(self.plan(), recent).disposition, "protected")
        self.assertEqual(self.decision(self.plan(), old).disposition, "candidate")

    def test_legacy_part_orphan_marker_and_unknown_files_are_never_deleted(self):
        folder = self.root / "data/uploads"
        folder.mkdir(parents=True)
        for name in ("old.mp4", "a.mp4.part", "orphan.mp4.completed.json", "unknown.txt"):
            path = folder / name
            path.write_bytes(b"keep")
            os.utime(path, (self.old, self.old))
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        self.assertTrue(all(d.disposition == "omitted" for d in self.plan().decisions))
        self.task.apply_cleanup(self.task.plan_cleanup(self.now, 30))
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_all_indexed_and_orphan_projects_protect_references(self):
        replay = self.replay()
        upload = self.upload()
        self.project({"source": str(upload)})
        directory = self.settings / "projects"
        (directory / "p-b.json").write_text(json.dumps({"source": str(replay / "samples.jsonl")}))
        (directory / "index.json").write_text(json.dumps({"active": "p-a", "projects": [{"id": "p-a"}, {"id": "p-b"}]}))
        self.assertEqual([d.reason for d in self.plan().decisions], ["referenced_resource"] * 2)
        # Retained unindexed JSON still protects its sources.
        (directory / "index.json").write_text(json.dumps({"active": "p-a", "projects": [{"id": "p-a"}]}))
        self.assertEqual(self.decision(self.plan(), replay).reason, "referenced_resource")

    def test_live_runtime_and_counting_configuration_references_are_included(self):
        path = self.upload()
        self.engine.runtime_config = {"source": str(path)}
        self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), path).reason, "referenced_resource")
        self.engine.runtime_config = None
        (self.settings / "counting.local.json").write_text(json.dumps({"source": str(path)}))
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def test_full_counting_history_beyond_ui_limit_protects_resources(self):
        replay, upload = self.replay(), self.upload()
        with closing(sqlite3.connect(self.settings / "counting.sqlite")) as db, db:
            db.execute("CREATE TABLE sessions(id TEXT, created TEXT, payload TEXT)")
            db.executemany("INSERT INTO sessions VALUES (?, 'now', '{}')", [(str(i),) for i in range(50)])
            db.execute("INSERT INTO sessions VALUES ('old','before',?)", (json.dumps({"session": "aaaaaaaa", "config": {"source": str(upload)}}),))
        before = self.snapshot()
        self.assertEqual([d.reason for d in self.plan().decisions], ["referenced_resource"] * 2)
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_counting_database_fails_closed_without_writes(self):
        path = self.replay()
        (self.settings / "counting.sqlite").write_bytes(b"not sqlite")
        before = self.snapshot()
        self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")
        self.assertEqual(self.snapshot(), before)

    def test_invalid_index_missing_project_or_bad_project_json_fails_closed(self):
        path = self.replay()
        self.project({})
        directory = self.settings / "projects"
        index = directory / "index.json"
        for text in ("{", '{"projects":[{"id":"missing"}],"active":"missing"}',
                     '{"projects":[{"id":"p-a"},{"id":"P-A"}],"active":"p-a"}'):
            with self.subTest(text=text):
                index.write_text(text)
                self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")
        self.project({})
        (directory / "p-a.json").write_text("{")
        self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")

    def test_other_replay_manifests_protect_source_and_session_paths(self):
        source = self.replay()
        upload = self.upload()
        self.replay("bbbbbbbb", when=self.now.timestamp(), config={"replay": str(source), "source": str(upload)})
        self.assertEqual(self.decision(self.plan(), source).reason, "referenced_resource")
        self.assertEqual(self.decision(self.plan(), upload).reason, "referenced_resource")

    def test_remote_urls_are_not_interpreted_as_local_references(self):
        path = self.replay()
        documents = [{"source": "https://example.invalid/data/replays/aaaaaaaa"},
                     {"source": "rtsp://user:synthetic@example.invalid/aaaaaaaa"}]
        self.assertEqual(self.decision(self.plan(documents=documents), path).disposition, "candidate")

    def test_ambiguous_local_reference_fails_closed(self):
        path = self.replay()
        self.assertEqual(self.decision(self.plan(documents=[{"source": "data/replays/../replays/aaaaaaaa"}]), path).reason, "uncertain_references")

    def test_active_session_and_concrete_leases_protect_resources(self):
        replay, upload = self.replay(), self.upload()
        self.engine.state.update(status="running", session="aaaaaaaa")
        self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), replay).reason, "active_session")
        self.engine.state.update(status="idle")
        with self.engine.resource_use(upload):
            self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), upload).reason, "resource_in_use")
        with self.engine.resource_use(replay / "samples.jsonl"):
            self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), replay).reason, "resource_in_use")

    def test_background_worker_or_counting_activity_omits_candidates(self):
        path = self.replay()
        for name in ("worker", "preview_worker", "detector_warmup"):
            setattr(self.engine, name, Mock(is_alive=Mock(return_value=True)))
            self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), path).reason, "resources_in_use")
            setattr(self.engine, name, None)
        self.engine.counting = SimpleNamespace(lock=threading.RLock(), config={}, state={}, active=lambda: True)
        self.assertEqual(self.decision(self.task.plan_cleanup(self.now, 30), path).reason, "resources_in_use")

    def test_other_http_activity_prevents_apply_without_waiting(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        ready, release = threading.Event(), threading.Event()
        def request():
            with self.engine.resources.activity(writer=False):
                ready.set()
                self.assertTrue(release.wait(5))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(request)
            try:
                self.assertTrue(ready.wait(5))
                self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
            finally:
                release.set()
            future.result(5)
        self.assertTrue(path.exists())

    def test_engine_lock_unavailable_is_fail_closed_without_waiting(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        with ThreadPoolExecutor(max_workers=1) as pool, self.engine.lock:
            result = pool.submit(self.task.apply_cleanup, plan).result(3)
        self.assertEqual(self.outcome(result, path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_plan_does_not_create_or_migrate_sqlite(self):
        self.replay()
        database = self.settings / "legacy.negocios.sqlite"
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("CREATE TABLE incidentes(id TEXT,detalle TEXT)")
        before = self.snapshot()
        self.plan()
        self.assertEqual(self.snapshot(), before)
        with closing(sqlite3.connect(database)) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("incidentes",)])

    def test_old_plan_rechecks_configuration_reference_and_file_fingerprint(self):
        replay, upload = self.replay(), self.upload()
        plan = self.task.plan_cleanup(self.now, 30)
        self.engine.config["source"] = str(upload)
        (replay / "samples.jsonl").write_text("changed")
        outcomes = self.task.apply_cleanup(plan)
        self.assertTrue(all(d["reason"] == "plan_changed" for d in outcomes))
        self.assertTrue(upload.exists())
        self.assertTrue(replay.exists())

    def test_changed_upload_fingerprint_is_never_deleted(self):
        path = self.upload()
        plan = self.task.plan_cleanup(self.now, 30)
        path.write_bytes(b"different-video")
        self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_replay_replacement_with_identical_bytes_and_mtime_is_rejected(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        file = path / "samples.jsonl"
        replacement = self.root / "replacement"
        replacement.write_bytes(file.read_bytes())
        os.utime(replacement, ns=(file.stat().st_atime_ns, file.stat().st_mtime_ns))
        os.replace(replacement, file)
        self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(file.exists())

    def test_lease_acquired_after_plan_prevents_deletion(self):
        path = self.upload()
        plan = self.task.plan_cleanup(self.now, 30)
        with self.engine.resource_use(path, write=True):
            self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_extra_or_missing_replay_files_block_deletion(self):
        path = self.replay()
        other = self.replay("bbbbbbbb")
        (path / "unexpected.bin").write_bytes(b"keep")
        (other / "samples.jsonl").unlink()
        self.assertTrue(all(d.disposition == "omitted" for d in self.plan().decisions))

    def test_junction_or_hard_link_is_never_deleted(self):
        path = self.replay()
        original = Path.is_junction
        with patch.object(Path, "is_junction", lambda p: p == path or original(p)):
            self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")
        os.link(path / "samples.jsonl", self.root / "hardlink.jsonl")
        self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")
        self.assertTrue(path.exists())

    def test_forged_outside_root_candidate_cannot_delete(self):
        keep = self.root / "keep.txt"
        keep.write_text("keep")
        plan = self.task.plan_cleanup(self.now, 30)
        forged = replace(plan, decisions=(Decision("../../keep.txt", "candidate", "expired_unreferenced"),))
        self.assertEqual(self.task.apply_cleanup(forged)[0]["reason"], "plan_changed")
        self.assertEqual(keep.read_text(), "keep")

    def test_exact_replay_and_upload_deletion_and_durable_audit(self):
        replay, upload = self.replay(), self.upload()
        unrelated = []
        for name in ("data/IdentityMemory", "data/reports", "config/backups", "data/counting", "models", "external/P2PNet"):
            path = self.root / name / "keep.txt"
            path.parent.mkdir(parents=True)
            path.write_text("keep")
            unrelated.append(path)
        plan = self.task.plan_cleanup(self.now, 30)
        with patch("shutil.rmtree", side_effect=AssertionError("Recursive deletion forbidden")):
            outcomes = self.task.apply_cleanup(plan)
        self.assertEqual([r["decision"] for r in outcomes], ["deleted", "deleted"])
        self.assertFalse(replay.exists())
        self.assertFalse(upload.exists())
        self.assertFalse(uploads.metadata_path(upload).exists())
        self.assertTrue(all(p.read_text() == "keep" for p in unrelated))
        with self.store.connect() as db:
            rows = db.execute("SELECT at,detail FROM audit WHERE task='cleanup' ORDER BY id").fetchall()
        self.assertEqual([json.loads(row[1])["decision"] for row in rows], ["delete_planned", "deleted"] * 2)
        self.assertTrue(all(row[0] == self.now.timestamp() for row in rows))

    def test_partial_replay_delete_is_uncertain_and_not_resumed(self):
        path = self.replay()
        original = Path.unlink
        def fail_manifest(file, *args, **kwargs):
            if file == path / "manifest.json":
                raise PermissionError("synthetic sharing violation")
            return original(file, *args, **kwargs)
        plan = self.task.plan_cleanup(self.now, 30)
        with patch.object(Path, "unlink", fail_manifest):
            result = self.task.apply_cleanup(plan)
        self.assertEqual(self.outcome(result, path)["reason"], "delete_failed_or_changed")
        self.assertFalse((path / "samples.jsonl").exists())
        self.assertTrue((path / "manifest.json").exists())
        self.assertEqual(self.decision(self.plan(), path).disposition, "omitted")
        self.task.apply_cleanup(self.task.plan_cleanup(self.now, 30))
        self.assertTrue((path / "manifest.json").exists())

    def test_partial_upload_delete_leaves_orphan_marker_omitted(self):
        path = self.upload()
        marker = uploads.metadata_path(path)
        original = Path.unlink
        def fail_marker(file, *args, **kwargs):
            if file == marker:
                raise PermissionError("synthetic")
            return original(file, *args, **kwargs)
        plan = self.task.plan_cleanup(self.now, 30)
        with patch.object(Path, "unlink", fail_marker):
            result = self.task.apply_cleanup(plan)
        self.assertEqual(self.outcome(result, path)["reason"], "delete_failed_or_changed")
        self.assertFalse(path.exists())
        self.assertTrue(marker.exists())
        self.assertEqual(self.decision(self.plan(), marker).disposition, "omitted")

    def test_audit_failure_prevents_any_deletion(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        with patch.object(self.store, "audit", side_effect=sqlite3.OperationalError("disk")), self.assertRaises(sqlite3.Error):
            self.task.apply_cleanup(plan)
        self.assertTrue((path / "samples.jsonl").exists())

    def test_cancellation_during_plan_never_mutates_files(self):
        self.upload()
        before = self.snapshot()
        event = threading.Event()
        with self.assertRaises(Cancelled), budget(event, 60):
            event.set()
            self.task.plan_cleanup(self.now, 30)
        self.assertEqual(self.snapshot(), before)

    def test_cancellation_after_delete_planned_does_not_delete(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        event = threading.Event()
        audit = self.store.audit
        def cancel(task, detail, now):
            audit(task, detail, now)
            if json.loads(detail)["decision"] == "delete_planned":
                event.set()
        with patch.object(self.store, "audit", side_effect=cancel), self.assertRaises(Cancelled), budget(event, 60):
            self.task.apply_cleanup(plan)
        self.assertTrue((path / "samples.jsonl").exists())

    def test_cleanup_disabled_is_inert_and_injected_service_can_delete_temporary_data(self):
        path = self.replay()
        before = self.snapshot()
        self.assertEqual(self.task(self.now, {"enabled": False, "retention_days": 30}), "disabled")
        self.assertEqual(self.snapshot(), before)
        self.engine.automation.tasks = {"cleanup": self.task}
        self.assertEqual(self.engine.automation.run_due_tasks(self.now), {})
        automation_settings.save(self.settings, {"cleanup": {"enabled": True, "retention_days": 30}})
        result = self.engine.automation.run_due_tasks(self.now)
        self.assertEqual(self.outcome(result["cleanup"], path)["decision"], "deleted")
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
