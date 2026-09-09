"""
Continuidad entre camaras con CAMPO DE VISION SUPERPUESTO (no un tramo ciego
real): camara A y camara B ven en buena parte la misma explanada desde
angulo/altura distintos. El problema entonces no es "cuanto tarda alguien en
cruzar un hueco caminando", sino "¿esta deteccion nueva de camara B es la
misma persona que camara A ya esta viendo, en la misma zona del plano
compartido y casi al mismo instante?" -- asociacion espacio-temporal
simultanea, adaptada de "Enhancing Multi-Camera People Tracking with
Anchor-Guided Clustering and Spatio-Temporal Consistency ID Re-Assignment"
(arXiv:2304.09471) a un par de camaras con solape en vez de topologia de
corredor con huecos.

Capa 1 (obligatoria): cercania en el plano compartido (misma posicion real,
vista desde dos angulos) dentro de una ventana de tiempo corta.

Capa 2 (solo si hay ambiguedad): descriptor no biometrico (color de ropa +
proporcion alto/ancho) para desempatar entre varios candidatos cercanos.
Nunca se usa como identificador unico.
"""
import math
from typing import Dict, Optional

from nodes import NodoCamara, DescriptorApariencia, distancia_descriptores


class GestorContinuidad:
    def __init__(self, camaras: Dict[str, NodoCamara], umbral_distancia_metros: float = 1.5,
                 ventana_temporal_s: float = 1.0):
        """umbral_distancia_metros: que tan cerca en el plano compartido deben
        estar dos observaciones (de camaras distintas) para considerarlas la
        misma persona. ventana_temporal_s: que tan separadas en el tiempo
        pueden estar esas dos observaciones (cubre el desfase normal entre
        camaras y la diferencia de un par de frames de deteccion)."""
        self.camaras = camaras
        self.umbral_distancia_metros = umbral_distancia_metros
        self.ventana_temporal_s = ventana_temporal_s
        # id_global -> {"x", "y", "t", "descriptor", "camara"}: ultima vez
        # que se vio a cada persona activa, desde cualquier camara.
        self.activos: Dict[str, dict] = {}

    def actualizar_posicion(self, id_global: str, x: float, y: float, t: float,
                             descriptor: Optional[DescriptorApariencia], camara_id: str):
        """Refresca la posicion/descriptor conocidos de un id_global. Se llama
        para TODO track activo en cada frame (no solo los recien creados) para
        que la otra camara siempre pueda comparar contra el dato mas fresco."""
        self.activos[id_global] = {"x": x, "y": y, "t": t, "descriptor": descriptor, "camara": camara_id}

    def intentar_fusionar(self, camara_id: str, x: float, y: float, t: float,
                           descriptor: Optional[DescriptorApariencia]) -> Optional[str]:
        """Para un track nuevo (sin id_global todavia) visto por camara_id en
        el punto (x, y) del plano compartido al tiempo t: busca entre las
        personas activas vistas por OTRA camara si alguna esta lo bastante
        cerca en espacio y tiempo como para tratarse de la misma persona.
        Devuelve el id_global a reutilizar, o None si hay que crear uno nuevo."""
        candidatos = []
        for id_global, info in self.activos.items():
            if info["camara"] == camara_id:
                continue  # la continuidad dentro de la misma camara ya la da ByteTrack
            if info["camara"] not in self.camaras[camara_id].vecinos:
                continue
            if abs(t - info["t"]) > self.ventana_temporal_s:
                continue
            distancia = math.hypot(x - info["x"], y - info["y"])
            if distancia <= self.umbral_distancia_metros:
                candidatos.append((id_global, info, distancia))

        if not candidatos:
            return None
        if len(candidatos) == 1:
            return candidatos[0][0]

        # Capa 2: varios candidatos cercanos -> desempatar por descriptor no biometrico
        if descriptor is None:
            return min(candidatos, key=lambda c: c[2])[0]
        return min(
            candidatos,
            key=lambda c: distancia_descriptores(c[1]["descriptor"], descriptor)
            if c[1]["descriptor"] is not None else float("inf"),
        )[0]

    def purgar_antiguos(self, t_actual: float, max_antiguedad_s: float = 3.0):
        """Descarta del registro de activos a quien no se ha vuelto a ver en
        un rato (salio de ambas camaras), para no comparar contra datos viejos."""
        self.activos = {
            id_global: info for id_global, info in self.activos.items()
            if (t_actual - info["t"]) <= max_antiguedad_s
        }
