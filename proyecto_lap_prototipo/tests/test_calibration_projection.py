"""Calidad de la proyección: una calibración exacta con 4 puntos puede ser inservible."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from live_core import blocking_calibration_issue, calibration_diagnostics, collapsed_pairs

# Referencias reales de un proyecto cuya proyección colapsaba a personas distintas en un solo punto:
# cubren ~4% del video y el horizonte queda dentro de la imagen completa.
DEGENERATE = [[.59, .72, 3.22, 3.39], [.45, .94, 3.31, 3.37], [.82, .72, 3.19, 3.88], [.85, .61, 2.37, 4.45]]
HEALTHY = [[0, 0, 0, 0], [1, 0, 12, 0], [1, 1, 12, 8], [0, 1, 0, 8], [.5, .5, 6, 4]]


class ProjectionIssuesTests(unittest.TestCase):
    def test_degenerate_calibration_is_flagged_even_with_zero_fit_error(self):
        result = calibration_diagnostics(DEGENERATE)
        self.assertLess(result["rmse"], 1e-4)          # el ajuste parece perfecto...
        self.assertTrue(result["issues"])              # ...pero se avisa del problema
        self.assertEqual(result["warning"], " ".join(result["issues"]))
        self.assertTrue(any("cubren solo" in issue for issue in result["issues"]))

    def test_healthy_calibration_has_no_issues(self):
        result = calibration_diagnostics(HEALTHY)
        self.assertEqual(result["issues"], [])

    def test_a_detection_zone_away_from_the_horizon_removes_the_horizon_warning(self):
        full = calibration_diagnostics(DEGENERATE)["issues"]
        near = calibration_diagnostics(DEGENERATE, [[.4, .6], [.9, .6], [.9, .95], [.4, .95]])["issues"]
        self.assertTrue(any("horizonte" in issue for issue in full))
        self.assertFalse(any("horizonte" in issue for issue in near))


# Referencias de un proyecto real: puntos del video repartidos por toda la imagen, pero los
# puntos del plano clickeados en un cuadrado de ~0.1 en un plano de 12.
PLAN_POINTS_TOGETHER = [[.785, .652, 6.68, 6.456], [.787, .547, 6.658, 6.417], [.717, .561, 6.658, 6.443],
                        [.344, .533, 6.577, 6.578], [.538, .519, 6.61, 6.505], [.538, .927, 6.684, 6.55]]


class PlanSpanTests(unittest.TestCase):
    def test_local_reference_extent_is_only_a_scale_warning(self):
        result = calibration_diagnostics(PLAN_POINTS_TOGETHER, None, (12, 9))
        self.assertIn("área local", result["issues"][0])

    def test_well_separated_plan_points_do_not_block(self):
        self.assertIsNone(blocking_calibration_issue(HEALTHY, (12, 8)))
        self.assertFalse(any("mismo lugar" in i for i in calibration_diagnostics(HEALTHY, None, (12, 8))["issues"]))

    def test_local_calibration_is_independent_of_airport_extent(self):
        local = [[u,v,x+800,y+1000] for u,v,x,y in HEALTHY]
        self.assertIsNone(blocking_calibration_issue(local, (2000,2000)))
        self.assertIsNone(blocking_calibration_issue(local, (12000,12000)))

    def test_degenerate_points_are_blocked_even_without_plan_size(self):
        self.assertIsNotNone(blocking_calibration_issue([[0,0,1,1]]*4, None))


class CollapsedPairsTests(unittest.TestCase):
    def person(self, x, y, left):
        return {"point": (x, y), "box": (left, 0, left + 40, 100)}

    def test_distinct_people_at_the_same_plan_point_are_counted(self):
        people = [self.person(3.3, 3.4, 0), self.person(3.31, 3.4, 100), self.person(3.3, 3.41, 200)]
        self.assertEqual(collapsed_pairs(people), 3)

    def test_overlapping_boxes_or_separated_points_are_not_collapse(self):
        same_person_twice = [self.person(3.3, 3.4, 0), self.person(3.3, 3.4, 5)]
        spread = [self.person(1, 1, 0), self.person(5, 4, 100)]
        self.assertEqual(collapsed_pairs(same_person_twice), 0)
        self.assertEqual(collapsed_pairs(spread), 0)


if __name__ == "__main__":
    unittest.main()
