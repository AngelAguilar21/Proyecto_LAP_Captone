"""Filtros de falsos positivos (gorros, pósters) y selección de perfil de hardware."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import hardware
from following.clutter import SizeFilter, StaticClutter


def det(conf, height, width=40):
    return SimpleNamespace(confianza=conf, box=(0, 0, width, height))


def track(tid, x, y, score, width=40):
    return SimpleNamespace(id=tid, posicion=(x, y), score=score, ultima_caja=(x, y, x + width, y + 100))


class SizeFilterTests(unittest.TestCase):
    def test_drops_small_doubtful_detections_but_keeps_small_sure_ones(self):
        f = SizeFilter()
        people = [det(.85, 130) for _ in range(4)]
        hat, far_sure = det(.35, 50), det(.8, 50)
        kept, dropped = f.apply(people + [hat, far_sure])
        self.assertEqual(dropped, 1)
        self.assertIn(far_sure, kept)
        self.assertNotIn(hat, kept)

    def test_no_filtering_without_a_reference(self):
        kept, dropped = SizeFilter().apply([det(.3, 20)])
        self.assertEqual((len(kept), dropped), (1, 0))

    def test_keeps_doubtful_detection_of_normal_size(self):
        f = SizeFilter()
        f.apply([det(.9, 130) for _ in range(4)])
        kept, dropped = f.apply([det(.33, 120)])
        self.assertEqual(dropped, 0)


    def test_truncated_detection_at_the_border_is_kept(self):
        f = SizeFilter()
        f.apply([det(.9, 130) for _ in range(4)])
        edge = SimpleNamespace(confianza=.35, box=(1230, 300, 1280, 360))
        kept, dropped = f.apply([edge], (1280, 720))
        self.assertEqual(dropped, 0)


class StaticClutterTests(unittest.TestCase):
    def test_static_low_confidence_track_is_suppressed_after_min_age(self):
        s = StaticClutter()
        out = set()
        for step in range(12):
            out = s.update([track(1, 100, 100, .35)], step * .3)
        self.assertEqual(out, {1})

    def test_moving_track_and_confident_static_track_survive(self):
        s = StaticClutter()
        out = set()
        for step in range(12):
            out = s.update([track(1, 100 + step * 15, 100, .35), track(2, 300, 300, .9)], step * .3)
        self.assertEqual(out, set())

    def test_static_track_at_the_border_is_not_suppressed(self):
        s = StaticClutter()
        out = set()
        for step in range(12):
            edge = SimpleNamespace(id=1, posicion=(100, 700), score=.3, ultima_caja=(80, 620, 140, 720))
            out = s.update([edge], step * .3, (1280, 720))
        self.assertEqual(out, set())

    def test_young_track_is_not_suppressed(self):
        s = StaticClutter()
        self.assertEqual(s.update([track(1, 100, 100, .3)], 0.), set())


class HardwareTests(unittest.TestCase):
    def info(self, **kw):
        base = {"cpuThreads": 8, "ramGb": 16, "gpu": None, "vramGb": 0., "cudaTorch": False,
                "ortProviders": ["CPUExecutionProvider"], "hint": None}
        return {**base, **kw}

    def test_tiers_follow_vram(self):
        gpu = lambda gb: self.info(gpu="X", vramGb=gb, cudaTorch=True)
        self.assertEqual(hardware.tier_for(gpu(24)), "gpu_alta")
        self.assertEqual(hardware.tier_for(gpu(8)), "gpu_media")
        self.assertEqual(hardware.tier_for(gpu(4)), "gpu_baja")
        self.assertEqual(hardware.tier_for(self.info()), "cpu")

    def test_gpu_profile_uses_cuda_fp16_and_higher_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("yolo11n.pt", "yolo11m.pt"):
                (Path(d) / name).write_bytes(b"x")
            info = self.info(gpu="RTX", vramGb=16, cudaTorch=True, ortProviders=["CUDAExecutionProvider", "CPUExecutionProvider"])
            p = hardware.choose({}, True, info, d)
        self.assertEqual((p["device"], p["half"], p["imgsz"]), ("cuda:0", True, 1920))
        self.assertTrue(p["weights"].endswith("yolo11m.pt"))
        self.assertEqual(p["osnetProviders"][0], "CUDAExecutionProvider")

    def test_missing_weights_fall_back_to_what_exists(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "yolo11n.pt").write_bytes(b"x")
            info = self.info(gpu="RTX", vramGb=24, cudaTorch=True)
            p = hardware.choose({}, False, info, d)
        self.assertEqual(p["missingWeights"], "yolo11m.pt")
        self.assertTrue(p["weights"].endswith("yolo11n.pt"))

    def test_cpu_forced_and_gpu_without_cuda_torch_hint(self):
        info = self.info(gpu="RTX", vramGb=24, cudaTorch=True)
        self.assertEqual(hardware.choose({"hardware": "cpu"}, False, info)["device"], "cpu")
        no_cuda = self.info(gpu="RTX", vramGb=24, cudaTorch=False, hint="instala torch CUDA")
        p = hardware.choose({}, False, no_cuda)
        self.assertEqual((p["device"], p["half"]), ("cpu", False))
        self.assertTrue(p["hint"])


if __name__ == "__main__":
    unittest.main()
