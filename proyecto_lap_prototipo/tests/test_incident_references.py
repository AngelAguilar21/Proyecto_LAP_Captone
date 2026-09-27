import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import business_data
from automation_cleanup import incident_references, plan_cleanup


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "orphan.json"

    def test_all_incident_states_protect_replays_in_orphan_database(self):
        with closing(business_data.connect(self.path)) as db:
            for i, state in enumerate(("pendiente", "revisado", "resuelto", "falsa_alarma")):
                business_data.registrar_incidente(db, str(i), "equipaje", "z", None, 0,
                                                  detalle={"sesion": f"{i:08x}"})
                business_data.actualizar_estado_incidente(db, str(i), state)
        refs = incident_references(self.root)
        self.assertEqual({r["session"] for r in refs}, {f"{i:08x}" for i in range(4)})

    def test_legacy_read_does_not_create_migration_tables_or_change_database(self):
        path = business_data.path_for(self.path)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE incidentes (id TEXT, detalle TEXT)")
            db.execute("INSERT INTO incidentes VALUES ('legacy', ?)", (json.dumps({"sesion": "aaaaaaaa"}),))
        before = path.read_bytes()
        self.assertEqual(incident_references(self.root), [{"session": "aaaaaaaa"}])
        self.assertEqual(path.read_bytes(), before)

    def test_missing_or_corrupt_reference_is_not_treated_as_no_reference(self):
        with closing(business_data.connect(self.path)) as db:
            business_data.registrar_incidente(db, "unknown", "equipaje", "z", None, 0)
        with self.assertRaises(ValueError):
            incident_references(self.root)

    def test_repeatable_migration_keeps_original_ids_and_links(self):
        with closing(business_data.connect(self.path)) as db:
            business_data.registrar_incidente(db, "old-id", "equipaje", "z", None, 0,
                                              detalle={"sesion": "aaaaaaaa"})
            db.execute("DROP TABLE incident_replay_links")
            db.commit()
        for _ in range(3):
            with closing(business_data.connect(self.path)) as db:
                self.assertEqual(db.execute("SELECT * FROM incident_replay_links").fetchall(),
                                 [("old-id", "linked", "aaaaaaaa")])

    def test_wal_committed_reference_is_visible(self):
        with closing(business_data.connect(self.path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            business_data.registrar_incidente(db, "wal", "equipaje", "z", None, 0,
                                              detalle={"sesion": "bbbbbbbb"})
            self.assertEqual(incident_references(self.root), [{"session": "bbbbbbbb"}])

    def test_more_than_ui_limit_are_all_protected(self):
        with closing(business_data.connect(self.path)) as db:
            for i in range(205):
                business_data.registrar_incidente(db, str(i), "equipaje", "z", None, 0,
                                                  detalle={"sesion": f"{i:08x}"})
        self.assertEqual(len(incident_references(self.root)), 205)

    def test_unknown_database_schema_omits_otherwise_expired_replay(self):
        with closing(sqlite3.connect(business_data.path_for(self.path))) as db:
            db.execute("CREATE TABLE unrelated (id TEXT)")
        replay = self.root / "data" / "replays" / "aaaaaaaa"
        replay.mkdir(parents=True)
        (replay / "manifest.json").write_text(json.dumps(dict(session="aaaaaaaa", cameras=[], config={},
            status="ended", created="2020-01-01T00:00:00Z")))
        (replay / "samples.jsonl").write_text("")
        plan = plan_cleanup(self.root, self.root, datetime(2030,1,1,tzinfo=timezone.utc), 30)
        self.assertEqual(plan.decisions[0].reason, "uncertain_references")


if __name__ == "__main__":
    unittest.main()
