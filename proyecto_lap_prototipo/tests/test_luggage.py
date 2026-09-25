"""Public luggage monitoring with synthetic detections and controlled time."""
import sys
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from following.luggage import LuggageWatch


class LuggageTests(unittest.TestCase):
    def setUp(self):
        self.camera = {"id": "enabled", "luggageWatch": True,
                       "luggageDwell": 10, "luggageInterval": 2}
        self.disabled_camera = {**self.camera, "id": "disabled", "luggageWatch": False}
        executor = self.enterContext(patch("following.luggage.ThreadPoolExecutor"))
        self.pool = executor.return_value
        self.pool.submit.side_effect = self.complete_immediately
        self.watch = LuggageWatch([self.camera, self.disabled_camera])
        self.addCleanup(self.watch.close)
        self.detect = self.enterContext(patch.object(self.watch, "_detect"))
        # Inference is mocked, so no image library or real frame is needed.
        self.frame = Mock(name="synthetic_frame")

    @staticmethod
    def complete_immediately(function, *args):
        future = Future()
        future.set_result(function(*args))
        return future

    @staticmethod
    def bag(x=0.1):
        return {"box": [x, 0.1, x + 0.2, 0.3], "kind": "maleta"}

    def observe_detections(self, t, found):
        self.detect.return_value = (self.camera["id"], found, t)
        calls_before = self.detect.call_count
        self.watch.observe(self.camera, self.frame, t)
        # A second observation collects the completed Future. The same timestamp
        # prevents scheduling another scan; tracking itself is not mocked.
        result = self.watch.observe(self.camera, self.frame, t)
        self.assertEqual(self.detect.call_count, calls_before + 1)
        self.assertIsNone(result["error"])
        return result

    def test_stationary_luggage_alerts_at_configured_dwell(self):
        first = self.observe_detections(0, [self.bag()])
        self.assertEqual(len(first["items"]), 1)
        item_id = first["items"][0]["id"]
        self.assertEqual(first["alerts"], [])

        before = self.observe_detections(8, [self.bag()])
        self.assertEqual(before["items"][0]["id"], item_id)
        self.assertEqual(before["items"][0]["duration"], 8)
        self.assertFalse(before["items"][0]["alert"])
        self.assertEqual(before["alerts"], [])

        at_threshold = self.observe_detections(10, [self.bag()])
        self.assertEqual(at_threshold["dwell"], 10)
        self.assertEqual(at_threshold["items"][0]["duration"], 10)
        self.assertTrue(at_threshold["items"][0]["alert"])
        self.assertEqual(at_threshold["alerts"], [item_id])

    def test_moving_luggage_does_not_alert(self):
        first = self.observe_detections(0, [self.bag()])
        item_id = first["items"][0]["id"]
        # Each shift exceeds stillness tolerance but preserves track association.
        # Total elapsed time exceeds the configured dwell twice.
        for step in range(1, 11):
            t = step * 2
            with self.subTest(t=t):
                result = self.observe_detections(t, [self.bag(0.1 + step * 0.04)])
                self.assertEqual(len(result["items"]), 1)
                item = result["items"][0]
                self.assertEqual(item["id"], item_id)
                self.assertEqual(item["since"], t)
                self.assertEqual(item["duration"], 0)
                self.assertFalse(item["alert"])
                self.assertEqual(result["alerts"], [])

    def test_missing_luggage_is_removed_after_two_scans(self):
        first = self.observe_detections(0, [self.bag()])
        item_id = first["items"][0]["id"]
        self.assertEqual(self.observe_detections(10, [self.bag()])["alerts"], [item_id])

        missing_once = self.observe_detections(12, [])
        self.assertEqual([item["id"] for item in missing_once["items"]], [item_id])
        missing_twice = self.observe_detections(14, [])
        self.assertEqual(missing_twice["items"], [])
        self.assertEqual(missing_twice["alerts"], [])
        self.assertEqual(self.watch.snapshot(self.camera["id"])["items"], [])

        returned = self.observe_detections(16, [self.bag()])
        self.assertEqual(len(returned["items"]), 1)
        self.assertNotEqual(returned["items"][0]["id"], item_id)
        self.assertEqual(returned["items"][0]["duration"], 0)
        self.assertEqual(returned["alerts"], [])

    def test_disabled_camera_does_not_detect_track_or_alert(self):
        # Keep another camera enabled: this is how a shared watch can receive
        # observations for a disabled camera in the server.
        self.observe_detections(0, [self.bag()])
        self.observe_detections(10, [self.bag()])
        enabled_before = self.watch.snapshot(self.camera["id"])
        disabled_before = self.watch.snapshot(self.disabled_camera["id"])
        self.pool.submit.reset_mock()
        self.detect.reset_mock()
        self.frame.reset_mock()

        self.assertFalse(LuggageWatch.enabled_for(self.disabled_camera))
        for t in (0, 10, 100):
            with self.subTest(t=t):
                self.assertIsNone(self.watch.observe(self.disabled_camera, self.frame, t))
                result = self.watch.snapshot(self.disabled_camera["id"])
                self.assertEqual(result["items"], [])
                self.assertEqual(result["alerts"], [])
                self.assertEqual(result, disabled_before)
        self.pool.submit.assert_not_called()
        self.detect.assert_not_called()
        self.frame.copy.assert_not_called()
        self.assertEqual(self.watch.snapshot(self.camera["id"]), enabled_before)


if __name__ == "__main__":
    unittest.main()
