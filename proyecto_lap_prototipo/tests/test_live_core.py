"""Meaningful regression cases for live identity assignment and occupancy."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_server import default_config
from live_core import IdentityStore, Occupancy, calibration, project, validate_config


def obs(camera, local, x, y):
    return {"camera": camera, "local": local, "point": (x, y), "color": None}


class LiveCoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = default_config()
        self.cfg["clocksVerified"] = True

    def test_no_cross_camera_merging_without_clock_verification(self):
        self.cfg["clocksVerified"] = False
        rows = IdentityStore(self.cfg).update([obs("A", 1, 1, 1), obs("B", 1, 1, 1)], 0)
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def test_overlap_and_double_count_suppression(self):
        rows = IdentityStore(self.cfg).update([obs("A", 1, 1, 1), obs("B", 1, 1.05, 1)], 0)
        self.assertEqual(rows[0]["id"], rows[1]["id"])
        self.assertEqual(rows[1]["association"], "estimated")
        self.assertEqual(Occupancy(self.cfg).update(rows, 0)["mappedCount"], 1)

    def test_two_simultaneous_people_in_one_camera_do_not_share_id(self):
        store = IdentityStore(self.cfg)
        first = store.update([obs("A", 1, 1, 1)], 0)[0]["id"]
        rows = store.update([obs("B", 1, 1, 1), obs("B", 2, 1.1, 1)], .2)
        self.assertEqual(rows[0]["id"], first)
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def test_ambiguous_candidates_are_not_forcibly_merged(self):
        store = IdentityStore(self.cfg)
        old = store.update([obs("A", 1, 1, 1), obs("A", 2, 1.4, 1)], 0)
        row = store.update([obs("B", 1, 1.2, 1)], .2)[0]
        self.assertNotIn(row["id"], {p["id"] for p in old})
        self.assertEqual(row["association"], "uncertain")

    def test_non_overlap_handoff_uses_motion_and_time(self):
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1)], 0)[0]["id"]
        store.update([obs("A", 1, 2, 1)], 1)
        row = store.update([obs("B", 7, 3, 1)], 3)[0]
        self.assertEqual(row["id"], pid)
        self.assertEqual(row["association"], "estimated")

    def test_no_handoff_without_a_declared_camera_link(self):
        self.cfg["cameras"][0]["links"] = []
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1)], 0)[0]["id"]
        row = store.update([obs("B", 1, 1, 1)], 1)[0]
        self.assertNotEqual(row["id"], pid)

    def test_id_expires_after_handoff_window(self):
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1)], 0)[0]["id"]
        store.update([], 20)
        self.assertFalse(store.people)
        self.assertNotEqual(store.update([obs("B", 1, 1, 1)], 21)[0]["id"], pid)

    def test_ground_projection_and_degenerate_calibration(self):
        h = calibration([[0, 0, 0, 0], [1, 0, 12, 0], [1, 1, 12, 8], [0, 1, 0, 8]])
        p = project(h, .5, .5)
        self.assertAlmostEqual(p[0], 6)
        self.assertAlmostEqual(p[1], 4)
        with self.assertRaises(ValueError):
            calibration([[0, 0, 0, 0], [.2, 0, 1, 0], [.4, 0, 2, 0], [.6, 0, 3, 0]])

    def test_alert_requires_persistence_and_clears_when_empty(self):
        self.cfg.update(minPeople=2, dwell=2)
        store, occupancy = IdentityStore(self.cfg), Occupancy(self.cfg)
        rows = store.update([obs("A", 1, 1, 1), obs("A", 2, 1.1, 1)], 0)
        self.assertFalse(occupancy.update(rows, 0)["clusters"][0]["alert"])
        self.assertTrue(occupancy.update(rows, 2)["clusters"][0]["alert"])
        self.assertEqual(occupancy.update([], 3)["clusters"], [])

    def test_predictions_do_not_inflate_occupancy(self):
        occupancy = Occupancy(self.cfg)
        row = {"id": "P1", "point": [1, 1], "predicted": True}
        self.assertEqual(occupancy.update([row], 1)["mappedCount"], 0)

    def test_configuration_rejects_invalid_geometry_and_nonfinite_values(self):
        for patch in ({"radius": float("nan")}, {"width": 0}, {"minPeople": 2.5}, {"background": "javascript:bad"}):
            with self.assertRaises(ValueError):
                validate_config({**copy.deepcopy(self.cfg), **patch})


if __name__ == "__main__":
    unittest.main()
