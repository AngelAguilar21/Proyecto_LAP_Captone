import copy
import math
from datetime import datetime

import cv2
import numpy as np


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate(config):
    if not isinstance(config, dict):
        raise ValueError("Configuración inválida.")
    source = config.get("source")
    if config.get("recordedAt"):
        try:
            if datetime.fromisoformat(config["recordedAt"].replace("Z", "+00:00")).tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("La fecha de grabación debe incluir una zona horaria válida.")
    if not isinstance(source, str) or not source.strip() or len(source) > 2048:
        raise ValueError("Selecciona un video o escribe una fuente válida.")
    for key, low, high in [("confidence", .05, .99), ("interval", .2, 30), ("maxSide", 256, 1920)]:
        if not number(config.get(key), low, high):
            raise ValueError(f"{key}: valor fuera de rango.")
    if config["maxSide"] != int(config["maxSide"]):
        raise ValueError("La resolución debe ser un número entero.")
    zones = config.get("zones")
    if config.get("cameraZone"):
        from spatial_scope import validate_polygon
        validate_polygon(config["cameraZone"],1,1,"Zona útil de cámara")
    if not isinstance(zones, list) or not 1 <= len(zones) <= 20:
        raise ValueError("Define entre 1 y 20 zonas de análisis.")
    ids = set()
    for zone in zones:
        if not isinstance(zone, dict):
            raise ValueError("Zona inválida.")
        zid = zone.get("id")
        if not isinstance(zid, str) or not zid or len(zid) > 80 or zid in ids:
            raise ValueError("Cada zona necesita un identificador único.")
        ids.add(zid)
        if not isinstance(zone.get("name"), str) or not zone["name"].strip() or len(zone["name"]) > 80:
            raise ValueError("Pon un nombre de hasta 80 caracteres a cada zona.")
        if not number(zone.get("threshold"), 1, 100000) or int(zone["threshold"]) != zone["threshold"]:
            raise ValueError("El umbral debe ser un número entero de personas mayor que cero.")
        if not number(zone.get("dwell"), 0, 3600):
            raise ValueError("La permanencia debe estar entre 0 y 3600 segundos.")
        pts = zone.get("points")
        if not isinstance(pts, list) or not 3 <= len(pts) <= 40 or any(
            not isinstance(p, list) or len(p) != 2 or any(not number(v, 0, 1) for v in p) for p in pts
        ):
            raise ValueError("Dibuja de 3 a 40 puntos dentro de la imagen.")
        from spatial_scope import validate_polygon
        validate_polygon(pts, 1, 1, "Zona")
    return copy.deepcopy(config)


class CountingAnalytics:
    def __init__(self, config):
        self.config = config
        self.zones = {z["id"]: {"id": z["id"], "name": z["name"], "threshold": z["threshold"], "dwell": z["dwell"], "count": 0, "peak": 0,
                     "personSeconds": 0., "since": None, "alert": False, "candidatePeak": 0,
                     "peakAt": None} for z in config["zones"]}
        self.heat = np.zeros((24, 40), dtype=float)
        self.previous_heat = self.heat.copy()
        self.last_t = None
        self.observed_seconds = 0.
        self.episodes = []
        self.active = {}
        self.count = 0
        self.peak = 0
        self.peak_at = None
        self.person_seconds = 0.

    def _integrate(self, t):
        # Integramos la última observación solo hasta la siguiente muestra cercana.
        dt = 0. if self.last_t is None else max(0., t-self.last_t)
        if dt > self.config["interval"]*1.5:
            dt = 0.
        self.observed_seconds += dt
        self.heat += self.previous_heat * dt
        self.person_seconds += self.count * dt
        for zone in self.zones.values():
            zone["personSeconds"] += zone["count"] * dt

    def _close(self, zid, t, reason):
        event = self.active.pop(zid, None)
        if event:
            event.update(end=t, duration=max(0., t-event["start"]), reason=reason)

    def update(self, detections, width, height, t):
        if self.last_t is not None and t < self.last_t:
            raise ValueError("El tiempo de fuente no puede retroceder.")
        gap = self.last_t is not None and t-self.last_t > self.config["interval"]*1.5
        self._integrate(t)
        if gap:
            for zid, zone in self.zones.items():
                self._close(zid, self.last_t, "interrupción")
                zone.update(since=None, alert=False, candidatePeak=0)
        points = [(float(d.x)/width, float(d.y)/height) for d in detections
                  if 0 <= d.x < width and 0 <= d.y < height]
        if self.config.get("cameraZone"):
            mask=np.asarray(self.config["cameraZone"],dtype=np.float32)
            points=[p for p in points if cv2.pointPolygonTest(mask,p,False)>=0]
        accepted = set()
        for definition in self.config["zones"]:
            zid = definition["id"]
            polygon = np.asarray(definition["points"], dtype=np.float32)
            members = {i for i, p in enumerate(points) if cv2.pointPolygonTest(polygon, p, False) >= 0}
            accepted.update(members)
            zone = self.zones[zid]
            zone["count"] = len(members)
            if zone["peakAt"] is None or len(members) > zone["peak"]:
                zone["peakAt"] = t
            zone["peak"] = max(zone["peak"], len(members))
            if len(members) >= definition["threshold"]:
                if zone["since"] is None:
                    zone["since"] = t
                zone["candidatePeak"] = max(zone["candidatePeak"], zone["count"])
                zone["alert"] = t-zone["since"] >= definition["dwell"]
                if zone["alert"] and zid not in self.active:
                    event = {"id": len(self.episodes)+1, "zone": zone["name"], "zoneId": zid,
                             "start": zone["since"], "confirmed": t, "end": None,
                             "peak": zone["candidatePeak"], "duration": t-zone["since"], "reason": "activo"}
                    self.episodes.append(event)
                    self.active[zid] = event
                if zid in self.active:
                    self.active[zid].update(peak=max(self.active[zid]["peak"], zone["count"]), duration=t-zone["since"])
            else:
                self._close(zid, t, "umbral despejado")
                zone.update(since=None, alert=False, candidatePeak=0)
        self.count = len(accepted)
        if self.peak_at is None or self.count > self.peak:
            self.peak_at = t
        self.peak = max(self.peak, self.count)
        self.previous_heat = np.zeros_like(self.heat)
        visible = [points[i] for i in sorted(accepted)]
        for x, y in visible:
            self.previous_heat[min(23, int(y*24)), min(39, int(x*40))] += 1
        self.last_t = t
        return visible

    def finish(self, t, reason):
        if self.last_t is not None:
            self._integrate(max(t, self.last_t))
        for zid, zone in self.zones.items():
            self._close(zid, t, reason)
            zone["alert"] = False

    def snapshot(self):
        return {"count": self.count, "peak": self.peak, "peakAt": self.peak_at, "personSeconds": self.person_seconds,
                "observedSeconds": self.observed_seconds,
                "mean": self.person_seconds/self.observed_seconds if self.observed_seconds else self.count,
                "zones": copy.deepcopy(list(self.zones.values())), "episodes": copy.deepcopy(self.episodes),
                "heat": self.heat.tolist(), "instant": self.previous_heat.tolist()}
