import copy
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import uuid

import cv2
from resource_control import ResourceRegistry, managed_operation, hold_source

from .analytics import CountingAnalytics, validate
from .source import VideoSource
from .storage import CountStore

ACTIVE = {"starting", "running", "paused", "stopping"}


def defaults(source=""):
    return {"source": source, "name": "Video de prueba", "confidence": .5, "interval": 1., "maxSide": 768,
            "zones": [{"id": "full", "name": "Área completa", "threshold": 10, "dwell": 5.,
                       "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}


class CountingEngine:
    def __init__(self, root, config_path=None, detector_factory=None):
        self.root = root
        self.data_root = Path(config_path).parent if config_path else root
        self.resources = ResourceRegistry(self.data_root)
        self.path = config_path or root/"config"/"counting.local.json"
        self.store = CountStore(self.path.parent/"counting.sqlite")
        self.store.recover_interrupted()
        self.weights = root/"external"/"P2PNet"/"weights"/"SHTechA.pth"
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        self.frame = None
        self.model = None
        self.detector_factory = detector_factory
        self.config = defaults()
        self.state = {"status": "idle", "t": 0, "samples": 0, "points": [], "series": [], "error": None}
        if self.path.exists():
            try:
                self.config = validate(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError) as exc:
                self.state["error"] = f"Revisa la configuración guardada: {exc}"

    def active(self):
        return self.worker is not None and self.worker.is_alive()

    def readiness(self):
        missing = [m for m in ("torch", "torchvision", "cv2", "scipy") if importlib.util.find_spec(m) is None]
        code = (self.root/"external"/"P2PNet"/"models"/"p2pnet.py").is_file()
        return {"ready": not missing and code and self.weights.is_file(), "missing": missing,
                "code": code, "weights": self.weights.is_file(), "model": "P2PNet · ShanghaiTech A", "device": "CPU"}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def configure(self, data):
        config = validate(data)
        config["name"] = str(data.get("name") or "Video de prueba")[:120]
        with self.lock:
            if self.active():
                raise ValueError("Detén el análisis antes de cambiar la fuente o las zonas.")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.path)
            self.config = config

    @managed_operation
    def preview(self, source, seconds=0):
        if not isinstance(source, str) or not source.strip() or len(source) > 2048:
            raise ValueError("Selecciona una fuente de video.")
        if type(seconds) not in (int, float) or not 0 <= seconds <= 86400:
            raise ValueError("Instante de vista previa inválido.")
        with self.lock:
            if self.active():
                raise ValueError("Detén el análisis antes de obtener otra imagen.")
            video = VideoSource(source, self.root)
            try:
                frame, t = video.read(seconds)
                if frame is None:
                    raise ValueError("Ese instante queda fuera del video.")
                self.frame = self.encode(frame)
                return {"width": frame.shape[1], "height": frame.shape[0], "duration": video.duration,
                        "fps": video.fps, "live": video.live, "t": t}
            finally:
                video.close()

    def start(self, data):
        if self.resources.closing:
            raise ValueError("Runtime is closing")
        self.configure(data)
        with self.lock:
            if self.active():
                raise ValueError("Ya hay un análisis activo.")
            if not self.detector_factory and not self.readiness()["ready"]:
                raise ValueError("P2PNet no está preparado. Ejecuta setup_counting.py y reinicia el servidor.")
            self.stop_event.clear()
            self.pause_event.clear()
            self.frame = None
            config = copy.deepcopy(self.config)
            self.state = {"status": "starting", "session": uuid.uuid4().hex[:16], "name": config["name"],
                          "created": datetime.now(timezone.utc).isoformat(), "config": config, "model": "P2PNet",
                          "t": 0., "samples": 0, "points": [], "series": [], "error": None,
                          "note": "Conteo estimado sobre imagen. No son visitantes únicos ni personas/m²."}
            self.worker = self.resources.start_thread(self.run, args=(config,), name="counting")

    def pause(self, paused):
        with self.lock:
            if not self.active() or self.state["status"] not in ("running", "paused"):
                raise ValueError("No hay un análisis en ejecución.")
            if self.state.get("live"):
                raise ValueError("Las fuentes en vivo se detienen; no se pausan para evitar acumular video atrasado.")
            if paused:
                self.pause_event.set()
            else:
                self.pause_event.clear()
            self.state["status"] = "paused" if paused else "running"

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()
        with self.lock:
            if self.active():
                self.state["status"] = "stopping"

    @staticmethod
    def encode(frame):
        scale = min(1., 1440/max(frame.shape[:2]))
        if scale < 1:
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
        ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            raise ValueError("No se pudo preparar la imagen de video.")
        return data.tobytes()

    @managed_operation
    def run(self, config):
        hold_source(config["source"], self.root)
        video = None
        replay = None
        analytics = CountingAnalytics(config)
        finish_t = 0.
        started = time.monotonic()
        try:
            video = VideoSource(config["source"], self.root)
            if not video.live:
                from replay import ReplayWriter
                replay=ReplayWriter(self.data_root,self.state["session"],"counting",[{"id":config.get("cameraId","video"),"name":config["name"],"source":config["source"],"offset":0}],config)
            with self.lock:
                self.state.update(live=video.live, duration=video.duration, fps=video.fps,
                                  timeOrigin=(datetime.now(timezone.utc)-timedelta(seconds=time.monotonic()-video.started)).isoformat())
            if self.model is None:
                if self.detector_factory:
                    self.model = self.detector_factory()
                else:
                    import torch
                    from detection import DetectorP2PNet
                    torch.set_num_threads(max(1, min(4, (os.cpu_count() or 2)//2)))
                    self.model = DetectorP2PNet(str(self.weights), umbral=config["confidence"], device="cpu")
            self.model.umbral = config["confidence"]
            fingerprint = hashlib.sha256(self.weights.read_bytes()).hexdigest() if self.weights.is_file() else "test"
            with self.lock:
                self.state.update(weightsSha256=fingerprint, status="running")
            target = 0.
            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    self.stop_event.wait(.1)
                    continue
                frame, t = video.read(target)
                if frame is None:
                    finish_t = video.duration or finish_t
                    break
                infer_start = time.monotonic()
                h, w = frame.shape[:2]
                scale = min(1., config["maxSide"]/max(h, w))
                small = cv2.resize(frame, (max(1, round(w*scale)), max(1, round(h*scale)))) if scale < 1 else frame
                detections = self.model.detectar(small)
                points = analytics.update(detections, small.shape[1], small.shape[0], t)
                finish_t = t
                metrics = analytics.snapshot()
                if replay:
                    replay.append({"t":t,"cameras":[{"id":config.get("cameraId","video"),"t":t,"points":points,"count":metrics["count"]}],"analytics":metrics})
                sample = {"t": t, "count": metrics["count"],
                          "zones": [{"id": z["id"], "name": z["name"], "count": z["count"]} for z in metrics["zones"]]}
                with self.lock:
                    self.frame = self.encode(frame)
                    series = (self.state["series"]+[sample])[-600:]
                    self.state.update(**metrics, t=t, points=points, width=w, height=h,
                                      samples=self.state["samples"]+1, series=series,
                                      inferenceMs=round((time.monotonic()-infer_start)*1000),
                                      elapsed=round(time.monotonic()-started, 2))
                    self.store.save(self.state, sample)
                target += config["interval"]
                if video.live:
                    self.stop_event.wait(max(0., config["interval"]-(time.monotonic()-infer_start)))
        except Exception as exc:
            with self.lock:
                self.state.update(status="error", error=f"No se completó el análisis: {type(exc).__name__}: {exc}")
        finally:
            if video:
                video.close()
            with self.lock:
                status = "error" if self.state["status"] == "error" else "stopped" if self.stop_event.is_set() else "ended"
                analytics.finish(finish_t, {"error": "fuente o análisis interrumpido", "stopped": "detenido por operador", "ended": "fin del video"}[status])
                self.state.update(**analytics.snapshot(), status=status, elapsed=round(time.monotonic()-started, 2))
                self.store.save(self.state)
                if replay:
                    replay.finish(status)
