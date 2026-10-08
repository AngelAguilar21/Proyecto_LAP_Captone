"""Tracklet: tramo continuo de un id local de una cámara, con sus vistas Re-ID y su trayectoria.

Portado de AeroVision (camaras_reid.Tracklet). Un id local de ByteTrack puede
partirse en varios tracklets si el Re-ID detecta que cambió la persona, y un
tracklet nuevo nace si el id local desaparece más de `tracklet_gap_s`.
"""
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Tracklet:
    """Tramo continuo de un local_id con sus vistas Re-ID y posiciones en el plano."""
    uid: str
    tracklet_uuid: str
    camera_id: str
    local_id: int
    inicio_s: float
    fin_s: float
    global_id: int
    vistas: dict = field(default_factory=dict)
    suma: np.ndarray | None = None
    n_muestras: int = 0
    pendientes: list = field(default_factory=list)
    verificar: bool = False
    huella: deque = field(default_factory=lambda: deque(maxlen=24))
    tiempos: deque = field(default_factory=lambda: deque(maxlen=120))
    posiciones: deque = field(default_factory=lambda: deque(maxlen=180))
    primera_posicion: tuple | None = None
    ultima_posicion: tuple | None = None
    ultimo_muestreo: float = -math.inf
    ultimo_vector: np.ndarray | None = None
    observaciones: int = 0
    match_score: float | None = None
    corte_s: float = math.inf
    sucesor: str | None = None

    def prototipo(self):
        """Memoria multivista: promedio normalizado de todas las vistas (frente, espalda y costado)."""
        return None if self.suma is None else self.suma / (np.linalg.norm(self.suma) + 1e-12)

    def orientacion(self):
        """F/E/C según el desplazamiento de los pies en la imagen (cámara elevada); '?' si está quieto."""
        if len(self.huella) < 2:
            return "?"
        ultimo = self.huella[-1]
        primero = next((p for p in self.huella if ultimo[0] - p[0] <= 0.8), None)
        dt = ultimo[0] - primero[0]
        if dt < 0.3:
            return "?"
        alto = max(ultimo[3], 1.0)
        dx, dy = (ultimo[1] - primero[1]) / alto / dt, (ultimo[2] - primero[2]) / alto / dt
        if math.hypot(dx, dy) < 0.15:
            return "?"
        if abs(dy) >= 0.7 * abs(dx):
            return "F" if dy > 0 else "E"
        return "C"

    def guardar_vista(self, orientacion, vector):
        """Suma una vista Re-ID al prototipo del tracklet."""
        self.vistas[orientacion] = self.vistas.get(orientacion, 0) + 1
        self.suma = vector.copy() if self.suma is None else self.suma + vector
        self.n_muestras += 1

    def movimiento(self):
        """Velocidad en el plano (unidades por segundo) con una ventana >= 0.25 s para no amplificar el jitter."""
        if len(self.posiciones) < 2:
            return None
        ultima = self.posiciones[-1]
        primera = next((p for p in reversed(self.posiciones) if 0.25 <= ultima[0] - p[0] <= 1.5), None)
        if primera is None:
            return None
        return (np.array(ultima[1:]) - primera[1:]) / (ultima[0] - primera[0])


def se_solapan(a, b):
    """True si dos tracklets coinciden en el tiempo."""
    return min(a.fin_s, b.fin_s) - max(a.inicio_s, b.inicio_s) >= -1e-8
