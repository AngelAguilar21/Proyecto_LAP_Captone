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
from live_core import (ESTATURA_MEDIA, IdentityStore, Occupancy, body_box, calibration,
                       estimate_height, ground_point, validate_config)
from identity_memory import IdentityMemory, clamp_retention
from live_metrics import SessionMetrics
from spatial_scope import accepts
import projects
import business_data
import business_catalog
import commercial
import sqlite3
import auth
from resource_control import ResourceRegistry, managed_operation, http_operation, hold_source, hold_path
from shutdown_control import ManagedHTTPServer, stop_server, defer_close
from counting.source import is_youtube_url, low_latency_ffmpeg, resolve_stream_source

CONFIG_PATH = ROOT / "config" / "live.local.json"


def default_config():
    legacy = ROOT / "config" / "camaras.json"
    definitions = json.loads(legacy.read_text(encoding="utf-8")).get("camaras",[]) if legacy.exists() else []
    cameras = [{"id": c["id"], "name": f"Cámara {c['id']}", "location": "", "type":"tilted", "source": str((ROOT / c["video_path"]).resolve()), "x": 1+10*(i/max(1,len(definitions)-1)), "y": 1, "offset":0, "links":c.get("vecinos",[]), "pairs":[], "heading":90, "fov":60, "range":4, "height":2, "tilt":45} for i,c in enumerate(definitions)]
    # Sin identidad de ningún cliente: el nombre del espacio lo pone cada proyecto.
    # Antes decía «Aeropuerto LAP / Terminal A · Nivel 1», y un proyecto nuevo heredaba
    # ese rótulo y lo mostraba como si fuera suyo.
    return {"airport":"", "floor":"", "sourceMode":"recordings", "mapConfigured":False, "setupComplete":False,
            "width": 12, "height": 8, "unit": "relative", "background": "", "radius": 1.5,
            "minPeople": 4, "dwell": 3, "handoffSeconds": 12, "matchDistance": 1,
            "personHeight": ESTATURA_MEDIA,
            "clocksVerified": False, "zones": [], "cameras": cameras}


class Engine:
    def __init__(self, config_path=None):
        # Con ruta explícita (pruebas) se trabaja sobre un archivo suelto; sin
        # ella se usa el proyecto activo del índice.
        self.managed = config_path is None
        if self.managed:
            self.project_id = projects.ensure_index(ROOT, CONFIG_PATH)["active"]
            self.config_path = projects.project_path(ROOT, self.project_id)
        else:
            self.project_id = None
            self.config_path = Path(config_path)
        self.data_root = ROOT if self.managed else self.config_path.parent
        self.closing = False
        self.resources = ResourceRegistry(self.data_root)
        self.resource_lock = self.resources.lock
        self.preview_lifecycle_lock = threading.RLock()
        self.preview_workers = {}
        # Ajustes que no pertenecen a un proyecto (conteo especializado) siguen
        # viviendo en config/, no dentro de la carpeta de proyectos.
        self.settings_root = (ROOT / "config") if self.managed else self.config_path.parent
        self.config = default_config()
        self.config_error = None
        self.read_config_file()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        # Cargar los pesos de un detector cuesta varios segundos (medido: ~8 s
        # para P2PNet en este equipo) y no depende de nada de la sesión que
        # termina, así que reconstruirlo en cada «Iniciar» es tiempo perdido.
        # Se conserva mientras el proceso siga vivo y solo se descarta si se
        # pide otro modelo o pesos distintos.
        self.detector_cache = None
        self.detector_cache_key = None
        self.detector_caches = {}
        self.detector_lock = threading.Lock()
        self.detector_warmup = None
        self.token = secrets.token_urlsafe(32)
        self.instance = secrets.token_hex(8)
        self.revision = 0
        self.runtime_config = None
        self.frames = {}
        self.preview_frames = {}
        self.source_checks = {}
        self.preview_worker = None
        self.preview_stop_event = threading.Event()
        self.preview_pause_event = threading.Event()
        self.preview_seek_request = None
        self.preview_touch = 0.
        self.camera_restart_requests = set()
        self.preview_state = {"camera": None, "playing": False, "t": 0., "duration": 0., "live": False, "error": None}
        from notifier import Mailer
        self.mailer = Mailer(self.settings_root)
        from incident_notifications import IncidentNotifications
        self.notifications = IncidentNotifications(self.mailer)
        if business_data.path_for(self.config_path).exists():
            self.notifications.recover(self.config_path)
        self.sessions = auth.Sesiones()
        self.business_error = None
        self.traffic_buffer = {}
        self.traffic_flushed = 0.
        self.audit = deque(maxlen=300)
        self.state = {"status": "idle", "people": [], "cameras": [], "events": [], "t": 0,
                      "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": self.config_error}

        # Restaura únicamente agregados finalizados; nunca reactiva una fuente ni IDs en vivo.
        if not self.config_error:
            summaries=[]
            for path in (self.data_root/'data/replays').glob('*/manifest.json'):
                try:
                    meta=json.loads(path.read_text(encoding='utf-8'))
                    if meta.get('projectId') not in (self.project_id, None):continue
                    if meta.get('module') in ('unified','demo') and meta.get('status') in ('ended','stopped') and meta.get('cameraAnalytics'):
                        summaries.append(meta)
                except (OSError,ValueError):pass
            if summaries:
                last=max(summaries,key=lambda value:value['created']);pid=last['config'].get('planId','custom')
                if any(c['id'] in last['cameraAnalytics'] for c in self.config['cameras']):
                    analytics=copy.deepcopy(last.get('levelAnalytics',{}).get(pid,self.state['analytics']))
                    analytics.update(clusters=[],mappedCount=0)
                    for zone in analytics.get('zones',[]):zone.update(count=0,alert=False)
                    self.state.update(status=last['status'],session=last['session'],mode='demo' if last['module']=='demo' else 'p2pnet',t=last['end'],planId=pid,analytics=analytics,levelAnalytics=last.get('levelAnalytics',{}),cameraAnalytics=last['cameraAnalytics'],identityDeleted=True)

        # Unifica la restauración para el arranque inicial y para el cambio de
        # proyecto, incluyendo sesiones con estado parcial o error recuperable.
        self.restore_last_result()
        from automation import AutomationService
        self.automation = AutomationService(self, tasks={})

    @property
    def resource_users(self):
        with self.resource_lock:
            return sum(self.resources.users.values())

    def resource_use(self, path, write=False):
        return self.resources.use(path, write)

    def automation_snapshot(self):
        from automation_snapshot import snapshot
        return snapshot(self)

    def dispatch_alerts(self, camera_analytics, analytics, level_analytics=None):
        """Guarda cada alerta nueva en la bitacora y, si el correo esta
        configurado, la envia. Nunca interrumpe la sesion: un fallo de disco o
        de correo se registra pero no corta el seguimiento."""
        pendientes = []
        names = {c["id"]: c.get("name", c["id"]) for c in self.config["cameras"]}
        place = " - ".join(v for v in (self.config.get("airport"), self.config.get("floor")) if v)
        nota = "Estimacion automatica de AeroTrack: requiere que una persona lo compruebe."
        for cid, data in (camera_analytics or {}).items():
            for episode in (data.get("occupancy") or {}).get("episodes", []):
                key = "aglomeracion:{}:{}".format(cid, episode.get("id"))
                body = [
                    "Se detecto una concentracion de personas.",
                    "",
                    "Lugar: " + place,
                    "Camara: " + str(names.get(cid, cid)),
                    "Zona: " + str(episode.get("zone")),
                    "Personas: " + str(episode.get("peak")),
                    "Inicio (tiempo de fuente): " + str(episode.get("start")) + " s",
                    "",
                    nota,
                ]
                pendientes.append({
                    "key": key, "tipo": "aglomeracion", "zona": episode.get("zone"), "camara": cid,
                    "inicio": episode.get("start"), "pico": episode.get("peak"),
                    "duracion": episode.get("duration"),
                    "detalle": {"camara": names.get(cid, cid), "origen": "camara"},
                    "asunto": "AeroTrack - Aglomeracion en " + str(episode.get("zone")),
                    "cuerpo": chr(10).join(body)})
        plans = level_analytics.values() if level_analytics is not None else [analytics or {}]
        for episode in (e for plan in plans for e in plan.get("zoneEpisodes", [])):
            if not episode.get("alert"):
                continue
            key = "zona:{}:{}".format(episode["scope"], episode["id"])
            body = [
                "La zona " + str(episode["zone"]) + " del plano supero su umbral.",
                "",
                "Lugar: " + place,
                "Personas observadas: " + str(episode["peak"]),
                "Duracion: " + str(round(episode["duration"])) + " s",
                "",
                nota,
            ]
            pendientes.append({
                "key": key, "tipo": "aglomeracion", "zona": episode["zone"], "camara": None,
                "inicio": episode["start"], "pico": episode["peak"], "duracion": episode["duration"],
                "detalle": {"origen": "plano", "scope": episode["scope"],
                            "zoneId": episode["zoneId"], "episodeId": episode["id"]},
                "asunto": "AeroTrack - Alerta en " + str(episode["zone"]),
                "cuerpo": chr(10).join(body)})

        if not pendientes:
            return
        sesion = self.state.get("session", "sin-sesion")
        conexion = None
        try:
            conexion = business_data.connect(self.config_path)
            conexion.execute("BEGIN IMMEDIATE")
            for alerta in pendientes:
                business_data.registrar_incidente(
                    conexion, f"{sesion}:{alerta['key']}", alerta["tipo"], alerta["zona"],
                    alerta["camara"], alerta["inicio"] or 0, alerta["pico"], alerta["duracion"],
                    {**alerta["detalle"], "sesion": sesion}, commit=False)
            conexion.commit()
            self.business_error = None
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.business_error = type(exc).__name__
            return  # Never send without a committed incident. A later dispatch may retry.
        finally:
            if conexion:
                conexion.close()
        if self.mailer.ready():
            for alerta in pendientes:
                try:
                    self.notifications.send(self.config_path, f"{sesion}:{alerta['key']}",
                                            alerta["asunto"], alerta["cuerpo"])
                except (sqlite3.Error, OSError, ValueError) as exc:
                    self.business_error = type(exc).__name__

    def record_traffic(self, analytics, live):
        """Acumula el conteo por zona y lo vuelca cada minuto al historico.

        Solo tiene sentido en sesiones en vivo: el reloj de pared dice cuando
        se observo. En una grabacion analizada hoy, el trafico pertenece al dia
        en que se grabo, no a hoy, y atribuirselo a hoy ensuciaria el promedio
        contra el que despues se comparan las alertas.
        """
        if not live:
            return
        ahora = datetime.now()
        clave_tiempo = (ahora.strftime("%Y-%m-%d"), ahora.hour, ahora.weekday())
        for zone in (analytics or {}).get("zones", []):
            nombre = zone.get("name")
            if not nombre:
                continue
            clave = (nombre, *clave_tiempo)
            actual = self.traffic_buffer.get(clave, {"suma": 0, "muestras": 0, "pico": 0})
            conteo = int(zone.get("count") or 0)
            actual["suma"] += conteo
            actual["muestras"] += 1
            actual["pico"] = max(actual["pico"], conteo)
            self.traffic_buffer[clave] = actual
        if time.time() - self.traffic_flushed < 60 or not self.traffic_buffer:
            return
        self.flush_traffic()

    def flush_traffic(self):
        if not self.traffic_buffer:
            return
        pendiente, self.traffic_buffer = self.traffic_buffer, {}
        self.traffic_flushed = time.time()
        conexion = None
        try:
            conexion = business_data.connect(self.config_path)
            for (zona, fecha, hora, dia_semana), valores in pendiente.items():
                promedio = round(valores["suma"] / max(1, valores["muestras"]))
                business_data.registrar_trafico(conexion, zona, fecha, hora, dia_semana, promedio)
            self.business_error = None
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.business_error = str(exc)
        finally:
            if conexion:
                conexion.close()

    def traffic_baseline(self, zona, hora=None, dia_semana=None):
        ahora = datetime.now()
        conexion = None
        try:
            conexion = business_data.connect(self.config_path)
            return business_data.promedio_historico(
                conexion, zona, ahora.hour if hora is None else hora,
                ahora.weekday() if dia_semana is None else dia_semana,
                excluir_fecha=ahora.strftime("%Y-%m-%d"))
        finally:
            if conexion:
                conexion.close()

    def update_alert_rules(self, data):
        """Ajusta solo los umbrales de aglomeracion, sin tocar plano ni camaras.

        Existe aparte de /api/config para que el administrador pueda cambiar
        cuando le avisan sin tener acceso a la configuracion completa."""
        with self.lock:
            config = copy.deepcopy(self.config)
            for campo, minimo, maximo in (("radius", .01, 1000), ("minPeople", 2, 1000), ("dwell", 0, 3600)):
                if campo in data:
                    valor = data[campo]
                    if not isinstance(valor, (int, float)) or isinstance(valor, bool) or not minimo <= valor <= maximo:
                        raise ValueError(f"Valor fuera de rango para {campo}.")
                    config[campo] = valor
            reglas = data.get("zones")
            if reglas is not None:
                if not isinstance(reglas, list):
                    raise ValueError("Reglas por zona inválidas.")
                por_nombre = {r.get("name"): r.get("rule") for r in reglas if isinstance(r, dict)}
                for zona in config["zones"]:
                    if zona["name"] in por_nombre:
                        zona["rule"] = por_nombre[zona["name"]]
        self.configure(config)
        self.record("Umbrales de alerta actualizados",
                    f"{config['minPeople']} personas · {config['dwell']} s · radio {config['radius']}")

    def incidents(self, estado=None):
        conexion = None
        try:
            conexion = business_data.connect(self.config_path)
            return {"incidentes": business_data.listar_incidentes(conexion, estado),
                    "error": self.business_error}
        finally:
            if conexion:
                conexion.close()

    def update_incident(self, incident_id, estado):
        conexion = None
        try:
            conexion = business_data.connect(self.config_path)
            business_data.actualizar_estado_incidente(conexion, incident_id, estado)
            self.record("Incidente actualizado", f"{incident_id} -> {estado}")
            return {"incidentes": business_data.listar_incidentes(conexion), "error": None}
        finally:
            if conexion:
                conexion.close()

    def preview_snapshot(self):
        return dict(self.preview_state)

    def preview_stop(self, timeout=4):
        """Corta la vista en vivo y suelta la cámara.

        Nunca debe llamarse sosteniendo self.lock: espera a que termine el hilo
        de previsualización, que a su vez necesita ese mismo candado para
        escribir su última imagen."""
        with self.preview_lifecycle_lock:
            return self._stop_preview(timeout)

    def _stop_preview(self, timeout):
        worker = self.preview_worker
        event = self.preview_stop_event
        event.set()
        if worker and worker.is_alive():
            worker.join(timeout=max(0, timeout))
        if worker and worker.is_alive():
            return False
        # Never wait behind an unrelated writer after spending the stop budget.
        if self.lock.acquire(blocking=False):
            try:
                if self.preview_worker is worker:
                    self.preview_worker = None
                    self.preview_state = {"camera": None, "playing": False, "t": 0., "duration": 0., "live": False, "error": None}
            finally:
                self.lock.release()
        return True

    def preview_start(self, cid, seconds=0.):
        if self.closing:
            raise ValueError("El servidor está cerrando.")
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Finaliza la sesión de seguimiento para usar la vista en vivo.")
            camera = next((c for c in self.config["cameras"] if c["id"] == cid), None)
            if not camera:
                raise ValueError("Cámara desconocida.")
            if camera.get("source", "") == "":
                raise ValueError("Configura una fuente antes de ver la cámara.")
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0 <= seconds <= 86400:
                raise ValueError("Instante inválido.")
        with self.preview_lifecycle_lock:
            self.preview_stop()
            self._start_preview(camera, seconds)

    def _start_preview(self, camera, seconds):
        with self.lock:
            if self.closing:
                raise ValueError("El servidor está cerrando.")
            cid = camera["id"]
            self.preview_stop_event = threading.Event()
            self.preview_pause_event = threading.Event()
            self.preview_seek_request = None
            self.preview_touch = time.time()
            self.preview_state = {"camera": cid, "playing": True, "t": float(seconds), "duration": 0., "live": False, "error": None}
            self.preview_worker = self.resources.start_thread(self._preview_loop,
                args=(copy.deepcopy(camera), float(seconds), self.preview_stop_event, self.preview_pause_event), name="preview")
            self.preview_workers = {w: event for w, event in self.preview_workers.items() if w.is_alive()}
            self.preview_workers[self.preview_worker] = self.preview_stop_event
            self.record("Vista en vivo", f"{camera.get('name', cid)} abierta para revisión")

    def preview_control(self, action, seconds=None):
        with self.lock:
            if not (self.preview_worker and self.preview_worker.is_alive()):
                raise ValueError("No hay ninguna vista en vivo abierta.")
            self.preview_touch = time.time()
            if action == "pause":
                self.preview_pause_event.set()
                self.preview_state["playing"] = False
            elif action == "resume":
                self.preview_pause_event.clear()
                self.preview_state["playing"] = True
            elif action == "seek":
                if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0 <= seconds <= 86400:
                    raise ValueError("Instante inválido.")
                self.preview_seek_request = float(seconds)
                self.preview_pause_event.clear()
                self.preview_state["playing"] = True
            elif action == "stop":
                pass
            else:
                raise ValueError("Acción de vista en vivo desconocida.")
        if action == "stop":
            self.preview_stop()

    @staticmethod
    def _preview_jpeg(frame, width=800, quality=72):
        """Imagen ligera: la vista previa se mira, no se mide."""
        import cv2
        if frame.shape[1] > width:
            frame = cv2.resize(frame, (width, round(frame.shape[0] * width / frame.shape[1])))
        ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise ValueError("No se pudo preparar la imagen de video.")
        return data.tobytes()

    @managed_operation
    def _preview_loop(self, camera, seconds, stop_event=None, pause_event=None):
        """Refresca imágenes sin correr detección: es solo para ver la cámara."""
        import cv2
        stop_event = stop_event if stop_event is not None else self.preview_stop_event
        pause_event = pause_event if pause_event is not None else self.preview_pause_event
        hold_source(camera["source"], ROOT)
        cid = camera["id"]
        source = camera["source"]
        if isinstance(source, str) and "://" not in source:
            source = str((ROOT / source).resolve())
        hls = isinstance(source, str) and is_youtube_url(source)
        if isinstance(source, str):
            source = resolve_stream_source(source)
        remote = isinstance(source, str) and "://" in source
        if remote:
            with low_latency_ffmpeg(hls):
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
        else:
            cap = cv2.VideoCapture(source)
        reader = None
        reader_stop = threading.Event()
        try:
            if not cap.isOpened():
                raise ValueError("No se pudo abrir la cámara. Comprueba la URL y que esté en la misma red.")
            cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            live = remote or isinstance(source, int) or frames <= 1
            with self.lock:
                if self.preview_stop_event is stop_event and not stop_event.is_set():
                    self.preview_state.update(live=live, duration=0. if live else frames / max(1., fps))
            if seconds and not live:
                cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)

            if live:
                # La cámara manda más cuadros de los que mostramos. Si los
                # leyéramos al ritmo de la pantalla, la cola de FFmpeg crecería y
                # la imagen se atrasaría más y más. Este hilo los consume a la
                # velocidad que llegan y guarda solo el último: así siempre se
                # muestra el presente, descartando lo que ya quedó viejo.
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except cv2.error:
                    pass
                newest = {"frame": None, "failed": False}

                def drain():
                    try:
                        while not reader_stop.is_set() and not stop_event.is_set():
                            ok, frame = cap.read()
                            if not ok:
                                newest["failed"] = True
                                return
                            newest["frame"] = frame
                    finally:
                        cap.release()

                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                started_at = time.monotonic()
                while not stop_event.is_set():
                    if time.time() - self.preview_touch > 20:
                        break
                    if newest["failed"]:
                        raise ValueError("Se perdió la señal de la cámara.")
                    if pause_event.is_set():
                        stop_event.wait(.15)
                        continue
                    frame = newest["frame"]
                    if frame is None:
                        stop_event.wait(.05)
                        continue
                    encoded = self._preview_jpeg(frame)
                    with self.lock:
                        if self.preview_stop_event is stop_event and not stop_event.is_set():
                            self.frames[cid] = encoded
                            self.preview_state["t"] = time.monotonic() - started_at
                    stop_event.wait(1 / 15)
            else:
                while not stop_event.is_set():
                    if time.time() - self.preview_touch > 20:
                        break
                    with self.lock:
                        seek = self.preview_seek_request if self.preview_stop_event is stop_event else None
                        if seek is not None:
                            self.preview_seek_request = None
                    if seek is not None:
                        cap.set(cv2.CAP_PROP_POS_MSEC, seek * 1000)
                    if pause_event.is_set():
                        stop_event.wait(.15)
                        continue
                    started = time.monotonic()
                    ok, frame = cap.read()
                    if not ok:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    encoded = self._preview_jpeg(frame)
                    with self.lock:
                        if self.preview_stop_event is stop_event and not stop_event.is_set():
                            self.frames[cid] = encoded
                            self.preview_state["t"] = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                    # Una grabación se reproduce a su velocidad real.
                    stop_event.wait(max(0., 1 / max(1., min(fps, 30)) - (time.monotonic() - started)))
        except (ValueError, OSError, RuntimeError) as exc:
            with self.lock:
                if self.preview_stop_event is stop_event and not stop_event.is_set():
                    self.preview_state.update(playing=False, error=str(exc))
        finally:
            reader_stop.set()
            if reader:
                # The owner remains alive while the native reader is blocked.
                # Only the reader releases its capture; no read/release race.
                reader.join()
            else:
                cap.release()
            with self.lock:
                if self.preview_stop_event is stop_event:
                    self.preview_state["playing"] = False

    def read_config_file(self):
        self.config = default_config()
        self.config_error = None
        if self.config_path.exists():
            try:
                stored = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.config = validate_config({**self.config, **copy.deepcopy(stored)})
                from zone_episodes import ensure_zone_ids
                if ensure_zone_ids(stored):
                    projects.atomic_write(self.config_path, json.dumps(stored, ensure_ascii=False, indent=2))
            except (ValueError, OSError) as exc:
                self.config_error = str(exc)
        if self.config.get("background") and "planLines" not in self.config:
            try:
                import base64
                from plan_import import plan_lines_from_bytes
                self.config["planLines"] = plan_lines_from_bytes(base64.b64decode(self.config["background"].split(",",1)[1]),self.config["width"])["planLines"]
            except (ValueError, KeyError):
                self.config["planLines"] = []

    def require_managed(self):
        if not self.managed:
            raise ValueError("Los proyectos no están disponibles en este modo.")
        if self.worker and self.worker.is_alive():
            raise ValueError("Finaliza la sesión antes de cambiar de proyecto.")

    def projects_listing(self):
        with self.lock:
            if not self.managed:
                return {"active": None, "projects": []}
            return projects.listing(ROOT, self.config, self.project_id)

    def restore_last_result(self):
        """Carga el último análisis terminado del proyecto sin reactivar fuentes."""
        hold_path(self.data_root / "data" / "replays")
        if self.config_error:
            return
        summaries = []
        for path in (self.data_root / 'data/replays').glob('*/manifest.json'):
            try:
                meta = json.loads(path.read_text(encoding='utf-8'))
                if meta.get('projectId') not in (self.project_id, None):
                    continue
                if meta.get('module') not in ('unified', 'tracking', 'demo'):
                    continue
                if meta.get('status') not in ('ended', 'stopped', 'error'):
                    continue
                if float(meta.get('end') or 0) <= 0:
                    continue
                if meta.get('cameraAnalytics') or meta.get('reportAnalytics'):
                    summaries.append(meta)
            except (OSError, ValueError, TypeError):
                continue
        if not summaries:
            return
        last = max(summaries, key=lambda value: value.get('created', ''))
        pid = last.get('config', {}).get('planId', 'custom')
        camera_ids = {c.get('id') for c in self.config.get('cameras', [])}
        saved_ids = set((last.get('cameraAnalytics') or {}).keys())
        if camera_ids and saved_ids and not camera_ids.intersection(saved_ids):
            return
        analytics = copy.deepcopy(last.get('reportAnalytics') or last.get('levelAnalytics', {}).get(pid) or {
            'clusters': [], 'zones': [], 'heat': [], 'mappedCount': 0,
        })
        analytics.update(clusters=[], mappedCount=0)
        for zone in analytics.get('zones', []):
            zone.update(count=0, alert=False)
        camera_analytics = copy.deepcopy(last.get('cameraAnalytics') or {})
        camera_status = []
        for camera in self.config.get('cameras', []):
            analysis = camera_analytics.get(camera.get('id'), {})
            occupancy = analysis.get('occupancy') or {}
            camera_status.append({
                'id': camera.get('id'), 'status': 'ended',
                'lastCount': occupancy.get('count', 0),
                'count': 0, 'calibrated': bool(camera.get('pairs')),
            })
        self.state.update(
            status=last.get('status', 'ended'),
            session=last.get('session'),
            mode='demo' if last.get('module') == 'demo' else 'hybrid',
            t=last.get('end', 0), planId=pid,
            analytics=analytics,
            levelAnalytics=copy.deepcopy(last.get('levelAnalytics', {})),
            cameraAnalytics=camera_analytics,
            cameras=camera_status,
            identityDeleted=True,
            error=None,
        )

    def open_project(self, pid):
        with self.lock:
            self.require_managed()
            self.config_path = projects.activate(ROOT, pid)
            self.project_id = pid
            self.read_config_file()
            if business_data.path_for(self.config_path).exists():
                self.notifications.recover(self.config_path)
            self.frames = {}
            self.preview_frames = {}
            self.source_checks = {}
            self.camera_restart_requests.clear()
            self.revision += 1
            self.state = {"status": "idle", "people": [], "cameras": [], "events": [], "t": 0,
                          "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": self.config_error}
            self.restore_last_result()
            self.record("Proyecto abierto", projects.entry(projects.read_index(ROOT), pid)["name"])
            return self.projects_listing()

    def new_project(self, name, copy_current=False):
        with self.lock:
            self.require_managed()
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Escribe un nombre para el proyecto.")
            config = copy.deepcopy(self.config) if copy_current else default_config()
            if not copy_current:
                config["cameras"] = []
                config["airport"] = name.strip()
                # Un proyecto nuevo no hereda el espacio ni el nivel de ningún otro.
                config["floor"] = ""
            config["setupComplete"] = False
            pid = projects.create(ROOT, name.strip(), config)
            self.record("Proyecto creado", name.strip())
            return self.open_project(pid)

    def request_camera_restart(self, camera_id):
        """Solicita reabrir una cámara caída sin detener las demás."""
        with self.lock:
            if not self.worker or not self.worker.is_alive():
                raise ValueError("No hay un monitoreo activo para relanzar la cámara.")
            camera = next((c for c in self.config.get('cameras', []) if c.get('id') == camera_id), None)
            if not camera:
                raise ValueError("Cámara desconocida.")
            self.camera_restart_requests.add(camera_id)
            for item in self.state.get('cameras', []):
                if item.get('id') == camera_id:
                    item.update(status='reconnecting', error='Reintentando abrir la fuente…')
            self.record("Reintento de cámara", str(camera.get('name') or camera_id))
            return {"camera": camera_id, "status": "reconnecting"}

    def rename_project(self, pid, name):
        with self.lock:
            if not self.managed:
                raise ValueError("Los proyectos no están disponibles en este modo.")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Escribe un nombre para el proyecto.")
            projects.rename(ROOT, pid, name.strip())
            return self.projects_listing()

    def delete_project(self, pid):
        with self.lock:
            self.require_managed()
            remaining = projects.remove(ROOT, pid)
            self.record("Proyecto eliminado", pid)
            if pid == self.project_id:
                return self.open_project(remaining)
            return self.projects_listing()

    def business_metrics(self):
        # Reads persisted replay metadata while updating business SQLite.
        hold_path(self.data_root / "data" / "replays")
        with self.lock:
            con = business_data.connect(self.config_path)
            try:
                businesses = business_catalog.sync(con, self.config, ROOT / "dashboard" / "public")
                observed = self.runtime_config or self.config
                analytics = self.state.get("cameraAnalytics", {})
                mode, sid, elapsed = self.state.get("mode"), self.state.get("session"), self.state.get("t", 0)
                if not sid:
                    histories = []
                    for path in (self.data_root / "data/replays").glob("*/manifest.json"):
                        try:
                            candidate = json.loads(path.read_text(encoding="utf-8"))
                            if candidate.get("projectId") == self.project_id and candidate.get("status") in ("ended", "stopped") and candidate.get("cameraAnalytics"):
                                histories.append(candidate)
                        except (OSError, ValueError):
                            continue
                    if histories:
                        last = max(histories, key=lambda m:m["created"])
                        sid, elapsed = last["session"], last["end"]
                        mode = "demo" if last["module"] == "demo" else "p2pnet"
                        analytics = last["cameraAnalytics"]
                if sid:
                    from replay import manifest
                    try:
                        meta = manifest(self.data_root, sid)
                        observed = {**meta["config"], "cameras": meta["cameras"]}
                    except (OSError, ValueError, KeyError):
                        pass
                traffic = business_catalog.traffic(businesses, analytics, observed, self.config)
                if sid:
                    try:
                        meta["end"] = elapsed
                        meta["cameraAnalytics"] = analytics
                        commercial.save_session(con, meta, traffic)
                    except (UnboundLocalError, OSError, ValueError):
                        pass
                return {"negocios": traffic, "mode": mode, "session": sid, "t": elapsed}
            finally:
                con.close()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({**self.state, "serverTime": time.time(), "serverInstance": self.instance, "configRevision": self.revision, "sourceChecks":self.source_checks, "audit":list(self.audit), "preview": self.preview_snapshot()})

    def record(self, action, detail):
        self.audit.appendleft({"at":datetime.now(timezone.utc).isoformat(),"action":action,"detail":detail})

    def configure(self, config):
        validate_config(config)
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Detén la sesión antes de cambiar el plano o la calibración.")
            con = business_data.connect(self.config_path)
            try:
                businesses = business_catalog.sync(con, config, ROOT / "dashboard" / "public")
                known = {b["id"] for b in businesses}
                if all(not l.get("place") or l["place"]["id"] in known for c in config["cameras"] for l in c.get("countLines", [])):
                    config = business_catalog.bind_config(con, config, businesses)
                    business_catalog.save_bindings(con, config)
            finally:
                con.close()
            projects.atomic_write(self.config_path, json.dumps(config, ensure_ascii=False, indent=2))
            if self.managed and self.project_id:
                projects.touch(ROOT, self.project_id)
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
        if self.closing:
            raise ValueError("El servidor está cerrando.")
        self.preview_stop()
        with self.lock:
            if getattr(self, "counting", None) and self.counting.active():
                raise ValueError("Detén el análisis de conteo antes de iniciar tracking.")
            if self.worker and self.worker.is_alive():
                raise ValueError("Ya hay una sesión activa; detenla primero.")
            mode = request.get("detector", "hybrid")
            test_run = request.get('testRun') is True
            if mode not in ("hybrid", "yolo", "p2pnet", "demo"):
                raise ValueError("AeroTrack opera únicamente con P2PNet.")
            requested_size = int(request.get("inferenceSize") or (256 if mode == "p2pnet" else 640))
            if mode in ("hybrid", "yolo") and requested_size == 256:
                requested_size = 640
            if mode in ("hybrid", "yolo") and requested_size not in (320, 480, 640, 960):
                raise ValueError("El tamaÃ±o YOLO debe ser 320, 480, 640 o 960 pÃ­xeles.")
            if mode == "p2pnet" and requested_size not in (128, 256, 384, 512):
                raise ValueError("El tamaño de inferencia debe ser 128, 256, 384 o 512 píxeles.")
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
            if mode in ("hybrid", "yolo", "p2pnet"):
                if any(c.get("illustrative") for c in selected) and not test_run:
                    raise ValueError("Las ubicaciones ilustrativas no sirven para medir ocupación comercial.")
                if not test_run and any(len(c.get("pairs", [])) < 4 for c in selected):
                    raise ValueError("Calibra todas las cámaras con al menos cuatro referencias antes de iniciar.")
                if mode == "p2pnet" and any(float(c.get("height") or 0) <= float(self.config.get("personHeight") or ESTATURA_MEDIA) for c in selected):
                    raise ValueError("La altura de cada cámara debe superar la estatura media para proyectar cabezas al suelo.")
                if not test_run and any(not c.get("detectionZone") for c in selected):
                    raise ValueError("Delimita la zona útil de cada cámara para excluir espejos, vidrios y áreas externas.")
                for camera in selected:
                    calibration(camera.get("pairs", []))
            if request.get("requireUnified") and mode != "demo":
                if any(c.get('illustrative') for c in selected) and not test_run:
                    raise ValueError('Las ubicaciones ilustrativas permiten probar el mapa, pero no validar identidades entre cámaras. Usa referencias reales del mismo suelo y tiempos sincronizados.')
                if len(selected)>1 and not self.config["clocksVerified"]:
                    raise ValueError("Verifica el tiempo común y los desfases antes del conteo multicámara.")
                if any(len(c.get("pairs",[]))<4 for c in selected):
                    raise ValueError("Calibra todas las cámaras antes del conteo en el plano.")
                import cv2
                import numpy as np
                if any(cv2.contourArea(cv2.convexHull(np.asarray(c["pairs"],dtype=np.float32)[:,:2].copy()))<.005 for c in selected):
                    raise ValueError("Calibración insuficiente: distribuye las referencias por el suelo, no sobre una sola línea.")
                if any(not c.get("detectionZone") for c in selected):
                    raise ValueError("Delimita la zona útil de cada cámara para excluir espejos, vidrios y áreas externas.")
            self.stop_event.clear()
            self.pause_event.clear()
            self.frames = {}
            self.preview_frames = {}
            self.state = {"status": "starting", "mode": mode, "people": [], "cameras": [], "events": [], "t": 0,
                          "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": None, "session": secrets.token_hex(4)}
            self.runtime_config = copy.deepcopy(self.config)
            self.runtime_config['testRun'] = test_run
            self.runtime_config["cameras"] = copy.deepcopy(selected)
            selected_ids = {camera['id'] for camera in selected}
            for camera in self.runtime_config['cameras']:
                explicit = [cid for cid in camera.get('links', []) if cid in selected_ids]
                # En la configuración básica no se obliga al operador a dibujar una
                # red técnica. Sin enlaces explícitos se asocian automáticamente las
                # cámaras del mismo plano; la homografía, el tiempo y la apariencia
                # siguen siendo los filtros que deciden cada traspaso.
                camera['links'] = explicit or [
                    other['id'] for other in selected
                    if other['id'] != camera['id']
                    and other.get('planId', 'custom') == camera.get('planId', 'custom')
                ]
            self.state["planId"] = selected[0].get("planId","custom")
            if not request.get("requireUnified"):
                self.runtime_config["clocksVerified"]=False
            if camera_id:
                pid=selected[0].get("planId","custom")
                if pid!=self.config.get("planId","custom"):
                    self.runtime_config.update(copy.deepcopy(self.config.get("plans",{}).get(pid,{})))
            runtime_request = {
                **request,
                "detector": mode,
                "weights": None,
                # El modo operativo prioriza continuidad. P2PNet reescala las
                # coordenadas al frame original después de inferir.
                "inferenceSize": min(requested_size, 256) if mode == "p2pnet" else requested_size,
            }
            self.worker = self.resources.start_thread(self.run, args=(self.runtime_config, runtime_request), name="tracking")
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

    def load_detector(self, mode, request):
        """Construye el detector o reutiliza el de la sesión anterior.

        Cargar los pesos es lo que de verdad tarda, no el análisis en sí:
        medido en este equipo, construir P2PNet toma unos 8 s. Ese costo no depende de la
        sesión que termina, así que pagarlo en cada «Iniciar» — incluida cada
        prueba rápida de una cámara durante la configuración — es tiempo
        perdido. Se conserva mientras el proceso siga vivo y solo se
        reconstruye mientras el proceso siga vivo; lo que sí varía entre
        sesiones (resolución de análisis) se ajusta sobre la
        instancia ya cargada, que es barato.
        """
        if mode in ("hybrid", "yolo"):
            key = ("yolo", int(request.get("inferenceSize") or 640))
            with self.detector_lock:
                if key not in self.detector_caches:
                    from following.detector import YoloPersonDetector
                    self.detector_caches[key] = YoloPersonDetector(ROOT / "models" / "yolo11n.pt", imgsz=key[1])
                return self.detector_caches[key]
        if mode == "p2pnet":
            key = ("p2pnet",)
            lado_max = int(request.get("inferenceSize") or 256)
            if not hasattr(self, "detector_lock"):
                self.detector_lock = threading.Lock()
            with self.detector_lock:
                if self.detector_cache_key != key:
                    from detection import DetectorP2PNet
                    self.detector_cache = DetectorP2PNet(str(ROOT / "external" / "P2PNet" / "weights" / "SHTechA.pth"),
                                                          umbral=.1, lado_max=lado_max)
                    self.detector_cache_key = key
                else:
                    self.detector_cache.lado_max = lado_max
                return self.detector_cache
        raise ValueError("AeroTrack opera únicamente con P2PNet.")

        if mode in ("hybrid", "yolo"):
            key = ("yolo", int(request.get("inferenceSize") or 640))
            with self.detector_lock:
                if key not in self.detector_caches:
                    from following.detector import YoloPersonDetector
                    self.detector_caches[key] = YoloPersonDetector(ROOT / "models" / "yolo11n.pt", imgsz=key[1])
                return self.detector_caches[key]
        raise ValueError("Detector no soportado.")

    def warm_detector_async(self, mode="yolo"):
        """Prepara P2PNet después de comprobar una fuente, antes de pulsar Probar."""
        if self.closing or (mode == "p2pnet" and self.detector_cache_key == ("p2pnet",)) or (mode != "p2pnet" and ("yolo", 640) in self.detector_caches) or (self.detector_warmup and self.detector_warmup.is_alive()):
            return
        def warm():
            try:
                self.load_detector(mode, {"inferenceSize": 256 if mode == "p2pnet" else 640})
            except Exception as exc:
                self.record("Preparación de P2PNet", f"No se pudo anticipar la carga: {exc}")
        self.detector_warmup = self.resources.start_thread(warm, name="p2pnet-warmup")

    @managed_operation
    def run(self, config, request):
        for camera in config["cameras"]:
            hold_source(camera.get("source"), ROOT)
        captures = {}
        replay = None
        combined = None
        density_sampler = None
        identity_memory = None
        level_occupancy = {}
        mode = request.get("detector", "hybrid")
        try:
            if mode == "demo":
                self.demo(config)
                return
            import cv2
            import numpy as np
            from types import SimpleNamespace
            from tracking import ByteTrackPuntos
            from following.appearance import torso_histogram
            from following.flow import ZoneFlow, FlowField
            person_height = float(config.get("personHeight") or ESTATURA_MEDIA)
            primary_mode = "yolo" if mode == "hybrid" else mode
            detector = self.load_detector(primary_mode, request)
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
                    try:
                        cap = NetworkCapture(source, ROOT)
                    except (ValueError, RuntimeError, OSError) as exc:
                        # Una fuente remota puede fallar de forma aislada. No
                        # dejamos que impida iniciar las demás cámaras y
                        # conservamos el motivo para mostrarlo en la interfaz.
                        statuses[c["id"]] = {
                            "id": c["id"],
                            "status": "error",
                            "error": str(exc) or "No se pudo abrir la fuente.",
                        }
                        continue
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
                    cap.release()
                    continue
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not np.isfinite(fps) or fps <= 0:
                    fps = 25.
                c.update(cap=cap, fps=fps, stream=stream, duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps if not stream else None, frameIndex=-1,
                         # Mantiene el track durante 1.8 s a 25 FPS para
                         # recuperar la identidad tras una oclusión corta.
                         tracker=ByteTrackPuntos(umbral_alto=.6,max_frames_perdido=45),
                         h=calibration(c.get("pairs", [])), headPoints=primary_mode=="p2pnet")
                # P2PNet marca cabezas: se proyectan al suelo corrigiendo por la altura de la
                # cámara, que por eso tiene que superar la estatura supuesta.
                if c["headPoints"] and c["h"] is not None and not float(c.get("height") or 0) > person_height:
                    raise ValueError(f"{c['id']}: con P2PNet la altura de la cámara debe ser mayor que la estatura media ({person_height:g} m) para poder ubicar a la gente en el plano. Corrige la altura en el paso de ubicación.")
                c["projects"] = c["h"] is not None and (not c["headPoints"] or ground_point(c, .5, .5, person_height) is not None)
                try:
                    c["hInv"] = np.linalg.inv(c["h"]) if c["projects"] and c["headPoints"] else None
                except np.linalg.LinAlgError:
                    c["hInv"] = None
                if c.get("restrictCoverage") and not c["projects"]:
                    raise ValueError(f"{c['id']}: calibra el suelo para limitar por cobertura del plano, o usa solo la zona útil de la imagen.")
                statuses[c["id"]] = {"id": c["id"], "status": "ready"}
            active = [c for c in cams if "cap" in c]
            if len(active)!=len(cams) and request.get("requireUnified"):
                raise ValueError("Falta una cámara: no se publica un conteo multicámara parcial.")
            if not active:
                with self.lock:
                    self.state["cameras"] = list(statuses.values())
                details = "; ".join(
                    f"{item.get('id', 'cámara')}: {item.get('error', 'fuente no disponible')}"
                    for item in statuses.values()
                    if item.get("status") == "error"
                )
                if details:
                    raise ValueError(details)
                raise ValueError("Ninguna fuente pudo abrirse; revisa las rutas o la conexión de cámara.")
            if len({c["stream"] for c in active}) > 1:
                raise ValueError("No mezcles archivos y cámaras en vivo en una sesión; sus relojes no son equivalentes.")
            identities, occupancy, metrics = IdentityStore(config), Occupancy(config), SessionMetrics()
            # Posición, ropa y aspecto físico por ID temporal, con retención corta.
            # Un fallo al abrir la base no debe impedir el monitoreo.
            try:
                identity_memory = IdentityMemory(
                    self.data_root / "data" / "identidad" / f"{self.project_id or 'local'}.sqlite",
                    retention_hours=clamp_retention(config.get("identityRetentionHours", 24)))
            except (OSError, sqlite3.Error):
                identity_memory = None
            # Guardamos observaciones y métricas también para fuentes en vivo.
            # El video remoto no se archiva y la URL no se escribe en el
            # manifiesto para evitar conservar credenciales o enlaces efímeros.
            from replay import ReplayWriter
            replay = ReplayWriter(
                self.data_root,
                self.state["session"],
                "unified" if request.get("combined") else "tracking",
                [{"id":c["id"],"name":c.get("name",c["id"]),
                  "source":c["source"] if not (c.get("stream") or (isinstance(c.get("source"), str) and "://" in c["source"])) else "",
                  "sourceKind":"live" if (c.get("stream") or (isinstance(c.get("source"), str) and "://" in c["source"])) else "recording",
                  "offset":c.get("offset",0),"planId":c.get("planId","custom"),
                  "countLines":c.get("countLines",[])} for c in cams],
                {k:v for k,v in config.items() if k != "cameras"},
                self.project_id,
            )
            from following.combined import CombinedAnalysis
            combined = CombinedAnalysis(cams, ROOT) if request.get('combined') else None
            from following.adaptive import AdaptiveVisionController, AsyncDensitySampler
            avie = {c['id']: AdaptiveVisionController(c.get('crowdThreshold', 30)) for c in cams}
            density_sampler = AsyncDensitySampler(lambda: self.load_detector('p2pnet', {'inferenceSize': 256})) if mode == 'hybrid' else None
            camera_analytics = {}
            from zone_episodes import plan_observed
            level_configs={pid:config if pid==config.get('planId','custom') else {**config,**config.get('plans',{}).get(pid,{}), 'planId':pid} for pid in {c.get('planId','custom') for c in cams}}
            level_occupancy={pid:Occupancy(value) for pid,value in level_configs.items()}
            level_flow={pid:ZoneFlow(value) for pid,value in level_configs.items()}
            flow_fields={pid:FlowField(value) for pid,value in level_configs.items()}
            camera_maps={c['id']:Occupancy(level_configs[c.get('planId','custom')], scope='camera-map:'+c['id']) for c in cams}
            camera_levels={c['id']:c.get('planId','custom') for c in cams}
            for camera in cams:
                plan=level_configs[camera.get('planId','custom')]
                camera['scope']={key:plan.get(key) for key in ('width','height','workArea','zones','mapAsset')}
            from bag_signal import BagSignal
            bag_signal = BagSignal(ROOT,cams)
            flow = ZoneFlow(config)
            trails = {}
            wall_start = time.monotonic()
            timeline = 0.
            while not self.stop_event.is_set():
                # Permite relanzar una cámara que perdió señal sin detener las
                # demás ni reconstruir el detector.
                with self.lock:
                    restart_ids = list(self.camera_restart_requests)
                    self.camera_restart_requests.clear()
                for restart_id in restart_ids:
                    if any(c.get("id") == restart_id for c in active):
                        continue
                    camera = next((c for c in cams if c.get("id") == restart_id), None)
                    if camera is None:
                        continue
                    source = camera.get("source")
                    try:
                        hold_source(source, ROOT)
                        if source == "":
                            raise ValueError("Configura una fuente para esta cámara.")
                        if isinstance(source, str) and not source.lower().startswith(("rtsp://", "http://", "https://", "rtmp://")):
                            source = str((ROOT / source).resolve())
                        stream = isinstance(source, int) or "://" in str(source)
                        if stream:
                            from following.source import NetworkCapture
                            cap = NetworkCapture(source, ROOT)
                        else:
                            cap = cv2.VideoCapture(source)
                        if not cap.isOpened():
                            cap.release()
                            raise ValueError("No se pudo abrir la fuente.")
                        try:
                            cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
                        except cv2.error:
                            pass
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        if not np.isfinite(fps) or fps <= 0:
                            fps = 25.
                        camera.update(
                            cap=cap, fps=fps, stream=stream,
                            duration=cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps if not stream else None,
                            frameIndex=-1,
                            tracker=ByteTrackPuntos(umbral_alto=.6, max_frames_perdido=45),
                            h=calibration(camera.get("pairs", [])),
                            headPoints=primary_mode == "p2pnet",
                        )
                        camera["projects"] = camera["h"] is not None and (not camera["headPoints"] or ground_point(camera, .5, .5, person_height) is not None)
                        try:
                            camera["hInv"] = np.linalg.inv(camera["h"]) if camera["projects"] and camera["headPoints"] else None
                        except np.linalg.LinAlgError:
                            camera["hInv"] = None
                        captures[restart_id] = cap
                        active.append(camera)
                        statuses[restart_id] = {"id": restart_id, "status": "ready"}
                    except (ValueError, RuntimeError, OSError) as exc:
                        statuses[restart_id] = {"id": restart_id, "status": "error", "error": str(exc) or "No se pudo abrir la fuente."}
                    with self.lock:
                        self.state["cameras"] = list(statuses.values())
                if not active:
                    # Solo se espera un reinicio si alguna cámara cayó por error;
                    # si todas terminaron (fin de archivo) la sesión se cierra.
                    if not self.stop_event.is_set() and any(s.get("status") in ("error", "reconnecting") for s in statuses.values()):
                        self.stop_event.wait(.25)
                        continue
                    break
                if self.pause_event.is_set():
                    self.stop_event.wait(.1)
                    continue
                start = time.monotonic()
                # En vivo prima la latencia. En archivos prima conservar las
                # muestras: el coste de inferencia no debe saltarse cruces.
                t = start - wall_start if active[0]["stream"] else timeline
                observations, raw_frames, pending = [], {}, []
                for c in list(active):
                    if self.stop_event.is_set():
                        break
                    cap = c["cap"]
                    if not c["stream"]:
                        target = max(0, int((t + c.get("offset", 0)) * c["fps"]))
                        if target < c["frameIndex"]:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                            c["frameIndex"] = target - 1
                        while c["frameIndex"] < target - 1:
                            if not cap.grab():
                                break
                            c["frameIndex"] += 1
                    ok, frame = cap.read()
                    c["frameIndex"] += 1
                    if not ok or frame is None or frame.size == 0:
                        statuses[c["id"]] = {**statuses[c["id"]], "status": "error" if c["stream"] else "ended", "error": "Fuente sin imagen" if c["stream"] else None}
                        active.remove(c)
                        cap.release()
                        with self.lock:
                            self.state["cameras"] = list(statuses.values())
                        if request.get("requireUnified"):
                            active.clear()
                            break
                        continue
                    if frame.shape[1]>1280:
                        frame=cv2.resize(frame,(1280,round(frame.shape[0]*1280/frame.shape[1])))
                    height, width = frame.shape[:2]
                    raw_frames[c["id"]] = frame
                    pending.append((c, frame, height, width))
                if self.stop_event.is_set():
                    break
                if not active:
                    for counter in [occupancy, *level_occupancy.values(), *camera_maps.values()]:
                        counter.update([], t, observation_valid=False)
                    if any(s.get("status") in ("error", "reconnecting") for s in statuses.values()):
                        self.stop_event.wait(.25)
                        continue
                    break
                detector_started = time.monotonic()
                detection_batches = (detector.detectar_lote([item[1] for item in pending])
                                     if hasattr(detector, "detectar_lote")
                                     else [detector.detectar(item[1]) for item in pending])
                detector_ms = (time.monotonic() - detector_started) * 1000
                observed_ids = set()
                for (c, frame, height, width), detections in zip(pending, detection_batches):
                    if detections is None:
                        continue
                    observed_ids.add(c['id'])
                    keep = []
                    for i,d in enumerate(detections):
                        ground = ground_point(c,d.x/width,d.y/height,person_height) if c["projects"] else None
                        if accepts(c,c["scope"],d.x/width,d.y/height,ground,image_only=not c["projects"]):
                            keep.append(i)
                    excluded = len(detections)-len(keep)
                    detections = [detections[i] for i in keep]
                    for detection in detections:
                        detection.appearance = torso_histogram(frame, getattr(detection, "box", None))
                    tracks, _, _ = c["tracker"].actualizar(detections, t)
                    for tr in tracks:
                        px, py = tr.posicion
                        box = tr.ultima_caja
                        point = ground_point(c, px / width, py / height, person_height) if c["projects"] else None
                        if not accepts(c,c["scope"],px/width,py/height,point,image_only=not c["projects"]):
                            continue
                        if point and not (0 <= point[0] <= c["scope"]["width"] and 0 <= point[1] <= c["scope"]["height"]):
                            point = None
                        # Sin recuadro no hay color de ropa, y sin color la fusión entre cámaras
                        # nunca pasa su umbral: la misma persona se contaría dos veces. Con
                        # P2PNet se deriva un recorte solo para muestrear el color; no se
                        # publica como detección porque es una estimación, no una medición.
                        sample = box if box is not None else (body_box(c.get("hInv"), px, py, point, width, height) if c["headPoints"] else None)
                        color = getattr(tr, "apariencia", None)
                        if color is None:
                            color = torso_histogram(frame, sample)
                        observations.append({"camera": c["id"], "local": tr.id, "point": point, "pixel": [float(px), float(py)], "box": box, "color": color, "score": tr.score,
                                             "height": estimate_height(c, box, width, height)})
                    camera_count = sum(o["camera"] == c["id"] for o in observations)
                    avie_state = avie[c["id"]].update(detections, tracks, detector_ms / max(1, len(pending)))
                    if density_sampler and avie_state["p2pRequested"]:
                        density_sampler.submit(c["id"], frame, t)
                    statuses[c["id"]] = {"id": c["id"], "status": "live", "width": width, "height": height, "fps":c["fps"], "duration":c.get("duration"), "calibrated": c["projects"], "count": camera_count, "excluded":excluded, "timestamp": t, "sourceTime":c["frameIndex"]/c["fps"] if not c["stream"] else None, "detector": primary_mode, "inferenceMs": round(detector_ms / max(1, len(pending)), 2), "avie": avie_state}
                    with self.lock:
                        self.source_checks[c["id"]] = {"source":c["source"],"valid":True,"width":width,"height":height,"fps":c["fps"],"checkedAt":time.time()}
                people = identities.update(observations, t)
                if identity_memory:
                    identity_memory.record(self.state["session"], people, identities, t)
                if combined:
                    for c in active:
                        if c['id'] not in observed_ids:
                            continue
                        group=[p for p in people if p['camera']==c['id']]
                        camera_analytics[c['id']] = combined.observe(c, raw_frames[c['id']], group, t,
                            density=density_sampler.latest(c['id']) if density_sampler else None,
                            avie=avie[c['id']].last)
                        camera_analytics[c['id']]['map']=camera_maps[c['id']].update(group,t, observation_valid=bool(c.get('projects')))
                for c in cams:
                    if c['id'] not in observed_ids:
                        camera_maps[c['id']].update([], t, observation_valid=False)
                for cid, frame in raw_frames.items():
                    try:
                        bag_events = bag_signal.observe(cid,frame,t)
                        if bag_events:
                            con = business_data.connect(self.config_path)
                            try:
                                commercial.setup(con)
                                with con:
                                    for event in bag_events:
                                        ident = f"{self.state['session']}:{cid}:{event['business']}:{event['t']}"
                                        con.execute("INSERT OR IGNORE INTO commercial_bags VALUES (?,?,?,?,?,?,?,?,?)", (ident,self.state['session'],event['business'],t,int(event['matched']),int(event['changed']),event['similarity'],event['reason'],'demo' if config.get('testRun') else 'real'))
                            finally:
                                con.close()
                        if cid in bag_signal.cameras:
                            camera_analytics.setdefault(cid,{})['bagSignal'] = {'status':'experimental','samples':len(bag_events)}
                    except (ValueError, ImportError, OSError, RuntimeError) as exc:
                        camera_analytics.setdefault(cid,{})['bagSignal'] = {'status':'unavailable','error':str(exc)}
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
                    primary_plan = config.get('planId','custom')
                    analytics = occupancy.update([p for p in people if camera_levels[p['camera']]==primary_plan], t,
                        observation_valid=plan_observed(cams, observed_ids, primary_plan))
                    analytics["flow"] = flow.update(people,t)
                    levels={}
                    for pid, counter in level_occupancy.items():
                        group=[p for p in people if camera_levels[p['camera']]==pid]
                        levels[pid]=counter.update(group,t, observation_valid=plan_observed(cams, observed_ids, pid))
                        levels[pid]['flow']=level_flow[pid].update(group,t)
                        levels[pid]['flowVectors']=flow_fields[pid].update(group,t)
                    analytics=levels.get(config.get('planId','custom'),analytics)
                    if replay:
                        views=[]
                        for c in active:
                            h,w=raw_frames[c["id"]].shape[:2]
                            views.append({"id":c["id"],"t":statuses[c["id"]].get("sourceTime"),"observed":c["id"] in observed_ids,"analysis":camera_analytics.get(c["id"]),"people":[{"id":p["id"],"box":[p["box"][0]/w,p["box"][1]/h,p["box"][2]/w,p["box"][3]/h] if p["box"] else None,"pixel":[p["pixel"][0]/w,p["pixel"][1]/h],"point":p["point"],"association":p["association"],"history":p.get("history",[])[-30:]} for p in people if p["camera"]==c["id"]]})
                        replay.append({"t":t,"cameras":views,"analytics":analytics,"levels":levels})
                    self.dispatch_alerts(camera_analytics, analytics, levels)
                    self.record_traffic(analytics, bool(active and active[0].get("stream")))
                    self.state.update(status="paused" if self.pause_event.is_set() else "running", people=people, cameras=list(statuses.values()), events=list(identities.events), t=t,
                                      analytics=analytics, levelAnalytics=levels, cameraAnalytics=copy.deepcopy(camera_analytics), synchronization={"mode":"live" if active[0]["stream"] else "recordings", "contentVerified":config["clocksVerified"], "sampleSkewSeconds":round(skew,5), "commonTime":t}, totals=metrics.update(people,analytics,t), series=list(metrics.series), processingMs=round(elapsed * 1000), updatedAt=time.time())
                timeline = round(timeline+.2,6)
                self.stop_event.wait(max(0., .2 - elapsed))
        except Exception as exc:
            with self.lock:
                self.state.update(status="error", error=f"{type(exc).__name__}: {exc}", people=[])
        finally:
            # Close aggregate episodes at their last source observation, never
            # fabricate a below-threshold sample when a source/session ends.
            reason = "source_error" if self.state["status"] == "error" else "session_stopped" if self.stop_event.is_set() else "session_ended"
            for pid, counter in level_occupancy.items():
                counter.zone_episodes.finish(reason)
                with self.lock:
                    snapshot = self.state.get('levelAnalytics', {}).get(pid)
                    if snapshot is not None:
                        snapshot['zoneEpisodes'] = counter.zone_episodes.snapshot()
            if density_sampler:
                density_sampler.close()
            if identity_memory:
                identity_memory.close()
            self.flush_traffic()
            if combined:
                final_analytics=combined.close()
                with self.lock:
                    self.state['cameraAnalytics']=copy.deepcopy(final_analytics)
                if replay:
                    replay.meta['cameraAnalytics']=final_analytics
                    replay.meta['levelAnalytics']=self.state.get('levelAnalytics',{})
                    replay.meta['derivedMapVersion']=2
            if replay:
                try:
                    replay.meta['reportAnalytics'] = copy.deepcopy(self.state['analytics'])
                    replay.meta['totals'] = copy.deepcopy(self.state.get('totals', {}))
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
        from following.line_counter import LineCounter
        counters = {c["id"]: LineCounter(c.get("countLines", [])) for c in config["cameras"]}
        from replay import ReplayWriter
        replay = ReplayWriter(self.data_root, self.state["session"], "demo", config["cameras"], {k:v for k,v in config.items() if k != "cameras"}, self.project_id)
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
            camera_analytics = {}
            for c in config["cameras"]:
                synthetic = []
                for l in c.get("countLines", []):
                    a,b = l["a"],l["b"]
                    dx,dy = b[0]-a[0],b[1]-a[1]
                    length = math.hypot(dx,dy) or 1
                    side = .02 if int(t/2)%2 else -.02
                    synthetic.append({"id": "DEMO-"+l["id"], "pixel": [(a[0]+b[0])/2-dy/length*side,(a[1]+b[1])/2+dx/length*side]})
                camera_analytics[c["id"]] = {"crossings": counters[c["id"]].update(synthetic,t)}
            analytics = occupancy.update(people,t)
            replay.append({"t":t,"analytics":analytics,"levels":{config.get("planId","custom"):analytics},"cameras":[{"id":cid,"t":t,"analysis":a,"people":[p for p in people if p["camera"]==cid]} for cid,a in camera_analytics.items()]})
            with self.lock:
                self.state["cameraAnalytics"] = copy.deepcopy(camera_analytics)
                self.state.update(status="paused" if self.pause_event.is_set() else "running", people=people, t=t, analytics=analytics, totals=metrics.update(people,analytics,t), series=list(metrics.series), updatedAt=time.time(), cameras=[])
            self.stop_event.wait(.2)
            t += .2
        replay.meta["cameraAnalytics"] = camera_analytics if t else {}
        occupancy.zone_episodes.finish("session_stopped")
        with self.lock:
            self.state['analytics']['zoneEpisodes'] = occupancy.zone_episodes.snapshot()
        replay.meta['reportAnalytics'] = copy.deepcopy(self.state['analytics'])
        replay.meta['totals'] = copy.deepcopy(self.state.get('totals', {}))
        replay.finish("stopped")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_data(self, code, body, content_type="application/json"):
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8") if content_type == "application/json" and not isinstance(body, bytes) else body
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type == "application/json" else content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
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

    @http_operation
    def do_GET(self):
        if not self.allowed():
            return self.send_data(403, {"error": "Acceso local requerido."})
        url = urlparse(self.path)
        engine = self.server.engine
        if url.path == "/api/commercial/sample":
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401,{"error":"Inicia sesión."})
            try:
                sample = json.loads((ROOT / "data/commercial-tests/validacion.json").read_text(encoding="utf-8"))
                if sample.get("projectId") != engine.project_id:
                    raise ValueError("No hay una prueba comercial guardada en este proyecto.")
                return self.send_data(200,sample)
            except (OSError, ValueError) as exc:
                return self.send_data(404,{"error":str(exc)})
        if url.path in ("/api/commercial", "/api/commercial/template", "/api/commercial/export"):
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión para consultar ventas."})
            with engine.lock:
                metrics = engine.business_metrics()
                con = business_data.connect(engine.config_path)
                try:
                    businesses = business_catalog.sync(con, engine.config, ROOT / "dashboard/public")
                    if url.path == "/api/commercial/template":
                        return self.send_data(200, commercial.template(businesses).encode("utf-8-sig"), "text/csv; charset=utf-8")
                    query = parse_qs(url.query)
                    result = commercial.summary(con, businesses, metrics["negocios"], query.get("dataset",["real"])[0], query.get("date",[None])[0], query.get("hour",[None])[0], query.get("empresa",[None])[0] or None)
                    if url.path == "/api/commercial/export":
                        import csv, io
                        output = io.StringIO(); writer = csv.writer(output)
                        if query.get('kind', [''])[0] == 'incidents':
                            writer.writerow(['Negocio','Origen','Inicio','Duración segundos','Pico personas','Ventas de la hora PEN','Referencia histórica PEN','Días comparables','Diferencia descriptiva %','Alcance de comparación'])
                            for row in result['businesses']:
                                for incident in row['incidents']:
                                    writer.writerow([row['name'],result['dataset'],incident['start'],incident['duration'],incident['peak'],incident['sales'],incident['baseline'],incident['sampleDays'],incident['differencePercent'],incident['scope']])
                            return self.send_data(200, output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8')
                        writer.writerow(["Negocio","Fecha","Hora","Origen","Entradas","Ventas PEN","Proyección PEN","Días históricos","Salidas emparejadas","Objetos nuevos","Salidas sin emparejar"])
                        for row in result["businesses"]:
                            writer.writerow([row["name"],result["date"],result["hour"],result["dataset"],row["entries"],row["sales"],row["forecast"]["estimate"],row["forecast"]["days"],row["bags"]["matched"],row["bags"]["changed"],row["bags"]["unmatched"]])
                        return self.send_data(200, output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")
                    return self.send_data(200,result)
                except (ValueError, TypeError) as exc:
                    return self.send_data(400,{"error":str(exc)})
                finally:
                    con.close()
        if url.path == "/api/businesses/metrics":
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión."})
            return self.send_data(200, engine.business_metrics())
        if url.path == "/api/businesses":
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión para consultar los negocios."})
            with engine.lock:
                conexion = business_data.connect(engine.config_path)
                try:
                    return self.send_data(200, {"negocios": business_catalog.sync(conexion, engine.config, ROOT / "dashboard" / "public"), "projectId": engine.project_id})
                finally:
                    conexion.close()
        if url.path.startswith("/api/replay/"):
            from replay import get
            return get(self,url,self.server.engine.data_root)
        if url.path.startswith("/api/counting/"):
            from counting.api import get
            return get(self, url, ROOT)
        if url.path == "/api/mail":
            import notifier
            return self.send_data(200, {**notifier.public(engine.settings_root), "lastError": engine.mailer.error, "sent": engine.mailer.sent,
                                         "deliveryPersistence": engine.notifications.diagnostics()})
        if url.path == "/api/auth":
            sesion = engine.sessions.leer(self.headers.get("X-LAP-Session", ""))
            return self.send_data(200, {
                "configurado": auth.hay_usuarios(engine.settings_root),
                "usuario": sesion["usuario"] if sesion else None,
                "rol": sesion["rol"] if sesion else None,
                "usuarios": auth.listar(engine.settings_root) if sesion and sesion["rol"] == "operador" else [],
            })
        if url.path == "/api/incidents":
            estado = parse_qs(url.query).get("estado", [None])[0]
            return self.send_data(200, engine.incidents(estado))
        if url.path == "/api/traffic-baseline":
            query = parse_qs(url.query)
            zona = query.get("zona", [""])[0]
            if not zona:
                return self.send_data(400, {"error": "Indica la zona."})
            return self.send_data(200, {"zona": zona, "historico": engine.traffic_baseline(zona)})
        if url.path == "/api/projects":
            return self.send_data(200, engine.projects_listing())
        if url.path == "/api/config":
            with engine.lock:
                return self.send_data(200, {"config": engine.config, "token": engine.token, "revision": engine.revision, "projectId": engine.project_id})
        if url.path == "/api/state":
            return self.send_data(200, engine.snapshot())
        if url.path in ("/api/report", "/api/report/session"):
            from live_reports import export
            query=parse_qs(url.query)
            try:
                with engine.lock:
                    config=copy.deepcopy(engine.config)
                    snapshot=engine.snapshot()
                if query.get('session'):
                    from replay import report_snapshot
                    config,snapshot,meta=report_snapshot(engine.data_root,query['session'][0],engine.project_id)
                if url.path == '/api/report/session':
                    return self.send_data(200, {'config':config,'state':snapshot,'created':meta['created'] if query.get('session') else None,'scope':'session'})
                result,mime=export(config,snapshot,query.get("kind",["zones"])[0],query.get("format",["csv"])[0])
                with engine.lock:
                    engine.record("Reporte exportado",query.get("kind",["zones"])[0]+" · "+query.get("format",["csv"])[0])
                return self.send_data(200,result,mime)
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                return self.send_data(400,{"error":str(exc)})
        if url.path == "/api/frame":
            cid = parse_qs(url.query).get("camera", [""])[0]
            with engine.lock:
                if engine.preview_state.get("camera") == cid:
                    engine.preview_touch = time.time()
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

    # Rutas de configuracion: solo el operador. El administrador entra al
    # sistema, ve todo y ajusta umbrales de alerta, pero no toca la geometria
    # ni la calibracion, para no romper por error algo que costo calibrar.
    SOLO_OPERADOR = ("/api/commercial/import", "/api/commercial/simulate", "/api/businesses", "/api/config", "/api/import-plan", "/api/plan-lines", "/api/upload", "/api/camera-restart",
                     "/api/camera-preview", "/api/calibration-check")

    def reject(self, size, code, message):
        """Rechaza leyendo primero el cuerpo enviado.

        Si se responde sin consumirlo, el cliente se queda escribiendo contra
        una conexion que ya se cerro y recibe un error de red en vez del
        mensaje que explica que paso."""
        try:
            remaining = max(0, size)
            while remaining:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass
        return self.send_data(code, {"error": message})

    @http_operation
    def do_POST(self):
        engine = self.server.engine
        size = int(self.headers.get("Content-Length", "0"))
        if not self.allowed() or not secrets.compare_digest(self.headers.get("X-LAP-Token", ""), engine.token):
            return self.reject(size, 403, "Recarga la interfaz local antes de continuar.")
        try:
            parsed = urlparse(self.path)
            sesion = engine.sessions.leer(self.headers.get("X-LAP-Session", ""))
            if parsed.path != "/api/auth" and auth.hay_usuarios(engine.settings_root):
                if not sesion:
                    return self.reject(size, 401, "Inicia sesión para continuar.")
                if sesion["rol"] != "operador" and parsed.path in self.SOLO_OPERADOR:
                    return self.reject(size, 403, "Tu usuario no puede cambiar la configuración. Pídeselo a un operador.")
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
                modo=query.get("mode",["estructuras"])[0]
                if modo not in ("estructuras","bordes"):
                    raise ValueError("Modo de trazado inválido.")
                result=plan_lines_from_bytes(self.rfile.read(size),width,modo)
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
                hold_path(target, write=True)
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
            if parsed.path == "/api/commercial/simulate":
                with engine.lock:
                    if data.get("projectId") != engine.project_id:
                        raise ValueError("El proyecto cambió; recarga antes de generar datos.")
                    con = business_data.connect(engine.config_path)
                    try:
                        businesses = business_catalog.sync(con, engine.config, ROOT / "dashboard/public")
                        result = commercial.simulate_demo(con, businesses, data.get("days", 28), engine.project_id)
                        engine.record("Datos comerciales simulados", f"{result['businesses']} negocios · {result['days']} días")
                        return self.send_data(200, result)
                    finally:
                        con.close()
            if parsed.path == "/api/commercial/import":
                with engine.lock:
                    if data.get("projectId") != engine.project_id:
                        raise ValueError("El proyecto cambió; recarga antes de importar.")
                    con = business_data.connect(engine.config_path)
                    try:
                        businesses = business_catalog.sync(con, engine.config, ROOT / "dashboard/public")
                        result = commercial.import_sales(con,data.get("csv"),businesses,data.get("name","ventas.csv"),data.get("dataset","real"),bool(data.get("preview")))
                        return self.send_data(200,result)
                    finally:
                        con.close()
            if parsed.path == "/api/businesses":
                with engine.lock:
                    if data.get("projectId") != engine.project_id:
                        raise ValueError("El proyecto cambió. Recarga los negocios antes de guardar.")
                    if engine.worker and engine.worker.is_alive():
                        raise ValueError("Detén el monitoreo antes de editar los negocios o sus accesos.")
                    conexion = business_data.connect(engine.config_path)
                    try:
                        if data.get("action") == "reopen":
                            with conexion:
                                conexion.execute("INSERT OR REPLACE INTO negocio_estados VALUES (?,?)", (data.get("id"), "activo"))
                        elif data.get("action") == "delete":
                            with conexion:
                                conexion.execute("INSERT OR REPLACE INTO negocio_estados VALUES (?,?)", (data.get("id"), "cerrado"))
                            updated = copy.deepcopy(engine.config)
                            for c in updated["cameras"]:
                                for l in c.get("countLines", []):
                                    if (l.get("place") or {}).get("id") == data.get("id"):
                                        l.pop("place", None)
                            engine.configure(updated)
                        elif data.get("action") == "save":
                            referencia = data.get("referencia")
                            catalogo = None
                            if referencia:
                                asset = referencia.get("asset") if isinstance(referencia, dict) else None
                                if asset not in [f"/maps/lap/{n}.json" for n in (1, 2, 3, 4)]:
                                    raise ValueError("Referencia cartográfica inválida.")
                                catalogo = json.loads((ROOT / "dashboard" / "public" / asset.lstrip("/")).read_text(encoding="utf-8"))
                            business_data.guardar_negocio(conexion, data, engine.config, catalogo)
                            updated = copy.deepcopy(engine.config)
                            for c in updated["cameras"]:
                                for l in c.get("countLines", []):
                                    if (l.get("place") or {}).get("id") == data["id"]:
                                        l.pop("place", None)
                                    if any(p["camaraId"] == c["id"] and p["lineaId"] == l["id"] for p in data.get("puertas", [])):
                                        l["place"] = {"id": data["id"], "name": data["nombre"], **data["ubicacion"]}
                            engine.configure(updated)
                        else:
                            raise ValueError("Acción de negocio desconocida.")
                        engine.record("Negocios actualizados", data.get("nombre") or data.get("id", ""))
                        return self.send_data(200, {"negocios": business_data.listar_negocios(conexion), "projectId": engine.project_id, "config": engine.config})
                    except sqlite3.IntegrityError as exc:
                        raise ValueError("No se pudo guardar el negocio: revisa sus puertas.") from exc
                    finally:
                        conexion.close()
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
                from live_core import calibration_diagnostics
                return self.send_data(200,calibration_diagnostics(pairs))
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
                hold_source(source, ROOT)
                if isinstance(source,str) and "://" not in source:
                    source=str((ROOT/source).resolve())
                hls = isinstance(source, str) and is_youtube_url(source)
                if isinstance(source, str):
                    source = resolve_stream_source(source)
                if isinstance(source,str) and "://" in source:
                    with low_latency_ffmpeg(hls):
                        cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
                else:
                    cap=cv2.VideoCapture(source)
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
                    engine.warm_detector_async()
                    return self.send_data(200,{"width":w,"height":h,"fps":fps,"duration":cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps})
                finally:
                    cap.release()
            if parsed.path == "/api/camera-restart":
                return self.send_data(200, engine.request_camera_restart(data.get("camera")))
            if self.path == "/api/projects":
                # Los dos roles administran proyectos: crear y eliminar es gestión del
                # espacio de trabajo, no configuración de cámaras ni de plano, que sigue
                # reservada al operador mediante SOLO_OPERADOR.
                action = data.get("action")
                pid = data.get("id")
                if action == "create":
                    return self.send_data(200, engine.new_project(data.get("name",""), bool(data.get("copyCurrent"))))
                if action == "open":
                    return self.send_data(200, engine.open_project(pid))
                if action == "rename":
                    return self.send_data(200, engine.rename_project(pid, data.get("name","")))
                if action == "delete":
                    return self.send_data(200, engine.delete_project(pid))
                raise ValueError("Acción de proyecto desconocida.")
            if parsed.path == "/api/auth":
                accion = data.get("accion")
                if accion == "login":
                    rol = auth.verificar(engine.settings_root, data.get("usuario", ""), data.get("clave", ""))
                    if not rol:
                        return self.send_data(401, {"error": "Usuario o contraseña incorrectos."})
                    usuario = str(data.get("usuario", "")).strip().lower()
                    token = engine.sessions.abrir(usuario, rol)
                    engine.record("Inicio de sesión", f"{usuario} ({rol})")
                    return self.send_data(200, {"sesion": token, "usuario": usuario, "rol": rol})
                if accion == "logout":
                    engine.sessions.cerrar(self.headers.get("X-LAP-Session", ""))
                    return self.send_data(200, {"ok": True})
                primero = not auth.hay_usuarios(engine.settings_root)
                if primero:
                    # Sin usuarios todavía, el primero que se crea es el operador
                    # que después dará de alta a los demás.
                    usuarios = auth.crear(engine.settings_root, data.get("usuario", ""), data.get("clave", ""), "operador")
                    engine.record("Primer usuario creado", str(data.get("usuario", "")))
                    return self.send_data(200, {"usuarios": usuarios})
                if not sesion or sesion["rol"] != "operador":
                    return self.send_data(403, {"error": "Solo un operador puede administrar usuarios."})
                if accion == "crear":
                    return self.send_data(200, {"usuarios": auth.crear(engine.settings_root, data.get("usuario", ""), data.get("clave", ""), data.get("rol", ""))})
                if accion == "eliminar":
                    engine.sessions.cerrar_usuario(str(data.get("usuario", "")).strip().lower())
                    return self.send_data(200, {"usuarios": auth.eliminar(engine.settings_root, str(data.get("usuario", "")).strip().lower())})
                if accion == "clave":
                    auth.cambiar_clave(engine.settings_root, str(data.get("usuario", "")).strip().lower(), data.get("clave", ""))
                    return self.send_data(200, {"usuarios": auth.listar(engine.settings_root)})
                raise ValueError("Acción de usuario desconocida.")
            if parsed.path == "/api/alert-rules":
                # Umbrales de aglomeración: es lo único de configuración que el
                # administrador sí puede ajustar, porque define cuándo le avisan.
                engine.update_alert_rules(data)
                return self.send_data(200, {"ok": True})
            if parsed.path == "/api/incidents":
                return self.send_data(200, engine.update_incident(data.get("id"), data.get("estado")))
            if self.path == "/api/mail":
                import notifier
                if data.get("action") == "test":
                    engine.mailer.send("AeroTrack · Correo de prueba",
                                       "Si recibes este mensaje, los avisos de seguridad de AeroTrack están bien configurados.",
                                       blocking=True)
                    engine.record("Correo de prueba", "Enviado al personal configurado")
                    return self.send_data(200, {"ok": True})
                result = notifier.save(engine.settings_root, data)
                engine.record("Avisos por correo", "Configuración actualizada")
                return self.send_data(200, result)
            if self.path == "/api/preview":
                action = data.get("action", "start")
                if action == "start":
                    engine.preview_start(data.get("camera"), data.get("seconds", 0) or 0)
                else:
                    engine.preview_control(action, data.get("seconds"))
                return self.send_data(200, engine.preview_snapshot())
            if parsed.path == "/api/config":
                # El navegador dice a qué proyecto cree que pertenecen los
                # cambios. Si no es el abierto, se rechazan: son el borrador del
                # proyecto anterior y sobrescribirían el plano de este.
                intended = parse_qs(parsed.query).get("project", [None])[0]
                if intended and engine.project_id and intended != engine.project_id:
                    raise ValueError("Esos cambios pertenecen a otro proyecto y no se guardaron. Vuelve a abrirlo para editarlo.")
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
    server = ManagedHTTPServer(("127.0.0.1", args.port), Handler, bind_and_activate=False)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        server.allow_reuse_address = False
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.server_bind()
    server.server_activate()
    server.engine = Engine(args.config_path)
    try:
        from automation_reports import ScheduledReports
        service = server.engine.automation
        service.tasks = {"reports": ScheduledReports(server.engine, service.store)}
        server.engine.automation.start()
        # La interfaz y la configuración pueden abrirse mientras P2PNet prepara sus
        # pesos en segundo plano. Así el primer monitoreo no paga toda la carga del
        # modelo después de que el operador pulsa «Iniciar».
        server.engine.warm_detector_async()
        from replay import recover_interrupted
        recover_interrupted(server.engine.data_root)
        print(f"LAP: http://127.0.0.1:{args.port} — solo equipo local", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if stop_server(server):
            server.server_close()
        else:
            print("Cierre incompleto: esperando trabajadores/recursos activos.", flush=True)
            defer_close(server)


if __name__ == "__main__":
    main()
