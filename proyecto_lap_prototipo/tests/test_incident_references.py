import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

from cleanup_fixtures import CleanupFixture
import business_data
from cleanup_references import incident_references, reference_paths


class IncidentReferenceTests(CleanupFixture, unittest.TestCase):
    def incident(self, iid="incident", sid="aaaaaaaa", state="pendiente"):
        with closing(business_data.connect(self.settings / "orphan.json")) as db:
            business_data.registrar_incidente(db, iid, "aglomeracion", "zone", "C", 0, detalle={"sesion": sid})
            if state != "pendiente":
                business_data.actualizar_estado_incidente(db, iid, state)

    def test_new_incident_uses_persisted_detail_for_link_and_never_rewrites_it(self):
        self.incident()
        self.incident(sid="bbbbbbbb")
        with closing(business_data.connect(self.settings / "orphan.json")) as db:
            self.assertEqual(db.execute("SELECT * FROM incident_replay_links").fetchall(), [("incident", "linked", "aaaaaaaa")])
            self.assertEqual(json.loads(db.execute("SELECT detalle FROM incidentes").fetchone()[0])["sesion"], "aaaaaaaa")

    def test_invalid_or_missing_session_is_unknown(self):
        for i, sid in enumerate((None, "../outside", "not-a-session", "https://example.invalid/aaaaaaaa", 123)):
            self.incident(str(i), sid)
        with closing(business_data.connect(self.settings / "orphan.json")) as db:
            self.assertEqual(db.execute("SELECT resolution,session_id FROM incident_replay_links").fetchall(), [("unknown", None)] * 5)
        path = self.replay()
        self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")

    def test_all_incident_states_protect_replays_in_retained_orphan_database(self):
        for i, state in enumerate(("pendiente", "revisado", "resuelto", "falsa_alarma")):
            sid = f"{i:08x}"
            self.replay(sid)
            self.incident(sid, sid, state)
        self.assertEqual([d.reason for d in self.plan().decisions], ["referenced_resource"] * 4)

    def test_contradictory_link_fails_closed(self):
        path = self.replay()
        self.incident()
        with closing(business_data.connect(self.settings / "orphan.json")) as db, db:
            db.execute("UPDATE incident_replay_links SET session_id='bbbbbbbb'")
        self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")

    def test_missing_legacy_link_is_read_without_migration(self):
        path = business_data.path_for(self.settings / "legacy.json")
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE incidentes(id TEXT,detalle TEXT)")
            db.execute("INSERT INTO incidentes VALUES ('old',?)", (json.dumps({"sesion": "aaaaaaaa"}),))
        before = self.snapshot()
        refs = reference_paths(incident_references(self.settings), self.root)
        self.assertIn(self.root / "data/replays/aaaaaaaa", refs)
        self.assertEqual(self.snapshot(), before)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("incidentes",)])

    def test_additive_link_migration_is_repeatable_and_preserves_incident(self):
        self.incident()
        path = business_data.path_for(self.settings / "orphan.json")
        with closing(sqlite3.connect(path)) as db, db:
            before = db.execute("SELECT * FROM incidentes").fetchall()
            db.execute("DROP TABLE incident_replay_links")
        for _ in range(3):
            with closing(business_data.connect(self.settings / "orphan.json")) as db:
                self.assertEqual(db.execute("SELECT * FROM incidentes").fetchall(), before)
                self.assertEqual(db.execute("SELECT * FROM incident_replay_links").fetchall(), [("incident", "linked", "aaaaaaaa")])
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_unknown_database_schema_blocks_unreferenced_candidates(self):
        path = self.replay()
        with closing(sqlite3.connect(business_data.path_for(self.settings / "bad.json"))) as db:
            db.execute("CREATE TABLE other(id TEXT)")
        self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")

    def test_full_incident_history_not_limited_to_ui_rows(self):
        with closing(business_data.connect(self.settings / "orphan.json")) as db:
            for i in range(205):
                business_data.registrar_incidente(db, str(i), "aglomeracion", "z", None, 0, detalle={"sesion": f"{i:08x}"})
        refs = reference_paths(incident_references(self.settings), self.root)
        self.assertEqual(len(refs), 205)

    def test_live_wal_is_uncertain_and_planning_never_creates_or_changes_sidecars(self):
        path = self.replay()
        with closing(business_data.connect(self.settings / "wal.json")) as db:
            db.execute("PRAGMA journal_mode=WAL")
            business_data.registrar_incidente(db, "wal", "aglomeracion", "z", None, 0, detalle={"sesion": "aaaaaaaa"})
            before = self.snapshot()
            self.assertEqual(self.decision(self.plan(), path).reason, "uncertain_references")
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def test_reference_committed_after_plan_protects_replay_at_apply(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        self.incident()
        self.assertEqual(self.outcome(self.task.apply_cleanup(plan), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())

    def test_concurrent_reference_writer_prevents_apply_without_waiting(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        with ThreadPoolExecutor(max_workers=1) as pool, business_data.reference_lock:
            future = pool.submit(self.task.apply_cleanup, plan)
            self.incident()
            self.assertEqual(self.outcome(future.result(3), path)["reason"], "plan_changed")
        self.assertTrue(path.exists())
        self.assertEqual(self.decision(self.plan(), path).reason, "referenced_resource")

    def test_reference_added_during_delete_audit_is_rechecked(self):
        path = self.replay()
        plan = self.task.plan_cleanup(self.now, 30)
        audit = self.store.audit
        def add_reference(task, detail, now):
            audit(task, detail, now)
            if json.loads(detail)["decision"] == "delete_planned":
                self.incident()
        with patch.object(self.store, "audit", side_effect=add_reference):
            result = self.task.apply_cleanup(plan)
        self.assertEqual(self.outcome(result, path)["reason"], "delete_failed_or_changed")
        self.assertTrue(path.exists())

    def test_dispatch_holds_reference_guard_through_commit(self):
        self.engine.state.update(session="aaaaaaaa", t=10)
        register = business_data.registrar_incidente
        attempted = []
        def observe(*args, **kwargs):
            def acquire():
                held = business_data.reference_lock.acquire(blocking=False)
                if held:
                    business_data.reference_lock.release()
                return held
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempted.append(pool.submit(acquire).result(3))
            return register(*args, **kwargs)
        with patch.object(business_data, "registrar_incidente", side_effect=observe), patch.object(self.engine.mailer, "ready", return_value=False):
            self.engine.dispatch_alerts({"C": {"occupancy": {"episodes": [
                {"id": "E1", "zone": "Z", "start": 0, "duration": 10, "peak": 8}]}}}, {})
        self.assertEqual(attempted, [False])
        with closing(business_data.connect(self.engine.config_path)) as db:
            self.assertEqual(db.execute("SELECT resolution,session_id FROM incident_replay_links").fetchall(), [("linked", "aaaaaaaa")])


if __name__ == "__main__":
    unittest.main()
