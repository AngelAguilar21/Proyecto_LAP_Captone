"""Adaptive Vision Inference Engine (AVIE).

AVIE never replaces tracked identities with a density estimate.  It only asks
P2PNet for an asynchronous crowd signal when the primary detector reports a
dense or heavily occluded scene.
"""
from collections import defaultdict
import threading
import time


class AdaptiveVisionController:
    def __init__(self, crowd_threshold=30, area_threshold=.45, latency_budget_ms=120):
        self.crowd_threshold = max(2, int(crowd_threshold))
        self.area_threshold = float(area_threshold)
        self.latency_budget_ms = float(latency_budget_ms)
        self.state = "normal"
        self.last = None
        self._dense_frames = 0
        self._normal_frames = 0

    def update(self, detections, tracks, inference_ms):
        count = len(detections)
        boxes = [getattr(item, "box", None) for item in detections]
        boxes = [box for box in boxes if box]
        overlap = 0.0
        for index, first in enumerate(boxes):
            if index + 1 >= len(boxes):
                continue
            for second in boxes[index + 1:]:
                ix1, iy1 = max(first[0], second[0]), max(first[1], second[1])
                ix2, iy2 = min(first[2], second[2]), min(first[3], second[3])
                intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                area = max(1, (first[2]-first[0])*(first[3]-first[1]) + (second[2]-second[0])*(second[3]-second[1]))
                overlap = max(overlap, intersection / area)
        track_ratio = len(tracks) / max(1, count)
        dense = count >= self.crowd_threshold or overlap >= .25 or track_ratio < .55 and count >= 8 or inference_ms > self.latency_budget_ms and count >= 8
        self._dense_frames = self._dense_frames + 1 if dense else 0
        self._normal_frames = self._normal_frames + 1 if not dense else 0
        if self.state == "normal" and self._dense_frames >= 3:
            self.state = "dense"
        elif self.state == "dense" and self._normal_frames >= 8:
            self.state = "recovering"
        elif self.state == "recovering" and self._normal_frames >= 3:
            self.state = "normal"
        self.last = {"state": self.state, "detections": count, "tracks": len(tracks),
                     "trackRatio": round(track_ratio, 3), "overlap": round(overlap, 3),
                     "inferenceMs": round(float(inference_ms), 2), "p2pRequested": self.state == "dense"}
        return self.last


class AsyncDensitySampler:
    def __init__(self, detector_factory):
        self.detector_factory = detector_factory
        self._pending = {}
        self._latest = {}
        self._condition = threading.Condition()
        self._closed = False
        self._detector = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="avie-p2p-density")
        self._thread.start()

    def submit(self, camera_id, frame, timestamp):
        with self._condition:
            self._pending[camera_id] = (frame.copy(), timestamp)
            self._condition.notify()

    def latest(self, camera_id):
        with self._condition:
            return dict(self._latest.get(camera_id, {"status": "idle"}))

    def _run(self):
        while True:
            with self._condition:
                while not self._pending and not self._closed:
                    self._condition.wait(.25)
                if self._closed and not self._pending:
                    return
                camera_id, (frame, timestamp) = self._pending.popitem()
            try:
                if self._detector is None:
                    self._detector = self.detector_factory()
                started = time.monotonic()
                points = self._detector.detectar(frame)
                value = {"status": "ready", "t": timestamp, "count": len(points),
                         "points": [{"x": float(p.x), "y": float(p.y), "confidence": float(p.confianza)} for p in points],
                         "inferenceMs": round((time.monotonic() - started) * 1000, 2)}
            except Exception as exc:
                value = {"status": "error", "error": str(exc), "t": timestamp}
            with self._condition:
                self._latest[camera_id] = value

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        self._thread.join(timeout=2)
