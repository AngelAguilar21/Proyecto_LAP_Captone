"""Regresiones de continuidad temporal y separación de cámaras."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from following.tracker import BoxTracker
from following.flow import ZoneFlow


def sample(tracker, boxes, t, scores=None):
    scores = scores or [.9]*len(boxes)
    detections = [SimpleNamespace(confianza=s) for s in scores]
    return tracker.update(detections, boxes, t, (480, 640))


class FollowingTests(unittest.TestCase):
    def test_zone_crossings_ignore_initial_presence_jitter_and_loss(self):
        flow = ZoneFlow({"zones": [{"name": "Tienda", "points": [[0,0],[2,0],[2,2],[0,2]]}]})
        def observe(x, t):
            return flow.update([{"id": "P1", "point": [x, 1]}], t)[0]
        self.assertEqual(observe(1, 0)["entries"], 0)
        observe(3, .2)
        self.assertEqual(observe(1, .4)["exits"], 0)
        observe(3, .6)
        self.assertEqual(observe(3, .8)["exits"], 1)
        observe(1, 1)
        self.assertEqual(observe(1, 1.2)["entries"], 1)
        flow.update([], 4)
        self.assertEqual(observe(3, 5)["exits"], 1)

    def test_reordered_detections_keep_identity_and_box(self):
        tracker = BoxTracker()
        a, b = [20, 20, 60, 120], [200, 20, 240, 120]
        first = sample(tracker, [a, b], 0)
        second = sample(tracker, [b, a], .2)
        self.assertEqual({p.id: p.box for p in first}, {p.id: p.box for p in second})
        self.assertEqual(len({tuple(p.box) for p in second}), 2)

    def test_occlusion_does_not_publish_invisible_people(self):
        tracker = BoxTracker()
        box = [20, 20, 60, 120]
        first = sample(tracker, [box], 0)[0]
        self.assertEqual(sample(tracker, [], .2), [])
        recovered = sample(tracker, [box], .4)
        self.assertEqual(recovered[0].id, first.id)

    def test_low_score_recovers_existing_track_only(self):
        tracker = BoxTracker()
        box = [20, 20, 60, 120]
        first = sample(tracker, [box], 0)[0]
        weak = sample(tracker, [box, [300, 20, 350, 120]], .2, [.2, .2])
        self.assertEqual([p.id for p in weak], [first.id])

    def test_camera_states_independent(self):
        a, b = BoxTracker(), BoxTracker()
        box = [20, 20, 60, 120]
        first = sample(a, [box], 0)[0]
        sample(b, [[400, 20, 450, 120]], 0)
        sample(b, [], .2)
        self.assertEqual(sample(a, [box], .2)[0].id, first.id)

    def test_long_gap_does_not_reuse_old_identity(self):
        tracker = BoxTracker()
        box = [20, 20, 60, 120]
        first = sample(tracker, [box], 0)[0]
        sample(tracker, [box], 9)
        second = sample(tracker, [box], 9.2)[0]
        self.assertNotEqual(second.id, first.id)


if __name__ == "__main__":
    unittest.main()
