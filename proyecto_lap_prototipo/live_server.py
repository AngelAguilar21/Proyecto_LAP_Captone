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
import projects
import business_data
import sqlite3
import auth

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
        self.token = secrets.token_urlsafe(32)
        self.instance = secrets.token_hex(8)
        self.revision = 0
        self.runtime_config = None
        self.report_config = None
        self.frames = {}
        self.preview_frames = {}
        self.source_checks = {}
        self.preview_worker = None
        self.preview_stop_event = threading.Event()
        self.preview_pause_event = threading.Event()
        self.preview_seek_request = None
        self.preview_touch = 0.
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

    def dispatch_alerts(self, camera_analytics, analytics):
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
            for item in ((data.get("luggage") or {}).get("items") or []):
                if not item.get("alert"):
                    continue
                key = "equipaje:{}:{}".format(cid, item.get("id"))
                body = [
                    "Un bulto lleva " + str(round(item.get("duration", 0))) + " segundos sin moverse.",
                    "",
                    "Lugar: " + place,
                    "Camara: " + str(names.get(cid, cid)),
                    "Tipo detectado: " + str(item.get("kind")),
                    "",
                    "El sistema no determina si es peligroso: avisa para que alguien vaya a revisarlo.",
                    "Tambien salta con equipaje que un pasajero dejo a su lado mientras espera.",
                ]
                pendientes.append({
                    "key": key, "tipo": "equipaje", "zona": item.get("kind"), "camara": cid,
                    "inicio": item.get("since"), "pico": None, "duracion": item.get("duration"),
                    "detalle": {"camara": names.get(cid, cid), "bulto": item.get("id"),
                                "tipoObjeto": item.get("kind")},
                    "asunto": "AeroTrack - Equipaje sin custodia en " + str(names.get(cid, cid)),
                    "cuerpo": chr(10).join(body)})
        for zone in (analytics or {}).get("zones", []):
            if not zone.get("alert"):
                continue
            key = "zona:{}:{}".format(zone.get("name"), round(self.state.get("t", 0)))
            body = [
                "La zona " + str(zone.get("name")) + " del plano supero su umbral.",
                "",
                "Lugar: " + place,
                "Personas observadas: " + str(zone.get("count")),
                "Duracion: " + str(round(zone.get("duration", 0))) + " s",
                "",
                nota,
            ]
            pendientes.append({
                "key": key, "tipo": "aglomeracion", "zona": zone.get("name"), "camara": None,
                "inicio": self.state.get("t", 0) - (zone.get("duration") or 0),
                "pico": zone.get("peak") or zone.get("count"), "duracion": zone.get("duration"),
                "detalle": {"origen": "plano"},
                "asunto": "AeroTrack - Alerta en " + str(zone.get("name")),
                "cuerpo": chr(10).join(body)})

        if not pendientes:
            return
        sesion = self.state.get("session", "sin-sesion")
        conexion = None
        try:
            conexion = business_data.connect(self.config_path)
            for alerta in pendientes:
                business_data.registrar_incidente(
                    conexion, f"{sesion}:{alerta['key']}", alerta["tipo"], alerta["zona"],
                    alerta["camara"], alerta["inicio"] or 0, alerta["pico"], alerta["duracion"],
                    {**alerta["detalle"], "sesion": sesion})
            self.business_error = None
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.business_error = str(exc)
            return  # Never send a notification without a durable incident.
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

    def validate_incident_history(self, incident_id, never_attended):
        """Backend for an explicit human history decision; never run automatically."""
        with self.lock:
            conexion = business_data.connect(self.config_path)
            try:
                business_data.validar_historial_incidente(conexion, incident_id, never_attended)
                return {"incidentes": business_data.listar_incidentes(conexion), "error": None}
            finally:
                conexion.close()

    def preview_snapshot(self):
        return dict(self.preview_state)

    def preview_stop(self):
        """Corta la vista en vivo y suelta la cámara.

        Nunca debe llamarse sosteniendo self.lock: espera a que termine el hilo
        de previsualización, que a su vez necesita ese mismo candado para
        escribir su última imagen."""
        worker = self.preview_worker
        if worker and worker.is_alive():
            self.preview_stop_event.set()
            worker.join(timeout=4)
        with self.lock:
            self.preview_worker = None
            self.preview_state = {"camera": None, "playing": False, "t": 0., "duration": 0., "live": False, "error": None}

    def preview_start(self, cid, seconds=0.):
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
        self.preview_stop()
        with self.lock:
            self.preview_stop_event = threading.Event()
            self.preview_pause_event = threading.Event()
            self.preview_seek_request = None
            self.preview_touch = time.time()
            self.preview_state = {"camera": cid, "playing": True, "t": float(seconds), "duration": 0., "live": False, "error": None}
            self.preview_worker = threading.Thread(target=self._preview_loop, args=(copy.deepcopy(camera), float(seconds)), daemon=True)
            self.preview_worker.start()
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

    def _preview_loop(self, camera, seconds):
        """Refresca imágenes sin correr detección: es solo para ver la cámara."""
        import cv2
        cid = camera["id"]
        source = camera["source"]
        if isinstance(source, str) and "://" not in source:
            source = str((ROOT / source).resolve())
        remote = isinstance(source, str) and "://" in source
        previous_options = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
        if remote:
            # Sin esto FFmpeg acumula segundos de video antes de entregarlo.
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0|reorder_queue_size;0"
        try:
            cap = (cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
                   if remote else cv2.VideoCapture(source))
        finally:
            if remote:
                if previous_options is None:
                    os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
                else:
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous_options
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
                    while not reader_stop.is_set() and not self.preview_stop_event.is_set():
                        ok, frame = cap.read()
                        if not ok:
                            newest["failed"] = True
                            return
                        newest["frame"] = frame

                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                started_at = time.monotonic()
                while not self.preview_stop_event.is_set():
                    if time.time() - self.preview_touch > 20:
                        break
                    if newest["failed"]:
                        raise ValueError("Se perdió la señal de la cámara.")
                    if self.preview_pause_event.is_set():
                        time.sleep(.15)
                        continue
                    frame = newest["frame"]
                    if frame is None:
                        time.sleep(.05)
                        continue
                    encoded = self._preview_jpeg(frame)
                    with self.lock:
                        self.frames[cid] = encoded
                        self.preview_state["t"] = time.monotonic() - started_at
                    time.sleep(1 / 15)
            else:
                while not self.preview_stop_event.is_set():
                    if time.time() - self.preview_touch > 20:
                        break
                    seek = self.preview_seek_request
                    if seek is not None:
                        self.preview_seek_request = None
                        cap.set(cv2.CAP_PROP_POS_MSEC, seek * 1000)
                    if self.preview_pause_event.is_set():
                        time.sleep(.15)
                        continue
                    started = time.monotonic()
                    ok, frame = cap.read()
                    if not ok:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    encoded = self._preview_jpeg(frame)
                    with self.lock:
                        self.frames[cid] = encoded
                        self.preview_state["t"] = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                    # Una grabación se reproduce a su velocidad real.
                    time.sleep(max(0., 1 / max(1., min(fps, 30)) - (time.monotonic() - started)))
        except (ValueError, OSError, RuntimeError) as exc:
            with self.lock:
                self.preview_state.update(playing=False, error=str(exc))
        finally:
            reader_stop.set()
            if reader and reader.is_alive():
                reader.join(timeout=2)
            cap.release()
            with self.lock:
                self.preview_state["playing"] = False

    def read_config_file(self):
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

    def open_project(self, pid):
        with self.lock:
            self.require_managed()
            self.config_path = projects.activate(ROOT, pid)
            self.project_id = pid
            self.report_config = None
            self.read_config_file()
            if business_data.path_for(self.config_path).exists():
                self.notifications.recover(self.config_path)
            self.frames = {}
            self.preview_frames = {}
            self.source_checks = {}
            self.revision += 1
            self.state = {"status": "idle", "people": [], "cameras": [], "events": [], "t": 0,
                          "analytics": {"clusters": [], "zones": [], "heat": [], "mappedCount": 0}, "error": self.config_error}
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
            config["setupComplete"] = False
            pid = projects.create(ROOT, name.strip(), config)
            self.record("Proyecto creado", name.strip())
            return self.open_project(pid)

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

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({**self.state, "serverTime": time.time(), "serverInstance": self.instance, "configRevision": self.revision, "sourceChecks":self.source_checks, "audit":list(self.audit), "preview": self.preview_snapshot()})

    def automation_snapshot(self):
        """Capture one project/session generation, without individual trajectories."""
        with self.lock:
            state = {key: self.state[key] for key in
                     ("session", "status", "mode", "t", "analytics", "cameraAnalytics",
                      "totals", "series", "cameras") if key in self.state}
            return copy.deepcopy({"project_id": self.project_id, "config_path": self.config_path,
                                  "revision": self.revision, "config": self.report_config,
                                  "state": state})

    def record(self, action, detail):
        self.audit.appendleft({"at":datetime.now(timezone.utc).isoformat(),"action":action,"detail":detail})

    def configure(self, config):
        validate_config(config)
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Detén la sesión antes de cambiar el plano o la calibración.")
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
        self.preview_stop()
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
            self.report_config = copy.deepcopy(self.runtime_config)
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
        luggage = None
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
                replay = ReplayWriter(self.data_root,self.state["session"],"unified" if request.get("combined") else "tracking",[{"id":c["id"],"name":c.get("name",c["id"]),"source":c["source"],"offset":c.get("offset",0),"planId":c.get("planId","custom"),"countLines":c.get("countLines",[])} for c in active],{k:v for k,v in config.items() if k != "cameras"},self.project_id)
            from following.combined import CombinedAnalysis
            from following.luggage import LuggageWatch
            combined = CombinedAnalysis(cams, ROOT) if request.get('combined') else None
            luggage = LuggageWatch(cams, request.get("weights")) if any(LuggageWatch.enabled_for(c) for c in cams) else None
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
                        if luggage:
                            camera_analytics[c['id']]['luggage']=luggage.observe(c,raw_frames[c['id']],t)
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
                    self.dispatch_alerts(camera_analytics, analytics)
                    self.record_traffic(analytics, bool(active and active[0].get("stream")))
                    self.state.update(copy.deepcopy(dict(status="paused" if self.pause_event.is_set() else "running", people=people, cameras=list(statuses.values()), events=list(identities.events), t=t,
                                      analytics=analytics, levelAnalytics=levels, cameraAnalytics=camera_analytics, synchronization={"mode":"live" if active[0]["stream"] else "recordings", "contentVerified":config["clocksVerified"], "sampleSkewSeconds":round(skew,5), "commonTime":t}, totals=metrics.update(people,analytics,t), series=list(metrics.series), processingMs=round(elapsed * 1000), updatedAt=time.time())))
                timeline = round(timeline+.2,6)
                self.stop_event.wait(max(0., .2 - elapsed))
        except Exception as exc:
            with self.lock:
                self.state.update(status="error", error=f"{type(exc).__name__}: {exc}", people=[])
        finally:
            self.flush_traffic()
            if luggage:
                luggage.close()
            if combined:
                final_analytics=combined.close()
                with self.lock:
                    self.state['cameraAnalytics']=copy.deepcopy(final_analytics)
                if replay:
                    replay.meta['cameraAnalytics']=final_analytics
                    with self.lock:
                        replay.meta['levelAnalytics']=copy.deepcopy(self.state.get('levelAnalytics',{}))
                    replay.meta['derivedMapVersion']=2
            if replay:
                try:
                    replay.finish("error" if self.state["status"]=="error" else "stopped" if self.stop_event.is_set() else "ended")
                except OSError as exc:
                    with self.lock:
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
                self.state.update(copy.deepcopy(dict(status="paused" if self.pause_event.is_set() else "running", people=people, t=t, analytics=analytics, totals=metrics.update(people,analytics,t), series=list(metrics.series), updatedAt=time.time(), cameras=[])))
            self.stop_event.wait(.2)
            t += .2


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_data(self, code, body, content_type="application/json"):
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8") if content_type == "application/json" and not isinstance(body, bytes) else body
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
        if url.path == "/api/mail":
            import notifier
            return self.send_data(200, {**notifier.public(engine.settings_root), "lastError": engine.mailer.error, "sent": engine.mailer.sent})
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
    SOLO_OPERADOR = ("/api/config", "/api/import-plan", "/api/plan-lines", "/api/upload",
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
            if self.path == "/api/projects":
                action = data.get("action")
                if sesion and sesion["rol"] != "operador" and action != "open":
                    return self.send_data(403, {"error": "Tu usuario solo puede abrir proyectos existentes."})
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
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler, bind_and_activate=False)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        server.allow_reuse_address = False
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.server_bind()
    server.server_activate()
    server.engine = Engine(args.config_path)
    from replay import recover_interrupted
    recover_interrupted(server.engine.data_root)
    from automation import AutomationService
    automation = AutomationService(server.engine)
    print(f"LAP: http://127.0.0.1:{args.port} — solo equipo local", flush=True)
    try:
        automation.start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        automation.stop()
        server.engine.stop()
        if server.engine.worker:
            server.engine.worker.join()
        server.engine.notifications.join()
        server.engine.preview_stop()
        if getattr(server.engine, "counting", None):
            server.engine.counting.stop()
            if server.engine.counting.worker:
                server.engine.counting.worker.join(timeout=10)
        server.server_close()


if __name__ == "__main__":
    main()
