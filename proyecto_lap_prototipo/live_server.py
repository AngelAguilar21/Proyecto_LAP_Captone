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
import shutil
import socket
import sys
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import numpy as np

ROOT = Path(__file__).resolve().parent


RESERVA_DISCO = 1024 ** 3   # espacio libre que debe quedar después de guardar un video


def validar_tamano_de_video(size, libre):
    """Un video no tiene tope de peso; solo debe caber en el disco con una reserva. `libre` son los bytes libres."""
    if size <= 0:
        raise ValueError("El video está vacío o el navegador no informó su tamaño.")
    if size + RESERVA_DISCO > libre:
        raise ValueError(f"No hay espacio en el disco: el video ocupa {size / 1024 ** 3:.1f} GB y quedan {libre / 1024 ** 3:.1f} GB libres "
                         f"(se deja {RESERVA_DISCO // 1024 ** 3} GB de reserva).")


def desfase_temporal(deltas):
    """(desfase, dispersión, fiable) de las diferencias de posición pb - pa entre parejas de personas.

    Se usa la mediana y el MAD para que una pareja mal marcada no cambie el resultado. Es fiable con 4 o más parejas y una
    dispersión de hasta 0,25 s."""
    deltas = np.asarray(deltas, dtype=float)
    if not len(deltas):
        return 0.0, float("inf"), False
    desfase = float(np.median(deltas))
    dispersion = max(float(np.median(np.abs(deltas - desfase))) * 1.4826, 0.0)
    return desfase, dispersion, bool(len(deltas) >= 4 and dispersion <= 0.25)


def source_time_offset(camera):
    """Offset total de lectura: inicio omitido más corrección temporal estimada.

    ``offset`` sigue siendo el ajuste manual no negativo del inicio del archivo;
    ``syncOffset`` es firmado y solo se escribe cuando la evidencia de personas
    entre cámaras supera la validación automática.
    """
    try:
        return float(camera.get("offset", 0)) + float(camera.get("syncOffset", 0))
    except (TypeError, ValueError):
        return float(camera.get("offset", 0) or 0)


def posiciones_de_pareja(item, base, destino):
    """(pa, pb): instante de la persona en el archivo de video de cada cámara.

    Las parejas nuevas guardan `pa` y `pb`, que no dependen del desfase que se aplique después. Las antiguas solo tienen el
    tiempo común (`ta`, `tb`), que se pasa a archivo con el desfase actual de cada cámara."""
    ta = float(item.get("ta", item.get("t", 0)))
    tb = float(item.get("tb", item.get("t", 0)))
    pa = float(item["pa"]) if "pa" in item else ta + source_time_offset(base)
    pb = float(item["pb"]) if "pb" in item else tb + source_time_offset(destino)
    return pa, pb


def ajuste_de_relojes(base, destino, diferencias):
    """Desfase de tiempo para que la misma persona caiga en el mismo instante común en las dos cámaras.

    `diferencias`: pb - pa de cada pareja, es decir cuánto más adelante está el suceso en el video de `destino`. Ese valor es
    exactamente el desfase de lectura que debe tener `destino` respecto de `base` (si es positivo, `destino` empezó antes y se
    lee más adelante). Como la lectura no puede empezar antes del archivo, si saliera negativa se retrasa `base` en su lugar.
    Devuelve el desfase (`offset`), su dispersión, si es fiable, si hay que cambiar algo y los `syncOffset` de cada cámara."""
    desfase, dispersion, fiable = desfase_temporal(diferencias)
    base_actual, destino_actual = source_time_offset(base), source_time_offset(destino)
    necesita = bool(fiable and abs(desfase - (destino_actual - base_actual)) >= 0.15)
    total_base, total_destino = base_actual, base_actual + desfase
    if total_destino < 0:
        total_base, total_destino = base_actual - total_destino, 0.0
    sync_base = total_base - float(base.get("offset", 0) or 0)
    sync_destino = total_destino - float(destino.get("offset", 0) or 0)
    if not necesita:
        sync_base, sync_destino = float(base.get("syncOffset", 0) or 0), float(destino.get("syncOffset", 0) or 0)
    return {"offset": desfase, "dispersion": dispersion, "fiable": fiable, "necesita": necesita,
            "sync_base": round(sync_base, 4), "sync_destino": round(sync_destino, 4)}


def problemas_de_parejas(filas, ajuste, espacial, unidad, con_geometria):
    """Frases para el operador sobre las parejas de personas: qué falta y qué conviene revisar. {"nivel", "texto"}."""
    n = len(filas)
    if n < 4:
        return [{"nivel": "error", "texto": f"Hay {n} {'pareja' if n == 1 else 'parejas'}; hacen falta 4 como mínimo para relacionar y sincronizar las cámaras. Marca {4 - n} más."}]
    salida = []
    if not ajuste["fiable"]:
        salida.append({"nivel": "error", "texto": f"Las parejas no coinciden en el tiempo (sus desfases varían {ajuste['dispersion']:.2f} s; se admite hasta 0,25 s). "
                                                  "Revisa que cada pareja sea la misma persona en la misma pose."})
    elif any(f["fueraDeTiempo"] for f in filas):
        salida.append({"nivel": "aviso", "texto": "Algunas parejas dan otro desfase que el resto (marcadas en la lista): revisa que sean la misma persona."})
    if len({(f["ta"], f["tb"]) for f in filas}) == 1:
        salida.append({"nivel": "aviso", "texto": "Todas las parejas están en el mismo instante: marca a la persona también en otros momentos para comprobar el desfase."})
    if not con_geometria:
        salida.append({"nivel": "info", "texto": "Sin puntos del suelo en las dos cámaras solo se calcula el desfase de tiempo; la posición en el plano no se puede comparar."})
    elif espacial and not espacial["concuerdan"]:
        salida.append({"nivel": "aviso", "texto": f"La misma persona queda a {espacial['mediana']:.2f} {unidad} (mediana) entre las dos cámaras: sus puntos del suelo no concuerdan. "
                                                  "Recalibra usando los mismos puntos del plano en las dos cámaras."})
    return salida


def abrir_archivo(ruta):
    """VideoCapture de un archivo, con decodificación por hardware si el equipo la ofrece.

    Medido con 7 cámaras de 1920x1080 a 60 fps en un i5 sin GPU: avanzar 0,2 s de video costaba 495 ms por software y 137 ms con
    aceleración (D3D11 en Windows). Si no abre, o no entrega el primer cuadro, se usa el modo normal."""
    import cv2
    try:
        cap = cv2.VideoCapture(ruta, cv2.CAP_FFMPEG, [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY])
        if cap.isOpened() and cap.read()[0]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return cap
        cap.release()
    except (cv2.error, AttributeError):
        pass
    return cv2.VideoCapture(ruta)


# Cuánto analizar por segundo de video. En un i5 sin GPU, YOLO11n a 960 px cuesta unos 0,33 s por cámara y paso y OSNet unos
# 0,2 s por bloque de 16 recortes: con varias cámaras, analizar cada 0,2 s va entre 5 y 25 veces más lento que el video.
RENDIMIENTO = {
    "precise": {"step": 0.2, "size": None, "reid": 16, "nombre": "Preciso"},      # resolución del equipo, una muestra cada 0,2 s
    "balanced": {"step": 0.4, "size": 800, "reid": 16, "nombre": "Equilibrado"},
    "fast": {"step": 0.6, "size": 640, "reid": 16, "nombre": "Rápido"},
}


def rendimiento_elegido(pedido, n_camaras, tier="cpu"):
    """(clave, preset). `auto` elige por el número de cámaras en CPU; con GPU se conserva el modo preciso."""
    if pedido not in ("auto", *RENDIMIENTO):
        raise ValueError("performance inválido: auto, precise, balanced o fast.")
    if pedido == "auto":
        pedido = "precise" if tier != "cpu" or n_camaras <= 1 else "balanced" if n_camaras <= 4 else "fast"
    return pedido, RENDIMIENTO[pedido]


EXPANSION_REGION_FIABLE = 1.5     # la región de la imagen donde se confía en la homografía: casco de sus referencias x 1,5


def region_fiable(camera, factor=EXPANSION_REGION_FIABLE):
    """Región de la imagen (u, v en 0..1) donde la homografía de la cámara es fiable, o None si no se puede acotar.

    Una homografía solo vale donde hay referencias: ajustada con personas que caminaron lejos, fuera de esa franja coloca a la
    gente en cualquier parte del plano (y el límite de trabajo la descarta). Es el casco de las referencias ampliado un 50 %."""
    import cv2
    pares = camera.get("pairs") or []
    if len(pares) < 4:
        return None
    try:
        pares = reference_inliers(pares)
    except ValueError:
        pass
    uv = np.asarray([[q[0], q[1]] for q in pares], np.float32)
    casco = cv2.convexHull(uv).reshape(-1, 2)
    if len(casco) < 3 or cv2.contourArea(casco) < 1e-4:
        return None
    centro = casco.mean(axis=0)
    return np.clip(centro + (casco - centro) * factor, 0.0, 1.0).astype(np.float32)


def ubicar_en_plano(camera, u, v, estatura):
    """(posición en el plano o None, fiable). Fuera de la región fiable no se extrapola: la persona sigue en el video, sin punto en el plano."""
    import cv2
    if not camera.get("projects"):
        return None, False
    region = camera.get("fiable")
    if region is not None and cv2.pointPolygonTest(region, (float(u), float(v)), False) < 0:
        return None, False
    return ground_point(camera, u, v, estatura), True


def embed_lote(embedder, trabajos):
    """Vectores de varios cuadros en una sola pasada si el encoder lo permite. `trabajos` = [(frame, cajas, tapados)]."""
    if hasattr(embedder, "embed_varios"):
        return embedder.embed_varios(trabajos)
    return [embedder.embed(frame, cajas, tapados) for frame, cajas, tapados in trabajos]


# Al abrir el servidor directamente, conservar el entorno validado del proyecto.
project_env = ROOT.parent / ".venv"
project_python = project_env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if __name__ == "__main__" and project_python.is_file() and Path(sys.prefix).resolve() != project_env.resolve():
    os.execv(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])
sys.path.insert(0, str(ROOT / "src"))
import hardware
from live_core import (ESTATURA_MEDIA, Occupancy, calibration, estimate_height, ground_point, validate_config,
                       collapsed_pairs, blocking_calibration_issue, pairs_hash, related_cameras, reference_inliers)
from live_metrics import SessionMetrics
from spatial_scope import accepts, outline_scope
from following.detector import clip_box
import projects
import business_data
import business_catalog
import commercial
import sqlite3
import auth
from contextlib import closing
from resource_control import ResourceRegistry, managed_operation, http_operation, hold_source, hold_path
from shutdown_control import ManagedHTTPServer, stop_server, defer_close
from following.stream_source import is_youtube_url, low_latency_ffmpeg, resolve_stream_source

CONFIG_PATH = ROOT / "config" / "live.local.json"


def default_config():
    legacy = ROOT / "config" / "camaras.json"
    definitions = json.loads(legacy.read_text(encoding="utf-8")).get("camaras",[]) if legacy.exists() else []
    cameras = [{"id": c["id"], "name": f"Cámara {c['id']}", "location": "", "type":"tilted", "source": str((ROOT / c["video_path"]).resolve()), "x": 1+10*(i/max(1,len(definitions)-1)), "y": 1, "offset":0, "links":c.get("vecinos",[]), "pairs":[], "height":2} for i,c in enumerate(definitions)]
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
        self._resume_generation = 0
        self.worker = None
        # Cargar los pesos de YOLO cuesta segundos y no depende de la sesión que termina: se conservan mientras el
        # proceso siga vivo y solo se cargan otros si se piden otro modelo o resolución.
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
        business_data.reference_lock.acquire()
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
            try:
                if conexion:
                    conexion.close()
            finally:
                business_data.reference_lock.release()
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

    def update_alert_rules(self, data, *, expected_project=None):
        """Ajusta solo los umbrales de aglomeracion, sin tocar plano ni camaras.

        Existe aparte de /api/config para que el administrador pueda cambiar
        cuando le avisan sin tener acceso a la configuracion completa."""
        with self.lock:
            if self.managed and (not isinstance(expected_project, str) or
                                 expected_project != self.project_id):
                raise ValueError("El proyecto cambió o no se indicó. Recarga los umbrales antes de guardar.")
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
            # Keep the snapshot and write in the same project context. configure
            # uses this RLock too, so opening another project cannot interleave.
            self.configure(config, expected_project=expected_project)
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

    @managed_operation
    def validate_incident_history(self, incident_id, never_attended, project_id):
        with self.lock:
            if project_id != self.project_id:
                raise ValueError("El proyecto activo cambió. Recarga los incidentes antes de validar.")
            path = self.config_path
        with self.resource_use(business_data.path_for(path), write=True), closing(business_data.connect(path)) as db:
            business_data.validar_historial_incidente(db, incident_id, never_attended)
            result = business_data.listar_incidentes(db)
        self.record("Historial de incidente validado", f"{incident_id}: nunca atendido={never_attended}")
        return {"incidentes": result, "error": None}

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
        if projects.document_exists(self.config_path):
            try:
                stored = projects.read_document(self.config_path)
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
        self.report_config = None
        self.report_identity = None
        hold_path(self.data_root / "data" / "replays")
        if self.config_error:
            return
        summaries = []
        from replay import validate_manifest
        for path in (self.data_root / 'data/replays').glob('*/manifest.json'):
            try:
                meta = json.loads(path.read_text(encoding='utf-8'))
                validate_manifest(meta, path.parent.name)
                if meta.get('projectId') not in (self.project_id, None):
                    continue
                if meta.get('module') not in ('unified', 'tracking', 'demo'):
                    continue
                if meta.get('status') not in ('ended', 'stopped', 'error'):
                    continue
                # A zero-duration result may still have a valid summary. Report
                # eligibility separately requires usable samples and duration.
                if meta.get('cameraAnalytics') or meta.get('reportAnalytics'):
                    summaries.append(meta)
            except (OSError, ValueError) as exc:
                self.record("Histórico inválido", f"{path.parent.name}: {type(exc).__name__}; no se modificó el archivo.")
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
            mode='demo' if last.get('module') == 'demo' else 'yolo',
            t=last.get('end', 0), planId=pid,
            analytics=analytics,
            levelAnalytics=copy.deepcopy(last.get('levelAnalytics', {})),
            cameraAnalytics=camera_analytics,
            cameras=camera_status,
            identityDeleted=True,
            error=None,
        )
        # The scheduler requires the same saved evidence as the session report.
        # Keep its configuration separate from today's editable project and do
        # not make incomplete or unscoped legacy results reportable by inference.
        from replay import report_snapshot
        try:
            report_config, report_state, _ = report_snapshot(
                self.data_root, last['session'], self.project_id, strict=True)
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            return
        self.state.update({key: copy.deepcopy(report_state[key])
                           for key in ('totals', 'series', 'testRun')})
        self.report_config = report_config
        self.report_identity = (self.project_id, last['session'])

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
                from identity.spatial_graph import build_graph, persist_graph
                persist_graph(con, build_graph(self.config, businesses))
                observed = self.runtime_config or self.config
                analytics = self.state.get("cameraAnalytics", {})
                mode, sid, elapsed = self.state.get("mode"), self.state.get("session"), self.state.get("t", 0)
                if not sid:
                    histories = []
                    for path in (self.data_root / "data/replays").glob("*/manifest.json"):
                        try:
                            candidate = projects.read_document(path)
                            if candidate.get("projectId") == self.project_id and candidate.get("status") in ("ended", "stopped") and candidate.get("cameraAnalytics"):
                                histories.append(candidate)
                        except (OSError, ValueError):
                            continue
                    if histories:
                        last = max(histories, key=lambda m:m["created"])
                        sid, elapsed = last["session"], last["end"]
                        mode = "demo" if last["module"] == "demo" else "yolo"
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

    def configure(self, config, *, expected_project=None):
        validate_config(config)
        with self.lock:
            if expected_project and self.project_id and expected_project != self.project_id:
                raise ValueError("Esos cambios pertenecen a otro proyecto y no se guardaron. Vuelve a abrirlo para editarlo.")
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
            self.config_error = None
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
        if self.config_error:
            raise ValueError(f"Corrige la configuración del proyecto antes de iniciar: {self.config_error}")
        self.preview_stop()
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Ya hay una sesión activa; detenla primero.")
            mode = request.get("detector", "yolo")
            test_run = request.get('testRun') is True
            if mode not in ("yolo", "demo"):
                raise ValueError("Detector no admitido: usa yolo.")
            requested_size = int(request.get("inferenceSize") or 640)
            if request.get("performance", "auto") not in ("auto", *RENDIMIENTO):
                raise ValueError("performance inválido: auto, precise, balanced o fast.")
            if requested_size == 256:
                requested_size = 640      # valor antiguo de la interfaz
            if requested_size not in (320, 480, 640, 960):
                raise ValueError("El tamaño YOLO debe ser 320, 480, 640 o 960 píxeles.")
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
            source_modes = {isinstance(c.get('source'), int) or str(c.get('source', '')).isdigit() or '://' in str(c.get('source', '')) for c in selected}
            if mode == 'yolo' and len(source_modes) > 1:
                raise ValueError('Selecciona solo videos grabados o solo cámaras en vivo. No se pueden mezclar sus relojes en un monitoreo.')
            if mode == "yolo":
                if any(c.get("illustrative") for c in selected) and not test_run:
                    raise ValueError("Las ubicaciones ilustrativas no sirven para medir ocupación comercial.")
                if not test_run and any(not c.get("detectionZone") for c in selected):
                    raise ValueError("Delimita la zona útil de cada cámara para excluir espejos, vidrios y áreas externas.")
                for camera in selected:
                    calibration(camera.get("pairs", []))
            if request.get("requireUnified") and mode != "demo":
                if any(c.get('illustrative') for c in selected) and not test_run:
                    raise ValueError('Las ubicaciones ilustrativas permiten probar el mapa, pero no validar identidades entre cámaras. Usa referencias reales del mismo suelo y tiempos sincronizados.')
                if len(selected)>1 and not self.config["clocksVerified"]:
                    raise ValueError("Marca personas de apoyo en Homografía para calcular el desfase de tiempo entre cámaras antes del conteo multicámara.")
                # Las referencias del suelo son opcionales: solo se revisan en las cámaras que las tienen.
                import cv2
                import numpy as np
                for c in [c for c in selected if len(c.get("pairs",[]))>=4]:
                    problem = blocking_calibration_issue(c["pairs"], (self.config["width"], self.config["height"]))
                    if problem:
                        raise ValueError(f"Calibración de la cámara {c['id']}: {problem}")
                if any(cv2.contourArea(cv2.convexHull(np.asarray(c["pairs"],dtype=np.float32)[:,:2].copy()))<.005 for c in selected if len(c.get("pairs",[]))>=4):
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
            # Cámaras vecinas: las que el usuario relacionó marcando a la misma persona en ambas (o enlaces manuales).
            selected_ids = {camera['id'] for camera in selected}
            if self.runtime_config.get('cameraRoutes') is not None:
                self.runtime_config['cameraRoutes'] = [r for r in self.runtime_config['cameraRoutes']
                                                       if r['from'] in selected_ids and r['to'] in selected_ids]
            vecinas = {cid: set(v) for cid, v in related_cameras(self.runtime_config).items()}
            bloqueadas_geometria = []
            if mode == "yolo":
                # Una similitud OSNet no basta si las homografías de dos cámaras
                # proyectan a lugares incompatibles. En ese caso es más seguro
                # conservar IDs locales que publicar una fusión falsa.
                for base in sorted(vecinas):
                    for destino in sorted(list(vecinas[base])):
                        if base >= destino or destino not in vecinas:
                            continue
                        pares = [p for p in self.runtime_config.get("personPairs", [])
                                 if {p.get("a", {}).get("camera"), p.get("b", {}).get("camera")} == {base, destino}]
                        if len(pares) < 4:
                            continue
                        try:
                            espacial = self.person_pairs_check(base, destino, pares).get("espacial")
                        except (ValueError, KeyError, TypeError):
                            espacial = None
                        if espacial and not espacial.get("concuerdan", False):
                            vecinas[base].discard(destino)
                            vecinas[destino].discard(base)
                            bloqueadas_geometria.append({"base": base, "destino": destino,
                                                         "distancia": round(float(espacial.get("mediana", 0)), 2),
                                                         "limite": round(float(espacial.get("max", 0)), 2)})
            for camera in self.runtime_config['cameras']:
                camera['links'] = [cid for cid in vecinas.get(camera['id'], []) if cid in selected_ids]
            self.runtime_config["identityBlockedPairs"] = bloqueadas_geometria
            for item in bloqueadas_geometria:
                self.record("Identidad", f"No se fusionan {item['base']} y {item['destino']}: homografías incompatibles ({item['distancia']} > {item['limite']} unidades). Se mantienen IDs locales hasta recalibrar.")
            if "identityGroupCrops" in request:
                if not isinstance(request["identityGroupCrops"], bool):
                    raise ValueError("identityGroupCrops inválido.")
                self.runtime_config["identityGroupCrops"] = request["identityGroupCrops"]
            self.runtime_config.setdefault("identityGroupCrops", True)
            self.state["planId"] = selected[0].get("planId","custom")
            sin_referencias = [c["id"] for c in selected if len(c.get("pairs", [])) < 4]
            if sin_referencias and not test_run:
                self.record("Calibración", f"Sin puntos del suelo en {', '.join(sin_referencias)}: esas cámaras cuentan por zonas de imagen pero no se ubican en el plano.")
            if len(selected) > 1 and not any(camera['links'] for camera in self.runtime_config['cameras']):
                self.record("Identidad", "Ninguna cámara está relacionada con otra: cada una conserva sus propios IDs. Marca a la misma persona en dos cámaras para relacionarlas.")
            if not request.get("requireUnified"):
                self.runtime_config["clocksVerified"]=False
            if camera_id:
                pid=selected[0].get("planId","custom")
                if pid!=self.config.get("planId","custom"):
                    self.runtime_config.update(copy.deepcopy(self.config.get("plans",{}).get(pid,{})))
            runtime_request = {**request, "detector": mode, "weights": None, "inferenceSize": requested_size}
            self.worker = self.resources.start_thread(self.run, args=(self.runtime_config, runtime_request), name="tracking")
            self.record("Sesión iniciada",f"{mode} · {camera_id or 'todas las cámaras'}")

    def pause(self, paused):
        with self.lock:
            if not self.worker or not self.worker.is_alive() or self.state["status"] not in ("running","paused"):
                raise ValueError("No hay una sesión en ejecución para pausar o reanudar.")
            if paused:
                self.pause_event.set()
            else:
                if self.pause_event.is_set():
                    self._resume_generation += 1
                self.pause_event.clear()
            self.state["status"] = "paused" if paused else "running"
            self.record("Sesión pausada" if paused else "Sesión reanudada","Control del operador")

    def compute_insights(self, sid):
        """Insights espaciales de una grabación: eventos, KDE, rutas, captación. Un fallo se avisa y no detiene nada.

        Usa las zonas y los negocios actuales del proyecto (no los de la sesión): si cambian, se pueden recalcular."""
        try:
            import insights
            from insights import ventas as insights_ventas
            with self.lock:
                plan = copy.deepcopy(self.config)
            con = business_data.connect(self.config_path)
            try:
                negocios = business_catalog.sync(con, plan, ROOT / "dashboard/public")
                resultado, eventos, meta = insights.analizar_replay(self.data_root, sid, plan, negocios)
                dataset = "demo" if meta.get("module") == "demo" or meta.get("config", {}).get("testRun") else "real"
                commercial.setup(con)
                insights_ventas.guardar(con, sid, dataset, resultado, eventos)
            finally:
                con.close()
            try:
                from storage.archive_queue import ArchiveQueue
                ArchiveQueue(self.data_root / 'data' / 'storage-outbox.sqlite').enqueue(
                    self.data_root / 'data' / 'replays' / sid, insights=resultado)
            except Exception as exc:
                self.record("PostGIS", f"Archivo pendiente de reintento ({type(exc).__name__}). Los resultados locales se conservan.")
            return resultado
        except Exception as exc:  # los insights son derivados: nunca pueden romper el cierre de una sesión
            self.record("Insights", f"No se pudieron calcular los insights de la sesión: {type(exc).__name__}: {exc}")
            return None

    def insights_data(self, sid):
        """Insights guardados de una sesión del proyecto abierto, con su relación con las ventas por negocio."""
        from replay import directory, manifest
        meta = manifest(self.data_root, sid)
        if self.project_id and meta.get("projectId") not in (self.project_id, None):
            raise ValueError("La sesión no pertenece al proyecto abierto.")
        ruta = directory(self.data_root, sid) / "insights.json"
        if not ruta.is_file():
            raise FileNotFoundError("Esta sesión todavía no tiene insights. Calcúlalos desde el panel.")
        resultado = json.loads(ruta.read_text(encoding="utf-8"))
        dataset = "demo" if meta.get("module") == "demo" or meta.get("config", {}).get("testRun") else "real"
        con = business_data.connect(self.config_path)
        try:
            commercial.setup(con)
            from insights import ventas as insights_ventas
            resultado["ventas"] = {l["negocio_id"]: insights_ventas.relacion_con_ventas(con, l["negocio_id"], dataset)
                                   for l in resultado["locales"] if l.get("negocio_id")}
        finally:
            con.close()
        resultado["dataset"] = dataset
        return resultado

    def _camera_file(self, cid):
        """Cámara del proyecto y la ruta de su video grabado (las fuentes en vivo no se pueden recorrer en el tiempo)."""
        camera = next((c for c in self.config["cameras"] if c["id"] == cid), None)
        if camera is None:
            raise ValueError("Cámara desconocida.")
        source = camera.get("source")
        if not isinstance(source, str) or not source or "://" in source:
            raise ValueError("Marcar personas necesita videos grabados: una fuente en vivo no se puede recorrer en el tiempo.")
        return camera, str((ROOT / source).resolve())

    def camera_frame_info(self, cid):
        """Duración, tamaño y desfase del video de una cámara, para sincronizar dos videos al marcar personas."""
        import cv2
        camera, path = self._camera_file(cid)
        cap = cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                raise ValueError("No se pudo abrir el video de la cámara.")
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            return {"duration": round(max(0., frames / fps - source_time_offset(camera)), 2), "fps": fps, "offset": source_time_offset(camera),
                    "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "pairsHash": pairs_hash(camera.get("pairs", []))}
        finally:
            cap.release()

    def camera_frame_at(self, cid, seconds):
        """JPEG de la cámara en el instante común `seconds` (igual que el monitoreo: segundos + desfase de la cámara)."""
        import cv2
        camera, path = self._camera_file(cid)
        cap = cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                raise ValueError("No se pudo abrir el video de la cámara.")
            try:
                cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
            except cv2.error:
                pass
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            instante = float(seconds)
            duracion = total / fps - source_time_offset(camera) if total > 0 else None
            if instante < 0 or (duracion is not None and instante > max(0., duracion) + .25):
                raise ValueError("Ese instante estÃ¡ fuera del video.")
            objetivo = max(0, int(round((instante + source_time_offset(camera)) * fps)))
            # Algunos contenedores informan un frame de más o fallan al buscar
            # exactamente el último índice. Acotamos y probamos unos frames
            # vecinos para no dejar la vista de parejas en negro.
            if total > 0:
                objetivo = min(objetivo, total - 1)
            ok, frame = False, None
            for candidato in (objetivo, max(0, objetivo - 1), max(0, objetivo - 2)):
                cap.set(cv2.CAP_PROP_POS_FRAMES, candidato)
                ok, frame = cap.read()
                if ok and frame is not None and getattr(frame, "size", 0):
                    break
            if not ok:
                raise ValueError("Ese instante está fuera del video.")
            if frame.shape[1] > 1280:
                frame = cv2.resize(frame, (1280, round(frame.shape[0] * 1280 / frame.shape[1])))
            return self._preview_jpeg(frame, width=1280, quality=82)
        finally:
            cap.release()

    def person_pairs_check(self, base, target, pairs):
        """La misma persona marcada en dos cámaras: desfase de tiempo entre sus videos y concordancia de sus homografías.

        Cada pareja son los pies de una persona en `base` y en `target`. Con 4 o más parejas se estima cuánto hay que desplazar
        la lectura de `target` para que la misma persona caiga en el mismo instante (mediana, robusta a una pareja mal marcada).
        Si las dos cámaras tienen puntos del suelo, también se mide a qué distancia quedan en el plano las parejas simultáneas:
        es un diagnóstico de la calibración, no una corrección. Nada se guarda aquí."""
        with self.lock:
            config = copy.deepcopy(self.config)
        cams = {c["id"]: c for c in config["cameras"]}
        if base == target or base not in cams or target not in cams:
            raise ValueError("Elige dos cámaras distintas del proyecto.")
        person_height = float(config.get("personHeight") or ESTATURA_MEDIA)
        geometria = {cid: {**cams[cid], "h": calibration(cams[cid].get("pairs", []))} for cid in (base, target)}
        con_geometria = all(geometria[cid]["h"] is not None for cid in (base, target))
        usable = []
        for item in pairs or []:
            try:
                lados = {item["a"]["camera"]: item["a"]["point"], item["b"]["camera"]: item["b"]["point"]}
            except (KeyError, TypeError):
                continue
            if set(lados) != {base, target}:
                continue
            pa, pb = posiciones_de_pareja(item, cams[base], cams[target])
            plano = {cid: ground_point(geometria[cid], lados[cid][0], lados[cid][1], person_height) for cid in (base, target)} if con_geometria else None
            usable.append((item, pa, pb, plano))
        deltas = np.asarray([u[2] - u[1] for u in usable], dtype=float)
        ajuste = ajuste_de_relojes(cams[base], cams[target], deltas)
        tolerancia = max(0.12, ajuste["dispersion"] * 2)
        unidad = "m" if config.get("unit") == "meters" else "u"
        filas, distancias = [], []
        for item, pa, pb, plano in usable:
            fuera_de_tiempo = len(usable) >= 4 and abs((pb - pa) - ajuste["offset"]) > tolerancia
            distancia = None
            if plano and None not in plano.values() and not fuera_de_tiempo:
                distancia = float(np.linalg.norm(np.asarray(plano[base]) - np.asarray(plano[target])))
                distancias.append(distancia)
            filas.append({"id": item["id"], "ta": round(pa - source_time_offset(cams[base]), 3), "tb": round(pb - source_time_offset(cams[target]), 3),
                          "dt": round((pb - pa) - ajuste["offset"], 3), "fueraDeTiempo": bool(fuera_de_tiempo),
                          "distancia": None if distancia is None else round(distancia, 3)})
        espacial = None
        if distancias:
            mediana = float(np.median(distancias))
            espacial = {"mediana": round(mediana, 3), "max": round(max(distancias), 3), "n": len(distancias),
                        "concuerdan": mediana <= float(config.get("matchDistance", 1.0))}
        avisos = problemas_de_parejas(filas, ajuste, espacial, unidad, con_geometria)
        return {"n": len(usable), "suficiente": len(usable) >= 4, "pares": filas, "avisos": avisos, "espacial": espacial,
                "temporal": {"offset": round(ajuste["offset"], 3), "muestras": len(usable), "dispersion": round(ajuste["dispersion"], 3) if len(usable) else None,
                             "necesita": ajuste["necesita"], "verificada": ajuste["fiable"], "syncBase": ajuste["sync_base"], "syncDestino": ajuste["sync_destino"]}}

    def purge_identities(self):
        """Borrado inmediato de lo que el sistema recuerda de las personas de este proyecto.

        Vacía las observaciones por ID temporal y los vectores de apariencia, en RAM y en disco, y reinicia la
        numeración. No toca grabaciones ni reportes: esos llevan IDs de sesión y se borran desde Videos y resultados."""
        borradas = 0
        vivo = getattr(self, "appearance_memory_live", None)
        if vivo is not None:
            borradas += vivo.purgar_todo()
        carpeta = self.data_root / "data" / "identidad"
        nombre = self.project_id or "local"
        for ruta in (carpeta / f"{nombre}.sqlite", carpeta / f"{nombre}_apariencia.sqlite"):
            if not ruta.is_file():
                continue
            con = sqlite3.connect(str(ruta), timeout=5)
            try:
                tablas = {fila[0] for fila in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for tabla in ("identity_observations", "appearance_views", "appearance_people"):
                    if tabla in tablas:
                        borradas += max(con.execute(f"DELETE FROM {tabla}").rowcount, 0)
                con.commit()
                con.execute("VACUUM")
            finally:
                con.close()
        self.record("Identidad", f"Memoria de identidad borrada ({borradas} registros).")
        return borradas

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()
        with self.lock:
            if self.worker and self.worker.is_alive():
                self.state["status"] = "stopping"

    def load_detector(self, mode, request):
        """YOLO para personas, reutilizado entre sesiones (cargar los pesos es lo que tarda)."""
        if mode != "yolo":
            raise ValueError("Detector no admitido: usa yolo.")
        profile = request.get("profile") or {}
        weights = profile.get("weights") or str(ROOT / "models" / "yolo11n.pt")
        key = ("yolo", int(request.get("inferenceSize") or 640), weights, profile.get("device"), bool(profile.get("half")))
        with self.detector_lock:
            if key not in self.detector_caches:
                from following.detector import YoloPersonDetector
                self.detector_caches[key] = YoloPersonDetector(weights, imgsz=key[1], device=profile.get("device"), half=key[4])
            return self.detector_caches[key]

    def warm_detector_async(self):
        """Carga YOLO en segundo plano para que el primer «Iniciar» no espere los pesos."""
        if self.closing or any(k[:2] == ("yolo", 640) for k in self.detector_caches) or (self.detector_warmup and self.detector_warmup.is_alive()):
            return

        def warm():
            try:
                self.load_detector("yolo", {"inferenceSize": 640})
            except Exception as exc:
                self.record("Preparación del detector", f"No se pudo anticipar la carga de YOLO: {exc}")
        self.detector_warmup = self.resources.start_thread(warm, name="yolo-warmup")

    @managed_operation
    def run(self, config, request):
        for camera in config["cameras"]:
            hold_source(camera.get("source"), ROOT)
        captures = {}
        replay = None
        combined = None
        level_occupancy = {}
        appearance_memory = None
        mode = request.get("detector", "yolo")
        try:
            if mode == "demo":
                self.demo(config)
                return
            import cv2
            import numpy as np
            from types import SimpleNamespace
            from tracking import BoTSortPuntos
            from following.appearance import torso_histogram
            from following.reid import OSNetEmbedder, EmbeddingScheduler, occluded_ids
            from following.clutter import SizeFilter, StaticClutter
            from following.flow import ZoneFlow, FlowField
            person_height = float(config.get("personHeight") or ESTATURA_MEDIA)
            primary_mode = "yolo"
            preset_clave, preset = "precise", RENDIMIENTO["precise"]      # lo fija el bloque de YOLO más abajo
            # Con cámaras elevadas (>= 3 m) las personas miden pocos píxeles y a 640 px
            # YOLO casi no las detecta: se sube la resolución y se baja el umbral.
            elevated = any(float(c.get("height") or 0) >= 3 for c in config["cameras"] if c.get("active", True))
            profile = hardware.choose(config, elevated)
            if True:
                # El perfil del equipo fija modelo y resolución mínima.
                activas = sum(1 for c in config["cameras"] if c.get("active", True) and (not request.get("camera") or c["id"] == request["camera"]))
                preset_clave, preset = rendimiento_elegido(request.get("performance", "auto"), activas, profile["tier"])
                tamano = preset["size"] or profile["imgsz"]
                if elevated and preset["size"]:
                    tamano = max(tamano, 960)       # cámaras elevadas: las personas miden pocos píxeles
                request = {**request, "inferenceSize": tamano, "profile": profile}
                self.record("Rendimiento", f"{preset['nombre']}: una muestra cada {preset['step']:g} s, detector a {tamano} px, hasta "
                                           f"{int(config.get('reidMaxPerTick') or preset['reid'])} recortes de apariencia por muestra, {activas} cámara(s).")
                if profile["missingWeights"] or profile["hint"]:
                    self.record("Hardware", profile["hint"] or f"Falta {profile['missingWeights']}: se usa {Path(profile['weights']).name}. Descárgalo con tools/preparar_hardware.py.")
            detector = self.load_detector(primary_mode, request)
            detector.confidence = .15 if elevated else .25
            cams =[c for c in config["cameras"] if c.get("active",True) and (not request.get("camera") or c["id"] == request["camera"])]
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
                         tracker=BoTSortPuntos(umbral_alto=.4,max_frames_perdido=45),
                         h=calibration(c.get("pairs", [])))
                c["projects"] = c["h"] is not None
                c["fiable"] = region_fiable(c) if c["projects"] else None
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
            occupancy, metrics = Occupancy(config), SessionMetrics()
            # Re-ID: OSNet (models/osnet.onnx). Sin él no hay identidad entre cámaras fiable y no se inicia.
            model_name = config.get('reidModel', 'osnet.onnx')
            embedder = OSNetEmbedder(ROOT / 'models' / model_name, providers=profile["osnetProviders"], threads=profile.get("osnetThreads"))
            if not embedder.available:
                raise ValueError(f"No se pudo cargar el modelo {model_name}. Instálalo o selecciona OSNet ligero. {embedder.error}")
            # Motor de identidad: tracklets por cámara + OSNet + compuerta de tiempo y plano; al cerrar se reagrupa la grabación.
            from identity import crear_motor_identidad
            from identity.engine import crear_memoria
            if config.get("appearanceMemory", True):
                # Solo vectores de apariencia, con retención corta; si el disco falla la memoria queda en RAM.
                huella = getattr(embedder, 'fingerprint', None) or embedder.name
                appearance_memory = crear_memoria(config, self.data_root / "data" / "identidad" / f"{self.project_id or 'local'}_{huella}_apariencia.sqlite",
                                                  f"{embedder.name}:{huella}", embedder.dimension)
            self.appearance_memory_live = appearance_memory
            identities = crear_motor_identidad(config, memoria=appearance_memory, encoder_nombre=embedder.name)
            reid_interval = int(config.get("reidInterval") or profile["osnetInterval"])
            size_filters = {c["id"]: SizeFilter() for c in active}
            clutter = {c["id"]: StaticClutter() for c in active}
            # El intervalo del equipo está pensado en cuadros de un análisis cuadro a cuadro; con pasos de 0,2 s o más todo track
            # estaría siempre pendiente. Se pide como mínimo `reidIntervalSeconds` entre dos vectores de un mismo track (el motor
            # reid_v2 pide además los que le faltan, con `necesita_vista`).
            intervalo_s = float(config.get("reidIntervalSeconds") or 1.0)
            reid_schedulers = {c["id"]: EmbeddingScheduler(reid_interval if config.get("reidInterval") else max(reid_interval, round(c["fps"] * intervalo_s))) for c in active}
            collapse_steps = {}
            # Guardamos observaciones y métricas también para fuentes en vivo.
            # El video remoto no se archiva y la URL no se escribe en el
            # manifiesto para evitar conservar credenciales o enlaces efímeros.
            from replay import ReplayWriter, camera_snapshot
            replay = ReplayWriter(
                self.data_root,
                self.state["session"],
                "unified" if request.get("combined") else "tracking",
                camera_snapshot(cams),
                {k:v for k,v in config.items() if k != "cameras"},
                self.project_id,
            )
            from following.combined import CombinedAnalysis
            combined = CombinedAnalysis(cams, ROOT) if request.get('combined') else None
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
                # Sin límite de trabajo dibujado, el contorno cerrado de las líneas del plano hace de límite: nadie queda fuera de él.
                camera['scope'].update(outline_scope(plan))
            from bag_signal import BagSignal
            bag_signal = BagSignal(ROOT,cams)
            flow = ZoneFlow(config)
            trails = {}
            wall_start = time.monotonic()
            timeline = 0.
            paso_muestreo = preset["step"]
            max_embed = max(1, int(config.get("reidMaxPerTick") or preset["reid"]))
            lectores = ThreadPoolExecutor(max_workers=max(1, len(cams)))      # decodificar cada cámara en su propio hilo
            tiempos, avisados_zona = {}, set()
            recording_deadline = None
            recording_resume_generation = self._resume_generation
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
                            cap = abrir_archivo(source) if isinstance(source, str) else cv2.VideoCapture(source)
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
                            tracker=BoTSortPuntos(umbral_alto=.4, max_frames_perdido=45),
                            h=calibration(camera.get("pairs", [])),
                        )
                        camera["projects"] = camera["h"] is not None
                        camera["fiable"] = region_fiable(camera) if camera["projects"] else None
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
                    recording_deadline = None
                    self.stop_event.wait(.1)
                    continue
                cycle_started = time.perf_counter()
                if not active[0]["stream"] and (recording_deadline is None or
                        recording_resume_generation != self._resume_generation):
                    recording_deadline = cycle_started
                    recording_resume_generation = self._resume_generation
                start = time.monotonic()
                # En vivo prima la latencia. En archivos prima conservar las
                # muestras: el coste de inferencia no debe saltarse cruces.
                t = start - wall_start if active[0]["stream"] else timeline
                observations, raw_frames, pending, fuera_de_alcance = [], {}, [], {}
                def leer(c):
                    cap = c["cap"]
                    if not c["stream"]:
                        target = max(0, int((t + source_time_offset(c)) * c["fps"]))
                        # Saltar el desfase directamente al abrir el archivo evita
                        # procesar desde el fotograma 0 y garantiza que la primera
                        # muestra ya corresponda al tiempo común configurado.
                        if c["frameIndex"] < 0 and target > 0:
                            try:
                                if cap.set(cv2.CAP_PROP_POS_FRAMES, target):
                                    c["frameIndex"] = target - 1
                            except Exception:
                                # Algunos códecs no soportan seek; el bucle de
                                # grabación de abajo conserva el comportamiento seguro.
                                pass
                        if target < c["frameIndex"]:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                            c["frameIndex"] = target - 1
                        while c["frameIndex"] < target - 1:
                            if not cap.grab():
                                break
                            c["frameIndex"] += 1
                    ok, frame = cap.read()
                    c["frameIndex"] += 1
                    return ok, frame
                lectura_inicio = time.monotonic()
                lecturas = list(lectores.map(leer, list(active)))
                tiempos["decode"] = (time.monotonic() - lectura_inicio) * 1000
                for c, (ok, frame) in zip(list(active), lecturas):
                    if self.stop_event.is_set():
                        break
                    cap = c["cap"]
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
                tiempos["detector"] = detector_ms
                seguimiento_inicio = time.monotonic()
                etapas = []
                observed_ids = set()
                for (c, frame, height, width), detections in zip(pending, detection_batches):
                    if detections is None:
                        continue
                    observed_ids.add(c["id"])
                    # La salida del detector es la frontera de confianza para
                    # todo el pipeline. Normalizamos las cajas contra el
                    # frame real antes de calcular pies, homografías, Re-ID o
                    # dibujar overlays; algunos adaptadores/modelos pueden
                    # devolver coordenadas ligeramente fuera de la imagen.
                    limpias = []
                    for detection in detections:
                        box = clip_box(getattr(detection, "box", None), width, height)
                        if box is None:
                            # Adaptadores ligeros de laboratorio pueden
                            # entregar solo el punto de los pies. Se conserva
                            # si está dentro del frame, pero no se inventa una
                            # caja para Re-ID ni para el overlay.
                            try:
                                point = (float(detection.x), float(detection.y))
                            except (AttributeError, TypeError, ValueError):
                                continue
                            if not np.isfinite(point).all() or not (0 <= point[0] < width and 0 <= point[1] < height):
                                continue
                            detection.box = None
                        else:
                            detection.box = box
                            detection.x = (box[0] + box[2]) / 2
                            detection.y = box[3]
                        limpias.append(detection)
                    detections = limpias
                    keep = []
                    for i,d in enumerate(detections):
                        ground, fiable = ubicar_en_plano(c, d.x/width, d.y/height, person_height)
                        if accepts(c,c["scope"],d.x/width,d.y/height,ground,image_only=not fiable):
                            keep.append(i)
                    excluded = len(detections)-len(keep)
                    # Lo que descartan la zona útil o el límite de trabajo se dibuja en gris para que se vea que YOLO sí las detectó.
                    quedan = set(keep)
                    fuera_de_alcance[c["id"]] = [d.box for i, d in enumerate(detections) if i not in quedan and getattr(d, "box", None) is not None]
                    detections = [detections[i] for i in keep]
                    use_filters = config.get("clutterFilter", True)
                    if use_filters:
                        # Gorros, pósters y otros objetos pequeños que YOLO confunde con personas.
                        detections, small = size_filters[c["id"]].apply(detections, (width, height))
                        excluded += small
                    for detection in detections:
                        detection.appearance = torso_histogram(frame, getattr(detection, "box", None))
                    tracks, _, _ = c["tracker"].actualizar(detections, t)
                    for track in tracks:
                        track.ultima_caja = clip_box(getattr(track, "ultima_caja", None), width, height)
                    still = clutter[c["id"]].update(tracks, t, (width, height)) if use_filters else set()
                    if still:
                        tracks = [tr for tr in tracks if tr.id not in still]
                        excluded += len(still)
                    scheduler = reid_schedulers[c["id"]]
                    due, cubiertos = [], {}
                    if embedder.available:
                        # OSNet cada N frames, al crear el track o si su confianza es baja, y en cada muestra mientras
                        # el track no tiene ID público o le faltan vistas. Con min_visible, en grupos el recorte se
                        # rellena donde tapa otra persona (no se descarta).
                        min_visible = identities.min_visible
                        cubiertos = {}
                        if min_visible is not None:
                            from identity.quality import tapadores
                            con_caja = [tr for tr in tracks if tr.ultima_caja is not None]
                            cubiertos = dict(zip((tr.id for tr in con_caja), tapadores([tr.ultima_caja for tr in con_caja])))
                            blocked = {i for i, (visible, _) in cubiertos.items() if visible < min_visible}
                        else:
                            blocked = occluded_ids(tracks)
                        due = [tr for tr in tracks if tr.ultima_caja is not None and tr.id not in blocked
                               and (scheduler.due(tr.id, c["frameIndex"], tr.score) or identities.necesita_vista(c["id"], tr.id, t))]
                    etapas.append((c, frame, height, width, detections, tracks, excluded, scheduler, due, cubiertos))
                # OSNet: un solo paso para todas las cámaras (con lote fijo cada llamada cobra un bloque entero) y como mucho
                # `max_embed` recortes por muestra. Primero los tracks sin vector y luego los de vector más viejo; los que no
                # entran siguen pendientes para la muestra siguiente.
                tiempos["seguimiento"] = (time.monotonic() - seguimiento_inicio) * 1000
                embed_inicio = time.monotonic()
                candidatos = []
                for k, (c, frame, height, width, detections, tracks, excluded, scheduler, due, cubiertos) in enumerate(etapas):
                    for tr in due:
                        previo = scheduler.state.get(tr.id)
                        sin_vector = previo is None or previo["vec"] is None
                        candidatos.append((not sin_vector, -(c["frameIndex"] - previo["frame"]) if previo else 0, k, tr))
                candidatos.sort(key=lambda x: x[:3])
                elegidos = [set() for _ in etapas]
                for _, _, k, tr in candidatos[:max_embed]:
                    elegidos[k].add(tr.id)
                trabajos = []
                for k, (c, frame, height, width, detections, tracks, excluded, scheduler, due, cubiertos) in enumerate(etapas):
                    due[:] = [tr for tr in due if tr.id in elegidos[k]]
                    trabajos.append((frame, [tr.ultima_caja for tr in due], [cubiertos[tr.id][1] for tr in due] if cubiertos else None))
                vectores_por_camara = embed_lote(embedder, trabajos) if embedder.available and any(t[1] for t in trabajos) else [[] for _ in trabajos]
                tiempos["osnet"] = (time.monotonic() - embed_inicio) * 1000
                observaciones_inicio = time.monotonic()
                for (c, frame, height, width, detections, tracks, excluded, scheduler, due, cubiertos), vectors in zip(etapas, vectores_por_camara):
                    fresh, parciales = set(), set()
                    if embedder.available:
                        parciales = {tr.id for tr in due if cubiertos and cubiertos[tr.id][1]}      # vector calculado con zonas rellenas
                        for tr, vec in zip(due, vectors):
                            scheduler.store(tr.id, c["frameIndex"], vec)
                            if vec is not None:
                                fresh.add(tr.id)
                        scheduler.prune({tr.id for tr in c["tracker"].tracks_activos + c["tracker"].tracks_perdidos})
                    fuera_de_zona = 0
                    for tr in tracks:
                        px, py = tr.posicion
                        # Un Kalman puede rebasar un borde durante una
                        # actualización brusca. No proyectamos ese estado
                        # porque una homografía fuera del frame es una
                        # extrapolación sin significado físico.
                        if not (0 <= px < width and 0 <= py < height):
                            fuera_de_zona += 1
                            continue
                        original_box = getattr(tr, "ultima_caja", None)
                        box = clip_box(original_box, width, height)
                        if original_box is not None and box is None:
                            continue
                        point, fiable = ubicar_en_plano(c, px / width, py / height, person_height)
                        fuera_de_zona += bool(c["projects"] and not fiable)
                        if not accepts(c,c["scope"],px/width,py/height,point,image_only=not fiable):
                            continue
                        if point and not (0 <= point[0] <= c["scope"]["width"] and 0 <= point[1] <= c["scope"]["height"]):
                            point = None
                        color = getattr(tr, "apariencia", None)
                        if color is None:
                            color = torso_histogram(frame, box)
                        observations.append({"camera": c["id"], "local": tr.id, "point": point, "pixel": [float(px), float(py)], "box": box, "color": color, "embedding": scheduler.get(tr.id) if embedder.available else None, "embeddingFresh": tr.id in fresh, "partial": tr.id in fresh and tr.id in parciales, "score": tr.score,
                                             "height": estimate_height(c, box, width, height)})
                    camera_count = sum(o["camera"] == c["id"] for o in observations)
                    statuses[c["id"]] = {"id": c["id"], "status": "live", "width": width, "height": height, "fps":c["fps"], "duration":c.get("duration"), "calibrated": c["projects"], "outsideCalibration": fuera_de_zona, "count": camera_count, "excluded":excluded, "timestamp": t, "sourceTime":c["frameIndex"]/c["fps"] if not c["stream"] else None, "detector": primary_mode, "tracker": "botsort", "hardware": {"tier": profile["tier"], "device": profile["device"], "model": Path(profile["weights"]).name, "imgsz": request.get("inferenceSize")}, "reid": embedder.name if embedder.available else "color", "inferenceMs": round(detector_ms / max(1, len(pending)), 2)}
                    if fuera_de_zona and c["id"] not in avisados_zona:
                        avisados_zona.add(c["id"])
                        self.record("Calibración", f"Cámara {c['id']}: hay personas fuera de la región donde su homografía es fiable (donde hay referencias). "
                                                   "Se muestran en el video pero no en el plano. Marca personas de apoyo también en esa zona de la imagen.")
                    with self.lock:
                        self.source_checks[c["id"]] = {"source":c["source"],"valid":True,"width":width,"height":height,"fps":c["fps"],"checkedAt":time.time()}
                tiempos["observaciones"] = (time.monotonic() - observaciones_inicio) * 1000
                sizes = {cid: (item["width"], item["height"]) for cid, item in statuses.items() if "width" in item}
                motor_inicio = time.monotonic()
                people = identities.update(observations, t, tamanos=sizes)
                tiempos["identidad"] = (time.monotonic() - motor_inicio) * 1000
                # Con reid_v2 una persona recién vista lleva ID provisional: se dibuja y se muestra, pero no entra
                # en conteos, ocupación ni memoria hasta confirmarse (evita contarla dos veces al cambiar de ID).
                counted = [p for p in people if p.get("confirmed", True)]
                # Personas distintas proyectadas al mismo punto: la calibración no sirve para asociar.
                for c in active:
                    group = [p for p in people if p["camera"] == c["id"]]
                    if len(group) >= 3 and collapsed_pairs(group) >= 1:
                        collapse_steps[c["id"]] = collapse_steps.get(c["id"], 0) + 1
                        if collapse_steps[c["id"]] == 8:
                            self.record("Calibración", f"Cámara {c['id']}: personas distintas se proyectan al mismo punto del plano. Recalibra con referencias más separadas que cubran el suelo donde caminan.")
                    else:
                        collapse_steps[c["id"]] = 0
                if combined:
                    for c in active:
                        if c["id"] not in observed_ids:
                            continue
                        group=[p for p in counted if p['camera']==c['id']]
                        camera_analytics[c['id']] = combined.observe(c, raw_frames[c['id']], group, t)
                        camera_analytics[c['id']]['map']=camera_maps[c['id']].update(group,t, observation_valid=bool(c.get("projects")))
                for c in cams:
                    if c["id"] not in observed_ids:
                        camera_maps[c["id"]].update([], t, observation_valid=False)
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
                dibujo_inicio = time.monotonic()
                encoded = {}
                for cid, frame in raw_frames.items():
                    # Operator-only view on a loopback-only server: the operator already
                    # has the raw source video, so the feed is served at full detail with
                    # tracking overlays drawn on top, not degraded for anonymity.
                    overlay_scale = max(1., frame.shape[1]/1440)
                    line_width = max(2, round(2*overlay_scale))
                    for x1, y1, x2, y2 in fuera_de_alcance.get(cid, []):
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (150, 150, 150), 1)
                    if fuera_de_alcance.get(cid):
                        cv2.putText(frame, f"{len(fuera_de_alcance[cid])} fuera de la zona (gris)", (12, frame.shape[0]-14), cv2.FONT_HERSHEY_SIMPLEX, .6*overlay_scale, (190, 190, 190), max(1, line_width-1))
                    for p in [p for p in people if p["camera"] == cid]:
                        px = max(0, min(frame.shape[1] - 1, int(round(p["pixel"][0]))))
                        py = max(0, min(frame.shape[0] - 1, int(round(p["pixel"][1]))))
                        trail = trails.setdefault((cid, p["id"]), deque(maxlen=25))
                        trail.append((px, py))
                        if len(trail) > 1:
                            cv2.polylines(frame, [np.asarray(trail, dtype=np.int32)], False, (70, 220, 120), line_width)
                        if p["box"]:
                            box = clip_box(p["box"], frame.shape[1], frame.shape[0])
                            if box is not None:
                                x1, y1, x2, y2 = map(int, box)
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
                        crossing = next((x for x in camera_analytics.get(cid,{}).get('crossings',[]) if x['id']==line['id']), {})
                        recent = [e for e in crossing.get('events',[]) if 0 <= t-e['t'] <= .8]
                        directions = {e['direction'] for e in recent}
                        color = (220,100,220) if len(directions)>1 else (120,220,50) if 'entries' in directions else (255,165,50) if directions else (90,240,180)
                        cv2.line(frame,a,b,color,line_width*(2 if directions else 1))
                        if directions:
                            crossing_label = 'Entrada + salida' if len(directions)>1 else f"Entrada +{len(recent)}" if 'entries' in directions else f"Salida +{len(recent)}"
                            cv2.putText(frame, crossing_label, a, cv2.FONT_HERSHEY_SIMPLEX, .6*overlay_scale, color, line_width)
                        dx,dy=b[0]-a[0],b[1]-a[1];length=max(1.,(dx*dx+dy*dy)**.5)
                        middle=((a[0]+b[0])//2,(a[1]+b[1])//2);side=line.get('entrySide',1)
                        tip=(round(middle[0]-dy/length*35*side),round(middle[1]+dx/length*35*side))
                        cv2.arrowedLine(frame,middle,tip,color,line_width,tipLength=.3)
                    if frame.shape[1] > 1440:
                        frame = cv2.resize(frame, (1440, round(frame.shape[0]*1440/frame.shape[1])))
                    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    if ok:
                        encoded[cid] = jpg.tobytes()
                        with self.lock:
                            self.preview_frames[cid] = encoded[cid]
                tiempos["dibujo"] = (time.monotonic() - dibujo_inicio) * 1000
                sample_times = [c["frameIndex"]/c["fps"]-source_time_offset(c) for c in active if not c["stream"]]
                skew = max(sample_times)-min(sample_times) if len(sample_times)>1 else 0.
                elapsed = time.monotonic() - start
                seen = {(p["camera"], p["id"]) for p in people}
                trails = {key: value for key, value in trails.items() if key in seen}
                with self.lock:
                    self.frames.update(encoded)
                    primary_plan = config.get('planId','custom')
                    analytics = occupancy.update([p for p in counted if camera_levels[p['camera']]==primary_plan], t,
                        observation_valid=plan_observed(cams, observed_ids, primary_plan))
                    analytics["flow"] = flow.update(counted,t)
                    levels={}
                    for pid, counter in level_occupancy.items():
                        group=[p for p in counted if camera_levels[p['camera']]==pid]
                        levels[pid]=counter.update(group,t, observation_valid=plan_observed(cams, observed_ids, pid))
                        levels[pid]['flow']=level_flow[pid].update(group,t)
                        levels[pid]['flowVectors']=flow_fields[pid].update(group,t)
                    analytics=levels.get(config.get('planId','custom'),analytics)
                    if replay:
                        views=[]
                        for c in active:
                            h,w=raw_frames[c["id"]].shape[:2]
                            views.append({"id":c["id"],"t":statuses[c["id"]].get("sourceTime"),"observed":c["id"] in observed_ids,"analysis":camera_analytics.get(c["id"]),"people":[{"id":p["id"],"box":[p["box"][0]/w,p["box"][1]/h,p["box"][2]/w,p["box"][3]/h] if p["box"] else None,"pixel":[p["pixel"][0]/w,p["pixel"][1]/h],"local":p["local"],"point":p["point"],"association":p["association"],"confirmed":p.get("confirmed",True),"duplicate":p.get("duplicate",False),"history":p.get("history",[])[-30:]} for p in people if p["camera"]==c["id"]]})
                        replay.append({"t":t,"cameras":views,"analytics":analytics,"levels":levels})
                    self.dispatch_alerts(camera_analytics, analytics, levels)
                    self.record_traffic(analytics, bool(active and active[0].get("stream")))
                    self.state.update(status="paused" if self.pause_event.is_set() else "running", people=people, cameras=list(statuses.values()), events=list(identities.events), t=t,
                                      analytics=analytics, levelAnalytics=levels, cameraAnalytics=copy.deepcopy(camera_analytics), synchronization={"mode":"live" if active[0]["stream"] else "recordings", "contentVerified":config["clocksVerified"], "sampleSkewSeconds":round(skew,5), "commonTime":t}, totals=metrics.update(counted,analytics,t), series=list(metrics.series), processingMs=round(elapsed * 1000), updatedAt=time.time(),
                                      performance={"preset": preset_clave, "stepSeconds": paso_muestreo, "detectorSize": request.get("inferenceSize"), "maxEmbedPerStep": max_embed,
                                                   "msPorEtapa": {**{k: round(v) for k, v in tiempos.items()}, "otros": round(max(0., elapsed * 1000 - sum(tiempos.values())))}, "tiempoReal": round(elapsed / paso_muestreo, 2)},
                                      identity=identities.resumen())
                timeline = round(timeline+paso_muestreo,6)
                if active[0]["stream"]:
                    self.stop_event.wait(max(0., paso_muestreo - (time.perf_counter() - cycle_started)))
                else:
                    recording_deadline += paso_muestreo
                    self.stop_event.wait(max(0., recording_deadline - time.perf_counter()))
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
            if "lectores" in locals():
                lectores.shutdown(wait=True)
            self.appearance_memory_live = None
            if appearance_memory:
                appearance_memory.cerrar()
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
                    if 'identities' in locals():
                        replay.meta['identityDiagnostics'] = identities.resumen()
                        replay.meta['inferenceRuntime'] = {'detector': profile['device'],
                                                          'reidProviders': getattr(embedder, 'providers', []),
                                                          'modelFingerprint': getattr(embedder, 'fingerprint', None)}
                    replay.finish("error" if self.state["status"]=="error" else "stopped" if self.stop_event.is_set() else "ended")
                    # Con el análisis terminado la CPU queda libre: se prepara la copia que el navegador puede reproducir (AVI/MKV).
                    import video_web
                    for camera in cams:
                        fuente = camera.get("source")
                        if isinstance(fuente, str) and fuente and "://" not in fuente and Path(fuente).is_file():
                            video_web.preparar(Path(fuente))
                    if config.get("identityFinalize", True) and "identities" in locals():
                        # Reagrupación con el plano al cerrar: IDs finales 1..N en la grabación. Un fallo aquí
                        # deja la grabación con los IDs en vivo y lo avisa, sin perder la sesión.
                        try:
                            from identity.closing import reescribir_replay
                            reescribir_replay(replay.directory, identities.cierre())
                        except (OSError, ValueError, KeyError) as exc:
                            self.record("Identidad", f"No se pudo reagrupar la sesión al cerrar: {exc}")
                    self.compute_insights(replay.directory.name)
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


def storage_response(method):
    """La indisponibilidad de la BD es un 503 recuperable, nunca un login vacío."""
    from functools import wraps
    @wraps(method)
    def handle(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            from storage import operational
            if operational.is_database_error(exc):
                return self.send_data(503, {'error': 'La base de datos no está disponible. Revisa Docker y vuelve a intentar. No se cambiaron los datos locales.'})
            raise
    return handle


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
    @storage_response
    def do_GET(self):
        try:
            return self._get()
        except auth.UserStoreError as exc:
            return self.send_data(503, {"error": str(exc)})

    def _get(self):
        if not self.allowed():
            return self.send_data(403, {"error": "Acceso local requerido."})
        url = urlparse(self.path)
        engine = self.server.engine
        if url.path == '/api/storage':
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get('X-LAP-Session', '')):
                return self.send_data(401, {'error': 'Inicia sesión.'})
            from storage.postgis import health
            from storage.archive_queue import ArchiveQueue
            from storage import operational
            queue = ArchiveQueue(engine.data_root / 'data' / 'storage-outbox.sqlite')
            return self.send_data(200, {**health(), **queue.status(), 'scope': 'operational' if operational.enabled(engine.config_path) else 'session_archive',
                                       'operationalStorage': 'PostgreSQL: usuarios, proyectos, negocios y ventas' if operational.enabled(engine.config_path) else 'SQLite y JSON locales'})
        if url.path in ("/api/commercial/trial", "/api/commercial/trial-template"):
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión."})
            import commercial_trial
            with engine.lock:
                con = business_data.connect(engine.config_path)
                try:
                    businesses = business_catalog.sync(con, engine.config, ROOT / "dashboard/public")
                    options = commercial_trial.session_options(engine.data_root, engine.project_id, businesses, engine.config)
                    if url.path.endswith('trial-template'):
                        query = parse_qs(url.query)
                        selected = next((b for s in options if s['id'] == query.get('session', [''])[0] for b in s['businesses'] if b['id'] == query.get('business', [''])[0]), None)
                        if not selected:
                            return self.send_data(400, {'error': 'Selecciona una tienda y un video finalizado.'})
                        return self.send_data(200, commercial_trial.example_csv(selected['id'], selected['date'], selected['hour']).encode('utf-8-sig'), 'text/csv; charset=utf-8')
                    return self.send_data(200, {'sessions': options, 'saved': commercial_trial.saved(con)})
                finally:
                    con.close()
        if url.path == "/api/commercial/sample":
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401,{"error":"Inicia sesión."})
            try:
                con = business_data.connect(engine.config_path)
                try:
                    commercial.setup(con)
                    row = con.execute("SELECT session,negocio_id,fecha,hora FROM commercial_traffic WHERE dataset='demo' AND session NOT LIKE 'demo-%' ORDER BY fecha DESC,hora DESC,coverage DESC,session DESC LIMIT 1").fetchone()
                    if not row:
                        raise ValueError('Todavía no hay videos de prueba con accesos vinculados en este proyecto.')
                    return self.send_data(200,dict(session=row[0],businessId=row[1],date=row[2],hour=row[3],projectId=engine.project_id))
                finally:
                    con.close()
            except (OSError, ValueError) as exc:
                return self.send_data(404,{"error":str(exc)})
        if url.path in ("/api/camera-frame", "/api/camera-frame-info"):
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión para ver los videos."})
            query = parse_qs(url.query)
            try:
                cid = query.get("camera", [""])[0]
                if url.path == "/api/camera-frame-info":
                    return self.send_data(200, engine.camera_frame_info(cid))
                return self.send_data(200, engine.camera_frame_at(cid, float(query.get("t", ["0"])[0])), "image/jpeg")
            except (ValueError, OSError) as exc:
                return self.send_data(400, {"error": str(exc)})
        if url.path == "/api/insights":
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión para consultar los insights."})
            try:
                return self.send_data(200, engine.insights_data(parse_qs(url.query).get("session", [""])[0]))
            except FileNotFoundError as exc:
                return self.send_data(404, {"error": str(exc)})
            except (ValueError, OSError) as exc:
                return self.send_data(400, {"error": str(exc)})
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
                        writer.writerow(["Negocio","Fecha","Hora Lima","Origen","Sesión de video","Cobertura segundos","Entradas","Ventas PEN","Transacciones","Transacciones por entrada %","Proyección PEN","Alcance de proyección","Ingreso histórico por entrada PEN","Días históricos","Siguiente hora","Entradas esperadas","Pronóstico siguiente hora PEN","Salidas emparejadas","Objetos nuevos","Salidas sin emparejar"])
                        for row in result["businesses"]:
                            writer.writerow([row["name"],result["date"],result["hour"],result["dataset"],row["session"],row["coverage"],row["entries"],row["sales"],row["transactions"],row["conversion"],row["forecast"]["estimate"],row["estimateScope"],row["forecast"].get("perEntry"),row["forecast"]["days"],row["nextForecast"].get("target"),row["nextForecast"].get("expectedEntries"),row["nextForecast"].get("estimate"),row["bags"]["matched"],row["bags"]["changed"],row["bags"]["unmatched"]])
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
        if url.path in ("/api/businesses", "/api/spatial-graph"):
            if auth.hay_usuarios(engine.settings_root) and not engine.sessions.leer(self.headers.get("X-LAP-Session", "")):
                return self.send_data(401, {"error": "Inicia sesión para consultar los negocios."})
            with engine.lock:
                conexion = business_data.connect(engine.config_path)
                try:
                    businesses = business_catalog.sync(conexion, engine.config, ROOT / "dashboard" / "public")
                    if url.path == '/api/spatial-graph':
                        from identity.spatial_graph import build_graph, persist_graph
                        graph = build_graph(engine.config, businesses)
                        persist_graph(conexion, graph)
                        return self.send_data(200, graph)
                    return self.send_data(200, {"negocios": businesses, "projectId": engine.project_id})
                finally:
                    conexion.close()
        if url.path.startswith("/api/replay/"):
            from replay import get
            return get(self,url,self.server.engine.data_root)
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
                    config=copy.deepcopy(engine.report_config if engine.report_identity ==
                                         (engine.project_id, engine.state.get("session")) else engine.config)
                    snapshot=engine.snapshot()
                if query.get('session'):
                    from replay import report_snapshot
                    config,snapshot,meta=report_snapshot(engine.data_root,query['session'][0],engine.project_id,strict=True)
                if url.path == '/api/report/session':
                    return self.send_data(200, {'config':config,'state':snapshot,'created':meta['created'] if query.get('session') else None,'scope':'session',
                                                'evidenceIntegrity':meta.get('evidenceIntegrity','unknown') if query.get('session') else 'in_memory'})
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
    SOLO_OPERADOR = ("/api/commercial/trial", "/api/commercial/import", "/api/commercial/simulate", "/api/businesses", "/api/config", "/api/import-plan", "/api/plan-lines", "/api/upload", "/api/camera-restart",
                     "/api/camera-preview", "/api/calibration-check", "/api/person-pairs/check")

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
    @storage_response
    def do_POST(self):
        import cv2
        engine = self.server.engine
        size = int(self.headers.get("Content-Length", "0"))
        if not self.allowed() or not secrets.compare_digest(self.headers.get("X-LAP-Token", ""), engine.token):
            return self.reject(size, 403, "Recarga la interfaz local antes de continuar.")
        try:
            parsed = urlparse(self.path)
            sesion = engine.sessions.leer(self.headers.get("X-LAP-Session", ""))
            try:
                configured = auth.hay_usuarios(engine.settings_root)
            except auth.UserStoreError as exc:
                return self.reject(size, 503, str(exc))
            if parsed.path != "/api/auth" and configured:
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
                filename = parse_qs(parsed.query).get("name",[""])[0]
                suffix = Path(filename).suffix.lower()
                if suffix not in (".mp4",".avi",".mov",".mkv",".webm",".m4v"):
                    raise ValueError("Formato de video no admitido.")
                from uploads import receive, deduplicate_completed
                validar_tamano_de_video(size, shutil.disk_usage(engine.data_root).free)
                target = receive(engine.data_root, self.rfile, size, suffix, resources=engine.resources)
                import video_web
                target = deduplicate_completed(engine.data_root, target)
                video_web.preparar(target)
                with engine.lock:
                    engine.record("Video cargado",f"Archivo de prueba {suffix} · {size} bytes")
                return self.send_data(200,{"path":str(target)})
            if not 0 < size <= 4000000:
                raise ValueError("Tamaño de solicitud inválido.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Solicitud inválida.")
            if parsed.path == "/api/commercial/trial":
                import commercial_trial
                with engine.lock:
                    if data.get('projectId') != engine.project_id:
                        raise ValueError('El proyecto cambió. Vuelve a seleccionar el video.')
                    con = business_data.connect(engine.config_path)
                    try:
                        businesses = business_catalog.sync(con, engine.config, ROOT / 'dashboard/public')
                        options = commercial_trial.session_options(engine.data_root, engine.project_id, businesses, engine.config)
                        observed = next((b for s in options if s['id'] == data.get('session') for b in s['businesses'] if b['id'] == data.get('businessId')), None)
                        if not observed:
                            raise ValueError('Selecciona un video de prueba finalizado y una tienda con cruces medidos.')
                        rows, fingerprint = commercial_trial.read_history(data.get('file'), str(data.get('filename', '')), observed['id'])
                        result = commercial_trial.calculate(rows, {k: v for k, v in observed.items() if k not in ('id', 'name')})
                        business = next(b for b in businesses if b['id'] == observed['id'])
                        return self.send_data(200, commercial_trial.save(con, result, business, str(data.get('filename', '')), fingerprint))
                    finally:
                        con.close()
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
            if self.path == "/api/calibration-check":
                from live_core import validate_calibration_pairs, calibration_diagnostics
                pairs = data.get("pairs",[])
                context=data.get("context")
                validate_calibration_pairs(pairs, context, require_complete=True)
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
                zone=data.get("zone")
                if zone is not None and (not isinstance(zone,list) or len(zone)<3 or any(not isinstance(q,list) or len(q)!=2 for q in zone)):
                    raise ValueError("Zona de detección inválida.")
                plan=data.get("plan", [context["width"],context["height"]] if context else [engine.config["width"],engine.config["height"]])
                if (not isinstance(plan,list) or len(plan)!=2 or any(not isinstance(v,(int,float)) or isinstance(v,bool)
                                                                    or not np.isfinite(v) or v<=0 for v in plan)):
                    raise ValueError("Dimensiones del plano inválidas.")
                if (points[:,2] < 0).any() or (points[:,2] > plan[0]).any() or (points[:,3] < 0).any() or (points[:,3] > plan[1]).any():
                    raise ValueError("Una referencia cae fuera del plano seleccionado.")
                return self.send_data(200,{**calibration_diagnostics(pairs,zone,tuple(plan)),"contextValidated":context is not None})
            if self.path == "/api/camera-preview":
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
                    encoded=engine._preview_jpeg(frame, width=1280, quality=82)
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
                engine.update_alert_rules(data, expected_project=data.get("projectId"))
                return self.send_data(200, {"ok": True})
            if parsed.path == "/api/incidents":
                return self.send_data(200, engine.update_incident(data.get("id"), data.get("estado")))
            if parsed.path == "/api/incidents/history":
                # Same operational roles as incident review, but this explicit
                # human assertion always requires a session, even before setup.
                if not sesion:
                    return self.send_data(401, {"error": "Inicia sesión para validar el historial."})
                if sesion["rol"] not in auth.ROLES:
                    return self.send_data(403, {"error": "Tu usuario no puede validar incidentes."})
                if "projectId" not in data:
                    raise ValueError("Indica el proyecto del incidente.")
                return self.send_data(200, engine.validate_incident_history(
                    data.get("id"), data.get("never_attended"), data["projectId"]))
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
                engine.configure(data, expected_project=intended)
            elif self.path == "/api/start":
                engine.start(data)
            elif self.path == "/api/settings":
                engine.settings(data)
            elif self.path == "/api/person-pairs/check":
                return self.send_data(200, engine.person_pairs_check(str(data.get("base", "")), str(data.get("target", "")), data.get("pairs", [])))
            elif self.path == "/api/insights/compute":
                from replay import manifest
                sid = str(data.get("session", ""))
                meta = manifest(engine.data_root, sid)
                if meta.get("status") == "running":
                    raise ValueError("Finaliza el monitoreo antes de calcular los insights.")
                if engine.project_id and meta.get("projectId") not in (engine.project_id, None):
                    raise ValueError("La sesión no pertenece al proyecto abierto.")
                if engine.compute_insights(sid) is None:
                    raise ValueError("No se pudieron calcular los insights; revisa la auditoría.")
                return self.send_data(200, {"ok": True})
            elif self.path == "/api/identity/purge":
                return self.send_data(200, {"ok": True, "borradas": engine.purge_identities()})
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
    from storage.environment import load_environment
    load_environment(ROOT.parent)
    from storage import operational
    operational.configure(ROOT)
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
    from storage.archive_queue import ArchiveQueue
    archive = ArchiveQueue(server.engine.data_root / "data" / "storage-outbox.sqlite")
    archive.recover(server.engine.data_root / "data" / "replays")
    archive.start()
    try:
        from automation_reports import ScheduledReports
        from automation_backups import ProjectBackups
        from automation_escalation import AlertEscalation
        from automation_cleanup import RetentionCleanup
        service = server.engine.automation
        service.tasks = {"reports": ScheduledReports(server.engine, service.store),
                         "backups": ProjectBackups(server.engine, service.store),
                         "escalation": AlertEscalation(server.engine),
                         "cleanup": RetentionCleanup(server.engine, service.store)}
        server.engine.automation.start()
        # La interfaz y la configuración pueden abrirse mientras YOLO prepara sus
        # pesos en segundo plano. Así el primer monitoreo no paga toda la carga del
        # modelo después de que el operador pulsa «Iniciar».
        server.engine.warm_detector_async()
        from replay import recover_interrupted
        recover_interrupted(server.engine.data_root,
                            on_error=lambda sid: server.engine.record("Histórico inválido", f"{sid}: recuperación interrumpida; archivo conservado."))
        print(f"LAP: http://127.0.0.1:{args.port} — solo equipo local", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        archive.close()
        if stop_server(server):
            server.server_close()
        else:
            print("Cierre incompleto: esperando trabajadores/recursos activos.", flush=True)
            defer_close(server)


if __name__ == "__main__":
    main()
