"""Estatura aproximada de una persona a partir de su recuadro y la homografía del suelo."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from live_core import estimate_height


class HeightTests(unittest.TestCase):
    def camera(self):
        # x=10u, y=10(1-v): el suelo se ve con y creciente hacia arriba de la imagen.
        h = np.array([[10., 0, 0], [0, -10., 10.], [0, 0, 1.]])
        return {'h': h, 'x': 5., 'y': 0., 'height': 3.4}

    def test_estimates_known_height_from_full_box(self):
        # Persona de 1,7 m a 4 m de la cámara: pies en y=4, cabeza proyectada en y=8.
        estimate = estimate_height(self.camera(), (45, 20, 55, 60), 100, 100)
        self.assertAlmostEqual(estimate, 1.7, places=2)

    def test_returns_none_when_box_touches_frame_edge_or_is_missing(self):
        self.assertIsNone(estimate_height(self.camera(), (45, 0, 55, 60), 100, 100))
        self.assertIsNone(estimate_height(self.camera(), (45, 20, 55, 100), 100, 100))
        self.assertIsNone(estimate_height(self.camera(), None, 100, 100))

    def test_returns_none_without_calibration_or_camera_height(self):
        self.assertIsNone(estimate_height({**self.camera(), 'h': None}, (45, 20, 55, 60), 100, 100))
        self.assertIsNone(estimate_height({**self.camera(), 'height': 0}, (45, 20, 55, 60), 100, 100))

    def test_implausible_heights_are_discarded(self):
        self.assertIsNone(estimate_height({**self.camera(), 'height': 9.}, (45, 20, 55, 60), 100, 100))


if __name__ == '__main__':
    unittest.main()
