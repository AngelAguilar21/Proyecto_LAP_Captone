import csv
import io
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager


class CountStore:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created TEXT, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS samples (session TEXT, t REAL, count INTEGER, zones TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS sample_session ON samples(session)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, state, sample=None):
        # Solo persisten métricas y configuración; no puntos, recortes ni imágenes.
        payload = {k: v for k, v in state.items() if k not in ("points", "series")}
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?)",
                       (state["session"], state["created"], json.dumps(payload, ensure_ascii=False)))
            if sample:
                db.execute("INSERT INTO samples VALUES (?,?,?,?)",
                           (state["session"], sample["t"], sample["count"], json.dumps(sample["zones"])))

    def recover_interrupted(self):
        # Al reiniciar no existe el trabajador de una sesión que quedó abierta.
        with self.connect() as db:
            for sid, payload in db.execute("SELECT id,payload FROM sessions").fetchall():
                state = json.loads(payload)
                if state.get("status") not in ("starting", "running", "paused", "stopping"):
                    continue
                state.update(status="error", error="El servidor se reinició antes de cerrar el análisis. Se conservan las muestras procesadas.")
                for event in state.get("episodes", []):
                    if event.get("end") is None:
                        end = state.get("t", event["start"])
                        event.update(end=end, duration=max(0, end-event["start"]), reason="servidor interrumpido")
                for zone in state.get("zones", []):
                    zone["alert"] = False
                db.execute("UPDATE sessions SET payload=? WHERE id=?", (json.dumps(state, ensure_ascii=False), sid))

    def history(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM sessions ORDER BY created DESC LIMIT 30").fetchall()
        result = []
        for row in rows:
            s = json.loads(row[0])
            result.append({k: s.get(k) for k in ("session", "created", "status", "name", "t", "peak", "samples")})
        return result

    def report(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                raise ValueError("La sesión no existe o todavía no tiene datos.")
            state = json.loads(row[0])
            rows = db.execute("SELECT t,count,zones FROM samples WHERE session=? ORDER BY t", (sid,)).fetchall()
        state["series"] = [{"t": r[0], "count": r[1], "zones": json.loads(r[2])} for r in rows]
        if state.get("peakAt") is None:
            state["peakAt"] = next((s["t"] for s in state["series"] if s["count"] == state.get("peak")), None)
        for zone in state.get("zones", []):
            if zone.get("peakAt") is None:
                zone["peakAt"] = next((s["t"] for s in state["series"] if any(
                    z["id"] == zone["id"] and z["count"] == zone["peak"] for z in s["zones"])), None)
        return state

    def csv(self, sid):
        state = self.report(sid)
        out = io.StringIO()
        writer = csv.writer(out)
        origin = (state.get("timeOrigin") or state["created"]) if state.get("live") else state["config"].get("recordedAt")
        def moment(seconds):
            if seconds is None:
                return "No disponible"
            if origin:
                date = datetime.fromisoformat(origin.replace("Z", "+00:00"))+timedelta(seconds=seconds)
                return date.astimezone(timezone(timedelta(hours=-5))).isoformat()
            return round(seconds, 3)
        writer.writerow(["AeroTrack", "Informe de concentración de personas"])
        writer.writerow(["Fuente", safe(state["name"]), "Fecha de análisis", state["created"]])
        writer.writerow(["Referencia temporal", "Fecha y hora de recepción (Lima)" if state.get("live") else "Fecha y hora de grabación (Lima)" if origin else "Segundos transcurridos del video"])
        writer.writerow(["Cobertura", "Video completo" if state["status"] == "ended" else "Análisis parcial",
                         "Desde", moment(0), "Hasta", moment(state.get("duration") if state["status"] == "ended" and state.get("duration") else state.get("t", 0))])
        writer.writerow(["Interpretación", "Personas presentes simultáneamente; no total de visitantes diferentes"])
        writer.writerow(["Resumen por zona", "Máximo de personas", "Momento del máximo", "Promedio de personas", "Tiempo en concentración (s)", "Intervalos"])
        for zone in state.get("zones", []):
            events = [e for e in state.get("episodes", []) if e.get("zoneId") == zone["id"]]
            mean = zone["personSeconds"]/state["observedSeconds"] if state.get("observedSeconds") else zone["count"]
            writer.writerow([safe(zone["name"]), zone["peak"], moment(zone.get("peakAt")), round(mean, 2),
                             round(sum(e["duration"] for e in events), 3), len(events)])
        writer.writerow([])
        writer.writerow(["Tipo", "Zona", "Inicio / momento", "Personas / máximo simultáneo", "Fin", "Duración (s)", "Estado"])
        for sample in state["series"]:
            writer.writerow(["muestra", "Unión de zonas", moment(sample["t"]), sample["count"], "", "", "observado"])
            for zone in sample["zones"]:
                writer.writerow(["muestra", safe(zone["name"]), moment(sample["t"]), zone["count"], "", "", "observado"])
        for event in state.get("episodes", []):
            writer.writerow(["episodio", safe(event["zone"]), moment(event["start"]), event["peak"], moment(event["end"]) if event["end"] is not None else "En curso", event["duration"], event["reason"]])
        return out.getvalue().encode("utf-8-sig")


def safe(value):
    return "'"+value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
