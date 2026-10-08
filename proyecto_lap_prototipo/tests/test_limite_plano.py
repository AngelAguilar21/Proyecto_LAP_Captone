import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from live_core import calibration, calibration_diagnostics, project, reference_inliers
from spatial_scope import accepts, outline_scope, plan_outline


def contorno(*puntos):
    """Líneas de plano (0..1) que unen los puntos en cadena y cierran el contorno."""
    return [[*puntos[i], *puntos[(i + 1) % len(puntos)]] for i in range(len(puntos))]


class ContornoDelPlanoTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'width': 6., 'height': 4., 'planLines': contorno((.1, .2), (.7, .2), (.7, .85), (.1, .85))}

    def test_una_cadena_cerrada_de_lineas_es_el_limite_del_plano(self):
        area = plan_outline(self.plan)
        self.assertEqual(len(area), 4)
        self.assertTrue(all(0 <= x <= 6 and 0 <= y <= 4 for x, y in area))

    def test_nadie_queda_fuera_del_contorno_dibujado(self):
        plan = {**self.plan, **outline_scope(self.plan)}
        self.assertTrue(accepts({}, plan, .5, .5, [2., 2.]))
        self.assertFalse(accepts({}, plan, .5, .5, [5.9, 2.]), 'una persona proyectada fuera de los muros no debe aparecer en el mapa')
        self.assertFalse(accepts({}, plan, .5, .5, [30., -7.]))

    def test_se_tolera_un_poco_de_error_de_calibracion_junto_al_muro(self):
        plan = {**self.plan, **outline_scope(self.plan)}
        borde = .7 * 6
        self.assertTrue(accepts({}, plan, .5, .5, [borde + .1, 2.]))
        self.assertFalse(accepts({}, plan, .5, .5, [borde + 1., 2.]))

    def test_un_plano_con_lineas_sueltas_no_delimita_un_area(self):
        suelto = {'width': 6., 'height': 4., 'planLines': contorno((.1, .2), (.7, .2), (.7, .85), (.1, .85)) + [[.3, .3, .4, .5]]}
        self.assertIsNone(plan_outline(suelto))
        self.assertEqual(outline_scope(suelto), {})
        self.assertTrue(accepts({}, {**suelto, **outline_scope(suelto)}, .5, .5, [5.9, 2.]))

    def test_un_limite_dibujado_a_proposito_manda_sobre_el_contorno(self):
        plan = {**self.plan, 'workArea': [[0, 0], [1, 0], [1, 1], [0, 1]]}
        self.assertEqual(outline_scope(plan), {})


class AjusteConReferenciasRuidosasTests(unittest.TestCase):
    # Referencias de una cámara real (video oblicuo, plano aéreo): todas marcadas con un error de unos 10-20 cm.
    REFERENCIAS = [[.7224, .5729, 3.2854, 1.9466], [.3449, .5340, 2.4374, 2.4766], [.5388, .5294, 2.9144, 2.1851],
                   [.7939, .6552, 3.8419, 2.2249], [.1969, .6335, 2.3513, 3.2008], [.7862, .4649, 3.3447, .8053],
                   [.5566, .9855, 3.7161, 3.0045]]

    def test_con_referencias_ruidosas_se_usan_todas_y_no_se_extrapola_a_decenas_de_metros(self):
        resultado = calibration_diagnostics(self.REFERENCIAS)
        self.assertEqual(resultado['inlierCount'], 7)
        self.assertEqual(resultado['outlierIndices'], [])
        h = calibration(self.REFERENCIAS)
        # Donde caminan las personas (junto a la referencia 4) el punto cae donde está la referencia, no a 900 m.
        x, y = project(h, .79, .66)
        self.assertLess(math.dist((x, y), (3.8, 2.15)), .5)

    def test_una_referencia_absurda_se_sigue_descartando(self):
        pares = self.REFERENCIAS + [[.5, .5, 60., -40.]]
        self.assertNotIn([.5, .5, 60., -40.], reference_inliers(pares))
        self.assertIn(8, calibration_diagnostics(pares)['outlierIndices'])
        x, y = project(calibration(pares), .79, .66)
        self.assertLess(math.dist((x, y), (3.8, 2.15)), .6)


if __name__ == '__main__':
    unittest.main()
