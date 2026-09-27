"""P2PNet marca cabezas: comprueba que se ubican bien en el plano.

Se arma una camara sintetica de la que conocemos la respuesta exacta, se calibra
igual que en el asistente y se le pide ubicar personas cuya posicion real ya
sabemos. Pasar la cabeza directo por la homografia del suelo la deja metros mas
lejos; head_to_ground la corrige con la altura de la camara.
"""
import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path('proyecto_lap_prototipo/src').resolve()))
from live_core import ESTATURA_MEDIA, body_box, calibration, ground_point, head_to_ground, project

ALTURA_CAMARA, INCLINACION, FOCAL = 3., 22., 900.
ANCHO, ALTO = 1280, 720
BASE = (0., 0.)                       # la camara en el plano
REFERENCIAS = [(-2., 4.), (2., 4.), (-3., 9.), (3., 9.)]
PERSONAS = [(0., 5.), (-2., 6.), (2.5, 8.), (0., 10.), (-1., 12.), (1.5, 15.)]


def camara():
    t = np.radians(INCLINACION)
    adelante = np.array([0., np.cos(t), -np.sin(t)])
    derecha = np.array([1., 0., 0.])
    R = np.vstack([derecha, np.cross(adelante, derecha), adelante])
    K = np.array([[FOCAL, 0, ANCHO / 2], [0, FOCAL, ALTO / 2], [0, 0, 1]])
    return K, R, np.array([BASE[0], BASE[1], ALTURA_CAMARA])


K, R, C = camara()


def a_imagen(punto):
    """Punto del mundo a coordenadas normalizadas de imagen, o None si no se ve."""
    p = R @ (np.asarray(punto, float) - C)
    if p[2] <= 1e-6:
        return None
    q = K @ p
    u, v = q[0] / q[2], q[1] / q[2]
    return (u / ANCHO, v / ALTO) if 0 <= u <= ANCHO and 0 <= v <= ALTO else None


class P2PNetPlanoTests(unittest.TestCase):
    def setUp(self):
        self.h = calibration([[*a_imagen((x, y, 0.)), x, y] for x, y in REFERENCIAS])
        self.assertIsNotNone(self.h)
        self.camara = {"h": self.h, "x": BASE[0], "y": BASE[1],
                       "height": ALTURA_CAMARA, "headPoints": True}

    def test_la_cabeza_corregida_cae_donde_esta_la_persona(self):
        for x, y in PERSONAS:
            uv = a_imagen((x, y, ESTATURA_MEDIA))
            self.assertIsNotNone(uv, f"la cabeza en {(x, y)} deberia verse")
            px, py = ground_point(self.camara, *uv)
            self.assertAlmostEqual(px, x, places=3)
            self.assertAlmostEqual(py, y, places=3)

    def test_sin_corregir_el_error_es_de_metros(self):
        # justifica por que la correccion existe: no es un ajuste cosmetico
        for x, y in PERSONAS:
            crudo = project(self.h, *a_imagen((x, y, ESTATURA_MEDIA)))
            self.assertGreater(np.hypot(crudo[0] - x, crudo[1] - y), 1.)

    def test_camara_no_mas_alta_que_la_gente_no_devuelve_posicion(self):
        # el rayo no vuelve al suelo por delante: no hay conversion posible
        for altura in (None, 1.2, ESTATURA_MEDIA):
            self.assertIsNone(head_to_ground(self.h, .5, .5, *BASE, altura))
        self.assertIsNone(ground_point({**self.camara, "height": 1.5}, .5, .5))

    def test_el_modo_pies_no_cambia(self):
        # El modo geométrico directo se conserva para validar la homografía.
        uv = a_imagen((0., 5., 0.))
        px, py = ground_point({**self.camara, "headPoints": False}, *uv)
        self.assertAlmostEqual(px, 0., places=6)
        self.assertAlmostEqual(py, 5., places=6)

    def test_el_recuadro_derivado_cubre_de_la_cabeza_a_los_pies(self):
        # sin recuadro no hay color de ropa y la fusion entre camaras nunca pasa
        # su umbral, asi que la misma persona se contaria en cada camara.
        h_inv = np.linalg.inv(self.h)
        for x, y in PERSONAS:
            uv = a_imagen((x, y, ESTATURA_MEDIA))
            cabeza_px, cabeza_py = uv[0] * ANCHO, uv[1] * ALTO
            suelo = ground_point(self.camara, *uv)
            caja = body_box(h_inv, cabeza_px, cabeza_py, suelo, ANCHO, ALTO)
            self.assertIsNotNone(caja, f"sin recuadro para la persona en {(x, y)}")
            x1, y1, x2, y2 = caja
            pies = a_imagen((x, y, 0.))
            self.assertAlmostEqual(y1, cabeza_py, places=3)
            self.assertAlmostEqual(y2, pies[1] * ALTO, places=2)
            self.assertGreater(y2, y1)
            self.assertAlmostEqual((x1 + x2) / 2, cabeza_px, places=3)

    def test_sin_posicion_en_el_suelo_no_hay_recuadro(self):
        self.assertIsNone(body_box(np.linalg.inv(self.h), 640., 360., None, ANCHO, ALTO))
        self.assertIsNone(body_box(None, 640., 360., (0., 5.), ANCHO, ALTO))

    def test_una_estatura_distinta_desplaza_pero_de_forma_acotada(self):
        # no se puede deducir la estatura de un punto de cabeza, asi que este
        # error es inherente; se documenta su magnitud en vez de ocultarlo.
        real = 1.9
        uv = a_imagen((0., 10., real))
        px, py = ground_point(self.camara, *uv)
        esperado = 10. * abs(ESTATURA_MEDIA - real) / (ALTURA_CAMARA - real)
        self.assertAlmostEqual(np.hypot(px - 0., py - 10.), esperado, places=3)
        self.assertLess(esperado, 2.)


if __name__ == '__main__':
    unittest.main()
