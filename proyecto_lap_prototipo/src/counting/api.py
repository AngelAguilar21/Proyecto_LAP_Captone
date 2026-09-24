import json
from urllib.parse import parse_qs

from .engine import CountingEngine


def engine_for(parent, root):
    with parent.lock:
        if getattr(parent, "counting", None) is None:
            settings = getattr(parent, "settings_root", None) or parent.config_path.parent
            parent.counting = CountingEngine(root, settings/"counting.local.json")
            parent.counting.data_root = parent.data_root
        return parent.counting


def get(handler, url, root):
    engine = engine_for(handler.server.engine, root)
    query = parse_qs(url.query)
    try:
        if url.path.endswith("/config"):
            # Se reutilizan los archivos ya cargados; no se duplican videos.
            uploads = list((root/"data"/"uploads").glob("*"))
            known = {str((root/c["source"]).resolve()): c.get("name", c["id"])
                     for c in handler.server.engine.config.get("cameras", [])
                     if isinstance(c.get("source"), str) and "://" not in c["source"]}
            files = [{"path": str(p.resolve()), "name": known.get(str(p.resolve()), f"Video cargado · {p.name[:8]}{p.suffix}")}
                     for p in uploads if p.is_file() and p.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")]
            return handler.send_data(200, {"config": engine.config, "readiness": engine.readiness(), "files": files,
                                           "token": handler.server.engine.token})
        if url.path.endswith("/state"):
            return handler.send_data(200, engine.snapshot())
        if url.path.endswith("/frame"):
            with engine.lock:
                frame = engine.frame
            return handler.send_data(200, frame, "image/jpeg") if frame else handler.send_data(404, {"error": "Obtén primero una imagen del video."})
        if url.path.endswith("/history"):
            return handler.send_data(200, engine.store.history())
        if url.path.endswith("/report"):
            sid = query.get("session", [""])[0]
            if query.get("format", ["json"])[0] == "csv":
                return handler.send_data(200, engine.store.csv(sid), "text/csv; charset=utf-8")
            return handler.send_data(200, engine.store.report(sid))
        return handler.send_data(404, {"error": "Ruta de conteo desconocida."})
    except (ValueError, OSError) as exc:
        return handler.send_data(400, {"error": str(exc)})


def post(handler, path, data, root):
    parent = handler.server.engine
    engine = engine_for(parent, root)
    with parent.lock:
        if parent.worker and parent.worker.is_alive():
            raise ValueError("Detén la sesión de tracking antes de usar el módulo de conteo.")
        if path.endswith("/start"):
            camera=next((c for c in parent.config.get("cameras",[]) if c.get("source")==data.get("source")),None)
            data={**data,"cameraId":camera["id"] if camera else "video","cameraZone":camera.get("detectionZone") if camera else None}
            engine.start(data)
        elif path.endswith("/config"):
            engine.configure(data)
        elif path.endswith("/preview"):
            return handler.send_data(200, engine.preview(data.get("source"), data.get("seconds", 0)))
        elif path.endswith("/pause"):
            engine.pause(True)
        elif path.endswith("/resume"):
            engine.pause(False)
        elif path.endswith("/stop"):
            engine.stop()
        else:
            raise ValueError("Acción de conteo desconocida.")
        labels = {"start": "Iniciar conteo", "config": "Configurar conteo", "pause": "Pausar conteo",
                  "resume": "Reanudar conteo", "stop": "Detener conteo"}
        parent.record(labels[path.rsplit("/", 1)[-1]], engine.config.get("name", "Conteo"))
    return handler.send_data(200, {"ok": True})
