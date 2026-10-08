"""Piso transitable: ninguna posición queda fuera del piso ni dentro de un obstáculo.

Portado de AeroVision (historico/piso.py) sin pandas. Las cámaras ubican a cada persona con un error de algunos
decímetros, así que un punto puede caer dentro de una pared, de una zona restringida o fuera del plano, donde nadie
camina. Cada posición inválida se lleva al punto libre más cercano: dentro del contorno del piso y a `margen` (el radio
de una persona) de cada obstáculo. Las posiciones válidas no se tocan.

En AeroTrack el piso es el área de trabajo del plano (`workArea`, o el plano completo) y los obstáculos son las zonas de
tipo pared y restringida.
"""
import numpy as np

from .zonas import dentro_poligono


def _lados(poligono, hacia_adentro):
    """Inicio, vector y normal unitaria (hacia adentro o hacia afuera) de cada lado del polígono."""
    a = np.asarray(poligono, dtype=float)
    d = np.roll(a, -1, axis=0) - a
    antihorario = np.sum(a[:, 0] * (a[:, 1] + d[:, 1]) - (a[:, 0] + d[:, 0]) * a[:, 1]) > 0
    n = np.c_[-d[:, 1], d[:, 0]] / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-12)[:, None]
    return a, d, n * (1.0 if antihorario == hacia_adentro else -1.0)


def _proyectar(p, a, d):
    """Punto más cercano de cada lado a cada posición: p (N, 2) -> (N, L, 2)."""
    t = np.clip(((p[:, None, :] - a) * d).sum(-1) / np.maximum((d * d).sum(-1), 1e-12), 0, 1)
    return a + t[..., None] * d


class PisoTransitable:
    """Contorno del piso y obstáculos del plano, con la holgura de una persona."""

    def __init__(self, piso=None, obstaculos=(), margen=0.2):
        self.piso = np.asarray(piso, dtype=float) if piso is not None and len(piso) >= 3 else None
        self.obstaculos = [np.asarray(o, dtype=float) for o in obstaculos if len(o) >= 3]
        self.margen = float(margen)
        lados = ([_lados(self.piso, True)] if self.piso is not None else []) + [_lados(o, False) for o in self.obstaculos]
        if lados:
            self._a, self._d, self._n = (np.concatenate(c) for c in zip(*lados))
        else:
            self._a = self._d = self._n = np.empty((0, 2))

    @property
    def activo(self):
        return self.piso is not None or bool(self.obstaculos)

    def libres(self, x, y, margen=None):
        """Máscara de las posiciones sobre el piso y a `margen` o más de todo obstáculo."""
        margen = self.margen if margen is None else margen
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        idx = np.flatnonzero(ok)
        if self.piso is not None:
            ok[idx] = dentro_poligono(x[idx], y[idx], self.piso)
        for o in self.obstaculos:
            idx = np.flatnonzero(ok)
            if not len(idx):
                break
            p = np.c_[x[idx], y[idx]]
            a, d, _ = _lados(o, False)
            cerca = np.hypot(*(p[:, None, :] - _proyectar(p, a, d)).transpose(2, 0, 1)).min(axis=1) < margen - 1e-9
            ok[idx] = ~dentro_poligono(x[idx], y[idx], o) & ~cerca
        return ok

    def _mas_cercano(self, x, y):
        """Punto libre más cercano: la proyección sobre algún lado, corrida `margen` hacia el lado libre."""
        p = np.array([[x, y]])
        base = _proyectar(p, self._a, self._d)[0]
        for margen in (self.margen, 1e-3):
            q = base + self._n * margen
            libres = np.flatnonzero(self.libres(q[:, 0], q[:, 1], margen - 1e-6))
            if len(libres):
                j = libres[np.argmin(np.hypot(q[libres, 0] - x, q[libres, 1] - y))]
                return q[j, 0], q[j, 1]
        return x, y

    def ajustar(self, x, y):
        """Posiciones llevadas al piso transitable y la máscara de las que se movieron."""
        x = np.array(x, dtype=float)
        y = np.array(y, dtype=float)
        if not self.activo:
            return x, y, np.zeros(len(x), dtype=bool)
        finitos = np.isfinite(x) & np.isfinite(y)
        movidos = finitos & ~self.libres(x, y)
        for i in np.flatnonzero(movidos):
            x[i], y[i] = self._mas_cercano(x[i], y[i])
        return x, y, movidos

    def ajustar_trayectorias(self, global_id, t, x, y, paso_s):
        """Como `ajustar`, y además cuida la posición de cada persona en cada instante.

        Se promedian las cámaras que ven a la misma persona en el mismo intervalo de `paso_s`: dos puntos libres a ambos
        lados de un obstáculo promedian dentro de él. Si eso pasa, las cámaras de ese instante se unen en el punto libre
        más cercano al promedio (así quedan libres cada punto y su promedio).
        """
        x, y, movidos = self.ajustar(x, y)
        if not self.activo or not len(x):
            return x, y, movidos
        _, personas = np.unique(np.asarray(global_id).astype(str), return_inverse=True)
        celdas = np.floor(np.asarray(t, dtype=float) / paso_s).astype(np.int64)
        claves, grupo = np.unique(np.c_[personas, celdas], axis=0, return_inverse=True)
        grupo = grupo.ravel()
        cuenta = np.bincount(grupo)
        media = np.c_[np.bincount(grupo, weights=x) / cuenta, np.bincount(grupo, weights=y) / cuenta][grupo]
        libre = self.libres(media[:, 0], media[:, 1]) | ~np.isfinite(media).all(axis=1)
        if libre.all():
            return x, y, movidos
        unicas, fila = np.unique(media[~libre], axis=0, return_inverse=True)
        nx, ny, _ = self.ajustar(unicas[:, 0], unicas[:, 1])
        idx = np.flatnonzero(~libre)
        x[idx], y[idx] = nx[fila.ravel()], ny[fila.ravel()]
        movidos[idx] = True
        return x, y, movidos


def piso_desde_config(config, margen=0.2):
    """Piso del plano activo: el área de trabajo (o el plano completo) y las paredes y zonas restringidas como obstáculos."""
    ancho, alto = float(config.get("width", 0)), float(config.get("height", 0))
    area = config.get("workArea")
    piso = area if area and len(area) >= 3 else ([[0, 0], [ancho, 0], [ancho, alto], [0, alto]] if ancho > 0 and alto > 0 else None)
    obstaculos = [z["points"] for z in config.get("zones", []) if z.get("kind") in ("wall", "restricted") and len(z.get("points") or []) >= 3]
    return PisoTransitable(piso, obstaculos, margen)
