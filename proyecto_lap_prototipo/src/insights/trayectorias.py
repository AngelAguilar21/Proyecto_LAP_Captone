"""Trayectorias consolidadas: una posición por persona e instante, a partir de una grabación (replay) de AeroTrack.

Portado de AeroVision (historico/consolidacion.py) sin pandas. Una persona vista por dos cámaras a la vez aporta dos
puntos en el mismo instante: se unen en uno solo (promedio ponderado por confianza) y después se descartan los saltos
físicamente imposibles. Las grabaciones de AeroTrack no guardan la confianza de cada punto, así que pesan igual.
"""
import json
from pathlib import Path

import numpy as np


class Consolidado:
    """Posiciones consolidadas ordenadas por persona y tiempo. Todos los campos son arreglos de la misma longitud."""

    CAMPOS = ("global_id", "t", "x", "y", "velocidad", "confianza", "observaciones")

    def __init__(self, **campos):
        for nombre in self.CAMPOS:
            setattr(self, nombre, np.asarray(campos[nombre]))
        self.zona = np.asarray(campos.get("zona", np.full(len(self.t), -1)), dtype=np.int64)

    def __len__(self):
        return len(self.t)

    def personas(self):
        """[(global_id, rebanada)] de cada persona (las filas de una persona son contiguas)."""
        if not len(self):
            return []
        cortes = np.flatnonzero(self.global_id[1:] != self.global_id[:-1]) + 1
        return [(str(self.global_id[a]), slice(a, b)) for a, b in zip(np.r_[0, cortes], np.r_[cortes, len(self)])]


def _sin_saltos(t, x, y, velocidad_max):
    """Máscara de las posiciones que se conservan: se quitan los picos aislados que exigirían superar la velocidad máxima."""
    activo = np.ones(len(t), dtype=bool)
    for _ in range(3):
        idx = np.flatnonzero(activo)
        if len(idx) < 3:
            break
        v = np.hypot(np.diff(x[idx]), np.diff(y[idx])) / np.maximum(np.diff(t[idx]), 1e-3)
        pico = np.zeros(len(idx), dtype=bool)
        pico[1:-1] = (v[:-1] > velocidad_max) & (v[1:] > velocidad_max)
        if not pico.any():
            break
        activo[idx[pico]] = False
    return activo


def _velocidad(t, x, y, medio=2):
    """Rapidez (unidades por segundo) con diferencias centrales de +-`medio` posiciones, para no amplificar el ruido."""
    n = len(t)
    if n < 2:
        return np.full(n, np.nan)
    i, j = np.clip(np.arange(n) - medio, 0, n - 1), np.clip(np.arange(n) + medio, 0, n - 1)
    return np.hypot(x[j] - x[i], y[j] - y[i]) / np.maximum(t[j] - t[i], 1e-3)


def consolidar(global_id, t, x, y, confianza=None, paso_s=0.2, velocidad_max=4.0):
    """Une las observaciones simultáneas de cada persona y quita los saltos imposibles. Devuelve un Consolidado."""
    global_id = np.asarray(global_id).astype(str)
    t, x, y = (np.asarray(v, dtype=float) for v in (t, x, y))
    vacio = Consolidado(global_id=np.array([], dtype=str), t=[], x=[], y=[], velocidad=[], confianza=[], observaciones=[])
    if not len(t):
        return vacio
    confianza = np.ones(len(t)) if confianza is None else np.asarray(confianza, dtype=float)
    _, persona = np.unique(global_id, return_inverse=True)
    instante = np.floor(t / paso_s).astype(np.int64)
    orden = np.lexsort((instante, persona))
    persona, instante, t, x, y, confianza, ids = (v[orden] for v in (persona, instante, t, x, y, confianza, global_id))
    w = np.clip(confianza, 1e-3, None)
    inicios = np.r_[0, np.flatnonzero((np.diff(persona) != 0) | (np.diff(instante) != 0)) + 1]
    n = np.diff(np.r_[inicios, len(t)])
    suma_w = np.add.reduceat(w, inicios)
    T, X, Y = (np.add.reduceat(w * v, inicios) / suma_w for v in (t, x, y))
    conf, grupo, nombres = np.add.reduceat(confianza, inicios) / n, persona[inicios], ids[inicios]
    columnas = {k: [] for k in Consolidado.CAMPOS}
    for p in np.unique(grupo):
        m = np.flatnonzero(grupo == p)
        mantener = _sin_saltos(T[m], X[m], Y[m], velocidad_max)
        m = m[mantener]
        v = _velocidad(T[m], X[m], Y[m])
        for campo, valor in zip(Consolidado.CAMPOS, (nombres[m], T[m], X[m], Y[m], v, conf[m], n[m])):
            columnas[campo].append(valor)
    return Consolidado(**{k: np.concatenate(v) for k, v in columnas.items()})


def desde_replay(directorio):
    """Observaciones de una grabación: (global_id, t, x, y) de cada persona con posición en el plano.

    Si la sesión se reagrupó al cerrar (motor reid_v2) los IDs ya son los finales; las pasadas breves
    (`confirmed: false`) no cuentan como personas y se omiten. Devuelve (meta, filas).
    """
    directorio = Path(directorio)
    meta = json.loads((directorio / "manifest.json").read_text(encoding="utf-8"))
    ids, t, x, y = [], [], [], []
    with (directorio / "samples.jsonl").open(encoding="utf-8") as fuente:
        for linea in fuente:
            try:
                muestra = json.loads(linea)
            except ValueError:
                break
            for camara in muestra.get("cameras", []):
                for p in camara.get("people", []):
                    if p.get("point") is None or p.get("confirmed", True) is False:
                        continue
                    ids.append(p["id"])
                    t.append(muestra["t"])
                    x.append(p["point"][0])
                    y.append(p["point"][1])
    return meta, {"global_id": np.array(ids, dtype=str), "t": np.array(t), "x": np.array(x), "y": np.array(y)}
