import copy
import sys
import unittest
import tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from identity.topology import validate_routes, allowed_pair, allowed_groups
from identity.engine import registro_desde_config
from identity.regroup import ReagrupadorPlano
from storage.postgis import observation_rows
from test_identity_engine import config
from test_appearance_memory import memoria_ram, asociador, A
from test_identity_core import Escena


class FoundationTests(unittest.TestCase):
    def test_mixed_sources_fail_before_opening_cameras(self):
        import json
        from unittest.mock import patch
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from live_server import Engine
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            c = config()
            c['cameras'][0]['source'] = 'video.mp4'
            c['cameras'][1]['source'] = 'https://example.com/live.m3u8'
            path.write_text(json.dumps(c), encoding='utf-8')
            engine = Engine(path)
            with patch.object(engine, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'mezclar'):
                    engine.start({'detector':'yolo','cameraIds':[x['id'] for x in c['cameras']]})
                run.assert_not_called()

    def test_camera_chain_does_not_need_a_direct_shortcut(self):
        a = {'camara':'A','t0':0,'t1':2}
        b = {'camara':'B','t0':4,'t1':6}
        c = {'camara':'C','t0':8,'t1':10}
        edges = {('A','B'):{'t_min_s':1,'t_max_s':3}, ('B','C'):{'t_min_s':1,'t_max_s':3}}
        self.assertTrue(allowed_groups([a,b], [c], edges, set()))
        self.assertFalse(allowed_groups([a], [c], edges, set()))

    def test_invalid_saved_config_cannot_start_demo_sources_silently(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from live_server import Engine
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.json'
            path.write_text('{broken', encoding='utf-8')
            engine = Engine(path)
            with self.assertRaisesRegex(ValueError, 'configuración'):
                engine.start({'detector': 'yolo'})

    def test_floor_validation_does_not_treat_project_routes_as_floor_cameras(self):
        from live_core import validate_config
        c = config(cameraRoutes=[{'from': 'A', 'to': 'B', 'kind': 'overlap', 'minSeconds': 0, 'maxSeconds': 12}])
        c['plans'] = {'custom': {k: c[k] for k in ('width','height','unit','background','zones')}}
        self.assertEqual(len(validate_config(c)['cameraRoutes']), 1)

    def test_explicit_routes_override_legacy_links_and_extend_window(self):
        c = config(cameraRoutes=[{'from': 'A', 'to': 'B', 'kind': 'transition', 'minSeconds': 8, 'maxSeconds': 600}])
        r = registro_desde_config(c)
        self.assertEqual([(t['from'], t['to']) for t in r['transitions']], [('A', 'B')])
        self.assertEqual(r['overlaps'], [])
        self.assertGreaterEqual(r['association']['candidate_window_s'], 600)
        c['clocksVerified'] = False
        self.assertEqual(registro_desde_config(c)['transitions'], [])

    def test_empty_graph_disables_legacy_associations(self):
        self.assertEqual(registro_desde_config(config(cameraRoutes=[]))['transitions'], [])

    def test_routes_reject_unknown_duplicate_nan_and_negative(self):
        route = {'from': 'A', 'to': 'B', 'kind': 'transition', 'minSeconds': 0, 'maxSeconds': 30}
        for bad in ({'to': 'missing'}, {'minSeconds': -1}, {'maxSeconds': float('nan')}, {'kind': 'unknown'}):
            with self.assertRaises(ValueError):
                validate_routes(config(cameraRoutes=[{**route, **bad}]))
        with self.assertRaises(ValueError):
            validate_routes(config(cameraRoutes=[route, copy.copy(route)]))

    def test_final_regroup_does_not_join_identical_embeddings_across_disconnected_cameras(self):
        tracks = [{'uid': 'a', 'camera': 'A', 'gid': 1, 'inicio': 0, 'fin': 4, 'muestras': 10},
                  {'uid': 'b', 'camera': 'B', 'gid': 2, 'inicio': 10, 'fin': 14, 'muestras': 10}]
        vectors = {x: np.array([1., 0.]) for x in ('a', 'b')}
        gate = lambda a, b: allowed_pair(a, b, {}, set())
        result = ReagrupadorPlano(usar_posicion=False, pair_gate=gate)(tracks, {}, vectors)
        self.assertEqual(result['personas'], 2)
        transitions = {('A', 'B'): {'t_min_s': 5, 't_max_s': 9}}
        gate = lambda a, b: allowed_pair(a, b, transitions, set())
        result = ReagrupadorPlano(usar_posicion=False, pair_gate=gate)(tracks, {}, vectors)
        self.assertEqual(result['personas'], 1)

    def test_memory_cannot_bypass_disconnected_cameras(self):
        memory = memoria_ram()
        first = Escena(asociador(memory)).ver(4, {'c1': [(1, A, 300)]})[('c1', 1)]
        second = Escena(asociador(memory, camaras=('c9',))).ver(4, {'c9': [(1, A, 300)]})[('c9', 1)]
        self.assertNotEqual(first, second)

    def test_postgis_rows_keep_floor_time_and_missing_geometry(self):
        meta = {'session': 'abc', 'projectId': 'p1', 'cameras': [{'id': 'A', 'planId': 'lap-3'}]}
        samples = [{'t': 1.2, 'cameras': [{'id': 'A', 'people': [{'id': 'P1', 'point': [2, 3]}, {'id': 'T1', 'point': None}]}]}]
        rows = list(observation_rows(meta, samples))
        self.assertEqual(rows[0][5:9], ('lap-3', 'P1', 1.2, True))
        self.assertEqual(rows[0][-1], 'POINT(2.0 3.0)')
        self.assertIsNone(rows[1][-1])
        self.assertFalse(rows[1][8])

if __name__ == '__main__':
    unittest.main()
