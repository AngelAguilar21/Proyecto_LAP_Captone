"""Adaptador de ByteTrack oficial. Crear una instancia por cámara y sesión."""
from dataclasses import dataclass
from types import SimpleNamespace
import numpy as np


@dataclass
class PersonTrack:
    id: int
    box: list
    score: float

    @property
    def posicion(self):
        x1, _, x2, y2 = self.box
        return (x1+x2)/2, y2


class BoxTracker:
    def __init__(self, sample_fps=5, lost_seconds=3):
        from ultralytics.trackers.byte_tracker import BYTETracker

        args = SimpleNamespace(track_high_thresh=.25, track_low_thresh=.1,
                               new_track_thresh=.35, track_buffer=90,
                               match_thresh=.8, fuse_score=True)
        self.tracker = BYTETracker(args, frame_rate=sample_fps)
        self.tracker.max_time_lost = max(1, round(sample_fps*lost_seconds))
        self.last_t = None
        self.lost_seconds = lost_seconds

    def update(self, detections, boxes, t, shape):
        from ultralytics.engine.results import Boxes

        # Una interrupción larga no debe unir trayectorias separadas por el corte.
        if self.last_t is not None and (t < self.last_t or t-self.last_t > self.lost_seconds):
            self.tracker.tracked_stracks.clear()
            self.tracker.lost_stracks.clear()
        self.last_t = t
        rows = np.asarray([b+[d.confianza, 0] for b, d in zip(boxes, detections)],
                          dtype=np.float32).reshape(-1, 6)
        tracks = self.tracker.update(Boxes(rows, shape))
        # Solo observaciones confirmadas: las predicciones perdidas no cuentan personas.
        return [PersonTrack(int(r[4]), r[:4].astype(float).tolist(), float(r[5])) for r in tracks]
