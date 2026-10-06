"""Mapa de calor KDE, rutas frecuentes (PrefixSpan) y grafo origen-destino.

Portado de AeroVision (historico/kde.py y historico/rutas.py) sin cambios de método.
"""
from collections import Counter

import numpy as np


def kde_grilla(x, y, pesos, origen, columnas, filas, celda, h, radio_h=4.0):
    """KDE gaussiano ponderado evaluado en el centro de cada celda de la grilla.

        f(x, y) = suma w_i * K((x - X_i)/h, (y - Y_i)/h) / h^2,   K(u) = exp(-|u|^2 / 2) / 2pi

    Con pesos que suman el total que se quiere repartir (segundos-persona, o 1 por persona), f queda en esas unidades por
    unidad de área. `origen` es la esquina inferior izquierda; el resultado se aplana por filas (de abajo hacia arriba).
    Solo se suman los puntos a menos de `radio_h` anchos de banda por eje de cada celda: con 4 se pierde ~0,01 % del peso.
    """
    x, y, w = (np.asarray(v, dtype=float) for v in (x, y, pesos))
    cx = origen[0] + (np.arange(columnas) + 0.5) * celda
    cy = origen[1] + (np.arange(filas) + 0.5) * celda
    densidad = np.zeros((filas, columnas))
    norma = 1.0 / (2 * np.pi * h * h)
    for i in range(0, len(x), 4096):
        xs, ys, ws = x[i:i + 4096], y[i:i + 4096], w[i:i + 4096]
        dx = (cx[None, :] - xs[:, None]) / h        # separable: exp(-(dx2 + dy2)/2h2) = exp(-dx2/2h2) * exp(-dy2/2h2)
        dy = (cy[None, :] - ys[:, None]) / h
        kx = np.where(np.abs(dx) <= radio_h, np.exp(-0.5 * dx * dx), 0.0)
        ky = np.where(np.abs(dy) <= radio_h, np.exp(-0.5 * dy * dy), 0.0)
        densidad += np.einsum("n,nf,nc->fc", ws, ky, kx)
    return (densidad * norma).ravel()


def secuencias_semanticas(estancias_por_persona):
    """Secuencia ordenada de zonas de cada persona, sin repeticiones consecutivas ni tramos fuera de zona."""
    secuencias = {}
    for gid, tramos in estancias_por_persona.items():
        seq = []
        for e in tramos:
            if e.zona >= 0 and (not seq or seq[-1] != e.zona):
                seq.append(e.zona)
        if seq:
            secuencias[gid] = seq
    return secuencias


def prefixspan(secuencias, soporte_min, longitud_min=2, longitud_max=5):
    """Subsecuencias (no necesariamente contiguas) presentes en al menos `soporte_min` secuencias.

    Implementación clásica de PrefixSpan: cada patrón se extiende solo con los elementos frecuentes de su base proyectada
    (los sufijos que siguen a la primera aparición del prefijo en cada secuencia). Devuelve [(patrón, soporte)].
    """
    resultado = []

    def extender(prefijo, proyeccion):
        conteo = Counter()
        for sid, inicio in proyeccion:
            conteo.update(set(secuencias[sid][inicio:]))
        for item, soporte in conteo.items():
            if soporte < soporte_min:
                continue
            patron = prefijo + [item]
            if len(patron) >= longitud_min:
                resultado.append((patron, soporte))
            if len(patron) < longitud_max:
                nueva = [(sid, secuencias[sid].index(item, inicio) + 1) for sid, inicio in proyeccion if item in secuencias[sid][inicio:]]
                extender(patron, nueva)

    extender([], [(sid, 0) for sid in range(len(secuencias))])
    return resultado


def origen_destino(secuencias):
    """Peso de cada arista Zi -> Zj: personas únicas que pasaron directamente de Zi a Zj."""
    personas = Counter()
    for seq in secuencias:
        personas.update({(a, b) for a, b in zip(seq, seq[1:]) if a != b})
    return personas
