"""Zonas del plano para los insights: locales (interior y frente), colas y zonas generales.

Portado de AeroVision (historico/zonas.py), adaptado a las zonas de AeroTrack (`config["zones"]`):
  kind "commercial"        -> INTERIOR de un local (se vincula a un negocio por su ubicación o su nombre)
                              y un FRONTAGE derivado: una franja alrededor del local para medir la exposición
  kind "queue"             -> COLA
  kind "roi", "room",
       "corridor"          -> ZONA (permanencia, visitantes y densidad, sin eventos de local)
  kind "wall", "door",
       "restricted"        -> no son zonas de medición (las paredes y áreas restringidas son obstáculos del piso)
Las unidades son las del plano del proyecto (metros o relativas).
"""
from dataclasses import dataclass

import numpy as np

FRENTE_POR_DEFECTO = 1.5   # ancho de la franja de exposición alrededor de un local, en unidades del plano


@dataclass(frozen=True)
class Zona:
    """Polígono del plano; `local_id` agrupa el INTERIOR y el FRONTAGE de un mismo local."""
    id: int
    nombre: str
    tipo: str            # INTERIOR | FRONTAGE | COLA | ZONA
    local_id: str | None
    area: float
    vertices: np.ndarray  # (V, 2), sin repetir el primero al final
    origen: str | None = None   # id de la zona en la configuración


def area_poligono(vertices):
    """Área por la fórmula del cordón."""
    v = np.asarray(vertices, dtype=float)
    x, y = v[:, 0], v[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2)


def dentro_poligono(x, y, vertices, tolerancia=1e-6):
    """Máscara de los puntos dentro del polígono o sobre su borde (como ST_Covers de PostGIS)."""
    x = np.asarray(x, dtype=float)[:, None]
    y = np.asarray(y, dtype=float)[:, None]
    x1, y1 = vertices[:, 0], vertices[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cruce = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1)   # rayo hacia +X
    dentro = np.count_nonzero(cruce, axis=1) % 2 == 1
    dx, dy = x2 - x1, y2 - y1
    largo2 = dx * dx + dy * dy
    with np.errstate(divide="ignore", invalid="ignore"):
        u = np.clip(((x - x1) * dx + (y - y1) * dy) / np.where(largo2 > 0, largo2, 1), 0, 1)
    borde = np.hypot(x1 + u * dx - x, y1 + u * dy - y) <= tolerancia
    return dentro | borde.any(axis=1)


def asignar_zonas(x, y, zonas):
    """Zona de cada posición (id, o -1 si ninguna). Si cae en varias, gana INTERIOR y luego la de menor área."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    zona = np.full(len(x), -1, dtype=np.int64)
    validos = np.isfinite(x) & np.isfinite(y)
    for z in sorted(zonas, key=lambda z: (z.tipo != "INTERIOR", z.area, z.id)):
        libres = validos & (zona == -1)
        if not libres.any():
            break
        idx = np.flatnonzero(libres)
        zona[idx[dentro_poligono(x[idx], y[idx], z.vertices)]] = z.id
    return zona


def expandir_poligono(vertices, distancia):
    """Polígono desplazado `distancia` hacia afuera (ingletes). Exacto para formas convexas, que son las de un local."""
    a = np.asarray(vertices, dtype=float)
    d = np.roll(a, -1, axis=0) - a
    largo = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-12)
    antihorario = np.sum(a[:, 0] * np.roll(a[:, 1], -1) - np.roll(a[:, 0], -1) * a[:, 1]) > 0
    normal = np.c_[d[:, 1], -d[:, 0]] / largo[:, None] * (1.0 if antihorario else -1.0)   # hacia afuera
    previa = np.roll(normal, 1, axis=0)
    bisectriz = normal + previa
    escala = distancia / np.maximum(1 + (normal * previa).sum(axis=1), 1e-6)
    return a + bisectriz * escala[:, None]


def vincular_negocio(vertices, nombre, negocios, plano_id):
    """Id del negocio de un local: el que tiene su ubicación dentro del polígono y, si no, el de igual nombre."""
    candidatos = [n for n in negocios if (n.get("ubicacion") or {}).get("planId", plano_id) == plano_id]
    for n in candidatos:
        punto = (n.get("ubicacion") or {}).get("point")
        if punto and dentro_poligono([punto[0]], [punto[1]], vertices)[0]:
            return n["id"]
    limpio = (nombre or "").strip().lower()
    return next((n["id"] for n in candidatos if n["nombre"].strip().lower() == limpio), None)


def desde_config(config, negocios=(), frente=None):
    """Zonas de medición del plano activo. Devuelve {id: Zona} y la lista de locales [{local_id, name, negocio_id}]."""
    frente = float(frente if frente is not None else config.get("insightsFrente", FRENTE_POR_DEFECTO))
    plano = config.get("planId", "custom")
    zonas, locales, siguiente = {}, [], 1
    for z in config.get("zones", []):
        kind = z.get("kind", "roi")
        pts = np.asarray(z.get("points") or [], dtype=float)
        if kind in ("wall", "door", "restricted") or len(pts) < 3:
            continue
        origen = z.get("id") or z["name"]
        if kind == "commercial":
            negocio = vincular_negocio(pts, z["name"], negocios, plano)
            local = negocio or f"zona:{origen}"
            locales.append({"local_id": local, "name": z["name"], "negocio_id": negocio, "categoria": (z.get("business") or {}).get("category", "")})
            zonas[siguiente] = Zona(siguiente, z["name"], "INTERIOR", local, area_poligono(pts), pts, origen)
            siguiente += 1
            marco = expandir_poligono(pts, frente)
            zonas[siguiente] = Zona(siguiente, f"{z['name']} (frente)", "FRONTAGE", local, area_poligono(marco), marco, origen)
            siguiente += 1
        else:
            tipo = "COLA" if kind == "queue" else "ZONA"
            zonas[siguiente] = Zona(siguiente, z["name"], tipo, None, area_poligono(pts), pts, origen)
            siguiente += 1
    return zonas, locales
