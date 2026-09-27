"""El trazado del plano distingue lo construido de lo que no es estructura.

Sobre un plano de conjunto a color, detectar todos los bordes devuelve arboles,
lineas de estacionamiento, rotulos y sombras. Lo construido se dibuja como
volumen relleno, mas oscuro que el fondo y de tono frio, mientras la vegetacion
es verde y las vias casi blancas: con eso se separa y se traza solo su contorno.
"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path('proyecto_lap_prototipo/src').resolve()))
from PIL import Image, ImageDraw
from live_core import validate_config
from plan_import import raster_to_lines


def plano_de_conjunto():
    """Imita un plano de campus: fondo claro, cesped verde, arboles, vias
    blancas, y edificios como bloques grises azulados. Los valores son los
    medidos sobre un plano real."""
    img = Image.new("RGB", (900, 700), (245, 247, 251))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 840, 640], fill=(205, 226, 178))            # cesped
    for x in range(90, 820, 45):                                      # arboles
        d.ellipse([x, 90, x + 26, 116], fill=(150, 196, 120))
        d.ellipse([x, 590, x + 26, 616], fill=(150, 196, 120))
    d.rectangle([60, 320, 840, 360], fill=(249, 254, 255))            # via
    for x in range(80, 820, 18):                                      # estacionamiento
        d.line([(x, 660), (x, 690)], fill=(215, 218, 222), width=2)
    edificios = [(140, 140, 360, 300), (430, 150, 640, 290), (200, 400, 430, 560), (520, 410, 760, 570)]
    for caja in edificios:
        d.rectangle(caja, fill=(190, 199, 212))                       # gris azulado
    d.text((150, 620), "EDIFICIO A", fill=(40, 48, 60))
    return img, edificios


class TrazadoEstructurasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.img, cls.edificios = plano_de_conjunto()
        cls.estructuras = raster_to_lines(cls.img, 12., "estructuras")
        cls.bordes = raster_to_lines(cls.img, 12., "bordes")

    def test_estructuras_traza_muchas_menos_lineas_que_todos_los_bordes(self):
        self.assertGreater(len(self.bordes["planLines"]), len(self.estructuras["planLines"]) * 2,
                           f"estructuras={len(self.estructuras['planLines'])} bordes={len(self.bordes['planLines'])}")

    def test_cada_edificio_queda_trazado(self):
        # el contorno de cada bloque debe aparecer: no vale limpiar quitando todo
        puntos = [(l[0], l[1]) for l in self.estructuras["planLines"]]
        for x1, y1, x2, y2 in self.edificios:
            centro = ((x1 + x2) / 2 / self.img.width, (y1 + y2) / 2 / self.img.height)
            cerca = [p for p in puntos if abs(p[0] - centro[0]) < .2 and abs(p[1] - centro[1]) < .2]
            self.assertTrue(cerca, f"el edificio en {(x1,y1,x2,y2)} no dejo ninguna linea")

    def test_no_traza_sobre_el_cesped_libre(self):
        # franja de cesped con arboles y sin edificios: no debe generar contorno
        alto, ancho = self.img.height, self.img.width
        franja = [l for l in self.estructuras["planLines"] if .10 < l[1] < .16 and .10 < l[0] < .90]
        self.assertLessEqual(len(franja), 4, f"se trazaron {len(franja)} lineas sobre vegetacion")
        del alto, ancho

    def test_avisa_de_que_dejo_cosas_fuera(self):
        texto = " ".join(self.estructuras["warnings"]).lower()
        self.assertIn("volumen construido", texto)

    def test_un_plano_en_blanco_y_negro_no_queda_vacio(self):
        # sin volumenes rellenos que separar, vuelve a detectar bordes
        cad = Image.new("RGB", (900, 700), "white")
        d = ImageDraw.Draw(cad)
        for x in range(100, 800, 120):
            d.line([(x, 80), (x, 620)], fill=(0, 0, 0), width=3)
        for y in range(80, 620, 130):
            d.line([(100, y), (790, y)], fill=(0, 0, 0), width=3)
        salida = raster_to_lines(cad, 12., "estructuras")
        self.assertTrue(salida["planLines"], "un plano CAD quedaria sin lineas")
        self.assertIn("no se distinguieron volumenes", " ".join(salida["warnings"]).lower())

    def test_la_vista_elegida_se_valida(self):
        base = {"width": 12, "height": 8, "unit": "relative", "radius": 1.5, "minPeople": 4,
                "dwell": 3, "handoffSeconds": 12, "matchDistance": 1, "clocksVerified": False,
                "zones": [], "cameras": []}
        for vista in ("image", "lines", None):
            validate_config({**base, "planView": vista})
        with self.assertRaises(ValueError):
            validate_config({**base, "planView": "otra"})


if __name__ == '__main__':
    unittest.main()
