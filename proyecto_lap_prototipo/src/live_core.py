"""Geometry, conservative camera handoffs and observed occupancy for the live UI.

Coordinates are always in a shared, user-defined plane. Association confidence is
a heuristic, not a calibrated probability. No biometric models are used here.
"""
import math
from collections import deque

import cv2
import numpy as np


def finite(value, low, high):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def validate_config(c):
    if not isinstance(c, dict):
        raise ValueError("La configuración debe ser un objeto.")
    for name in ("width", "height"):
        if not finite(c.get(name), 1, 10000):
            raise ValueError(f"{name}: valor entre 1 y 10000.")
    if c.get("unit") not in ("relative", "meters"):
        raise ValueError("Unidad inválida.")
    for key, lo, hi in [("radius", .01, 1000), ("minPeople", 2, 1000), ("dwell", 0, 3600), ("handoffSeconds", .1, 120), ("matchDistance", .01, 1000)]:
        if not finite(c.get(key), lo, hi):
            raise ValueError(f"Valor inválido: {key}.")
    if int(c["minPeople"]) != c["minPeople"]:
        raise ValueError("El mínimo de personas debe ser entero.")
    if not isinstance(c.get("clocksVerified"), bool):
        raise ValueError("Indicar si los relojes están verificados.")
    cameras = c.get("cameras")
    if not isinstance(cameras, list) or not 0 <= len(cameras) <= 32:
        raise ValueError("Configura como máximo 32 cámaras.")
    ids = set()
    for cam in cameras:
        if not isinstance(cam, dict):
            raise ValueError("Cámara inválida.")
        cid = cam.get("id", "")
        if not isinstance(cid, str) or not cid or len(cid) > 40 or not all(x.isalnum() or x in "_-" for x in cid) or cid in ids:
            raise ValueError("Cada cámara necesita un ID único, sin espacios ni símbolos especiales.")
        ids.add(cid)
        source = cam.get("source")
        if not ((isinstance(source, int) and not isinstance(source, bool) and 0 <= source <= 32) or (isinstance(source, str) and len(source) <= 2048)):
            raise ValueError(f"Fuente inválida: {cid}.")
        if not finite(cam.get("offset", 0), 0, 86400):
            raise ValueError("Offset debe ser no negativo (segundos que se omiten al inicio).")
        for key, maximum in [("x", c["width"]), ("y", c["height"])]:
            if not finite(cam.get(key), 0, maximum):
                raise ValueError(f"Posición {key} inválida en {cid}.")
        if not isinstance(cam.get("links", []), list):
            raise ValueError("links debe ser una lista de cámaras de destino.")
        for field, low, high in [("heading",0,360),("fov",5,170),("range",.01,10000),("height",0,10000),("tilt",0,90)]:
            if field in cam and not finite(cam[field], low, high):
                raise ValueError(f"{cid}: {field} fuera de rango.")
        for field in ("name", "location"):
            if field in cam and (not isinstance(cam[field], str) or len(cam[field]) > 160):
                raise ValueError(f"{cid}: {field} inválido.")
        pairs = cam.get("pairs", [])
        if not isinstance(pairs, list) or len(pairs) > 30:
            raise ValueError("Usa como máximo 30 correspondencias de calibración.")
        for p in pairs:
            if not isinstance(p, list) or len(p) != 4 or not all(finite(v, -10000, 10000) for v in p):
                raise ValueError("Cada correspondencia contiene [u, v, x, y].")
            if not 0 <= p[0] <= 1 or not 0 <= p[1] <= 1 or not 0 <= p[2] <= c["width"] or not 0 <= p[3] <= c["height"]:
                raise ValueError("Puntos fuera del video o del plano.")
        if len(pairs) >= 4:
            calibration(pairs)
        zone = cam.get("detectionZone")
        if zone is not None:
            if not isinstance(zone, list) or not 3 <= len(zone) <= 50:
                raise ValueError(f"{cid}: la zona de detección necesita entre 3 y 50 puntos.")
            for v in zone:
                if not isinstance(v, list) or len(v) != 2 or not finite(v[0], 0, 1) or not finite(v[1], 0, 1):
                    raise ValueError(f"{cid}: cada punto de la zona de detección es [u, v] normalizado entre 0 y 1.")
    for cam in cameras:
        if any(not isinstance(link, str) or link not in ids or link == cam["id"] for link in cam.get("links", [])):
            raise ValueError("Enlaces deben referirse a otras cámaras existentes.")
    zones = c.get("zones", [])
    if not isinstance(zones, list) or len(zones) > 100:
        raise ValueError("Máximo 100 zonas.")
    for z in zones:
        if not isinstance(z, dict) or not isinstance(z.get("name"), str) or not 1 <= len(z["name"]) <= 80:
            raise ValueError("Nombre de zona inválido.")
        pts = z.get("points")
        if not isinstance(pts, list) or not 3 <= len(pts) <= 100:
            raise ValueError("Una zona requiere de 3 a 100 puntos.")
        if any(not isinstance(p, list) or len(p) != 2 or not finite(p[0], 0, c["width"]) or not finite(p[1], 0, c["height"]) for p in pts):
            raise ValueError("Polígono fuera del plano.")
        if abs(cv2.contourArea(np.asarray(pts, dtype=np.float32))) < .000001:
            raise ValueError("El área dibujada es degenerada: separa sus vértices.")
        rule = z.get("rule")
        if rule is not None and (not isinstance(rule, dict) or not isinstance(rule.get("enabled"), bool) or not finite(rule.get("minPeople"),2,1000) or int(rule["minPeople"]) != rule["minPeople"] or not finite(rule.get("dwell"),0,3600)):
            raise ValueError("Regla de zona inválida.")
    bg = c.get("background", "")
    if not isinstance(bg, str) or len(bg) > 3000000 or (bg and not bg.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,"))):
        raise ValueError("El fondo debe ser una imagen PNG, JPEG o WebP de menos de 2 MB.")
    for field in ("airport", "floor", "planName"):
        if field in c and (not isinstance(c[field],str) or len(c[field])>200):
            raise ValueError(f"Campo {field} inválido.")
    if c.get("sourceMode", "recordings") not in ("recordings", "live", "demo"):
        raise ValueError("Modo de fuente inválido.")
    return c


def calibration(pairs):
    if len(pairs) < 4:
        return None
    points = np.asarray(pairs, dtype=np.float64)
    h, _ = cv2.findHomography(points[:, :2], points[:, 2:], 0)
    if h is None or not np.isfinite(h).all() or np.linalg.matrix_rank(h) < 3:
        raise ValueError("Calibración degenerada: distribuye los puntos por el suelo visible.")
    projected = cv2.perspectiveTransform(points[:, :2].reshape(-1, 1, 2), h).reshape(-1, 2)
    span = max(float(np.ptp(points[:, 2:], axis=0).max()), .01)
    if float(np.linalg.norm(projected - points[:, 2:], axis=1).max()) > span * .08:
        raise ValueError("Correspondencias inconsistentes; revisa los puntos de calibración.")
    return h


def project(h, u, v):
    q = h @ np.array([u, v, 1.0])
    if abs(q[2]) < 1e-8:
        return None
    p = q[:2] / q[2]
    return tuple(map(float, p)) if np.isfinite(p).all() else None


def color_distance(a, b):
    if a is None or b is None:
        return .5
    return float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))


class IdentityStore:
    """One assignment per global ID per camera per tick, with ambiguity rejection.

    Overlap compares simultaneous ground positions. Non-overlap uses declared
    directed camera links, elapsed time, velocity, and a clothing-color gate.
    Both are explicitly labelled 'estimated' camera associations.
    """
    def __init__(self, config):
        self.config = config
        self.people = {}
        self.local = {}
        self.serial = 0
        self.events = deque(maxlen=150)

    def update(self, observations, t):
        cfg = self.config
        claimed = set()
        observed_keys = {(o["camera"], o["local"]) for o in observations}
        mapped = {self.local[k] for k in observed_keys if k in self.local}
        output = []
        # Existing tracks first: this makes handoffs independent of camera ordering.
        ordered = sorted(observations, key=lambda o: (o["camera"], o["local"]) not in self.local)
        for o in ordered:
            key = (o["camera"], o["local"])
            gid = self.local.get(key)
            if gid is not None and (gid, o["camera"]) in claimed:
                gid = None
            association = "local"
            if gid is None and o.get("point") is not None and cfg["clocksVerified"]:
                candidates = []
                for pid, p in self.people.items():
                    if (pid, o["camera"]) in claimed or p["camera"] == o["camera"] or p["point"] is None:
                        continue
                    dt = t - p["t"]
                    if dt < 0 or dt > cfg["handoffSeconds"]:
                        continue
                    old_cam = next(c for c in cfg["cameras"] if c["id"] == p["camera"])
                    if o["camera"] not in old_cam.get("links", []):
                        continue
                    # A track still observed elsewhere can only match as an overlap.
                    overlap = pid in mapped or dt <= .5
                    if overlap:
                        target = p["point"]
                        gate = cfg["matchDistance"]
                    else:
                        target = (p["point"][0] + p["velocity"][0] * dt, p["point"][1] + p["velocity"][1] * dt)
                        gate = cfg["matchDistance"] * (1 + min(dt, 5) * .15)
                    dist = math.dist(o["point"], target)
                    appearance = color_distance(o.get("color"), p.get("color"))
                    if dist <= gate and appearance <= .65:
                        candidates.append((dist / gate + appearance * .3, pid))
                candidates.sort()
                if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] > .25):
                    gid = candidates[0][1]
                    association = "estimated"
                    self.events.appendleft({"type": "handoff", "id": gid, "from": self.people[gid]["camera"], "to": o["camera"], "t": t})
                elif candidates:
                    association = "uncertain"
            if gid is None:
                self.serial += 1
                gid = f"P{self.serial:05d}"
                self.people[gid] = {"history": deque(maxlen=180), "velocity": (0., 0.), "t": t, "point": None, "association": association}
            self.local[key] = gid
            claimed.add((gid, o["camera"]))
            p = self.people[gid]
            if o["point"] is not None and p["point"] is not None and t > p["t"]:
                dt = t - p["t"]
                p["velocity"] = tuple(.5 * p["velocity"][i] + .5 * (o["point"][i] - p["point"][i]) / dt for i in (0, 1))
            if association != "local":
                p["association"] = association
            p.update(camera=o["camera"], point=o["point"], t=t, color=o.get("color"))
            if o["point"] is not None:
                if not p["history"] or p["history"][-1][2] != t:
                    p["history"].append([*o["point"], t])
            neighbors = next(c for c in cfg["cameras"] if c["id"]==o["camera"]).get("links",[])
            next_camera = None
            if o["point"] is not None and math.hypot(*p["velocity"]) > .05 and neighbors:
                future = (o["point"][0]+p["velocity"][0]*2,o["point"][1]+p["velocity"][1]*2)
                next_camera = min((c for c in cfg["cameras"] if c["id"] in neighbors),key=lambda c:math.dist(future,(c["x"],c["y"])))["id"]
            output.append({**{k: v for k, v in o.items() if k != "color"}, "id": gid, "association": p["association"], "history": list(p["history"]), "predicted": False, "velocity": list(p["velocity"]), "nextCamera": next_camera})
        # Bound retention to the declared handoff window; no indefinite identities.
        expired = {pid for pid, p in self.people.items() if t - p["t"] > cfg["handoffSeconds"]}
        for pid in expired:
            del self.people[pid]
        # Local IDs no longer seen must expire even when another camera keeps
        # the same global identity alive indefinitely.
        last_seen = getattr(self, "last_seen", {})
        for key in observed_keys:
            last_seen[key] = t
        self.local = {k: v for k, v in self.local.items() if v not in expired and t - last_seen.get(k, t) <= cfg["handoffSeconds"]}
        self.last_seen = {k: last_seen[k] for k in self.local}
        return output


class Occupancy:
    def __init__(self, config):
        self.config = config
        self.cells = {}
        self.last_t = None
        self.zone_stats = {}
        self.zone_start = {}
        self.cell_visitors = {}

    def update(self, people, t):
        cfg = self.config
        # Count one observed global ID once, never extrapolated invisible people.
        unique = {p["id"]: p for p in people if p.get("point") is not None and not p.get("predicted")}
        points = list(unique.values())
        dt = 0 if self.last_t is None else max(0, min(t - self.last_t, 2))
        self.last_t = t
        size = cfg["radius"]
        grid_size = cfg["width"] / 24
        occupied = {}
        for p in points:
            x, y = p["point"]
            key = (int(x // grid_size), int(y // grid_size))
            occupied[key] = occupied.get(key, 0) + 1
            self.cell_visitors.setdefault(key, set()).add(p["id"])
        for key, n in occupied.items():
            cell = self.cells.setdefault(key, {"seconds": 0., "peak": 0})
            cell["seconds"] += n * dt
            cell["peak"] = max(cell["peak"], n)
            cell["visits"] = len(self.cell_visitors[key])
        # Circle candidates centered on observed people; suppress duplicate circles.
        candidates = []
        for p in points:
            group = [q for q in points if math.dist(p["point"], q["point"]) <= size]
            if len(group) >= cfg["minPeople"]:
                candidates.append((len(group), p["point"]))
        circles = []
        for n, center in sorted(candidates, reverse=True):
            if any(math.dist(center, c["center"]) < size for c in circles):
                continue
            circles.append({"center": center, "count": n, "radius": size})
        previous = getattr(self, "clusters", [])
        rules = (size, cfg["minPeople"], cfg["dwell"])
        if getattr(self, "rules", None) != rules:
            previous = []
        self.rules = rules
        used = set()
        for circle in circles:
            matches = [(math.dist(circle["center"], c["center"]), i, c) for i, c in enumerate(previous) if i not in used and math.dist(circle["center"], c["center"]) <= size]
            if matches:
                _, idx, old = min(matches, key=lambda item: item[0])
                used.add(idx)
                circle["since"] = old["since"]
            else:
                circle["since"] = t
            circle["duration"] = t - circle["since"]
            circle["alert"] = circle["duration"] >= cfg["dwell"]
        self.clusters = circles
        zones = []
        for index, zone in enumerate(cfg.get("zones", [])):
            if zone.get("kind") in ("wall", "door"):
                continue
            poly = np.asarray(zone["points"], dtype=np.float32)
            members = {p["id"] for p in points if cv2.pointPolygonTest(poly, tuple(p["point"]), False) >= 0}
            n = len(members)
            zkey = zone.get("id",str(index))
            stats = self.zone_stats.setdefault(zkey,{"seconds":0.,"peak":0,"visitors":set()})
            stats["seconds"] += n * dt
            stats["peak"] = max(stats["peak"],n)
            stats["visitors"].update(members)
            rule = zone.get("rule",{})
            if rule.get("enabled") and n >= rule["minPeople"]:
                self.zone_start.setdefault(zkey,t)
            else:
                self.zone_start.pop(zkey,None)
            duration = t-self.zone_start.get(zkey,t)
            zones.append({"name":zone["name"],"count":n,"seconds":stats["seconds"],"peak":stats["peak"],"visits":len(stats["visitors"]),"duration":duration,"alert":bool(rule.get("enabled") and zkey in self.zone_start and duration >= rule["dwell"])})
        ranked = sorted(self.cells.items(), key=lambda item: item[1]["seconds"], reverse=True)[:80]
        return {"clusters": circles, "zones": zones, "heat": [{"x": k[0] * grid_size, "y": k[1] * grid_size, "size": grid_size, **v} for k, v in ranked], "mappedCount": len(unique)}
