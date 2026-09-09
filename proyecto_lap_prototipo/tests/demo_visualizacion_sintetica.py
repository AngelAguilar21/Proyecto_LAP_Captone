"""
Genera una animacion de demostracion sobre el plano compartido de la
explanada con datos sinteticos (sin videos ni P2PNet): dos "personas" -- en
realidad la misma persona vista por camara A y por camara B con una pequena
diferencia de posicion (error de calibracion normal) -- deben terminar
dibujadas como un unico punto con un solo id_global tras pasar por
cross_camera.GestorContinuidad. Sirve para validar a ojo visualize.py antes
de conectarlo a datos reales.

Corre con:  python tests/demo_visualizacion_sintetica.py
Genera:     data/demo_visualizacion_sintetica.mp4
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import nodes
import persistence
import visualize
from cross_camera import GestorContinuidad


def generar_demo():
    camaras, area_comun = nodes.cargar_camaras(str(RAIZ / "config" / "camaras.json"))
    zonas = nodes.cargar_zonas(str(RAIZ / "data" / "plano_zonas.json"))
    gestor = GestorContinuidad(camaras, umbral_distancia_metros=1.5)

    ruta_bd = RAIZ / "data" / "demo_visualizacion_sintetica.sqlite"
    ruta_bd.unlink(missing_ok=True)
    bd = persistence.crear_bd(str(ruta_bd))

    velocidad_mps = 1.0
    paso_t = 0.2
    largo, ancho = area_comun["largo_metros"], area_comun["ancho_metros"]

    t = 0.0
    x, y = 1.0, ancho / 2
    id_global_a = None
    while x <= largo - 1.0:
        zona = nodes.punto_en_zona((x, y), zonas)

        # Camara A ve a la persona en (x, y); camara B la ve con un pequeno
        # error de calibracion (+0.15m). El gestor debe fusionarlas en un id.
        if id_global_a is None:
            id_global_a = "demo-1"
            gestor.actualizar_posicion(id_global_a, x, y, t, None, "A")
        else:
            gestor.actualizar_posicion(id_global_a, x, y, t, None, "A")

        id_global_b = gestor.intentar_fusionar("B", x + 0.15, y + 0.1, t, None) or "SIN_FUSIONAR"
        assert id_global_b == id_global_a, "La demo deberia fusionar siempre: revisar umbral_distancia_metros"

        persistence.guardar_posicion(bd, id_global_a, "A", x, y, t, zona, predicha=False)

        t += paso_t
        x += velocidad_mps * paso_t

    filas = persistence.cargar_todas_las_posiciones(bd)
    frames = visualize.agrupar_por_tiempo(filas, paso_tiempo=paso_t)
    ruta_salida = str(RAIZ / "data" / "demo_visualizacion_sintetica.mp4")
    visualize.reproducir(frames, area_comun, zonas, camaras, ruta_salida=ruta_salida, fps=int(1 / paso_t))
    print(f"Demo generada: {ruta_salida} ({len(frames)} frames, un solo id_global pese a 2 camaras)")


if __name__ == "__main__":
    generar_demo()
