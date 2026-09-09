"""
Nodo-camara y nodo-persona: las dos entidades base de la arquitectura.
Nada de identificadores biometricos aqui: NodoPersona solo guarda posicion,
zona, y un descriptor de apariencia no reversible (color de ropa + proporcion).
"""
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Nodo-camara
# ---------------------------------------------------------------------------

@dataclass
class NodoCamara:
    id: str
    video_path: str
    vecinos: list
    homografia: Optional[np.ndarray] = None  # 3x3, pixel -> PLANO COMPARTIDO (metros)

    def pixel_a_plano(self, px: float, py: float, ancho_frame: int, alto_frame: int):
        """Convierte un punto en pixeles del frame de esta camara a coordenadas
        del plano compartido (metros), el mismo sistema de referencia para
        todas las camaras -- imprescindible para poder comparar posiciones
        entre camara A y B en cross_camera.py.

        Requiere homografia calibrada (ver src/calibrar_camara.py). Como las
        camaras estan en angulo/altura distintos mirando la misma explanada
        (no es un pasillo recto visto de frente), no hay un mapeo lineal
        razonable sin calibrar: usar una aproximacion aqui daria posiciones
        con error suficiente para arruinar la fusion entre camaras.
        """
        if self.homografia is None:
            raise RuntimeError(
                f"La camara {self.id} no tiene homografia calibrada. Corre "
                f"src/calibrar_camara.py --video <video> --camara {self.id} "
                "usando las losetas del piso como referencia de distancia real."
            )
        punto = np.array([[[px, py]]], dtype=np.float32)
        transformado = cv2.perspectiveTransform(punto, self.homografia)
        return float(transformado[0, 0, 0]), float(transformado[0, 0, 1])


def cargar_camaras(ruta_config: str, ruta_calibracion: Optional[str] = None) -> dict:
    """Devuelve ({id_camara: NodoCamara}, area_comun) a partir de
    config/camaras.json, aplicando la homografia de config/calibracion.json
    si ya existe."""
    with open(ruta_config, "r", encoding="utf-8") as f:
        datos = json.load(f)

    calibraciones = {}
    if ruta_calibracion and Path(ruta_calibracion).exists():
        with open(ruta_calibracion, "r", encoding="utf-8") as f:
            calibraciones = json.load(f)

    camaras = {}
    for c in datos["camaras"]:
        homografia = None
        matriz = calibraciones.get(c["id"])
        if matriz:
            homografia = np.array(matriz, dtype=np.float32)
        camaras[c["id"]] = NodoCamara(
            id=c["id"],
            video_path=c["video_path"],
            vecinos=c["vecinos"],
            homografia=homografia,
        )
    return camaras, datos["area_comun"]


# ---------------------------------------------------------------------------
# Zonas / ROI
# ---------------------------------------------------------------------------

def cargar_zonas(ruta_zonas: str) -> list:
    with open(ruta_zonas, "r", encoding="utf-8") as f:
        datos = json.load(f)
    zonas = []
    for z in datos["zonas"]:
        zonas.append({
            "id": z["id"],
            "tipo": z["tipo"],
            "camara": z.get("camara"),
            "poligono": np.array(z["poligono"], dtype=np.float32),
        })
    return zonas


def cargar_alcances(ruta_alcance: str) -> dict:
    """{"A": poligono_pixeles, "B": poligono_pixeles} desde config/alcance.json
    (ver src/marcar_alcance.py). Si el archivo no existe o una camara no
    tiene poligono marcado, esa camara no se filtra (se detecta en todo el
    frame, comportamiento previo)."""
    ruta = Path(ruta_alcance)
    if not ruta.exists():
        return {}
    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return {cam: np.array(pts, dtype=np.int32) for cam, pts in datos.items()}


def dentro_del_alcance(x: float, y: float, poligono: Optional[np.ndarray],
                        margen_px: float = 15.0) -> bool:
    """True si el punto (pixel) cae dentro del poligono de alcance de la
    camara, o si esa camara no tiene poligono marcado (sin filtro).

    Se admite un margen de tolerancia (en distancia con signo al borde, via
    cv2.pointPolygonTest en modo measureDist) porque el borde marcado a mano
    sigue una linea diagonal (el limite real del piso en un angulo oblicuo),
    y el jitter normal de deteccion cuadro a cuadro puede tirar un punto
    genuino un par de pixeles al otro lado de esa linea."""
    if poligono is None:
        return True
    distancia = cv2.pointPolygonTest(poligono, (float(x), float(y)), True)
    return distancia >= -margen_px


def punto_en_zona(punto_xy, zonas: list) -> Optional[str]:
    """Dado un punto (x, y) en coordenadas de plano, devuelve el id de la
    zona que lo contiene, o None si cae fuera de todas."""
    for zona in zonas:
        if cv2.pointPolygonTest(zona["poligono"], tuple(punto_xy), False) >= 0:
            return zona["id"]
    return None


# ---------------------------------------------------------------------------
# Nodo-persona
# ---------------------------------------------------------------------------

@dataclass
class DescriptorApariencia:
    """Descriptor NO biometrico: histograma de color del torso + proporcion
    alto/ancho de la caja de la persona. Sirve solo para desempatar candidatos
    ambiguos en la continuidad entre camaras, nunca como identificador unico."""
    histograma_color: np.ndarray  # histograma HSV normalizado
    proporcion_alto_ancho: float


def distancia_descriptores(d1: DescriptorApariencia, d2: DescriptorApariencia,
                            peso_color: float = 0.7, peso_proporcion: float = 0.3) -> float:
    dist_color = cv2.compareHist(d1.histograma_color, d2.histograma_color, cv2.HISTCMP_BHATTACHARYYA)
    dist_proporcion = abs(d1.proporcion_alto_ancho - d2.proporcion_alto_ancho)
    return peso_color * dist_color + peso_proporcion * dist_proporcion


def crear_sustractor_fondo():
    """Las camaras son fijas, asi que una resta de fondo clasica alcanza para
    obtener una silueta aproximada de cada persona -- sin sumar un segundo
    modelo pesado solo para el descriptor no biometrico de desempate."""
    return cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=25, detectShadows=False)


def extraer_descriptor(frame_bgr: np.ndarray, mascara_fg: np.ndarray, punto_xy,
                        radio_busqueda: int = 60,
                        tam_crop_respaldo=(50, 70)) -> DescriptorApariencia:
    """Aproxima un descriptor no biometrico (color de ropa + alto/ancho) a
    partir del blob de foreground mas cercano al punto de cabeza detectado
    por P2PNet. Si no hay un blob claro cerca (ruido, oclusion parcial), usa
    un recorte fijo bajo el punto de cabeza como respaldo."""
    x, y = int(punto_xy[0]), int(punto_xy[1])
    alto_frame, ancho_frame = frame_bgr.shape[:2]

    x0, x1 = max(0, x - radio_busqueda), min(ancho_frame, x + radio_busqueda)
    y0, y1 = max(0, y - 5), min(alto_frame, y + radio_busqueda * 2)
    recorte_mascara = mascara_fg[y0:y1, x0:x1]

    caja = None
    if recorte_mascara.size > 0:
        contornos, _ = cv2.findContours(recorte_mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contornos:
            mayor = max(contornos, key=cv2.contourArea)
            if cv2.contourArea(mayor) > 200:
                cx, cy, cw, ch = cv2.boundingRect(mayor)
                caja = (x0 + cx, y0 + cy, cw, ch)

    if caja is None:
        ancho_c, alto_c = tam_crop_respaldo
        caja = (max(0, x - ancho_c // 2), y, ancho_c, alto_c)

    cx, cy, cw, ch = caja
    cw, ch = max(cw, 1), max(ch, 1)
    proporcion = ch / cw

    # Torso = mitad inferior de la caja (evita cabeza/cabello en el histograma)
    y_torso_ini = min(alto_frame - 1, cy + ch // 2)
    y_torso_fin = min(alto_frame, cy + ch)
    x_fin = min(ancho_frame, cx + cw)
    torso = frame_bgr[y_torso_ini:y_torso_fin, cx:x_fin]

    if torso.size == 0:
        histograma = np.zeros((8, 8), dtype=np.float32)
    else:
        torso_hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        histograma = cv2.calcHist([torso_hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
        cv2.normalize(histograma, histograma, 0, 1, cv2.NORM_MINMAX)

    return DescriptorApariencia(histograma_color=histograma, proporcion_alto_ancho=float(proporcion))


@dataclass
class Posicion:
    x: float
    y: float
    t: float
    zona: Optional[str]
    camara: Optional[str]
    predicha: bool = False  # True si viene de extrapolacion Kalman (no de una deteccion real)


@dataclass
class NodoPersona:
    id_global: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    camara_actual: Optional[str] = None
    zona_actual: Optional[str] = None
    descriptor: Optional[DescriptorApariencia] = None
    posiciones: list = field(default_factory=list)
    ids_locales_fusionados: list = field(default_factory=list)
    activo: bool = True

    def agregar_posicion(self, x, y, t, zona, camara, predicha=False):
        self.posiciones.append(Posicion(x=x, y=y, t=t, zona=zona, camara=camara, predicha=predicha))
        self.zona_actual = zona
        self.camara_actual = camara

    def actualizar_descriptor(self, nuevo_descriptor: DescriptorApariencia, alpha: float = 0.3):
        """Promedio movil simple para no depender de un solo frame."""
        if self.descriptor is None:
            self.descriptor = nuevo_descriptor
            return
        hist_mezclado = cv2.addWeighted(self.descriptor.histograma_color, 1 - alpha,
                                         nuevo_descriptor.histograma_color, alpha, 0)
        proporcion_mezclada = (1 - alpha) * self.descriptor.proporcion_alto_ancho \
            + alpha * nuevo_descriptor.proporcion_alto_ancho
        self.descriptor = DescriptorApariencia(hist_mezclado, proporcion_mezclada)
