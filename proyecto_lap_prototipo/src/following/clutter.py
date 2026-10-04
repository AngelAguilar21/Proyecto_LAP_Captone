"""Filtros contra falsos positivos de personas: gorros, pósters, reflejos pequeños.

YOLO a baja confianza confunde objetos con personas. Dos señales baratas y
generales, sin entrenar nada, descartan la mayoría:

1. Tamaño relativo: una detección dudosa mucho más pequeña que las personas
   seguras de la misma cámara es casi siempre un objeto (un gorro, una cara de
   póster). La referencia se aprende de la propia escena, así que funciona con
   cámaras a distinta altura.
2. Inmovilidad: un track que nunca se mueve y que además tiene baja confianza
   es mobiliario o exhibición. Una persona quieta pero bien detectada se conserva.
"""
from collections import deque

import numpy as np


def touches_border(box, size, margin=10):
    """Una persona cortada por el borde de la imagen parece más pequeña y dudosa: no es un objeto."""
    if box is None or size is None:
        return False
    width, height = size
    return box[0] <= margin or box[1] <= margin or box[2] >= width - margin or box[3] >= height - margin


class SizeFilter:
    """Descarta detecciones dudosas muy pequeñas frente a las personas seguras."""

    def __init__(self, sure_conf=.6, ratio=.62, min_refs=3, window=60):
        self.sure_conf = sure_conf
        self.ratio = ratio
        self.min_refs = min_refs
        self.heights = deque(maxlen=window)

    def reference(self):
        return float(np.median(self.heights)) if len(self.heights) >= self.min_refs else None

    def apply(self, detections, size=None):
        for d in detections:
            if d.confianza >= self.sure_conf and getattr(d, "box", None) is not None:
                self.heights.append(d.box[3] - d.box[1])
        ref = self.reference()
        if ref is None:
            return list(detections), 0
        kept = [d for d in detections
                if d.confianza >= self.sure_conf or getattr(d, "box", None) is None
                or touches_border(d.box, size) or (d.box[3] - d.box[1]) >= ref * self.ratio]
        return kept, len(detections) - len(kept)


class StaticClutter:
    """Marca tracks inmóviles de baja confianza (objetos, no personas)."""

    def __init__(self, min_age=2.0, max_move=.25, max_mean_score=.6):
        self.min_age = min_age
        self.max_move = max_move          # fracción del ancho de la caja
        self.max_mean_score = max_mean_score
        self.state = {}

    def update(self, tracks, t, size=None):
        """Devuelve los ids de tracks a ignorar en este instante."""
        suppressed = set()
        for tr in tracks:
            x, y = tr.posicion
            box = tr.ultima_caja
            width = (box[2] - box[0]) if box is not None else 40.
            s = self.state.setdefault(tr.id, {"t0": t, "x": x, "y": y, "move": 0., "n": 0, "score": 0.})
            s["move"] = max(s["move"], float(np.hypot(x - s["x"], y - s["y"])))
            s["n"] += 1
            s["score"] += tr.score
            if touches_border(box, size):
                s["t0"] = t  # truncado por el borde: no se puede juzgar, reinicia la espera
                continue
            if (t - s["t0"] >= self.min_age and s["move"] < max(8., self.max_move * width)
                    and s["score"] / s["n"] < self.max_mean_score):
                suppressed.add(tr.id)
        live = {tr.id for tr in tracks}
        self.state = {k: v for k, v in self.state.items() if k in live}
        return suppressed
