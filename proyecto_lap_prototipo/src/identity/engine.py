"""Motor de identidad entre cámaras: tracklets por cámara + OSNet + compuerta de tiempo y plano, y reagrupación al cerrar.

Sigue el esquema de los sistemas de seguimiento multicámara de referencia (DeepCC, Ristani y Tomasi 2018; ganador del AI City
Challenge 2023, Huang et al.): cada cámara entrega tracklets (YOLO + ByteTrack), cada tracklet reúne vectores OSNet de sus
vistas confiables, y la unión entre cámaras exige parecido de apariencia y coherencia de tiempo y posición en el plano
(homografía con puntos del suelo). Al terminar la sesión se reagrupa con la grabación completa a la vista.

Una persona recién vista lleva un ID provisional "T00007" y `confirmed: False` hasta reunir `min_samples` vistas durante
`min_identity_duration_s`; al confirmarse pasa a "P00007". Quien cuente (ocupación, flujo, métricas) filtra por `confirmed`.
El motor no detiene nunca el monitoreo: ante un error devuelve IDs provisionales y se reinicia.
"""
import math
from collections import deque

import cv2
import numpy as np

from .associator import AsociadorMulticamara
from .regroup import ReagrupadorPlano

# Parámetros base del asociador; los umbrales de similitud se sustituyen por los de OSNet (UMBRALES_OSNET).
ASOCIACION_DEFECTO = {
    "sample_interval_s": 0.4, "tracklet_views_target": 8, "identity_views_target": 30, "verify_interval_s": 2.0,
    "min_samples": 5, "min_query_samples": 3, "min_identity_duration_s": 2.0,
    "threshold": 0.60, "average_threshold": 0.55, "same_camera_threshold": 0.70, "ambiguity_margin": 0.05,
    "mutual_best": True, "split_threshold": 0.40, "split_strikes": 2,
    "candidate_window_s": 90.0, "reentry_window_s": 120.0, "tracklet_gap_s": 2.0, "sync_tolerance_s": 0.15,
    "min_conf": 0.55, "min_height": 40, "max_occlusion": 0.2,
    "closing_far": 1.33,         # al cerrar: dos tramos a la vez a mas de esto (x distancia de solape) en el plano no son la misma persona
    "closing_threshold": 0.60,   # al cerrar: parecido OSNet promedio mínimo para juntar dos grupos (ver regroup.py)
}
# Umbrales por encoder, elegidos con tools/barrido_umbrales.py (centro de la meseta de IDF1) sobre las cámaras demo
# A y B: 4 personas, 24 s, etiquetas provisionales. Son una primera estimación optimista (se calibra y se mide con
# los mismos datos): repetir el barrido con un conjunto propio y más grande antes de fiarse (docs/EVALUACION_IDENTIDAD.md).
UMBRALES_OSNET = {"threshold": 0.75, "average_threshold": 0.55, "same_camera_threshold": 0.79, "split_threshold": 0.65}
GRUPOS_MIN_VISIBLE = 0.6   # con identityGroupCrops: fracción mínima visible del recuadro (ver identity/quality.tapadores)
ESCALA_SOLAPE = 1.6        # distancia de coincidencia simultánea = matchDistance * 1.6
ESCALA_VELOCIDAD = 2.7     # velocidad máxima = matchDistance * 2.7 por segundo (4 m/s si matchDistance es 1.5 m)
EXPANSION_COBERTURA = 1.3  # la cobertura de una cámara es el casco de sus referencias, ampliado
TOLERANCIA_COBERTURA = 3.0  # dos coberturas a menos de esto (x distancia de solape) cuentan como solapadas: absorbe calibraciones desalineadas
MAX_SERIE = 20000          # posiciones guardadas por id local (a 5 por segundo, más de una hora)
DUDA_VIGENCIA_S = 3.0      # una identidad con candidata ambigua se marca "uncertain" este tiempo


def _casco_plano(camara):
    """Casco convexo (ampliado) de las referencias del suelo de una cámara en el plano, o None sin calibrar."""
    pares = camara.get("pairs") or []
    if len(pares) < 4:
        return None
    puntos = np.asarray([[p[2], p[3]] for p in pares], np.float32)
    casco = cv2.convexHull(puntos).reshape(-1, 2)
    centro = casco.mean(axis=0)
    return (centro + (casco - centro) * EXPANSION_COBERTURA).astype(np.float32)


def _distancia_cascos(a, b):
    """Distancia mínima entre dos polígonos convexos (0 si se cruzan)."""
    if cv2.intersectConvexConvex(a, b)[0] > 0:
        return 0.0
    mejor = min(abs(cv2.pointPolygonTest(b.reshape(-1, 1, 2), (float(x), float(y)), True)) for x, y in a)
    return float(min(mejor, min(abs(cv2.pointPolygonTest(a.reshape(-1, 1, 2), (float(x), float(y)), True)) for x, y in b)))


def _calibrada(camara):
    """True si las referencias de la cámara dan una homografía válida (la misma comprobación del servidor)."""
    from live_core import calibration
    try:
        return calibration(camara.get("pairs", [])) is not None
    except ValueError:
        return False


def registro_desde_config(config, ajustes=None):
    """Convierte la configuración de AeroTrack en el registro del asociador (cámaras, transiciones y solapes).

    - `links` (cámaras relacionadas por el usuario, ver live_core.related_cameras) y `handoffSeconds` pasan a transiciones
      origen->destino con ventana [0, handoffSeconds]. Sin relaciones, cada cámara conserva sus propios IDs.
    - Dos cámaras relacionadas se solapan si la cobertura de sus puntos del suelo se cruza en el plano o queda cerca (la
      tolerancia absorbe calibraciones algo desalineadas); si alguna no está calibrada no se puede saber, y se permite.
    - Las distancias se expresan con `matchDistance`, en las unidades del plano, sea metros o relativas.
    """
    camaras = [c for c in config["cameras"] if c.get("active", True)]
    ids = {c["id"] for c in camaras}
    calibradas = {c["id"]: _calibrada(c) for c in camaras}
    cascos = {c["id"]: _casco_plano(c) for c in camaras}
    match = float(config.get("matchDistance", 1.0))
    handoff = float(config.get("handoffSeconds", 12.0))
    velocidad = match * ESCALA_VELOCIDAD
    transiciones, solapes = [], set()
    # Sin relojes verificados no hay base para unir cámaras: cada una conserva sus propios IDs.
    for c in camaras if config.get("clocksVerified") else []:
        for destino in c.get("links", []):
            otra = next((o for o in camaras if o["id"] == destino), None)
            if otra is None or destino == c["id"] or otra.get("planId", "custom") != c.get("planId", "custom"):
                continue
            transiciones.append({"from": c["id"], "to": destino, "t_min_s": 0.0, "t_max_s": handoff,
                                 "max_distance_m": velocidad * handoff + match * ESCALA_SOLAPE, "min_direction_cos": -0.5})
            a, b = cascos[c["id"]], cascos[destino]
            if a is None or b is None or _distancia_cascos(a, b) <= TOLERANCIA_COBERTURA * match * ESCALA_SOLAPE:
                solapes.add(frozenset((c["id"], destino)))
    hay_geometria = bool(config.get("clocksVerified")) and any(calibradas.values())
    asociacion = {**ASOCIACION_DEFECTO, **UMBRALES_OSNET,
                  "overlap_distance_m": match * ESCALA_SOLAPE, "max_speed_m_s": velocidad,
                  **({"min_visible": GRUPOS_MIN_VISIBLE} if config.get("identityGroupCrops") else {}),
                  **(config.get("identityV2") or {}), **(ajustes or {})}
    return {"mode": "calibrado" if hay_geometria else "visual_temporal", "units": "m",
            "cameras": {cid: {"timestamp_offset": 0.0, "calibrada": calibradas[cid]} for cid in ids},
            "transitions": transiciones, "overlaps": [sorted(p) for p in solapes], "association": asociacion}


class MotorIdentidadV2:
    """Asigna IDs entre cámaras con el AsociadorMulticamara; `update` devuelve las filas que consume live_server."""

    nombre = "reid_v2"

    def __init__(self, config, encoder=None, memoria=None, ajustes=None, encoder_nombre="osnet"):
        self.config, self.encoder, self.memoria, self.ajustes = config, encoder, memoria, ajustes
        self.encoder_nombre = encoder_nombre
        self.tamanos = {}
        self.events = deque(maxlen=150)
        self.people = {}
        self.errores, self.ultimo_error = 0, None
        self._ultima_salida = None
        self._crear_asociador()

    def _crear_asociador(self):
        registro = registro_desde_config(self.config, self.ajustes)
        self.registro = registro
        if self.memoria is not None:
            from .memory import AsociadorConMemoria
            self.asociador = AsociadorConMemoria(self.encoder, registro, self.memoria)
        else:
            self.asociador = AsociadorMulticamara(self.encoder, registro)
        self._estado, self._n_enlaces, self._ultima_salida = {}, 0, None
        self._series, self._tiempos = {}, deque(maxlen=200)   # (cámara, local) -> [(t, x, y)] para reagrupar al cerrar

    def reiniciar(self):
        """Empieza una sesión nueva (el tiempo retrocedió o se pidió reiniciar)."""
        self._crear_asociador()

    @property
    def min_visible(self):
        """Fracción mínima visible del recuadro para calcular el vector (None: regla antigua de solape de cajas)."""
        return self.asociador.quality.get("min_visible")

    def necesita_vista(self, camara, local, t=None):
        """True si conviene calcular ya el vector de este track (aún sin ID público o con pocas vistas, y no muestreado hace poco)."""
        return self.asociador.necesita_vista(camara, int(local), t)

    def resumen(self):
        """Estado del motor para la interfaz y los reportes."""
        bloqueadas = self.config.get("identityBlockedPairs") or []
        advertencias = [f"{p['base']} y {p['destino']}: asociación bloqueada por homografía incompatible; se conservan IDs locales."
                        for p in bloqueadas if isinstance(p, dict) and p.get("base") and p.get("destino")]
        return {"engine": self.nombre, **self.asociador.resumen(), "errores": self.errores, "ultimo_error": self.ultimo_error,
                "umbrales_de": "osnet", "camaras_bloqueadas_geometria": bloqueadas, "advertencias": advertencias}

    def update(self, observations, t, tamanos=None, frames=None):
        """Asigna ID a las observaciones de un instante y devuelve una fila por observación."""
        self.tamanos.update(tamanos or {})
        try:
            return self._actualizar(observations, t, frames)
        except Exception as exc:  # el monitoreo nunca se detiene por la identidad
            self.errores += 1
            self.ultimo_error = f"{type(exc).__name__}: {exc}"
            self._crear_asociador()
            return [self._fila(o, f"T{o['camera']}{o['local']}", "local", None, None, False, t) for o in observations]

    def _actualizar(self, observations, t, frames):
        asociador = self.asociador
        if abs(t - asociador.last_timestamp) <= 1e-8 and self._ultima_salida is not None:
            return [dict(p) for p in self._ultima_salida]  # mismo instante repetido (pausa): no se reprocesa
        if t < asociador.last_timestamp - 1e-8:
            self.reiniciar()  # el video se repitió o se saltó atrás
            asociador = self.asociador
        por_camara, filas = {}, {}
        for o in observations:
            caja = o.get("box")
            if caja is None:
                continue
            punto = o.get("point")
            fila = {"local_id": int(o["local"]), "x1": float(caja[0]), "y1": float(caja[1]), "x2": float(caja[2]),
                    "y2": float(caja[3]), "confidence": float(o.get("score") if o.get("score") is not None else 1.0),
                    "punto": punto, "punto_crudo": o.get("point"), "embedding": o.get("embedding"),
                    "embedding_nuevo": o.get("embeddingFresh"), "parcial": bool(o.get("partial"))}
            por_camara.setdefault(o["camera"], []).append(fila)
            filas[(o["camera"], int(o["local"]))] = fila
        asociador.actualizar(t, frames, por_camara, tamanos=self.tamanos)
        self._guardar_series(por_camara, t)
        salida, vistos = [], set()
        for o in observations:
            fila = filas.get((o["camera"], int(o["local"]))) if o.get("box") is not None else None
            if fila is None:
                salida.append(self._fila(o, f"T{o['camera']}{o['local']}", "local", None, None, False, t))
                continue
            gid, publico = fila["gid_interno"], fila["global_id"]
            confirmada = publico is not None
            identidad = f"P{publico:05d}" if confirmada else f"T{gid:05d}"
            vistos.add(gid)
            salida.append(self._fila(o, identidad, self._asociacion(gid, o["camera"], publico), gid, fila, confirmada, t))
        self._marcar_duplicadas(salida, observations, filas)
        self._eventos(t)
        self._expirar(t)
        self.people = {p["id"]: {"color": None, "height": p.get("height")} for p in salida}
        self._ultima_salida = [dict(p) for p in salida]
        return salida

    def _marcar_duplicadas(self, salida, observations, filas):
        """Marca `duplicate` en los puntos provisionales que repiten a una persona que otra cámara ya dibuja en el mismo sitio.

        Mientras una identidad no se confirma (reúne vistas) no se sabe si es la misma persona que ve otra cámara, y el mapa
        mostraba dos puntos. Aquí solo se decide qué dibujar: la identidad y los conteos no cambian (el provisional no cuenta)
        y las cámaras siguen mostrando cada recuadro. Se oculta el de menor recuadro cuando coinciden en el plano."""
        a = self.asociador
        if a.mode != "calibrado" or a.geometry_close <= 0:
            return
        radio = a.geometry_close * a.max_distance
        puestos, pendientes = [], []
        for fila_salida, o in zip(salida, observations):
            fila = filas.get((o["camera"], int(o["local"]))) if o.get("box") is not None else None
            punto = fila["punto"] if fila and fila.get("punto") is not None else None
            if punto is None:
                continue
            if fila_salida["confirmed"]:
                puestos.append((o["camera"], punto))
            else:
                area = max(0.0, o["box"][2] - o["box"][0]) * max(0.0, o["box"][3] - o["box"][1])
                pendientes.append((area, fila_salida, o["camera"], punto))
        for _, fila_salida, camara, punto in sorted(pendientes, key=lambda x: -x[0]):
            repetida = any(otra != camara and frozenset((camara, otra)) in a.solapes and math.dist(punto, q) <= radio for otra, q in puestos)
            fila_salida["duplicate"] = repetida
            if not repetida:
                puestos.append((camara, punto))

    def _guardar_series(self, por_camara, t):
        """Guarda la posición (ya corregida) de cada id local en cada instante: la reagrupación final las necesita."""
        self._tiempos.append(t)
        for camara, filas in por_camara.items():
            for f in filas:
                if f.get("punto") is not None:
                    serie = self._series.setdefault((camara, f["local_id"]), [])
                    if len(serie) < MAX_SERIE:
                        serie.append((t, float(f["punto"][0]), float(f["punto"][1])))

    def cierre(self):
        """Reagrupa con el plano al cerrar la sesión y devuelve un CierreSesion: IDs finales 1..N por orden de aparición."""
        a = self.asociador
        tracklets = [{"uid": uid, "camera": t.camera_id, "gid": t.global_id, "inicio": t.inicio_s, "fin": t.fin_s,
                      "muestras": t.n_muestras} for uid, t in a.tracklets.items()]
        series = {uid: [p for p in self._series.get((t.camera_id, t.local_id), ())
                        if t.inicio_s - 1e-9 <= p[0] <= t.fin_s + 1e-9] for uid, t in a.tracklets.items()}
        pasos = np.diff(sorted(set(self._tiempos)))
        fps = float(np.clip(1.0 / np.median(pasos), 1.0, 60.0)) if len(pasos) else 5.0
        con_plano = a.mode == "calibrado"
        regrupar = ReagrupadorPlano(escala=a.max_distance, fps=fps, min_parecido=a.average_threshold, min_muestras=a.min_samples,
                                    min_visible_s=a.min_duration_s, usar_posicion=con_plano,
                                    min_parecido_global=float(a.config.get("association", {}).get("closing_threshold", ASOCIACION_DEFECTO["closing_threshold"])),
                                    factor_separados=float(a.config.get("association", {}).get("closing_far", ASOCIACION_DEFECTO["closing_far"])))
        resultado = regrupar(tracklets, series, a.prototipos())
        resultado["geometria"] = "plano" if con_plano else "solo apariencia"
        return CierreSesion(resultado, a.tracklets)

    def _asociacion(self, gid, camara, publico):
        """local: un solo tramo; estimated: une cámaras; reidentified: recupera un tramo o una persona de la memoria;
        uncertain: su mejor candidata fue ambigua hace poco."""
        a = self.asociador
        if gid in a.dudosas and a.last_timestamp - a.dudosas[gid] <= DUDA_VIGENCIA_S:
            return "uncertain"
        miembros = a._miembros(gid)
        if len({t.camera_id for t in miembros}) > 1:
            return "estimated"
        if publico is not None and publico in getattr(a, "reconocidas", ()):
            return "reidentified"
        return "reidentified" if len(miembros) > 1 else "local"

    def _fila(self, o, identidad, asociacion, gid, fila, confirmada, t):
        """Fila de salida con las claves que consume live_server."""
        estado = self._estado.setdefault(gid if gid is not None else identidad,
                                         {"history": deque(maxlen=180), "velocity": (0., 0.), "t": t, "point": None})
        punto = o.get("point")
        if punto is not None and estado["point"] is not None and t > estado["t"]:
            dt = t - estado["t"]
            estado["velocity"] = tuple(.5 * estado["velocity"][i] + .5 * (punto[i] - estado["point"][i]) / dt for i in (0, 1))
        if punto is not None and (not estado["history"] or estado["history"][-1][2] != t):
            estado["history"].append([*punto, t])
        estado.update(t=t, point=punto if punto is not None else estado["point"], camera=o["camera"])
        siguiente = None
        vecinas = next((c.get("links", []) for c in self.config["cameras"] if c["id"] == o["camera"]), [])
        if punto is not None and math.hypot(*estado["velocity"]) > .05 and vecinas:
            futuro = (punto[0] + estado["velocity"][0] * 2, punto[1] + estado["velocity"][1] * 2)
            candidatas = [c for c in self.config["cameras"] if c["id"] in vecinas]
            if candidatas:
                siguiente = min(candidatas, key=lambda c: math.dist(futuro, (c["x"], c["y"])))["id"]
        track = self.asociador.tracklets.get(fila["tracklet_id"]) if fila else None
        return {**{k: v for k, v in o.items() if k not in ("color", "embedding", "embeddingFresh", "partial")},
                "id": identidad, "association": asociacion, "reidScore": track.match_score if track else None,
                "history": list(estado["history"]), "predicted": False, "velocity": list(estado["velocity"]),
                "nextCamera": siguiente, "height": o.get("height"), "confirmed": confirmada}

    def _eventos(self, t):
        """Convierte las uniones nuevas del asociador en eventos de la interfaz (handoff / reidentification)."""
        a = self.asociador
        for enlace in a.enlaces[self._n_enlaces:]:
            if enlace["event"] != "associate":
                continue
            miembros = a._miembros(enlace["global_id"]) if enlace["global_id"] in a.globales else []
            camaras = sorted({m.camera_id for m in miembros})
            publico = a.confirmadas.get(enlace["global_id"])
            identidad = f"P{publico:05d}" if publico is not None else f"T{enlace['global_id']:05d}"
            self.events.appendleft({"type": "handoff" if len(camaras) > 1 else "reidentification", "id": identidad,
                                    "from": camaras[0] if camaras else "", "to": camaras[-1] if camaras else "",
                                    "t": t, "score": round(enlace["score"], 3)})
        self._n_enlaces = len(a.enlaces)

    def _expirar(self, t):
        """El estado de movimiento se retiene solo durante la ventana de traspaso declarada."""
        limite = float(self.config.get("handoffSeconds", 12.0))
        self._estado = {k: v for k, v in self._estado.items() if t - v["t"] <= limite}


class CierreSesion:
    """IDs finales de una sesión reagrupada: para cada observación (cámara, id local, instante) el número 1..N o None."""

    def __init__(self, resultado, tracklets):
        self.resultado = resultado
        self.publico = resultado["publico"]
        self._intervalos = {}
        for uid, t in tracklets.items():
            self._intervalos.setdefault((t.camera_id, t.local_id), []).append((t.inicio_s, t.fin_s, uid))
        for lista in self._intervalos.values():
            lista.sort()

    def id_final(self, camara, local, t):
        """Número final de la persona (1..N) o None si fue una pasada breve que no se cuenta."""
        lista = self._intervalos.get((camara, int(local)))
        if not lista:
            return None
        uid = min(lista, key=lambda i: 0.0 if i[0] - 1e-9 <= t <= i[1] + 1e-9 else min(abs(t - i[0]), abs(t - i[1])))[2]
        return self.publico.get(uid)

    def resumen(self):
        """Datos agregados para el manifiesto de la sesión (sin vectores ni imágenes)."""
        r = self.resultado
        return {"personas": r["personas"], "uniones_plano": r["uniones_plano"], "separados": r["separados"],
                "pasadas_breves": r["pasadas_breves"], "geometria": r["geometria"], "cambios": len(r["cambios"])}


def crear_memoria(config, ruta, encoder="osnet", dimension=512):
    """Memoria de apariencia con los mismos umbrales que el asociador. `ruta=None` la deja solo en RAM."""
    from .memory import MemoriaApariencia
    asociacion = registro_desde_config(config)["association"]
    return MemoriaApariencia(ruta, asociacion, dimension, encoder, config.get("identityRetentionHours", 24))


def crear_motor_identidad(config, encoder=None, memoria=None, encoder_nombre="osnet"):
    """Motor de identidad entre cámaras (necesita vectores OSNet)."""
    return MotorIdentidadV2(config, encoder, memoria, encoder_nombre=encoder_nombre)
