"""Vectores OSNet: cuándo se calculan por track y comportamiento sin modelo."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from following.reid import EmbeddingScheduler, OSNetEmbedder


FRONT = np.asarray([1, 0, 0, 0], dtype=np.float32)


class SchedulerTests(unittest.TestCase):
    def test_runs_on_new_track_interval_and_low_confidence(self):
        s = EmbeddingScheduler(interval=5)
        self.assertTrue(s.due(1, 0, .9))
        s.store(1, 0, FRONT)
        self.assertFalse(s.due(1, 3, .9))
        self.assertTrue(s.due(1, 5, .9))
        self.assertTrue(s.due(1, 1, .3))
        s.prune(set())
        self.assertIsNone(s.get(1))

    def test_embedder_without_model_degrades(self):
        with patch("following.reid.resolve_model_path", return_value=None):
            embedder = OSNetEmbedder("no-existe.onnx")
        self.assertFalse(embedder.available)
        self.assertEqual(embedder.embed(np.zeros((50, 50, 3), np.uint8), [(0, 0, 40, 40)]), [None])

    def test_project_model_is_available(self):
        """models/osnet.onnx viene con el repositorio: sin él el servidor no inicia una sesión."""
        embedder = OSNetEmbedder()
        self.assertTrue(embedder.available, getattr(embedder, "error", ""))
        vector = embedder.embed(np.random.default_rng(0).integers(0, 255, (256, 128, 3), dtype=np.uint8), [(0, 0, 128, 256)])[0]
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
