"""Memoria de identidad temporal: persistencia, retención y estatura estimada."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from live_server import default_config
from live_core import IdentityStore, estimate_height, height_penalty
from identity_memory import IdentityMemory, clamp_retention, decode_signature, encode_signature


def person(pid, x, y, camera='A', box=(10, 20, 30, 80)):
    return {'id': pid, 'camera': camera, 'point': (x, y), 'association': 'local', 'box': box, 'velocity': (.3, .4)}


class FakeStore:
    def __init__(self):
        self.people = {'P00001': {'color': np.linspace(0, 1, 8, dtype=np.float32), 'height': 1.71}}


class IdentityMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'identidad' / 'p.sqlite'
        self.memory = IdentityMemory(self.path, retention_hours=24, sample_interval=1.0)

    def tearDown(self):
        self.memory.close()
        self.directory.cleanup()

    def test_signature_round_trip_keeps_shape_and_values(self):
        original = np.linspace(0, 1, 16, dtype=np.float32)
        restored = decode_signature(encode_signature(original))
        self.assertEqual(restored.shape, original.shape)
        self.assertTrue(np.allclose(restored, original, atol=1e-3))
        self.assertIsNone(encode_signature(None))

    def test_stores_position_clothing_and_physical_attributes(self):
        stored = self.memory.record('s1', [person('P00001', 2., 3.)], FakeStore(), 0., now=1000.)
        self.assertEqual(stored, 1)
        camera, t, x, y, association, height = self.memory.trajectory('s1', 'P00001')[0]
        self.assertEqual((camera, x, y, association, height), ('A', 2., 3., 'local', 1.71))
        summary = self.memory.summary('s1')
        self.assertEqual((summary['people'], summary['withColor'], summary['withHeight']), (1, 1, 1))
        row = self.memory.con.execute('SELECT box_w, box_h, speed FROM identity_observations').fetchone()
        self.assertEqual(row[:2], (20., 60.))
        self.assertAlmostEqual(row[2], .5)

    def test_samples_at_most_once_per_interval_per_person(self):
        store = FakeStore()
        counts = [self.memory.record('s1', [person('P00001', 1., 1.)], store, t, now=1000.) for t in (0., .3, .9, 1.0, 1.4, 2.1)]
        self.assertEqual(counts, [1, 0, 0, 1, 0, 1])

    def test_skips_people_without_position_or_predicted(self):
        people = [{**person('P00001', 0, 0), 'point': None}, {**person('P00002', 1, 1), 'predicted': True}]
        self.assertEqual(self.memory.record('s1', people, FakeStore(), 0., now=1000.), 0)

    def test_schema_has_no_identity_or_image_columns(self):
        columns = {row[1] for row in self.memory.con.execute('PRAGMA table_info(identity_observations)')}
        self.assertFalse(columns & {'name', 'nombre', 'face', 'rostro', 'image', 'imagen', 'photo', 'email', 'dni'})

    def test_purge_removes_only_rows_older_than_retention(self):
        store = FakeStore()
        self.memory.record('old', [person('P00001', 0, 0)], store, 0., now=1000.)
        self.memory.record('new', [person('P00001', 0, 0)], store, 0., now=1000. + 23 * 3600)
        removed = self.memory.purge(now=1000. + 25 * 3600)
        self.assertEqual(removed, 1)
        self.assertEqual(self.memory.summary('old')['rows'], 0)
        self.assertEqual(self.memory.summary('new')['rows'], 1)

    def test_purge_all_erases_everything(self):
        self.memory.record('s1', [person('P00001', 0, 0)], FakeStore(), 0., now=1000.)
        self.assertEqual(self.memory.purge_all(), 1)
        self.assertEqual(self.memory.summary('s1')['rows'], 0)

    def test_periodic_purge_runs_during_recording(self):
        self.memory._last_purge = 0.
        self.memory.record('s1', [person('P00001', 0, 0)], FakeStore(), 0., now=1000.)
        self.memory.record('s2', [person('P00001', 0, 0)], FakeStore(), 0., now=1000. + 30 * 3600)
        self.assertEqual(self.memory.summary('s1')['rows'], 0)

    def test_disk_failure_disables_memory_without_raising(self):
        self.memory.con.close()
        self.assertEqual(self.memory.record('s1', [person('P00001', 0, 0)], FakeStore(), 0., now=1000.), 0)
        self.assertFalse(self.memory.enabled)
        self.assertEqual(self.memory.record('s1', [person('P00001', 0, 0)], FakeStore(), 5., now=1000.), 0)
        self.memory.con = sqlite3.connect(':memory:')

    def test_retention_is_clamped_and_tolerates_bad_values(self):
        self.assertEqual(clamp_retention(0), 1)
        self.assertEqual(clamp_retention(9999), 168)
        self.assertEqual(clamp_retention('x'), 24)
        self.assertEqual(clamp_retention(None), 24)


class HeightTests(unittest.TestCase):
    def camera(self):
        # x=10u, y=10(1-v): el suelo se ve con y creciente hacia arriba de la imagen.
        h = np.array([[10., 0, 0], [0, -10., 10.], [0, 0, 1.]])
        return {'h': h, 'x': 5., 'y': 0., 'height': 3.4, 'headPoints': False}

    def test_estimates_known_height_from_full_box(self):
        # Persona de 1,7 m a 4 m de la cámara: pies en y=4, cabeza proyectada en y=8.
        estimate = estimate_height(self.camera(), (45, 20, 55, 60), 100, 100)
        self.assertAlmostEqual(estimate, 1.7, places=2)

    def test_returns_none_when_box_touches_frame_edge_or_is_missing(self):
        self.assertIsNone(estimate_height(self.camera(), (45, 0, 55, 60), 100, 100))
        self.assertIsNone(estimate_height(self.camera(), (45, 20, 55, 100), 100, 100))
        self.assertIsNone(estimate_height(self.camera(), None, 100, 100))

    def test_returns_none_for_head_point_detectors_and_missing_calibration(self):
        self.assertIsNone(estimate_height({**self.camera(), 'headPoints': True}, (45, 20, 55, 60), 100, 100))
        self.assertIsNone(estimate_height({**self.camera(), 'h': None}, (45, 20, 55, 60), 100, 100))
        self.assertIsNone(estimate_height({**self.camera(), 'height': 0}, (45, 20, 55, 60), 100, 100))

    def test_implausible_heights_are_discarded(self):
        self.assertIsNone(estimate_height({**self.camera(), 'height': 9.}, (45, 20, 55, 60), 100, 100))

    def test_penalty_is_zero_without_data_small_within_tolerance_and_capped(self):
        self.assertEqual(height_penalty({}, {'height': 1.7}), 0.)
        self.assertEqual(height_penalty({'height': 1.7}, {'height': 1.75}), 0.)
        self.assertGreater(height_penalty({'height': 1.6}, {'height': 1.9}), 0.)
        self.assertEqual(height_penalty({'height': 1.0}, {'height': 2.4}), .25)


class StoreHeightTests(unittest.TestCase):
    def setUp(self):
        self.cfg = default_config()
        self.cfg['clocksVerified'] = True

    def test_store_keeps_median_height_and_publishes_it(self):
        store = IdentityStore(self.cfg)
        for step, height in enumerate((1.70, 1.72, 2.30, 1.71)):
            rows = store.update([{'camera': 'A', 'local': 1, 'point': (1 + step * .1, 1), 'color': None, 'height': height}], step * .2)
        gid = rows[0]['id']
        self.assertAlmostEqual(store.people[gid]['height'], 1.72)
        self.assertAlmostEqual(rows[0]['height'], 1.72)

    def test_height_helps_pick_the_right_candidate_between_cameras(self):
        store = IdentityStore(self.cfg)
        tall = {'camera': 'A', 'local': 1, 'point': (2.0, 2.0), 'color': None, 'height': 1.95}
        short = {'camera': 'A', 'local': 2, 'point': (2.1, 2.0), 'color': None, 'height': 1.45}
        first = store.update([tall, short], 0)
        tall_id = first[0]['id']
        arrival = {'camera': 'B', 'local': 7, 'point': (2.05, 2.0), 'color': None, 'height': 1.94}
        rows = store.update([{**tall, 'point': (2.0, 2.0)}, {**short, 'point': (2.1, 2.0)}, arrival], .2)
        self.assertEqual(rows[2]['id'], tall_id)


if __name__ == '__main__':
    unittest.main()
