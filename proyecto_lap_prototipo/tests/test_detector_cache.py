"""El detector YOLO se carga una vez por proceso, no en cada inicio de sesión."""
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import live_server  # noqa: E402


class DetectorCacheTests(unittest.TestCase):
    def setUp(self):
        self.engine = live_server.Engine.__new__(live_server.Engine)
        self.engine.detector_caches = {}
        self.engine.detector_lock = threading.Lock()
        self.engine.detector_warmup = None

    def test_modo_invalido_se_rechaza(self):
        for modo in ("otro", "p2pnet", "hybrid"):
            with self.assertRaises(ValueError):
                self.engine.load_detector(modo, {})

    def test_yolo_se_carga_una_vez_por_resolucion(self):
        with patch("following.detector.YoloPersonDetector", side_effect=lambda *a, **k: object()) as construir:
            primero = self.engine.load_detector("yolo", {"inferenceSize": 640})
            segundo = self.engine.load_detector("yolo", {"inferenceSize": 640})
            otro = self.engine.load_detector("yolo", {"inferenceSize": 960})
        self.assertIs(primero, segundo)
        self.assertIsNot(primero, otro)
        self.assertEqual(construir.call_count, 2)


if __name__ == "__main__":
    unittest.main()
