"""Local live dashboard API; run: python live_server.py (no new dependencies).

Only listens on loopback. Video sources and model paths are configured by the
local operator. This is a single-user prototype, not an airport deployment.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import secrets
import sys
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from live_core import IdentityStore, Occupancy, calibration, project, validate_config
from live_metrics import SessionMetrics

CONFIG_PATH = ROOT / "config" / "live.local.json"


def default_config():
    legacy = ROOT / "config" / "camaras.json"
    definitions = json.loads(legacy.read_text(encoding="utf-8")).get("camaras",[]) if legacy.exists() else []
    cameras = [{"id": c["id"], "name": f"Cámara {c['id']}", "location": "", "type":"tilted", "source": str((ROOT / c["video_path"]).resolve()), "x": 1+10*(i/max(1,len(definitions)-1)), "y": 1, "offset":0, "links":c.get("vecinos",[]), "pairs":[], "heading":90, "fov":60, "range":4, "height":3, "tilt":45} for i,c in enumerate(definitions)]
    return {"airport":"Aeropuerto LAP", "floor":"Terminal A · Nivel 1", "sourceMode":"recordings", "mapConfigured":False, "setupComplete":False,
            "width": 12, "height": 8, "unit": "relative", "background": "", "radius": 1.5,
            "minPeople": 4, "dwell": 3, "handoffSeconds": 12, "matchDistance": 1,
            "clocksVerified": False, "zones": [], "cameras": cameras}


class Engine:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config = default_config()
        self.config_error = None
        if self.config_path.exists():
            try:
                self.config = validate_config({**self.config, **json.loads(self.config_path.read_text(encoding="utf-8"))})
            except (ValueError, OSError) as exc:
                self.config_error = str(exc)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        self.token = secrets.token_urlsafe(32)
        self.revision = 0
        self.runtime_config = None
        self.frames = {}
        self.preview_frames = {}
        self.source_checks = {}
        self.audit = deque(maxlen=300)
        self.state = {"status": "idle", "people": [], "cameras": [], "events": [], "t": 0,
                      "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": self.config_error}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({**self.state, "serverTime": time.time(), "configRevision": self.revision, "sourceChecks":self.source_checks, "audit":list(self.audit)})

    def record(self, action, detail):
        self.audit.appendleft({"at":datetime.now(timezone.utc).isoformat(),"action":action,"detail":detail})

    def configure(self, config):
        validate_config(config)
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Detén la sesión antes de cambiar el plano o la calibración.")
            self.config_path.parent.mkdir(parents=True,exist_ok=True)
            tmp = self.config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.config_path)
            old_sources = {c["id"]:c["source"] for c in self.config["cameras"]}
            for cid in list(self.source_checks):
                new_source = next((c["source"] for c in config["cameras"] if c["id"]==cid),None)
                if new_source != old_sources.get(cid):
                    self.source_checks.pop(cid,None)
                    self.frames.pop(cid,None)
                    self.preview_frames.pop(cid,None)
                    self.state["cameras"] = [c for c in self.state["cameras"] if c["id"]!=cid]
            self.config = copy.deepcopy(config)
            self.revision += 1
            self.record("Configuración guardada",f"{len(config['cameras'])} cámaras · {len(config.get('zones',[]))} zonas")

    def settings(self, settings):
        with self.lock:
            allowed = {"radius", "minPeople", "dwell"}
            if not settings or not set(settings).issubset(allowed):
                raise ValueError("Solo se pueden ajustar radio, cantidad y permanencia en vivo.")
            draft = {**self.config, **settings}
            validate_config(draft)
            self.config = draft
            if self.runtime_config is not None:
                self.runtime_config.update(settings)
            self.revision += 1
            self.record("Reglas actualizadas",f"Mínimo {draft['minPeople']} · radio {draft['radius']} · permanencia {draft['dwell']} s")

    def start(self, request):
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Ya hay una sesión activa; detenla primero.")
            mode = request.get("detector", "yolo")
            if mode not in ("hog", "p2pnet", "yolo", "demo"):
                raise ValueError("Detector inválido.")
            if not self.config["cameras"]:
                raise ValueError("Añade al menos una cámara antes de iniciar.")
            camera_id = request.get("camera")
            if camera_id and camera_id not in {c["id"] for c in self.config["cameras"]}:
                raise ValueError("Cámara desconocida.")
            self.stop_event.clear()
            self.pause_event.clear()
            self.frames = {}
            self.preview_frames = {}
            self.state = {"status": "starting", "mode": mode, "people": [], "cameras": [], "events": [], "t": 0,
                          "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": None, "session": secrets.token_hex(4)}
            self.runtime_config = copy.deepcopy(self.config)
            self.worker = threading.Thread(target=self.run, args=(self.runtime_config, dict(request)), daemon=True)
            self.worker.start()
            self.record("Sesión iniciada",f"{mode} · {camera_id or 'todas las cámaras'}")

    def pause(self, paused):
        with self.lock:
            if not self.worker or not self.worker.is_alive() or self.state["status"] not in ("running","paused"):
                raise ValueError("No hay una sesión en ejecución para pausar o reanudar.")
            if paused:
                self.pause_event.set()
            else:
                self.pause_event.clear()
            self.state["status"] = "paused" if paused else "running"
            self.record("Sesión pausada" if paused else "Sesión reanudada","Control del operador")

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()
        with self.lock:
            if self.worker and self.worker.is_alive():
                self.state["status"] = "stopping"

    def run(self, config, request):
        captures = {}
        mode = request.get("detector", "yolo")
        try:
            if mode == "demo":
                self.demo(config)
                return
            import cv2
            import numpy as np
            from types import SimpleNamespace
            from tracking import ByteTrackPuntos
            detector = None
            if mode == "p2pnet":
                from detection import DetectorP2PNet
                detector = DetectorP2PNet(str(ROOT / "external" / "P2PNet" / "weights" / "SHTechA.pth"), umbral=.1)
            elif mode == "yolo":
                from ultralytics import YOLO
                weights = request.get("weights") or str(ROOT / "models" / "yolo11n.pt")
                if not weights or not Path(weights).is_file():
                    raise ValueError("Selecciona una ruta local de pesos YOLO; no se descargan modelos automáticamente.")
                detector = YOLO(weights)
            else:
                detector = cv2.HOGDescriptor()
                detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            cams = [c for c in config["cameras"] if not request.get("camera") or c["id"] == request["camera"]]
            statuses = {}
            for c in cams:
                if self.stop_event.is_set():
                    return
                source = c["source"]
                if source == "":
                    statuses[c["id"]] = {"id":c["id"],"status":"error","error":"Configura una fuente para esta cámara."}
                    continue
                if isinstance(source, str) and not source.lower().startswith(("rtsp://", "http://", "https://", "rtmp://")):
                    source = str((ROOT / source).resolve())
                stream = isinstance(source, int) or "://" in str(source)
                if isinstance(source, str) and stream:
                    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
                else:
                    cap = cv2.VideoCapture(source)
                try:
                    # Phones tag portrait video with a rotation flag instead of rotating the
                    # stored pixels; without this the frame arrives sideways/squashed relative
                    # to the reported width/height.
                    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
                except cv2.error:
                    pass
                captures[c["id"]] = cap
                if not cap.isOpened():
                    statuses[c["id"]] = {"id": c["id"], "status": "error", "error": "No se pudo abrir la fuente."}
                    continue
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not np.isfinite(fps) or fps <= 0:
                    fps = 25.
                c.update(cap=cap, fps=fps, stream=stream, frameIndex=-1, tracker=ByteTrackPuntos(umbral_alto=.35 if mode=="yolo" else .6,max_frames_perdido=15), h=calibration(c.get("pairs", [])))
                statuses[c["id"]] = {"id": c["id"], "status": "ready"}
            active = [c for c in cams if "cap" in c]
            if not active:
                with self.lock:
                    self.state["cameras"] = list(statuses.values())
                raise ValueError("Ninguna fuente pudo abrirse; revisa las rutas o la conexión de cámara.")
            if len({c["stream"] for c in active}) > 1:
                raise ValueError("No mezcles archivos y cámaras en vivo en una sesión; sus relojes no son equivalentes.")
            identities, occupancy, metrics = IdentityStore(config), Occupancy(config), SessionMetrics()
            wall_start = time.monotonic()
            timeline = 0.
            while active and not self.stop_event.is_set():
                if self.pause_event.is_set():
                    self.stop_event.wait(.1)
                    continue
                start = time.monotonic()
                t = start - wall_start if active[0]["stream"] else timeline
                observations, raw_frames = [], {}
                for c in list(active):
                    if self.stop_event.is_set():
                        break
                    cap = c["cap"]
                    if not c["stream"]:
                        target = int((t + c.get("offset", 0)) * c["fps"])
                        if target < c["frameIndex"]:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                            c["frameIndex"] = target - 1
                        while c["frameIndex"] < target - 1:
                            if not cap.grab():
                                break
                            c["frameIndex"] += 1
                    ok, frame = cap.read()
                    c["frameIndex"] += 1
                    if not ok:
                        statuses[c["id"]] = {"id": c["id"], "status": "error" if c["stream"] else "ended", "error": "Fuente sin imagen" if c["stream"] else None}
                        active.remove(c)
                        continue
                    height, width = frame.shape[:2]
                    raw_frames[c["id"]] = frame
                    detections, boxes = [], []
                    if mode == "p2pnet":
                        detections = detector.detectar(frame)
                    elif mode == "yolo":
                        result = detector.predict(frame, classes=[0], conf=.15, imgsz=960, max_det=1000, verbose=False)[0]
                        for b in result.boxes:
                            x1, y1, x2, y2 = b.xyxy[0].cpu().tolist()
                            score = float(b.conf[0])
                            detections.append(SimpleNamespace(x=(x1 + x2) / 2, y=y2, confianza=score))
                            boxes.append([x1, y1, x2, y2])
                    else:
                        scale = min(1., 640 / width)
                        small = cv2.resize(frame, (int(width * scale), int(height * scale)))
                        if small.shape[0] >= 128 and small.shape[1] >= 64:
                            rects, scores = detector.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
                            candidates = [[int(x), int(y), int(w), int(h)] for x, y, w, h in rects]
                            confidence = [float(s) for s in scores]
                            keep = cv2.dnn.NMSBoxes(candidates, confidence, .3, .4)
                            for idx in np.asarray(keep).reshape(-1):
                                x, y, w, h = rects[idx] / scale
                                boxes.append([x, y, x + w, y + h])
                                detections.append(SimpleNamespace(x=x + w / 2, y=y + h, confianza=.9))
                    zone = c.get("detectionZone")
                    if zone and detections:
                        # Restricts detection to the area the operator marked as useful for this
                        # camera (e.g. excludes mirrors, reflections, or neighboring areas the
                        # camera happens to see but that are not part of the assigned coverage).
                        zone_px = np.array([[u * width, v * height] for u, v in zone], dtype=np.float32)
                        keep = [i for i, d in enumerate(detections) if cv2.pointPolygonTest(zone_px, (d.x, d.y), False) >= 0]
                        detections = [detections[i] for i in keep]
                        if boxes:
                            boxes = [boxes[i] for i in keep]
                    tracks, _, _ = c["tracker"].actualizar(detections, t)
                    for tr in tracks:
                        px, py = tr.posicion
                        nearest = min(range(len(detections)), key=lambda i: (detections[i].x - px)**2 + (detections[i].y - py)**2) if detections else None
                        box = boxes[nearest] if boxes and nearest is not None else None
                        color = None
                        if box:
                            x1, y1, x2, y2 = box
                            roi = frame[max(0, int(y1 + (y2-y1)*.25)):min(height, int(y1 + (y2-y1)*.7)), max(0, int(x1)):min(width, int(x2))]
                            if roi.size:
                                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                                color = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
                                cv2.normalize(color, color, alpha=1, norm_type=cv2.NORM_L1)
                        point = None
                        if c["h"] is not None and mode != "p2pnet":
                            point = project(c["h"], px / width, py / height)
                            if point and not (0 <= point[0] <= config["width"] and 0 <= point[1] <= config["height"]):
                                point = None
                        observations.append({"camera": c["id"], "local": tr.id, "point": point, "pixel": [float(px), float(py)], "box": box, "color": color, "score": tr.score})
                    statuses[c["id"]] = {"id": c["id"], "status": "live", "width": width, "height": height, "fps":c["fps"], "calibrated": c["h"] is not None and mode != "p2pnet", "count": len(tracks), "timestamp": t}
                    with self.lock:
                        self.source_checks[c["id"]] = {"source":c["source"],"valid":True,"width":width,"height":height,"fps":c["fps"],"checkedAt":time.time()}
                people = identities.update(observations, t)
                encoded = {}
                for cid, frame in raw_frames.items():
                    # Operator-only view on a loopback-only server: the operator already
                    # has the raw source video, so the feed is served at full detail with
                    # tracking overlays drawn on top, not degraded for anonymity.
                    for p in [p for p in people if p["camera"] == cid]:
                        px, py = map(int, p["pixel"])
                        if p["box"]:
                            x1, y1, x2, y2 = map(int, p["box"])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (70, 220, 120), 2)
                        cv2.circle(frame, (px, py), 5, (70, 220, 120), -1)
                        suffix = " ~" if p["association"] != "local" else ""
                        cv2.putText(frame, p["id"] + suffix, (max(0, px - 25), max(18, py - 14)), cv2.FONT_HERSHEY_SIMPLEX, .55, (80, 255, 150), 2)
                    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    if ok:
                        encoded[cid] = jpg.tobytes()
                        with self.lock:
                            self.preview_frames[cid] = encoded[cid]
                elapsed = time.monotonic() - start
                with self.lock:
                    self.frames.update(encoded)
                    analytics = occupancy.update(people,t)
                    self.state.update(status="paused" if self.pause_event.is_set() else "running", people=people, cameras=list(statuses.values()), events=list(identities.events), t=t,
                                      analytics=analytics, totals=metrics.update(people,analytics,t), series=list(metrics.series), processingMs=round(elapsed * 1000), updatedAt=time.time())
                timeline += .2
                self.stop_event.wait(max(0., .2 - elapsed))
        except Exception as exc:
            with self.lock:
                self.state.update(status="error", error=f"{type(exc).__name__}: {exc}", people=[])
        finally:
            for cap in captures.values():
                cap.release()
            with self.lock:
                if self.state["status"] != "error":
                    self.state.update(status="stopped" if self.stop_event.is_set() else "ended", people=[])
                self.state["analytics"]["clusters"] = []
                for zone in self.state["analytics"]["zones"]:
                    zone["count"] = 0
                    zone["alert"] = False
                self.state["analytics"]["mappedCount"] = 0
                self.state["events"] = []
                self.state["identityDeleted"] = True
                self.frames = dict(self.preview_frames)
                self.runtime_config = None
                self.record("Sesión finalizada","IDs y recorridos individuales eliminados; se conservan métricas agregadas en memoria.")
                for camera in self.state.get("cameras", []):
                    if camera["status"] in ("live", "ready"):
                        camera["status"] = "stopped" if self.stop_event.is_set() else "ended"
                        camera["count"] = 0

    def demo(self, config):
        import math
        occupancy = Occupancy(config)
        metrics = SessionMetrics()
        history = {}
        t = 0.
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                self.stop_event.wait(.1)
                continue
            people = []
            for i in range(18):
                x = config["width"] * (.5 + .19 * math.sin(i * 1.7 + t * .06))
                y = config["height"] * (.5 + .19 * math.cos(i * 2.1 + t * .09))
                pid = f"DEMO-{i+1:02d}"
                h = history.setdefault(pid, [])
                h.append([x, y, t])
                del h[:-90]
                people.append({"id": pid, "camera": config["cameras"][i % len(config["cameras"])]["id"], "point": [x, y], "history": list(h), "association": "synthetic", "predicted": False})
            with self.lock:
                analytics = occupancy.update(people,t)
                self.state.update(status="paused" if self.pause_event.is_set() else "running", people=people, t=t, analytics=analytics, totals=metrics.update(people,analytics,t), series=list(metrics.series), updatedAt=time.time(), cameras=[])
            self.stop_event.wait(.2)
            t += .2


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_data(self, code, body, content_type="application/json"):
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8") if content_type == "application/json" else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self):
        # Block cross-origin control of local cameras (and DNS rebinding).
        host = self.headers.get("Host", "").split(":")[0]
        origin = self.headers.get("Origin")
        if host not in ("localhost", "127.0.0.1"):
            return False
        if origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1"):
            return False
        return self.headers.get("Sec-Fetch-Site", "same-origin") != "cross-site"

    def do_GET(self):
        if not self.allowed():
            return self.send_data(403, {"error": "Acceso local requerido."})
        url = urlparse(self.path)
        engine = self.server.engine
        if url.path == "/api/config":
            with engine.lock:
                return self.send_data(200, {"config": engine.config, "token": engine.token, "revision": engine.revision})
        if url.path == "/api/state":
            return self.send_data(200, engine.snapshot())
        if url.path == "/api/report":
            from live_reports import export
            query=parse_qs(url.query)
            try:
                with engine.lock:
                    config=copy.deepcopy(engine.config)
                    snapshot=engine.snapshot()
                result,mime=export(config,snapshot,query.get("kind",["zones"])[0],query.get("format",["csv"])[0])
                with engine.lock:
                    engine.record("Reporte exportado",query.get("kind",["zones"])[0]+" · "+query.get("format",["csv"])[0])
                return self.send_data(200,result,mime)
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                return self.send_data(400,{"error":str(exc)})
        if url.path == "/api/frame":
            cid = parse_qs(url.query).get("camera", [""])[0]
            with engine.lock:
                frame = engine.frames.get(cid)
            return self.send_data(200, frame, "image/jpeg") if frame else self.send_data(404, {"error": "Aún no hay imagen."})
        # A production Vite build can be served without a second process.
        dist = (ROOT / "dashboard" / "dist").resolve()
        path = (dist / url.path.lstrip("/")).resolve()
        if not path.is_relative_to(dist):
            return self.send_data(404, {"error": "No encontrado"})
        if url.path == "/":
            path = dist / "index.html"
        if path.is_file():
            import mimetypes
            mime = {".js": "text/javascript", ".css": "text/css"}.get(path.suffix, mimetypes.guess_type(str(path))[0] or "application/octet-stream")
            return self.send_data(200, path.read_bytes(), mime)
        self.send_data(404, {"error": "Interfaz no compilada. Usa el servidor Vite en el puerto 5173."})

    def do_POST(self):
        engine = self.server.engine
        if not self.allowed() or not secrets.compare_digest(self.headers.get("X-LAP-Token", ""), engine.token):
            return self.send_data(403, {"error": "Recarga la interfaz local antes de continuar."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            parsed = urlparse(self.path)
            if parsed.path == "/api/import-plan":
                if not 0 < size <= 16*1024*1024:
                    raise ValueError("El plano debe ocupar como máximo 16 MB.")
                from plan_import import import_plan
                query=parse_qs(parsed.query)
                page=int(query.get("page",["0"])[0])
                width=float(query.get("width",["12"])[0])
                if not 1<=width<=10000 or not 0<=page<=1000:
                    raise ValueError("Ancho o página del plano inválidos.")
                result=import_plan(self.rfile.read(size),query.get("name",[""])[0],width,page)
                return self.send_data(200,result)
            if parsed.path == "/api/plan-lines":
                if not 0 < size <= 16*1024*1024:
                    raise ValueError("La imagen recortada debe ocupar como máximo 16 MB.")
                from plan_import import plan_lines_from_bytes
                query=parse_qs(parsed.query)
                width=float(query.get("width",["12"])[0])
                if not 1<=width<=10000:
                    raise ValueError("Ancho del plano inválido.")
                result=plan_lines_from_bytes(self.rfile.read(size),width)
                return self.send_data(200,result)
            if parsed.path == "/api/upload":
                if not 0 < size <= 1024*1024*1024:
                    raise ValueError("El video debe ocupar entre 1 byte y 1 GB. Para videos mayores usa una ruta local.")
                filename = parse_qs(parsed.query).get("name",[""])[0]
                suffix = Path(filename).suffix.lower()
                if suffix not in (".mp4",".avi",".mov",".mkv",".webm",".m4v"):
                    raise ValueError("Formato de video no admitido.")
                directory = ROOT / "data" / "uploads"
                directory.mkdir(parents=True,exist_ok=True)
                target = directory / (secrets.token_hex(16)+suffix)
                try:
                    remaining = size
                    with target.open("xb") as output:
                        while remaining:
                            chunk = self.rfile.read(min(remaining,1024*1024))
                            if not chunk:
                                raise ValueError("La carga quedó incompleta.")
                            output.write(chunk)
                            remaining -= len(chunk)
                except Exception:
                    target.unlink(missing_ok=True)
                    raise
                with engine.lock:
                    engine.record("Video cargado",f"Archivo de prueba {suffix} · {size} bytes")
                return self.send_data(200,{"path":str(target)})
            if not 0 < size <= 4000000:
                raise ValueError("Tamaño de solicitud inválido.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Solicitud inválida.")
            if self.path == "/api/config":
                engine.configure(data)
            elif self.path == "/api/start":
                engine.start(data)
            elif self.path == "/api/settings":
                engine.settings(data)
            elif self.path == "/api/stop":
                engine.stop()
            elif self.path == "/api/pause":
                engine.pause(True)
            elif self.path == "/api/resume":
                engine.pause(False)
            else:
                return self.send_data(404, {"error": "Endpoint desconocido"})
            self.send_data(200, {"ok": True})
        except (ValueError, OSError, TimeoutError, subprocess.SubprocessError) as exc:
            self.send_data(400, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config-path", type=Path, help="Archivo de configuración alternativo para pruebas aisladas.")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.engine = Engine(args.config_path)
    print(f"LAP: http://127.0.0.1:{args.port} — solo equipo local", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.engine.stop()
        server.server_close()


if __name__ == "__main__":
    main()
