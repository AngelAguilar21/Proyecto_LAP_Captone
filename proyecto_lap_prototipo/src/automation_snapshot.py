"""Explicit aggregate-only projection. Unknown keys and nested values are dropped."""
import math

NUMERIC = {"count", "mappedCount", "peak", "peakAt", "personSeconds", "observedSeconds", "mean",
           "seconds", "visits", "duration", "start", "last", "end", "threshold", "dwell", "confirmed",
           "entries", "exits", "lastCrossing", "t", "updatedAt", "processingMs", "inferenceMs", "detections",
           "tracks", "identities", "meanObservedSeconds", "alerts", "mapped", "width", "height"}
BOOLEAN = {"alert", "testRun", "active", "p2pRequested"}


def permitted(key, value):
    if value is None:
        return True
    if key == "observed":  # count in totals; validity flag in zone observations
        return type(value) is bool or type(value) in (int, float) and math.isfinite(value)
    if key in BOOLEAN:
        return type(value) is bool
    if key in NUMERIC:
        return type(value) in (int, float) and math.isfinite(value)
    return type(value) is str


def scalars(value, fields):
    if not isinstance(value, dict):
        return {}
    return {k: v for k in fields if k in value for v in [value[k]] if permitted(k, v)}


ZONE = ("id", "name", "count", "seconds", "peak", "visits", "duration", "alert", "observed", "scope", "episodeId", "start", "threshold", "dwell")
EPISODE = ("id", "scope", "zoneId", "zone", "zoneName", "start", "last", "duration", "peak", "count", "end", "reason", "observed", "alert", "threshold", "dwell", "confirmed")


def rows(value, fields):
    return [scalars(row, fields) for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def analytics(value):
    value = value if isinstance(value, dict) else {}
    result = scalars(value, ("mappedCount", "count", "peak", "peakAt", "personSeconds", "observedSeconds", "mean"))
    result["zones"] = rows(value.get("zones"), ZONE)
    for key in ("zoneEpisodes", "episodes"):
        result[key] = rows(value.get(key), EPISODE)
    result["flow"] = rows(value.get("flow"), ("name", "entries", "exits", "lastCrossing"))
    return result


def snapshot(engine):
    with engine.lock:
        state, config = engine.state, engine.config
        if getattr(engine, "report_identity", None) == (engine.project_id, state.get("session")):
            config = engine.report_config
        safe = scalars(state, ("session", "status", "mode", "t", "planId", "testRun", "updatedAt", "processingMs"))
        safe["testRun"] = bool(state.get("testRun", config.get("testRun", False)))
        safe["analytics"] = analytics(state.get("analytics"))
        safe["levelAnalytics"] = {pid: analytics(a) for pid, a in state.get("levelAnalytics", {}).items()}
        safe["cameraAnalytics"] = {}
        for cid, data in state.get("cameraAnalytics", {}).items():
            camera = scalars(data, ("t",))
            camera["occupancy"] = analytics(data.get("occupancy"))
            camera["map"] = analytics(data.get("map"))
            camera["crossings"] = rows(data.get("crossings"), ("id", "name", "entries", "exits", "lastCrossing"))
            camera["dense"] = scalars(data.get("dense"), ("status", "t", "count", "inferenceMs"))
            camera["avie"] = scalars(data.get("avie"), ("state", "detections", "tracks", "inferenceMs", "p2pRequested"))
            safe["cameraAnalytics"][cid] = camera
        safe["totals"] = scalars(state.get("totals"), ("observed", "identities", "personSeconds", "meanObservedSeconds", "alerts"))
        safe["series"] = rows(state.get("series"), ("t", "count", "mapped", "alerts"))
        cfg = scalars(config, ("airport", "floor", "planId", "width", "height", "unit", "testRun"))
        cfg["cameras"] = rows(config.get("cameras"), ("id", "name", "planId", "active"))
        cfg["zones"] = rows(config.get("zones"), ("id", "name", "kind"))
        return {"projectId": engine.project_id, "config": cfg, "state": safe}
