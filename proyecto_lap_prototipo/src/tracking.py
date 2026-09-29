"""
Tracking mono-camara adaptado de ByteTrack (arXiv:2110.06864) para puntos de
cabeza en vez de cajas completas.

La asociacion usa distancia euclidiana en pixeles (no IoU de cajas): se
probo con una caja fija de 20px por punto y se rompia constantemente -- con
gente caminando junta, dos cabezas pueden estar a 15-25px de distancia en
esta vista tan oblicua, y apenas P2PNet fallaba una deteccion por 1 frame
(pasa seguido), el Kalman quedaba a 10px de la reaparicion, lo cual ya
bastaba para tirar el IoU de dos cajas de 20x20 por debajo del umbral y
crear un id nuevo en vez de recuperar el track. La distancia euclidiana con
la asignacion hungara (que igual busca el emparejamiento global optimo, no
"nearest neighbor" ingenuo) tolera mejor ese jitter tipico del detector.

No se reimplementa el filtro de Kalman: se usa filterpy con un modelo de
velocidad constante (x, y, vx, vy). La asignacion usa `lap` (Jonker-Volgenant),
la misma libreria que usa el repo oficial de ByteTrack.

La asociacion en dos etapas (alta confianza primero, baja despues) sigue el
algoritmo del paper: esto es lo que permite mantener el ID estable ante
oclusiones cortas y detecciones ruidosas.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

import numpy as np
import lap
from filterpy.kalman import KalmanFilter

DISTANCIA_MAX_ALTA_PX = 45.0  # gating para detecciones de alta confianza
DISTANCIA_MAX_BAJA_PX = 45.0  # gating para el segundo intento con detecciones de baja confianza


def _crear_kalman(x: float, y: float) -> KalmanFilter:
    kf = KalmanFilter(dim_x=4, dim_z=2)
    kf.F = np.array([
        [1, 0, 1, 0],
        [0, 1, 0, 1],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ], dtype=np.float64)
    kf.H = np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
    ], dtype=np.float64)
    kf.R *= 5.0
    kf.P *= 100.0
    kf.Q *= 0.5
    kf.x = np.array([x, y, 0.0, 0.0], dtype=np.float64)
    return kf


class EstadoTrack(Enum):
    ACTIVO = "activo"
    PERDIDO = "perdido"


@dataclass
class TrackPersona:
    id: int
    kf: KalmanFilter
    score: float
    ultimo_t: float
    frames_sin_actualizar: int = 0
    estado: EstadoTrack = EstadoTrack.ACTIVO
    ultima_posicion_real: Tuple[float, float] = None
    ultima_velocidad_real: Tuple[float, float] = None
    ultima_caja: Tuple[float, float, float, float] = None

    @property
    def posicion(self) -> Tuple[float, float]:
        return float(self.kf.x[0]), float(self.kf.x[1])

    @property
    def velocidad(self) -> Tuple[float, float]:
        return float(self.kf.x[2]), float(self.kf.x[3])

    def predecir(self):
        self.kf.predict()

    def actualizar(self, x: float, y: float, score: float, t: float, box=None):
        self.kf.update(np.array([x, y]))
        self.score = score
        self.ultimo_t = t
        self.frames_sin_actualizar = 0
        self.estado = EstadoTrack.ACTIVO
        self.ultima_posicion_real = (x, y)
        self.ultima_velocidad_real = self.velocidad
        if box is not None:
            self.ultima_caja = tuple(float(value) for value in box)


def _distancia_matriz(puntos_a: List[Tuple[float, float]], puntos_b: List[Tuple[float, float]]) -> np.ndarray:
    if len(puntos_a) == 0 or len(puntos_b) == 0:
        return np.zeros((len(puntos_a), len(puntos_b)), dtype=np.float32)
    a = np.asarray(puntos_a, dtype=np.float32)
    b = np.asarray(puntos_b, dtype=np.float32)
    return np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)


def _asignar(costo: np.ndarray, umbral: float):
    """Asignacion hungara (Jonker-Volgenant, via `lap`) con limite de costo.
    Devuelve (pares emparejados, filas sin pareja, columnas sin pareja)."""
    if costo.size == 0:
        return [], list(range(costo.shape[0])), list(range(costo.shape[1]))
    _, filas, columnas = lap.lapjv(costo, extend_cost=True, cost_limit=umbral)
    emparejados = [(i, filas[i]) for i in range(len(filas)) if filas[i] >= 0]
    sin_pareja_filas = [i for i in range(costo.shape[0]) if filas[i] < 0]
    sin_pareja_columnas = [j for j in range(costo.shape[1]) if columnas[j] < 0]
    return emparejados, sin_pareja_filas, sin_pareja_columnas


class ByteTrackPuntos:
    def __init__(self, umbral_alto: float = 0.6, umbral_bajo: float = 0.1,
                 distancia_max_alta_px: float = DISTANCIA_MAX_ALTA_PX,
                 distancia_max_baja_px: float = DISTANCIA_MAX_BAJA_PX,
                 max_frames_perdido: int = 30):
        self.umbral_alto = umbral_alto
        self.umbral_bajo = umbral_bajo
        self.distancia_max_alta_px = distancia_max_alta_px
        self.distancia_max_baja_px = distancia_max_baja_px
        self.max_frames_perdido = max_frames_perdido
        self.tracks_activos: List[TrackPersona] = []
        self.tracks_perdidos: List[TrackPersona] = []
        self._siguiente_id = 1

    def actualizar(self, detecciones, t: float):
        """detecciones: iterable de objetos con atributos x, y, confianza
        (p.ej. DeteccionCabeza de detection.py).
        Devuelve (tracks_activos, nuevos, expirados): nuevos son tracks
        recien creados en este frame; expirados son tracks que agotaron el
        buffer de oclusion y ya no se van a recuperar dentro de esta camara."""
        altas = [d for d in detecciones if d.confianza >= self.umbral_alto]
        bajas = [d for d in detecciones if self.umbral_bajo <= d.confianza < self.umbral_alto]

        candidatos = self.tracks_activos + self.tracks_perdidos
        for track in candidatos:
            track.predecir()

        # Etapa 1: detecciones de alta confianza vs todos los candidatos
        # (activos + perdidos, para poder recuperar el ID tras una oclusion corta)
        posiciones_candidatos = [t.posicion for t in candidatos]
        posiciones_altas = [(d.x, d.y) for d in altas]
        costo1 = _distancia_matriz(posiciones_candidatos, posiciones_altas)
        emparejados1, _, _ = _asignar(costo1, self.distancia_max_alta_px)

        usados_altas = set()
        emparejados_etapa1 = set()
        for i_c, i_d in emparejados1:
            candidatos[i_c].actualizar(altas[i_d].x, altas[i_d].y, altas[i_d].confianza, t, getattr(altas[i_d], "box", None))
            usados_altas.add(i_d)
            emparejados_etapa1.add(i_c)

        # Etapa 2: detecciones de baja confianza vs candidatos que siguen sin pareja
        indices_restantes = [i for i in range(len(candidatos)) if i not in emparejados_etapa1]
        posiciones_restantes = [candidatos[i].posicion for i in indices_restantes]
        posiciones_bajas = [(d.x, d.y) for d in bajas]
        costo2 = _distancia_matriz(posiciones_restantes, posiciones_bajas)
        emparejados2, _, _ = _asignar(costo2, self.distancia_max_baja_px)

        emparejados_etapa2 = set()
        for i_r, i_d in emparejados2:
            i_c = indices_restantes[i_r]
            candidatos[i_c].actualizar(bajas[i_d].x, bajas[i_d].y, bajas[i_d].confianza, t, getattr(bajas[i_d], "box", None))
            emparejados_etapa2.add(i_c)

        # Candidatos sin pareja en ninguna etapa: se marcan/mantienen perdidos
        for i, track in enumerate(candidatos):
            if i not in emparejados_etapa1 and i not in emparejados_etapa2:
                track.frames_sin_actualizar += 1
                track.estado = EstadoTrack.PERDIDO

        self.tracks_activos = [t for t in candidatos if t.estado == EstadoTrack.ACTIVO]
        perdidos_vigentes = [
            t for t in candidatos
            if t.estado == EstadoTrack.PERDIDO and t.frames_sin_actualizar <= self.max_frames_perdido
        ]
        # Tracks que ByteTrack ya da por perdidos definitivamente (agotaron el
        # buffer de oclusion): a partir de aqui la continuidad, si existe, ya
        # no es un problema mono-camara sino de cross_camera.py.
        expirados = [
            t for t in candidatos
            if t.estado == EstadoTrack.PERDIDO and t.frames_sin_actualizar > self.max_frames_perdido
        ]
        self.tracks_perdidos = perdidos_vigentes

        # Detecciones de alta confianza que no matchearon con nada -> nuevos tracks
        nuevos = []
        for i_d, d in enumerate(altas):
            if i_d not in usados_altas:
                nuevo = TrackPersona(id=self._siguiente_id, kf=_crear_kalman(d.x, d.y),
                                      score=d.confianza, ultimo_t=t,
                                      ultima_caja=getattr(d, "box", None))
                self._siguiente_id += 1
                nuevos.append(nuevo)
        self.tracks_activos.extend(nuevos)

        return self.tracks_activos, nuevos, expirados
