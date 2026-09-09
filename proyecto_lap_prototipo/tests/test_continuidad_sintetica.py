"""
Validacion sintetica de la fusion entre camaras con campo de vision
superpuesto, y del tracking mono-camara, SIN necesitar los videos reales ni
el checkpoint de P2PNet. El caso mas exigente de este prototipo es que una
misma persona vista por camara A y camara B AL MISMO TIEMPO termine con un
solo id_global, en vez de duplicarse.

Corre con:  python tests/test_continuidad_sintetica.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import numpy as np

import nodes
from cross_camera import GestorContinuidad
from tracking import ByteTrackPuntos


def _descriptor(hue_dominante):
    histograma = np.zeros((8, 8), dtype=np.float32)
    histograma[hue_dominante % 8, 4] = 1.0
    return nodes.DescriptorApariencia(histograma_color=histograma, proporcion_alto_ancho=2.4)


def _cargar_gestor(umbral_distancia_metros=1.5):
    camaras, _ = nodes.cargar_camaras(str(RAIZ / "config" / "camaras.json"))
    return GestorContinuidad(camaras, umbral_distancia_metros=umbral_distancia_metros), camaras


def test_fusion_misma_persona_vista_por_dos_camaras():
    """Camara A ya ve a alguien en (5.0, 3.0); un instante despues camara B
    detecta a alguien nuevo casi en el mismo punto (ligero error de
    calibracion/deteccion) -> debe fusionarse en el mismo id_global."""
    gestor, _ = _cargar_gestor()
    descriptor = _descriptor(hue_dominante=2)

    gestor.actualizar_posicion("persona-1", 5.0, 3.0, t=2.0, descriptor=descriptor, camara_id="A")

    resultado = gestor.intentar_fusionar("B", 5.2, 3.1, t=2.05, descriptor=descriptor)
    assert resultado == "persona-1", f"Se esperaba fusionar con persona-1, se obtuvo {resultado}"
    print("[OK] misma persona vista por A y B casi al mismo tiempo -> un solo id_global")


def test_no_fusiona_personas_lejanas():
    """Si la deteccion de B esta lejos de cualquier persona activa de A, son
    fisicamente personas distintas: no debe fusionar (crea un id nuevo)."""
    gestor, _ = _cargar_gestor()

    gestor.actualizar_posicion("persona-2", 1.0, 1.0, t=5.0, descriptor=_descriptor(3), camara_id="A")

    resultado = gestor.intentar_fusionar("B", 9.0, 7.0, t=5.05, descriptor=_descriptor(3))
    assert resultado is None, "No deberia fusionar: estan a mas de 10m de distancia en el plano"
    print("[OK] no fusiona dos detecciones lejanas en el plano (son personas distintas)")


def test_no_fusiona_fuera_de_la_ventana_temporal():
    """Si la deteccion de B ocurre mucho despues (fuera de la ventana
    temporal), no se asume que sigue siendo la misma persona en ese lugar."""
    gestor, _ = _cargar_gestor()

    gestor.actualizar_posicion("persona-3", 5.0, 3.0, t=0.0, descriptor=_descriptor(4), camara_id="A")

    resultado = gestor.intentar_fusionar("B", 5.0, 3.0, t=10.0, descriptor=_descriptor(4))
    assert resultado is None, "No deberia fusionar: paso demasiado tiempo (10s) para asumir la misma persona"
    print("[OK] no fusiona si la reaparicion esta fuera de la ventana temporal")


def test_desempate_por_descriptor_con_candidatos_ambiguos():
    """Dos personas de camara A estan cerca entre si; una nueva deteccion de
    camara B, ambigua en distancia, debe resolverse por el descriptor (capa 2)."""
    gestor, _ = _cargar_gestor(umbral_distancia_metros=1.5)

    descriptor_rojo = _descriptor(hue_dominante=0)
    descriptor_azul = _descriptor(hue_dominante=5)

    gestor.actualizar_posicion("persona-roja", 5.0, 3.0, t=1.0, descriptor=descriptor_rojo, camara_id="A")
    gestor.actualizar_posicion("persona-azul", 5.3, 3.0, t=1.0, descriptor=descriptor_azul, camara_id="A")

    resultado = gestor.intentar_fusionar("B", 5.15, 3.0, t=1.05, descriptor=descriptor_azul)
    assert resultado == "persona-azul", f"Se esperaba desempatar hacia persona-azul, se obtuvo {resultado}"
    print("[OK] capa 2 (descriptor no biometrico) desempata correctamente entre 2 candidatos ambiguos")


def test_purgar_antiguos_libera_personas_que_ya_no_estan():
    gestor, _ = _cargar_gestor()
    gestor.actualizar_posicion("persona-4", 5.0, 3.0, t=0.0, descriptor=None, camara_id="A")
    gestor.purgar_antiguos(t_actual=10.0, max_antiguedad_s=3.0)
    assert "persona-4" not in gestor.activos, "Deberia haberse purgado tras 10s sin verse (max 3s)"
    print("[OK] purgar_antiguos libera correctamente a quien ya no se ve en ninguna camara")


def test_kalman_mantiene_id_ante_oclusion_corta():
    """Mono-camara: si la deteccion falta un par de frames (oclusion), el
    mismo id de track debe recuperarse en vez de crear uno nuevo."""
    tracker = ByteTrackPuntos(umbral_alto=0.6, max_frames_perdido=5)

    class DetFalsa:
        def __init__(self, x, y, confianza=0.9):
            self.x, self.y, self.confianza = x, y, confianza

    posiciones = [(100 + 5 * i, 200) for i in range(10)]  # camina en linea recta
    ids_vistos = []
    for i, (x, y) in enumerate(posiciones):
        detecciones = [] if 4 <= i <= 5 else [DetFalsa(x, y)]
        activos, _, _ = tracker.actualizar(detecciones, t=i / 25.0)
        if activos:
            ids_vistos.append(activos[0].id)

    assert len(set(ids_vistos)) == 1, f"El id deberia mantenerse estable, se vieron: {set(ids_vistos)}"
    print(f"[OK] ByteTrack+Kalman mantiene el mismo id ({ids_vistos[0]}) pese a 2 frames de oclusion")


if __name__ == "__main__":
    test_fusion_misma_persona_vista_por_dos_camaras()
    test_no_fusiona_personas_lejanas()
    test_no_fusiona_fuera_de_la_ventana_temporal()
    test_desempate_por_descriptor_con_candidatos_ambiguos()
    test_purgar_antiguos_libera_personas_que_ya_no_estan()
    test_kalman_mantiene_id_ante_oclusion_corta()
    print("\nTodas las pruebas sinteticas pasaron.")
