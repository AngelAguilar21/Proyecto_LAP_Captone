"""Directed camera routes. Coordinates alone never imply a traversable route."""
import math


def validate_routes(config):
    routes = config.get("cameraRoutes")
    if routes is None:
        return
    if not isinstance(routes, list) or len(routes) > 10000:
        raise ValueError("Las rutas deben ser una lista de hasta 10000 conexiones.")
    ids = {c["id"] for c in config.get("cameras", [])}
    seen = set()
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("Ruta de cámara inválida.")
        pair = (route.get("from"), route.get("to"))
        if any(not isinstance(v, str) or v not in ids for v in pair) or pair[0] == pair[1] or pair in seen:
            raise ValueError("Cada ruta debe conectar dos cámaras existentes, sin duplicados.")
        seen.add(pair)
        low, high = route.get("minSeconds", 0), route.get("maxSeconds", 120)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (low, high)) or not 0 <= low <= high <= 3600 or high <= 0:
            raise ValueError("Tiempo de ruta inválido: usa entre 0 y 3600 segundos.")
        if route.get("kind") not in ("overlap", "transition"):
            raise ValueError("Indica vista compartida o tránsito entre cámaras.")
        if route["kind"] == "overlap" and low != 0:
            raise ValueError("Las vistas compartidas necesitan un tiempo mínimo de cero.")


def allowed_pair(a, b, transitions, overlaps, reentry=120):
    """Gate two closed tracklets, including the final offline regrouping."""
    if a["camara"] == b["camara"]:
        return max(a["t0"], b["t0"]) > min(a["t1"], b["t1"]) and max(a["t0"], b["t0"]) - min(a["t1"], b["t1"]) <= reentry
    if max(a["t0"], b["t0"]) <= min(a["t1"], b["t1"]):
        return frozenset((a["camara"], b["camara"])) in overlaps
    source, target = (a, b) if a["t1"] < b["t0"] else (b, a)
    edge = transitions.get((source["camara"], target["camara"]))
    return bool(edge and edge["t_min_s"] <= target["t0"] - source["t1"] <= edge["t_max_s"])


def allowed_groups(group_a, group_b, transitions, overlaps, reentry=120):
    """Respeta una cadena A→B→C sin exigir una arista directa A→C."""
    for a in group_a:
        for b in group_b:
            simultaneous = max(a['t0'], b['t0']) <= min(a['t1'], b['t1']) + 1e-8
            if (simultaneous or a['camara'] == b['camara']) and not allowed_pair(a, b, transitions, overlaps, reentry):
                return False
    union = sorted([(a, 0) for a in group_a] + [(b, 1) for b in group_b], key=lambda pair: (pair[0]['t0'], pair[0]['camara']))
    for index, (current, origin) in enumerate(union):
        prior = union[:index]
        if not prior or any(row['t1'] >= current['t0'] - 1e-8 for row, _ in prior):
            continue
        previous, previous_origin = max(prior, key=lambda pair: pair[0]['t1'])
        if origin != previous_origin and not allowed_pair(previous, current, transitions, overlaps, reentry):
            return False
    return True
