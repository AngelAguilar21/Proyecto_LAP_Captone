"""Reidentificación con embeddings: galería de vistas, evidencia débil y estados."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from live_server import default_config
from live_core import IdentityStore, association_score, embedding_distance
from following.reid import EmbeddingScheduler, OSNetEmbedder


def unit(*values):
    vec = np.asarray(values, dtype=np.float32)
    return vec / np.linalg.norm(vec)


FRONT, BACK, OTHER = unit(1, 0, 0, 0), unit(0, 1, 0, 0), unit(0, 0, 1, 0)
FRONT_BACK_BLEND = unit(1, 1, 0, 0)


def obs(camera, local, x, y, embedding=None):
    return {"camera": camera, "local": local, "point": (x, y), "color": None, "embedding": embedding}


class ReidEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = default_config()
        self.cfg["clocksVerified"] = True

    def test_gallery_keeps_front_and_back_views(self):
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1, FRONT)], 0)[0]["id"]
        store.update([obs("A", 1, 1.1, 1, BACK)], .2)
        self.assertEqual(len(store.people[pid]["embeddingGallery"]), 2)

    def test_back_view_matches_gallery_across_cameras(self):
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1, FRONT)], 0)[0]["id"]
        store.update([obs("A", 1, 1.4, 1, BACK)], .2)
        row = store.update([obs("B", 9, 1.9, 1, BACK)], 2.)[0]
        self.assertEqual(row["id"], pid)
        self.assertEqual(row["association"], "estimated")
        self.assertGreater(row["reidScore"], .4)

    def test_weak_appearance_creates_new_id_marked_uncertain(self):
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1, FRONT)], 0)[0]["id"]
        row = store.update([obs("B", 9, 1.1, 1, OTHER)], .3)[0]
        self.assertNotEqual(row["id"], pid)
        self.assertEqual(row["association"], "uncertain")

    def test_same_camera_recovery_is_reidentified(self):
        store = IdentityStore(self.cfg)
        pid = store.update([obs("A", 1, 1, 1, FRONT)], 0)[0]["id"]
        row = store.update([obs("A", 2, 1.1, 1, FRONT)], .6)[0]
        self.assertEqual(row["id"], pid)
        self.assertEqual(row["association"], "reidentified")

    def test_embedding_is_not_published(self):
        row = IdentityStore(self.cfg).update([obs("A", 1, 1, 1, FRONT)], 0)[0]
        self.assertNotIn("embedding", row)

    def test_score_weights_and_bounds(self):
        best = association_score({}, 0., 0., 1., 0., 1.)
        worst = association_score({}, 1., 1., -1., 1., 0.)
        self.assertAlmostEqual(best, 1.)
        self.assertAlmostEqual(worst, 0.)

    def test_cosine_distance(self):
        self.assertAlmostEqual(embedding_distance(FRONT, FRONT), 0.)
        self.assertAlmostEqual(embedding_distance(FRONT, BACK), 1.)
        self.assertLess(embedding_distance(FRONT, FRONT_BACK_BLEND), .35)


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
        # El modelo versionado no debe convertir este caso en un pase vacío.
        # Ninguna de las tres rutas candidatas existe en este escenario.
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.onnx"
            with patch("following.reid.DEFAULT_MODEL", missing), \
                    patch.dict("os.environ", {"AEROTRACK_OSNET_MODEL": str(missing)}):
                embedder = OSNetEmbedder(str(missing))
            self.assertFalse(embedder.available)
            self.assertEqual(embedder.embed(np.zeros((50, 50, 3), np.uint8), [(0, 0, 40, 40)]), [None])


if __name__ == "__main__":
    unittest.main()
