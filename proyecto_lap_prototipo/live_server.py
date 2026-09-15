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
import socket
import sys
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
# Al abrir el servidor directamente, conservar el entorno validado del proyecto.
project_env = ROOT.parent / ".venv"
project_python = project_env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if __name__ == "__main__" and project_python.is_file() and Path(sys.prefix).resolve() != project_env.resolve():
    os.execv(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])
sys.path.insert(0, str(ROOT / "src"))
from live_core import IdentityStore, Occupancy, calibration, project, validate_config
from live_metrics import SessionMetrics
from spatial_scope import accepts

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
        self.data_root = self.config_path.parent if config_path else ROOT
        self.config = default_config()
        self.config_error = None
        if self.config_path.exists():
            try:
                self.config = validate_config({**self.config, **json.loads(self.config_path.read_text(encoding="utf-8"))})
            except (ValueError, OSError) as exc:
                self.config_error = str(exc)
        if self.config.get("background") and "planLines" not in self.config:
            try:
                import base64
                from plan_import import plan_lines_from_bytes
                self.config["planLines"] = plan_lines_from_bytes(base64.b64decode(self.config["background"].split(",",1)[1]),self.config["width"])["planLines"]
            except (ValueError, KeyError):
                self.config["planLines"] = []
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        self.token = secrets.token_urlsafe(32)
        self.instance = secrets.token_hex(8)
        self.revision = 0
        self.runtime_config = None
        self.frames = {}
        self.preview_frames = {}
        self.source_checks = {}
        self.audit = deque(maxlen=300)
        self.state = {"status": "idle", "people": [], "cameras": [], "events": [], "t": 0,
                      "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": self.config_error}

        # Restaura únicamente agregados finalizados; nunca reactiva una fuente ni IDs en vivo.
        if not self.config_error:
            summaries=[]
            for path in (self.data_root/'data/replays').glob('*/manifest.json'):
                try:
                    meta=json.loads(path.read_text(encoding='utf-8'))
                    if meta.get('module')=='unified' and meta.get('status') in ('ended','stopped') and meta.get('cameraAnalytics') and meta.get('levelAnalytics'):
                        summaries.append(meta)
                except (OSError,ValueError):pass
            if summaries:
                last=max(summaries,key=lambda value:value['created']);pid=last['config'].get('planId','custom')
                if any(c['id'] in last['cameraAnalytics'] for c in self.config['cameras']):
                    analytics=copy.deepcopy(last['levelAnalytics'].get(pid,self.state['analytics']))
                    analytics.update(clusters=[],mappedCount=0)
                    for zone in analytics.get('zones',[]):zone.update(count=0,alert=False)
                    self.state.update(status=last['status'],session=last['session'],mode='yolo',t=last['end'],planId=pid,analytics=analytics,levelAnalytics=last['levelAnalytics'],cameraAnalytics=last['cameraAnalytics'],identityDeleted=True)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({**self.state, "serverTime": time.time(), "serverInstance": self.instance, "configRevision": self.revision, "sourceChecks":self.source_checks, "audit":list(self.audit)})

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
            if getattr(self, "counting", None) and self.counting.active():
                raise ValueError("Detén el análisis de conteo antes de iniciar tracking.")
            if self.worker and self.worker.is_alive():
                raise ValueError("Ya hay una sesión activa; detenla primero.")
            mode = request.get("detector", "yolo")
            if mode not in ("hog", "p2pnet", "yolo", "demo"):
                raise ValueError("Detector inválido.")
            if not self.config["cameras"]:
                raise ValueError("Añade al menos una cámara antes de iniciar.")
            camera_id = request.get("camera")
            camera_ids=request.get("cameraIds")
            if camera_ids is not None and (not isinstance(camera_ids,list) or not camera_ids or any(cid not in {c["id"] for c in self.config["cameras"]} for cid in camera_ids)):
                raise ValueError("Selecciona cámaras existentes.")
            if camera_id and camera_id not in {c["id"] for c in self.config["cameras"]}:
                raise ValueError("Cámara desconocida.")
            selected = [c for c in self.config["cameras"] if c.get("active",True) and (c["id"]==camera_id if camera_id else c.get("planId","custom")==self.config.get("planId","custom"))]
            if camera_ids is not None:
                selected=[c for c in self.config["cameras"] if c["id"] in camera_ids and c.get("active",True)]
            if not selected:
                raise ValueError("Activa al menos una cámara.")
            if request.get("requireUnified") and mode != "demo":
                if any(c.get('illustrative') for c in selected):
                    raise ValueError('Las ubicaciones ilustrativas permiten probar el mapa, pero no validar identidades entre cámaras. Usa referencias reales del mismo suelo y tiempos sincronizados.')
                if len(selected)>1 and not self.config["clocksVerified"]:
                    raise ValueError("Verifica el tiempo común y los desfases antes del conteo multicámara.")
                if any(len(c.get("pairs",[]))<4 for c in selected):
                    raise ValueError("Calibra todas las cámaras antes del conteo en el plano.")
                import cv2
                import numpy as np
                if any(cv2.contourArea(cv2.convexHull(np.asarray(c["pairs"],dtype=np.float32)[:,:2].copy()))<.005 for c in selected):
                    raise ValueError("Calibración insuficiente: distribuye las referencias por el suelo, no sobre una sola línea.")
                if any(not c.get("detectionZone") and not c.get("restrictCoverage") for c in selected):
                    raise ValueError("Delimita el área útil de cada cámara para excluir reflejos y áreas externas.")
            self.stop_event.clear()
            self.pause_event.clear()
            self.frames = {}
            self.preview_frames = {}
            self.state = {"status": "starting", "mode": mode, "people": [], "cameras": [], "events": [], "t": 0,
                          "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": None, "session": secrets.token_hex(4)}
            self.runtime_config = copy.deepcopy(self.config)
            self.runtime_config["cameras"] = copy.deepcopy(selected)
            for camera in self.runtime_config['cameras']:
                camera['links']=[cid for cid in camera.get('links',[]) if cid in {c['id'] for c in selected}]
            self.state["planId"] = selected[0].get("planId","custom")
            if not request.get("requireUnified"):
                self.runtime_config["clocksVerified"]=False
            if camera_id:
                pid=selected[0].get("planId","custom")
                if pid!=self.config.get("planId","custom"):
                    self.runtime_config.update(copy.deepcopy(self.config.get("plans",{}).get(pid,{})))
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
        replay = None
        combined = None
        mode = request.get("detector", "yolo")
        try:
            if mode == "demo":
                self.demo(config)
                return
            import cv2
            import numpy as np
            from types import SimpleNamespace
            from tracking import ByteTrackPuntos
            from following.appearance import torso_histogram
            from following.tracker import BoxTracker
            from following.flow import ZoneFlow, FlowField
            detector = None
            if mode == "p2pnet":
                from detection import DetectorP2PNet
                detector = DetectorP2PNet(str(ROOT / "external" / "P2PNet" / "weights" / "SHTechA.pth"), umbral=.1)
            elif mode == "yolo":
                from following.detector import PersonDetector
                detector = PersonDetector(request.get("weights"), image_size=request.get("inferenceSize",640))
            else:
                detector = cv2.HOGDescriptor()
                detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            cams = [c for c in config["cameras"] if c.get("active",True) and (not request.get("camera") or c["id"] == request["camera"])]
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
                if stream:
                    from following.source import NetworkCapture
                    cap = NetworkCapture(source, ROOT)
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
                c.update(cap=cap, fps=fps, stream=stream, duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps if not stream else None, frameIndex=-1,
                         tracker=BoxTracker() if mode=="yolo" else ByteTrackPuntos(umbral_alto=.6,max_frames_perdido=15),
                         h=calibration(c.get("pairs", [])))
                if c.get("restrictCoverage") and (c["h"] is None or mode=="p2pnet"):
                    raise ValueError(f"{c['id']}: calibra el suelo para limitar por cobertura del plano, o usa solo la zona útil de la imagen.")
                statuses[c["id"]] = {"id": c["id"], "status": "ready"}
            active = [c for c in cams if "cap" in c]
            if len(active)!=len(cams) and request.get("requireUnified"):
                raise ValueError("Falta una cámara: no se publica un conteo multicámara parcial.")
            if not active:
                with self.lock:
                    self.state["cameras"] = list(statuses.values())
                raise ValueError("Ninguna fuente pudo abrirse; revisa las rutas o la conexión de cámara.")
            if len({c["stream"] for c in active}) > 1:
                raise ValueError("No mezcles archivos y cámaras en vivo en una sesión; sus relojes no son equivalentes.")
            identities, occupancy, metrics = IdentityStore(config), Occupancy(config), SessionMetrics()
            if not active[0]["stream"]:
                from replay import ReplayWriter
                replay = ReplayWriter(self.data_root,self.state["session"],"unified" if request.get("combined") else "tracking",[{"id":c["id"],"name":c.get("name",c["id"]),"source":c["source"],"offset":c.get("offset",0),"planId":c.get("planId","custom"),"countLines":c.get("countLines",[])} for c in active],{k:v for k,v in config.items() if k != "cameras"})
            from following.combined import CombinedAnalysis
            combined = CombinedAnalysis(cams, ROOT) if request.get('combined') else None
            camera_analytics = {}
            level_configs={pid:config if pid==config.get('planId','custom') else {**config,**config.get('plans',{}).get(pid,{})} for pid in {c.get('planId','custom') for c in cams}}
            level_occupancy={pid:Occupancy(value) for pid,value in level_configs.items()}
            level_flow={pid:ZoneFlow(value) for pid,value in level_configs.items()}
            flow_fields={pid:FlowField(value) for pid,value in level_configs.items()}
            camera_maps={c['id']:Occupancy(level_configs[c.get('planId','custom')]) for c in cams}
            camera_levels={c['id']:c.get('planId','custom') for c in cams}
            for camera in cams:
                plan=level_configs[camera.get('planId','custom')]
                camera['scope']={key:plan.get(key) for key in ('width','height','workArea','zones','mapAsset')}
            flow = ZoneFlow(config)
            trails = {}
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
                        statuses[c["id"]] = {**statuses[c["id"]], "status": "error" if c["stream"] else "ended", "error": "Fuente sin imagen" if c["stream"] else None}
                        active.remove(c)
                        if request.get("requireUnified"):
                            active.clear()
                            break
                        continue
                    if frame.shape[1]>1280:
                        frame=cv2.resize(frame,(1280,round(frame.shape[0]*1280/frame.shape[1])))
                    height, width = frame.shape[:2]
                    raw_frames[c["id"]] = frame
                    detections, boxes = [], []
                    if mode == "p2pnet":
                        detections = detector.detectar(frame)
                    elif mode == "yolo":
                        detections, boxes = detector.detect(frame)
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
                    keep = []
                    for i,d in enumerate(detections):
                        ground = project(c['h'],d.x/width,d.y/height) if c['h'] is not None and mode!='p2pnet' else None
                        if accepts(c,c["scope"],d.x/width,d.y/height,ground,image_only=c['h'] is None or mode=='p2pnet'):
                            keep.append(i)
                    excluded = len(detections)-len(keep)
                    detections = [detections[i] for i in keep]
                    if boxes:
                        boxes = [boxes[i] for i in keep]
                    if mode == "yolo":
                        tracks = c["tracker"].update(detections, boxes, t, (height, width))
                    else:
                        tracks, _, _ = c["tracker"].actualizar(detections, t)
                    for tr in tracks:
                        px, py = tr.posicion
                        nearest = min(range(len(detections)), key=lambda i: (detections[i].x - px)**2 + (detections[i].y - py)**2) if detections else None
                        box = tr.box if mode == "yolo" else (boxes[nearest] if boxes and nearest is not None else None)
                        color = torso_histogram(frame, box)
                        if not accepts(c,c["scope"],px/width,py/height,project(c["h"],px/width,py/height) if c["h"] is not None and mode!="p2pnet" else None,image_only=c['h'] is None or mode=='p2pnet'):
                            continue
                        point = None
                        if c["h"] is not None and mode != "p2pnet":
                            point = project(c["h"], px / width, py / height)
                            if point and not (0 <= point[0] <= c["scope"]["width"] and 0 <= point[1] <= c["scope"]["height"]):
                                point = None
                        observations.append({"camera": c["id"], "local": tr.id, "point": point, "pixel": [float(px), float(py)], "box": box, "color": color, "score": tr.score})
                    statuses[c["id"]] = {"id": c["id"], "status": "live", "width": width, "height": height, "fps":c["fps"], "duration":c.get("duration"), "calibrated": c["h"] is not None and mode != "p2pnet", "count": sum(o["camera"]==c["id"] for o in observations), "excluded":excluded, "timestamp": t, "sourceTime":c["frameIndex"]/c["fps"] if not c["stream"] else None}
                    with self.lock:
                        self.source_checks[c["id"]] = {"source":c["source"],"valid":True,"width":width,"height":height,"fps":c["fps"],"checkedAt":time.time()}
                if not active or self.stop_event.is_set():
                    break
                people = identities.update(observations, t)
                if combined:
                    for c in active:
                        group=[p for p in people if p['camera']==c['id']]
                        camera_analytics[c['id']] = combined.observe(c,raw_frames[c['id']],group,t)
                        camera_analytics[c['id']]['map']=camera_maps[c['id']].update(group,t)
                encoded = {}
                for cid, frame in raw_frames.items():
                    # Operator-only view on a loopback-only server: the operator already
                    # has the raw source video, so the feed is served at full detail with
                    # tracking overlays drawn on top, not degraded for anonymity.
                    overlay_scale = max(1., frame.shape[1]/1440)
                    line_width = max(2, round(2*overlay_scale))
                    for p in [p for p in people if p["camera"] == cid]:
                        px, py = map(int, p["pixel"])
                        trail = trails.setdefault((cid, p["id"]), deque(maxlen=25))
                        trail.append((px, py))
                        if len(trail) > 1:
                            cv2.polylines(frame, [np.asarray(trail, dtype=np.int32)], False, (70, 220, 120), line_width)
                        if p["box"]:
                            x1, y1, x2, y2 = map(int, p["box"])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (70, 220, 120), line_width)
                        cv2.circle(frame, (px, py), 5, (70, 220, 120), -1)
                        suffix = " ~" if p["association"] != "local" else ""
                        label = p["id"] + suffix
                        font = .6*overlay_scale
                        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font, line_width)
                        lx, ly = max(0, min(px-tw//2, frame.shape[1]-tw)), max(th+6, py-round(10*overlay_scale))
                        cv2.rectangle(frame, (lx, ly-th-5), (lx+tw, ly+baseline), (12, 35, 23), -1)
                        cv2.putText(frame, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, font, (120, 255, 170), line_width)
                    camera=next(c for c in cams if c['id']==cid)
                    for line in camera.get('countLines',[]):
                        a,b=[(round(p[0]*frame.shape[1]),round(p[1]*frame.shape[0])) for p in (line['a'],line['b'])]
                        cv2.line(frame,a,b,(90,240,180),line_width)
                        dx,dy=b[0]-a[0],b[1]-a[1];length=max(1.,(dx*dx+dy*dy)**.5)
                        middle=((a[0]+b[0])//2,(a[1]+b[1])//2);side=line.get('entrySide',1)
                        tip=(round(middle[0]-dy/length*35*side),round(middle[1]+dx/length*35*side))
                        cv2.arrowedLine(frame,middle,tip,(90,240,180),line_width,tipLength=.3)
                    if frame.shape[1] > 1440:
                        frame = cv2.resize(frame, (1440, round(frame.shape[0]*1440/frame.shape[1])))
                    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    if ok:
                        encoded[cid] = jpg.tobytes()
                        with self.lock:
                            self.preview_frames[cid] = encoded[cid]
                sample_times = [c["frameIndex"]/c["fps"]-c.get("offset",0) for c in active if not c["stream"]]
                skew = max(sample_times)-min(sample_times) if len(sample_times)>1 else 0.
                elapsed = time.monotonic() - start
                seen = {(p["camera"], p["id"]) for p in people}
                trails = {key: value for key, value in trails.items() if key in seen}
                with self.lock:
                    self.frames.update(encoded)
                    analytics = occupancy.update(people,t)
                    analytics["flow"] = flow.update(people,t)
                    levels={}
                    for pid, counter in level_occupancy.items():
                        group=[p for p in people if camera_levels[p['camera']]==pid]
                        levels[pid]=counter.update(group,t)
                        levels[pid]['flow']=level_flow[pid].update(group,t)
                        levels[pid]['flowVectors']=flow_fields[pid].update(group,t)
                    analytics=levels.get(config.get('planId','custom'),analytics)
                    if replay:
                        views=[]
                        for c in active:
                            h,w=raw_frames[c["id"]].shape[:2]
                            views.append({"id":c["id"],"t":statuses[c["id"]]["sourceTime"],"analysis":camera_analytics.get(c["id"]),"people":[{"id":p["id"],"box":[p["box"][0]/w,p["box"][1]/h,p["box"][2]/w,p["box"][3]/h] if p["box"] else None,"pixel":[p["pixel"][0]/w,p["pixel"][1]/h],"point":p["point"],"association":p["association"]} for p in people if p["camera"]==c["id"]]})
                        replay.append({"t":t,"cameras":views,"analytics":analytics,"levels":levels})
                    self.state.update(status="paused" if self.pause_event.is_set() else "running", people=people, cameras=list(statuses.values()), events=list(identities.events), t=t,
                                      analytics=analytics, levelAnalytics=levels, cameraAnalytics=camera_analytics, synchronization={"mode":"live" if active[0]["stream"] else "recordings", "contentVerified":config["clocksVerified"], "sampleSkewSeconds":round(skew,5), "commonTime":t}, totals=metrics.update(people,analytics,t), series=list(metrics.series), processingMs=round(elapsed * 1000), updatedAt=time.time())
                timeline = round(timeline+.2,6)
                self.stop_event.wait(max(0., .2 - elapsed))
        except Exception as exc:
            with self.lock:
                self.state.update(status="error", error=f"{type(exc).__name__}: {exc}", people=[])
        finally:
            if combined:
                final_analytics=combined.close()
                self.state['cameraAnalytics']=final_analytics
                if replay:
                    replay.meta['cameraAnalytics']=final_analytics
                    replay.meta['levelAnalytics']=self.state.get('levelAnalytics',{})
                    replay.meta['derivedMapVersion']=2
            if replay:
                try:
                    replay.finish("error" if self.state["status"]=="error" else "stopped" if self.stop_event.is_set() else "ended")
                except OSError as exc:
                    self.state.update(status="error", error=f"No se pudo guardar la reproducción: {exc}")
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
                self.record("Sesión finalizada","Estado activo limpiado. Los análisis de archivos conservan observaciones e IDs de sesión para revisar el video.")
                for camera in self.state.get("cameras", []):
                    camera["lastCount"] = camera.get("count", 0)
                    camera["count"] = 0
                    if camera["status"] in ("live", "ready"):
                        camera["status"] = "stopped" if self.stop_event.is_set() else "ended"

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
        if url.path.startswith("/api/replay/"):
            from replay import get
            return get(self,url,self.server.engine.data_root)
        if url.path.startswith("/api/counting/"):
            from counting.api import get
            return get(self, url, ROOT)
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
            if parsed.path.startswith("/api/counting/"):
                from counting.api import post
                return post(self, parsed.path, data, ROOT)
            if self.path == "/api/calibration-check":
                import numpy as np
                import cv2
                pairs = data.get("pairs",[])
                if not isinstance(pairs,list) or len(pairs)<4 or len(pairs)>30 or any(not isinstance(p,list) or len(p)!=4 for p in pairs):
                    raise ValueError("Se necesitan entre 4 y 30 pares de referencias.")
                points=np.asarray(pairs,dtype=float)
                if not np.isfinite(points).all() or (points[:,:2]<0).any() or (points[:,:2]>1).any():
                    raise ValueError("Referencias inválidas.")
                h=calibration(pairs)
                predicted=cv2.perspectiveTransform(points[:,:2].reshape(-1,1,2),h).reshape(-1,2)
                spread=float(cv2.contourArea(cv2.convexHull(points[:,:2].astype(np.float32))))
                if spread<.005:
                    raise ValueError("Referencias casi alineadas: distribuye los nodos por todo el suelo visible.")
                return self.send_data(200,{"rmse":float(np.sqrt(np.mean(np.sum((predicted-points[:,2:])**2,axis=1)))),"spread":spread})
            if self.path == "/api/camera-preview":
                import cv2
                cid=data.get("camera")
                camera=next((c for c in engine.config["cameras"] if c["id"]==cid),None)
                if not camera:
                    raise ValueError("Cámara desconocida.")
                if engine.worker and engine.worker.is_alive():
                    raise ValueError("Finaliza el seguimiento para obtener una vista previa.")
                seconds=data.get("seconds",0)
                if not isinstance(seconds,(int,float)) or not 0<=seconds<=86400:
                    raise ValueError("Instante inválido.")
                source=data.get("source",camera["source"])
                if not isinstance(source,(str,int)) or isinstance(source,bool):
                    raise ValueError("Fuente inválida.")
                if isinstance(source,str) and "://" not in source:
                    source=str((ROOT/source).resolve())
                cap=(cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
                     if isinstance(source,str) and "://" in source else cv2.VideoCapture(source))
                try:
                    if not cap.isOpened(): raise ValueError("No se pudo abrir la cámara.")
                    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,1)
                    fps=cap.get(cv2.CAP_PROP_FPS) or 25
                    if seconds: cap.set(cv2.CAP_PROP_POS_MSEC,seconds*1000)
                    ok,frame=cap.read()
                    if not ok: raise ValueError("No hay imagen en ese instante.")
                    from counting.engine import CountingEngine
                    encoded=CountingEngine.encode(frame)
                    h,w=frame.shape[:2]
                    with engine.lock:
                        engine.frames[cid]=encoded
                        engine.state["cameras"]=[c for c in engine.state["cameras"] if c["id"]!=cid]+[{"id":cid,"status":"ready","width":w,"height":h,"fps":fps,"sourceTime":seconds}]
                        engine.source_checks[cid]={"source":camera["source"],"valid":True,"width":w,"height":h,"fps":fps,"checkedAt":time.time()}
                    return self.send_data(200,{"width":w,"height":h,"fps":fps,"duration":cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps})
                finally:
                    cap.release()
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
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler, bind_and_activate=False)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        server.allow_reuse_address = False
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.server_bind()
    server.server_activate()
    server.engine = Engine(args.config_path)
    from replay import recover_interrupted
    recover_interrupted(server.engine.data_root)
    print(f"LAP: http://127.0.0.1:{args.port} — solo equipo local", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.engine.stop()
        if getattr(server.engine, "counting", None):
            server.engine.counting.stop()
            if server.engine.counting.worker:
                server.engine.counting.worker.join(timeout=10)
        server.server_close()


if __name__ == "__main__":
    main()
