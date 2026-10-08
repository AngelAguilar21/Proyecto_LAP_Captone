import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from storage.archive_queue import ArchiveQueue
from storage.environment import load_environment


class StorageTests(unittest.TestCase):
    def test_enqueue_during_import_is_not_lost(self):
        with tempfile.TemporaryDirectory() as folder:
            def importer(*args, **kwargs):
                q.enqueue(folder, {'new': True})
                return {'ok': True}
            q = ArchiveQueue(Path(folder) / 'queue.sqlite', importer)
            q.enqueue(folder)
            q.run_once()
            self.assertEqual(q.status(), {'pending': 1, 'archived': 0})

    def test_failed_job_survives_restart_and_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'queue.sqlite'
            def fail(*args, **kwargs):
                raise ConnectionError('password=secret')
            q = ArchiveQueue(path, fail)
            q.enqueue(folder, {'count': 3})
            q.run_once()
            with q.connect() as db:
                self.assertEqual(db.execute('SELECT attempts,error,completed FROM jobs').fetchone(), (1,'ConnectionError',None))
                db.execute('UPDATE jobs SET due=0')
            calls = []
            def succeed(folder, insights):
                calls.append(insights)
                return {'ok': True}
            q = ArchiveQueue(path, succeed)
            self.assertTrue(q.run_once())
            self.assertFalse(q.run_once())
            self.assertEqual(calls, [{'count': 3}])

    def test_env_is_not_executable_and_respects_existing_environment(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            Path(folder, '.env').write_text('AEROTRACK_DB_PASSWORD=a@b\nPATH=bad\nAEROTRACK_TEST=file\n')
            os.environ['AEROTRACK_TEST'] = 'shell'
            load_environment(folder)
            self.assertNotIn('PATH', os.environ)
            self.assertEqual(os.environ['AEROTRACK_TEST'], 'shell')
            self.assertIn('a%40b@', os.environ['AEROTRACK_DATABASE_URL'])
