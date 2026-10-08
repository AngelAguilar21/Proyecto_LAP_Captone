"""Additive migration and irreversible human review, in temporary SQLite."""
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import business_data
import commercial


class IncidentHistoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="history-test-")
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "project.json"
        self.clock = self.enterContext(patch.object(business_data, "time", Mock()))
        self.clock.time.return_value = 1000.

    def legacy(self, state="pendiente"):
        db = sqlite3.connect(business_data.path_for(self.path))
        self.addCleanup(db.close)
        db.executescript(business_data.ESQUEMA)
        db.execute("DROP TABLE incident_replay_links")  # absent in the actual pre-migration schema
        db.executescript(business_data.NEGOCIOS_ESQUEMA)
        db.execute("INSERT INTO incidentes VALUES ('legacy','aglomeracion','zone','C',0,8,10,?,'{}',100,200)", (state,))
        db.commit()
        return db

    def connect(self):
        db = business_data.connect(self.path)
        self.addCleanup(db.close)
        return db

    def create(self, db):
        business_data.registrar_incidente(db, "new", "aglomeracion", "zone", "C", 0)

    def row(self, db, iid="new"):
        return next(r for r in business_data.listar_incidentes(db) if r["id"] == iid)

    def test_new_incident_has_known_unreviewed_history_and_reobservations_preserve_it(self):
        db = self.connect()
        self.create(db)
        first = self.row(db)
        self.assertTrue(first["review_history_known"])
        for field in ("reviewed_at", "history_validated_at", "escalated_at"):
            self.assertIsNone(first[field])
        self.clock.time.return_value = 2000.
        self.create(db)
        self.assertEqual(self.row(db), first)

    def test_all_attention_states_record_first_review_and_never_clear_it(self):
        db = self.connect()
        for state in ("revisado", "resuelto", "falsa_alarma"):
            with self.subTest(state=state):
                business_data.registrar_incidente(db, state, "aglomeracion", "zone", "C", 0)
                self.clock.time.return_value = 2000.
                business_data.actualizar_estado_incidente(db, state, state)
                self.clock.time.return_value = 3000.
                business_data.actualizar_estado_incidente(db, state, "pendiente")
                business_data.registrar_incidente(db, state, "aglomeracion", "zone", "C", 0)
                business_data.actualizar_estado_incidente(db, state, "resuelto")
                self.assertEqual(self.row(db, state)["reviewed_at"], 2000.)
                self.assertTrue(self.row(db, state)["review_history_known"])
                self.assertIsNone(self.row(db, state)["history_validated_at"])

    def test_legacy_unknown_is_not_inferred_from_any_existing_state(self):
        db = self.legacy()
        for state in ("revisado", "resuelto", "falsa_alarma"):
            db.execute("INSERT INTO incidentes SELECT ?,tipo,zona,camara_id,inicio,pico,duracion,?,detalle,creado,actualizado "
                       "FROM incidentes WHERE id='legacy'", (state, state))
        db.commit()
        db = self.connect()
        for row in business_data.listar_incidentes(db):
            self.assertFalse(row["review_history_known"])
            self.assertIsNone(row["reviewed_at"])
            self.assertIsNone(row["history_validated_at"])
        business_data.actualizar_estado_incidente(db, "legacy", "pendiente")
        self.assertFalse(self.row(db, "legacy")["review_history_known"])
        self.assertEqual(business_data.incidentes_para_escalar(db, 10000), [])

    def test_validating_never_attended_does_not_count_as_attention(self):
        self.legacy()
        db = self.connect()
        business_data.validar_historial_incidente(db, "legacy", True)
        row = self.row(db, "legacy")
        self.assertTrue(row["review_history_known"])
        self.assertEqual(row["history_validated_at"], 1000.)
        self.assertEqual(row["estado"], "pendiente")
        self.assertIsNone(row["reviewed_at"])
        self.assertEqual([r[0] for r in business_data.incidentes_para_escalar(db, 10000)], ["legacy"])

    def test_validating_attended_marks_review_and_excludes_future_pending(self):
        self.legacy()
        db = self.connect()
        business_data.validar_historial_incidente(db, "legacy", False)
        row = self.row(db, "legacy")
        self.assertEqual((row["estado"], row["reviewed_at"], row["history_validated_at"]), ("revisado", 1000., 1000.))
        business_data.actualizar_estado_incidente(db, "legacy", "pendiente")
        self.assertEqual(business_data.incidentes_para_escalar(db, 10000), [])
        self.assertEqual(self.row(db, "legacy")["reviewed_at"], 1000.)

    def test_legacy_validation_requires_boolean_and_rejects_repeated_or_new_history(self):
        self.legacy()
        db = self.connect()
        original = list(db.iterdump())
        for value in (None, 0, 1, "true", "false", [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                business_data.validar_historial_incidente(db, "legacy", value)
            self.assertEqual(list(db.iterdump()), original)
        business_data.validar_historial_incidente(db, "legacy", True)
        self.create(db)
        original = list(db.iterdump())
        for iid in ("legacy", "new", "absent"):
            for decision in (True, False):
                with self.subTest(iid=iid, decision=decision), self.assertRaises(ValueError):
                    business_data.validar_historial_incidente(db, iid, decision)
                self.assertEqual(list(db.iterdump()), original)

    def test_attended_validation_cannot_be_reversed_by_second_validation(self):
        self.legacy()
        db = self.connect()
        business_data.validar_historial_incidente(db, "legacy", False)
        business_data.actualizar_estado_incidente(db, "legacy", "pendiente")
        for value in (True, False):
            with self.assertRaises(ValueError):
                business_data.validar_historial_incidente(db, "legacy", value)
        self.assertEqual(self.row(db, "legacy")["reviewed_at"], 1000.)

    def test_never_attended_assertion_rejects_nonpending_legacy(self):
        self.legacy("resuelto")
        db = self.connect()
        with self.assertRaises(ValueError):
            business_data.validar_historial_incidente(db, "legacy", True)
        self.assertFalse(self.row(db, "legacy")["review_history_known"])
        business_data.validar_historial_incidente(db, "legacy", False)
        self.assertEqual(self.row(db, "legacy")["reviewed_at"], 1000.)

    def test_concurrent_human_decisions_only_accept_one(self):
        self.legacy()
        self.connect()
        gate = threading.Barrier(2)
        def decide(value):
            with closing(business_data.connect(self.path)) as db:
                gate.wait(5)
                try:
                    business_data.validar_historial_incidente(db, "legacy", value)
                    return True
                except ValueError:
                    return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, [True, False]))
        self.assertEqual(sorted(results), [False, True])

    def test_additive_repeatable_migration_preserves_all_modern_tables_and_rows(self):
        db = self.legacy()
        commercial.setup(db)
        business_data.crear_negocio(db, "shop", "Synthetic", "C", "door", empresa="Synthetic company")
        business_data.cargar_ventas(db, [("shop", "2026-09-01", 9, 10)], origen="synthetic")
        with db:
            db.execute("INSERT INTO negocio_ubicaciones VALUES ('shop','plan',1,2)")
            db.execute("INSERT INTO negocio_puertas VALUES ('shop','C','door')")
            db.execute("INSERT INTO negocio_referencias VALUES ('shop','synthetic','poi')")
            db.execute("INSERT INTO negocio_estados VALUES ('shop','cerrado')")
            db.execute("INSERT INTO commercial_sales VALUES ('shop','2026-09-01',9,10,1,'demo','import')")
            db.execute("INSERT INTO commercial_imports VALUES ('import','synthetic.csv','demo',1,'2026-09-01')")
            db.execute("INSERT INTO commercial_traffic VALUES ('session','shop','2026-09-01',9,2,1,60,'demo')")
            db.execute("INSERT INTO commercial_incidents VALUES ('ci','shop','2026-09-01',5,8,'demo')")
            db.execute("INSERT INTO commercial_bags VALUES ('cb','session','shop',1,1,0,0.95,'synthetic','demo')")
            db.execute("INSERT INTO trafico_historico(zona,fecha,hora,dia_semana) VALUES ('zone','2026-09-01',9,1)")
            db.execute("INSERT INTO incident_notifications VALUES ('legacy','original','sent',1,100,150,NULL,'old')")
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before = {t: (db.execute(f'PRAGMA table_info({t})').fetchall(), db.execute(f'SELECT * FROM {t}').fetchall()) for t in tables}
        migrated = None
        for _ in range(3):
            with closing(business_data.connect(self.path)) as current:
                for table, (schema, rows) in before.items():
                    fields = ','.join(f'"{r[1]}"' for r in schema)
                    self.assertEqual(current.execute(f'SELECT {fields} FROM {table}').fetchall(), rows)
                    self.assertEqual(current.execute(f'PRAGMA table_info({table})').fetchall()[:len(schema)], schema)
                dump = list(current.iterdump())
                if migrated is not None:
                    self.assertEqual(dump, migrated)
                migrated = dump
                self.assertEqual(current.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
                self.assertEqual(current.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_concurrent_migration_is_idempotent(self):
        self.legacy()
        gate = threading.Barrier(2)
        def migrate(_):
            gate.wait(5)
            with closing(business_data.connect(self.path)) as db:
                return self.row(db, "legacy")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(migrate, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertFalse(results[0]["review_history_known"])


if __name__ == "__main__":
    unittest.main()
