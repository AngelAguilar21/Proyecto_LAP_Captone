import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from replay import report_snapshot


class SavedReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / 'data' / 'replays' / 'abcd1234'
        self.folder.mkdir(parents=True)
        self.meta = {'session': 'abcd1234', 'projectId': 'principal',
                     'status': 'ended', 'module': 'unified', 'end': 20,
                     'config': {'planId': 'lap-3', 'testRun': True},
                     'cameras': [{'id': 'one'}, {'id': 'two'}],
                     'cameraAnalytics': {'one': {'occupancy': {'peak': 9}},
                                         'two': {'occupancy': {'peak': 3}}},
                     'reportAnalytics': {'zones': [{'id': 'saved'}]}}
        self.write()
        (self.folder / 'samples.jsonl').write_text(
            json.dumps({'t': 0, 'cameras': [{'id': 'one', 'people': [{}]}]})+'\n'+
            json.dumps({'t': 20, 'cameras': [{'id': 'two', 'people': [{}, {}]}]}),
            encoding='utf-8')

    def write(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.meta), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_keeps_results_of_camera_that_finished_earlier(self):
        config, state, _ = report_snapshot(self.root, 'abcd1234', 'principal')
        self.assertEqual(len(config['cameras']), 2)
        self.assertEqual(state['cameraAnalytics']['one']['occupancy']['peak'], 9)
        self.assertEqual(state['analytics']['zones'][0]['id'], 'saved')
        self.assertEqual([s['count'] for s in state['series']], [1, 2])
        self.assertTrue(state['testRun'])

    def test_rejects_other_project_and_active_session(self):
        with self.assertRaises(ValueError):
            report_snapshot(self.root, 'abcd1234', 'other')
        self.meta['status'] = 'running'
        self.write()
        with self.assertRaises(ValueError):
            report_snapshot(self.root, 'abcd1234', 'principal')
