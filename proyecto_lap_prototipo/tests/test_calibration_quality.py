import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from live_core import calibration, calibration_diagnostics


class CalibrationQualityTests(unittest.TestCase):
    def setUp(self):
        self.pairs = [[0, 0, 0, 0], [1, 0, 12, 0], [1, 1, 12, 8], [0, 1, 0, 8]]

    def test_four_points_do_not_claim_independent_validation(self):
        result = calibration_diagnostics(self.pairs)
        self.assertIsNone(result['validationError'])
        self.assertEqual(result['validationPoints'], 0)

    def test_extra_references_are_checked_outside_fit(self):
        result = calibration_diagnostics(self.pairs + [[.3, .4, 3.6, 3.2], [.7, .6, 8.4, 4.8]])
        self.assertEqual(result['validationPoints'], 6)
        self.assertLess(result['validationError'], .001)

    def test_ransac_reports_and_ignores_one_bad_reference(self):
        # Una referencia adicional fue marcada en un punto cercano, pero no en
        # la ubicación real del plano. El resto sigue describiendo la misma H.
        pairs = self.pairs + [[.25, .25, 3.0, 2.0], [.75, .75, 9.0, 6.0], [.1, .8, 99.0, 99.0]]
        result = calibration_diagnostics(pairs)
        self.assertEqual(result['fitMethod'], 'ransac')
        self.assertEqual(result['inlierCount'], 6)
        self.assertEqual(result['outlierIndices'], [7])
        self.assertIn('excluyeron del ajuste', result['warning'])

    def test_duplicate_and_crossed_references_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'repetidas'):
            calibration(self.pairs + [self.pairs[0]])
        with self.assertRaises(ValueError):
            calibration([[0, 0, 0, 0], [1, 0, 12, 8], [1, 1, 12, 0], [0, 1, 0, 8]])


if __name__ == '__main__':
    unittest.main()
