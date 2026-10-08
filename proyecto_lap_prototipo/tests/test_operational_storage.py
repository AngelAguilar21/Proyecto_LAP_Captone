import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from storage import operational as op
import auth
import business_data as business
import commercial
import projects
from migrar_operativo import migrate


class TranslationTests(unittest.TestCase):
    def test_parameters_and_literals(self):
        self.assertEqual(op.translate("SELECT '?' WHERE a=?"), "SELECT '?' WHERE a=%s")
        self.assertIn('ON CONFLICT DO NOTHING', op.translate('INSERT OR IGNORE INTO negocios VALUES (?)'))
        self.assertIn('ON CONFLICT (negocio_id,fecha,hora,dataset) DO UPDATE', op.translate('INSERT OR REPLACE INTO commercial_sales VALUES (?,?,?,?,?,?,?)'))
        with self.assertRaises(ValueError):
            op.translate('INSERT OR REPLACE INTO unknown VALUES (?)')


@unittest.skipUnless(os.environ.get('AEROTRACK_DATABASE_URL'), 'PostgreSQL no configurado')
class OperationalIntegrationTests(unittest.TestCase):
    def test_memory_moves_to_postgresql_and_reopens_without_sqlite(self):
        import hashlib
        import time
        import numpy as np
        from identity.memory import MemoriaApariencia
        from psycopg import sql
        installation = uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            path=root/'data'/'memory.sqlite'
            memory=MemoriaApariencia(path,dimension=4,encoder='test')
            pid=memory.nueva(time.time())
            memory.sumar(pid,np.ones(4),1,'A',time.time())
            memory.cerrar()
            schema='aero_m_'+hashlib.sha256((installation+':data/memory.sqlite:test:4').encode()).hexdigest()[:24]
            try:
                with patch.object(op,'_root',root), patch.object(op,'_installation',installation):
                    migrated=MemoriaApariencia(path,dimension=4,encoder='test')
                    self.assertEqual(migrated.backend,'PostgreSQL')
                    self.assertIn(pid,migrated.personas)
                    migrated.sumar(pid,np.ones(4),1,'B',time.time())
                    migrated.cerrar()
                    reopened=MemoriaApariencia(path,dimension=4,encoder='test')
                    self.assertEqual(reopened.personas[pid].muestras,2)
                    self.assertEqual(reopened.personas[pid].camaras,{'A','B'})
                    reopened.cerrar()
            finally:
                with op.connect_db() as db:
                    db.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))

    def test_existing_commercial_contracts_on_postgres(self):
        from psycopg import sql
        import test_commercial
        import test_business_management
        import test_business_catalog
        installation = uuid.uuid4().hex
        schemas = set()
        def connection(path):
            schema = op.schema_for(installation, str(path))
            schemas.add(schema)
            db = op.connect_db()
            con = op.prepare_business(db, installation, str(path))
            db.commit()
            return con
        result = unittest.TestResult()
        try:
            with patch.object(business, 'connect', side_effect=connection):
                for module in (test_commercial, test_business_management, test_business_catalog):
                    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
                    for group in suite:
                        for test in group:
                            # Este caso construye deliberadamente un SQLite antiguo:
                            # se cubre por la suite SQLite y la migración, no por PG.
                            if test._testMethodName != 'test_legacy_database_gets_company_default':
                                test.run(result)
            self.assertTrue(result.wasSuccessful(), str(result.errors + result.failures))
            self.assertGreater(result.testsRun, 10)
        finally:
            with op.connect_db() as db:
                for schema in schemas:
                    db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

    def test_migrate_and_use_without_local_fallback(self):
        from psycopg import sql
        installation = None
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'config'
            auth.crear(config, 'test', 'password-test', 'operador')
            pid = projects.create(root, 'Prueba', {'cameras': [], 'airport': 'Ñandú'})
            path = projects.project_path(root, pid)
            con = business.connect(path)
            business.crear_negocio(con, 'shop', 'Café')
            business.cargar_ventas(con, [('shop', '2026-10-07', 10, 123.45)])
            commercial.setup(con)
            con.close()
            try:
                report = migrate(root)
                installation = report['installation']
                self.assertEqual(report['projects'][pid]['ventas'], 1)
                op.configure(root)
                self.assertEqual(auth.verificar(config, 'test', 'password-test'), 'operador')
                self.assertEqual(projects.read_document(path)['airport'], 'Ñandú')
                # Cambiar un archivo obsoleto no afecta la fuente de verdad.
                path.write_text('{}', encoding='utf-8')
                self.assertEqual(projects.read_document(path)['airport'], 'Ñandú')
                auth.cambiar_clave(config, 'test', 'password-new')
                self.assertIsNone(auth.verificar(config, 'test', 'password-test'))
                self.assertEqual(auth.verificar(config, 'test', 'password-new'), 'operador')
                projects.rename(root, pid, 'Otro')
                self.assertEqual(projects.listing(root)['projects'][0]['name'], 'Otro')
                con = business.connect(path)
                try:
                    commercial.setup(con)
                    self.assertEqual(business.listar_negocios(con)[0]['nombre'], 'Café')
                    business.cargar_ventas(con, [('shop', '2026-10-07', 11, 20)])
                    self.assertEqual(con.execute('SELECT COUNT(DISTINCT id) FROM ventas').fetchone()[0], 2)
                    business.registrar_trafico(con, 'zone', '2026-10-07', 10, 2, 4)
                    business.registrar_trafico(con, 'zone', '2026-10-07', 10, 2, 7)
                    self.assertEqual(business.promedio_historico(con, 'zone', 10, 2)['picoHistorico'], 7)
                    with con:
                        con.execute('INSERT OR REPLACE INTO commercial_imports VALUES (?,?,?,?,?)', ('x','x.csv','demo',1,'today'))
                        con.execute('INSERT OR REPLACE INTO commercial_imports VALUES (?,?,?,?,?)', ('x','x.csv','demo',2,'today'))
                    self.assertEqual(con.execute('SELECT filas FROM commercial_imports WHERE id=?', ('x',)).fetchone()[0], 2)
                    with self.assertRaises(RuntimeError):
                        with con:
                            con.execute('DELETE FROM ventas')
                            raise RuntimeError('rollback')
                    self.assertEqual(con.execute('SELECT COUNT(*) FROM ventas').fetchone()[0], 2)
                finally:
                    con.close()
                with patch.object(op, 'connect_db', side_effect=RuntimeError('offline')):
                    with self.assertRaises(RuntimeError):
                        auth.hay_usuarios(config)
                with self.assertRaises(ValueError):
                    migrate(root)
            finally:
                op._root = op._installation = None
                if installation:
                    with op.connect_db() as db:
                        db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(op.schema_for(installation, pid))))
                        db.execute('DELETE FROM public.aero_documents WHERE installation=%s', (installation,))


if __name__ == '__main__':
    unittest.main()
