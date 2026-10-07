"""Pruebas optativas contra una base real: AEROTRACK_DATABASE_URL debe estar definida."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from storage.postgis import import_session


@unittest.skipUnless(os.environ.get('AEROTRACK_DATABASE_URL'), 'PostGIS no configurado en el entorno de pruebas')
class PostGISIntegrationTests(unittest.TestCase):
    def test_idempotence_geometry_and_transaction_rollback(self):
        import psycopg
        project = 'integration-' + uuid.uuid4().hex
        try:
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                meta = {'projectId': project, 'session':'test', 'created':'2026-10-07T00:00:00+00:00',
                        'status':'stopped', 'cameras':[{'id':'A','source':'secret'}]}
                sample = {'t':1, 'cameras':[{'id':'A','people':[{'id':'P1','point':[3,4]}]}]}
                (folder/'manifest.json').write_text(json.dumps(meta), encoding='utf-8')
                samples = folder/'samples.jsonl'
                samples.write_text(json.dumps(sample)+'\n', encoding='utf-8')
                import_session(folder)
                import_session(folder)
                with psycopg.connect(os.environ['AEROTRACK_DATABASE_URL']) as db:
                    self.assertEqual(db.execute('SELECT count(*),min(ST_X(position)),min(ST_SRID(position)) FROM aero_observations WHERE project_id=%s',(project,)).fetchone(), (1,3.,0))
                    self.assertNotIn('secret', str(db.execute('SELECT metadata FROM aero_sessions WHERE project_id=%s',(project,)).fetchone()))
                samples.write_text('{broken\n', encoding='utf-8')
                with self.assertRaises(ValueError):
                    import_session(folder)
                with psycopg.connect(os.environ['AEROTRACK_DATABASE_URL']) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM aero_observations WHERE project_id=%s',(project,)).fetchone()[0],1)
        finally:
            with psycopg.connect(os.environ['AEROTRACK_DATABASE_URL']) as db:
                db.execute('DELETE FROM aero_sessions WHERE project_id=%s',(project,))
