"""AsociadorMulticamara: galería global compartida, compuerta física, fusión mutua y confirmación de ID.

Portado de AeroVision (asociacion_multicamara.py). Cambios respecto al original:
- sin IPython, pandas, torch ni cv2: solo numpy y la biblioteca estándar;
- la posición en el plano la entrega quien llama (`punto` en cada fila, ya proyectado con la
  homografía de calibración del proyecto) en lugar de proyectar aquí;
- el vector de apariencia puede venir ya calculado (`embedding` en la fila) o calcularlo un
  `encoder` enchufable a partir de los recortes;
- si a una pareja de tracklets le falta la posición, se decide solo con tiempo y apariencia
  (modo visual_temporal) en lugar de rechazarla.

Interfaz: por instante y cámara se entregan filas {local_id, x1, y1, x2, y2, confidence, punto?,
embedding?} y se devuelven las mismas filas con `tracklet_id` y `global_id` (None hasta confirmar).
"""
import json
import math
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .quality import recortar, tapadores, vistas_confiables
from .tracklet import Tracklet, se_solapan

MODOS = ("calibrado", "visual_temporal")


@dataclass
class Camara:
    """Cámara registrada: desfase de reloj y si su suelo está calibrado (da posición en el plano)."""
    camera_id: str
    timestamp_offset: float = 0.0
    calibrada: bool = False


def cargar_registro(config, camera_ids=None):
    """Valida el registro de cámaras: cámaras, transiciones dirigidas y solapes. Devuelve (datos, camaras, transiciones, solapes)."""
    datos = json.loads(Path(config).read_text(encoding="utf-8")) if isinstance(config, (str, Path)) else config
    modo = datos.get("mode", "calibrado")
    if modo not in MODOS:
        raise ValueError("mode debe ser calibrado o visual_temporal.")
    camaras = {}
    for cid, item in datos["cameras"].items():
        desfase = float(item.get("timestamp_offset", 0))
        if not np.isfinite(desfase):
            raise ValueError(f"{cid}: timestamp_offset no es finito.")
        camaras[cid] = Camara(cid, desfase, bool(item.get("calibrada", False)))
    if not camaras or (camera_ids is not None and set(camera_ids) != set(camaras)):
        raise ValueError("Las cámaras del registro deben coincidir con las de la sesión.")
    transiciones = {}
    for borde in datos.get("transitions", []):
        clave = (borde["from"], borde["to"])
        if clave[0] not in camaras or clave[1] not in camaras or clave[0] == clave[1] or clave in transiciones:
            raise ValueError(f"Transición inválida o duplicada: {clave}")
        minimo, maximo = float(borde["t_min_s"]), float(borde["t_max_s"])
        distancia = float(borde.get("max_distance_m", 30))
        if not all(np.isfinite(x) for x in (minimo, maximo, distancia)) or not 0 <= minimo <= maximo or distancia <= 0:
            raise ValueError(f"Ventana temporal o distancia inválida: {clave}")
        transiciones[clave] = {**borde, "t_min_s": minimo, "t_max_s": maximo, "max_distance_m": distancia}
    solapes = set()
    for par in datos.get("overlaps", []):
        if len(par) != 2 or par[0] == par[1] or not set(par) <= set(camaras):
            raise ValueError(f"Solape inválido: {par}")
        solapes.add(frozenset(par))
    return datos, camaras, transiciones, solapes


class _GaleriaCompartida:
    """Tracklets, identidades internas (galería compartida) e IDs públicos de las personas contadas."""

    def reiniciar(self, session_uuid=None):
        """Vacía la galería y empieza una sesión nueva."""
        self.session_uuid = session_uuid or uuid.uuid4()
        self.tracklets = {}
        self.locales = {}
        self.globales = {}
        self.confirmadas = {}
        self.siguiente_publico = 1
        self.segmentos = {}
        self.siguiente = 1
        self.vigentes = set()
        self.sucias = set()
        self.last_camera_time = {}
        self.last_timestamp = -math.inf
        self.evidencia_solapes = {}
        self.dudosas = {}   # identidad -> último instante en que su mejor candidata fue ambigua
        self.rechazos_geometria = {}   # (tracklet, tracklet) -> (cámaras, distancia mediana en el plano) con parecido suficiente
        self.pares_rechazados = deque(maxlen=4000)   # (cám. a, punto a, cám. b, punto b) simultáneos de esas parejas
        self._vistos_rechazo = set()
        self.stats = {"muestras_reid": 0, "verificaciones": 0,
                      "fusiones": 0, "separaciones": 0, "cambios_de_persona": 0, "ambiguos": 0}
        self.enlaces = []
        self.stats.update(candidatas_grafo_descartadas=0, comparaciones_apariencia=0,
                          rechazos_apariencia=0, rechazos_fisicos=0, candidatas_tiempo_descartadas=0)

    def global_uuid(self, publico):
        """UUID v5 anónimo de un ID público dentro de la sesión."""
        return str(uuid.uuid5(self.session_uuid, f"G{publico}"))

    def _nuevo(self, cid, lid, timestamp):
        """Crea un tracklet nuevo con su propia identidad interna."""
        key = (cid, lid)
        self.segmentos[key] = self.segmentos.get(key, 0) + 1
        uid = f"{cid}/L{lid}/T{self.segmentos[key]}"
        track = Tracklet(uid, str(uuid.uuid5(self.session_uuid, uid)), cid, lid, timestamp, timestamp, self.siguiente)
        self.globales[self.siguiente] = {uid}
        self.vigentes.add(self.siguiente)
        self.siguiente += 1
        self.tracklets[uid] = self.locales[key] = track
        return track

    def resolver(self, uid, timestamp):
        """Tracklet real de una fila: sigue los cortes hechos cuando el Re-ID detectó otra persona."""
        track = self.tracklets[uid]
        while track.sucesor is not None and timestamp >= track.corte_s - 1e-9:
            track = self.tracklets[track.sucesor]
        return track

    def _miembros(self, gid):
        """Tracklets que forman una identidad."""
        return [self.tracklets[uid] for uid in self.globales[gid]]

    def _n_vistas(self, gid):
        """Total de vistas Re-ID de una identidad."""
        return sum(self.tracklets[uid].n_muestras for uid in self.globales[gid])

    def _minimo(self, gid, otra):
        """Vistas necesarias: una pasada provisional puede consultar a una identidad ya confirmada con menos vistas."""
        return self.min_query_samples if gid not in self.confirmadas and otra in self.confirmadas else self.min_samples

    def _duracion_visible(self, gid):
        """Segundos en que la identidad estuvo visible en alguna cámara (unión de intervalos)."""
        intervalos = sorted((t.inicio_s, t.fin_s) for t in self._miembros(gid))
        total, (inicio, fin) = 0.0, intervalos[0]
        for a, b in intervalos[1:]:
            if a > fin:
                total, inicio, fin = total + fin - inicio, a, b
            else:
                fin = max(fin, b)
        return total + fin - inicio

    def _fin(self, gid):
        """Último instante en que se vio la identidad."""
        return max(self.tracklets[uid].fin_s for uid in self.globales[gid])


class _ObservacionesReID:
    """Recibe las filas de todas las cámaras de un instante, decide qué vistas pasan por el Re-ID y corta tracklets."""

    def actualizar(self, timestamp, frames, observaciones, occluders=None, tamanos=None):
        """Recibe las filas locales de todas las cámaras de un mismo instante y les asigna global_id.

        frames: {cámara: imagen BGR} o None si todas las filas traen `embedding`.
        tamanos: {cámara: (ancho, alto)} cuando no hay imagen (se usa para descartar cajas pegadas al borde).
        """
        if not math.isfinite(timestamp) or timestamp < self.last_timestamp - 1e-8:
            raise ValueError("El asociador necesita instantes ordenados por timestamp corregido.")
        frames = frames or {}
        self.last_timestamp = timestamp
        crops, muestreadas, directas, tocados = [], [], [], set()
        for cid, filas in observaciones.items():
            if cid not in self.camaras:
                raise ValueError(f"Cámara sin registro: {cid}")
            if timestamp <= self.last_camera_time.get(cid, -math.inf):
                raise ValueError(f"{cid}: timestamp repetido o fuera de orden.")
            self.last_camera_time[cid] = timestamp
            vistos = set()
            for fila in filas:
                lid = int(fila["local_id"])
                if lid in vistos:
                    raise ValueError(f"{cid}: local_id duplicado en un frame.")
                vistos.add(lid)
                track = self.locales.get((cid, lid))
                if track is None or timestamp - track.fin_s > self.gap:
                    track = self._nuevo(cid, lid, timestamp)
                track.fin_s = timestamp
                track.tiempos.append(timestamp)
                track.huella.append((timestamp, (fila["x1"] + fila["x2"]) / 2, fila["y2"], fila["y2"] - fila["y1"]))
                track.verificar |= bool(fila.get("riesgo"))
                track.observaciones += 1
                fila["tracklet_id"] = track.uid
                fila["_vector_nuevo"] = self._vector_nuevo(track, fila)
                tocados.add((cid, lid))
                self._proyectar(track, fila, timestamp)
            if cid in frames:
                forma = frames[cid].shape
            elif tamanos and cid in tamanos:
                forma = (tamanos[cid][1], tamanos[cid][0])
            else:
                raise ValueError(f"{cid}: sin frame ni tamaño para evaluar la calidad de las vistas.")
            obstaculos = None if occluders is None else occluders.get(cid)
            for indice in vistas_confiables(filas, forma, **self.quality, occluders=obstaculos):
                fila = filas[indice]
                track = self.tracklets[fila["tracklet_id"]]
                if not self._debe_muestrear(track, fila, timestamp):
                    continue
                if fila.get("embedding") is not None:
                    if fila["_vector_nuevo"]:
                        track.ultimo_muestreo = timestamp
                        directas.append((track, track.orientacion(), fila["embedding"], bool(fila.get("parcial"))))
                    continue
                if self.encoder is not None and cid in frames:
                    tapados = None
                    if self.quality["min_visible"] is not None:
                        tapados = tapadores([[fila[k] for k in ("x1", "y1", "x2", "y2")]], [[o[k] for k in ("x1", "y1", "x2", "y2")] for o in filas])[0][1]
                    crop = recortar(frames[cid], fila, tapados)
                    if crop.size:
                        track.ultimo_muestreo = timestamp
                        crops.append(crop)
                        muestreadas.append((track, track.orientacion(), bool(tapados)))
        vistas = list(directas)
        if crops:
            vectores = self.encoder(crops)
            if len(vectores) != len(muestreadas):
                raise ValueError("El número de embeddings no coincide con los recortes.")
            vistas += [(t, o, v, p) for (t, o, p), v in zip(muestreadas, vectores)]
        for track, orientacion, vector, parcial in vistas:
            vector = np.asarray(vector, dtype=np.float32).reshape(-1)
            norma = np.linalg.norm(vector)
            if np.isfinite(vector).all() and norma > 1e-8:
                self.stats["muestras_reid"] += 1
                self._agregar_vista(self.locales[(track.camera_id, track.local_id)], vector / norma, timestamp, orientacion, parcial)
        self._separar_conflictos({self.locales[key].global_id for key in tocados})
        if self.sucias:
            self._asociar()
        self._confirmar({self.locales[key].global_id for key in tocados})
        for filas in observaciones.values():
            for fila in filas:
                track = self.resolver(fila["tracklet_id"], timestamp)
                fila["tracklet_id"], fila["global_id"] = track.uid, self.confirmadas.get(track.global_id)
                fila["gid_interno"] = track.global_id
                fila.pop("_vector_nuevo", None)

    @staticmethod
    def _vector_nuevo(track, fila):
        """True si la fila trae un vector calculado en este instante (no el último repetido)."""
        embedding = fila.get("embedding")
        if embedding is None:
            return False
        vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
        nuevo = fila.get("embedding_nuevo")
        if nuevo is None:
            nuevo = track.ultimo_vector is None or not np.array_equal(vector, track.ultimo_vector)
        track.ultimo_vector = vector
        return bool(nuevo)

    def necesita_vista(self, cid, lid, t=None):
        """True si conviene calcular ya el vector de este id local: aún no tiene ID público o le faltan vistas.

        Con `t` (el instante que se va a procesar) no se pide el vector si el motor lo descartaría: `_debe_muestrear` no usa una
        vista a menos de `sample_interval_s` de la última, y calcular OSNet para tirarla es el costo más evitable del paso."""
        track = self.locales.get((cid, lid))
        if track is None:
            return True
        if t is not None and t - track.ultimo_muestreo + 1e-8 < self.sample_s:
            return False
        return track.global_id not in self.confirmadas or track.n_muestras < self.tracklet_views_target

    def _confirmar(self, gids):
        """Una identidad nueva solo se cuenta si estuvo visible `min_identity_duration_s` y reunió `min_samples` vistas."""
        for gid in sorted(gids):
            if (gid in self.globales and gid not in self.confirmadas and self._n_vistas(gid) >= self.min_samples
                    and self._duracion_visible(gid) >= self.min_duration_s):
                self.confirmadas[gid] = self.siguiente_publico
                self.siguiente_publico += 1

    def _debe_muestrear(self, track, fila, timestamp):
        """Decide si vale la pena usar esta vista en el Re-ID, la parte más costosa del pipeline."""
        if timestamp - track.ultimo_muestreo + 1e-8 < self.sample_s:
            return False
        if track.pendientes or track.verificar:
            return True
        if (track.n_muestras < self.tracklet_views_target or not track.vistas.get(track.orientacion())
                or self._n_vistas(track.global_id) < self.identity_views_target):
            return True
        return timestamp - track.ultimo_muestreo + 1e-8 >= self.verify_s

    def _agregar_vista(self, track, vector, timestamp, orientacion, parcial=False):
        """Verifica la vista contra el prototipo; si encaja se suma, si varias seguidas no encajan se corta el tracklet.

        Una vista parcial (con zonas rellenas porque otra persona la tapa) que no encaja se descarta sin más: el relleno
        la aleja del prototipo aunque sea la misma persona, así que no alcanza para decir que cambió la persona."""
        prototipo = track.prototipo()
        if prototipo is not None and track.n_muestras >= 3 and float(vector @ prototipo) < self.split_threshold:
            if parcial:
                return
            track.pendientes.append((timestamp, vector, orientacion))
            if len(track.pendientes) >= self.split_strikes:
                self._partir(track)
            return
        if track.verificar or (track.n_muestras >= self.tracklet_views_target
                               and self._n_vistas(track.global_id) >= self.identity_views_target):
            self.stats["verificaciones"] += 1
        track.pendientes.clear()
        track.verificar = False
        track.guardar_vista(orientacion, vector)
        self.sucias.add(track.global_id)

    def _partir(self, track):
        """Corta el tracklet donde el Re-ID detectó a otra persona y abre uno nuevo."""
        corte = track.pendientes[0][0]
        nuevo = self._nuevo(track.camera_id, track.local_id, corte)
        nuevo.fin_s, nuevo.ultimo_muestreo = track.fin_s, track.ultimo_muestreo
        nuevo.ultimo_vector = track.ultimo_vector
        nuevo.tiempos.extend(t for t in track.tiempos if t >= corte - 1e-9)
        nuevo.huella.extend(h for h in track.huella if h[0] >= corte - 1e-9)
        nuevo.observaciones = len(nuevo.tiempos)
        for _, vector, orientacion in track.pendientes:
            nuevo.guardar_vista(orientacion, vector)
        anteriores = [t for t in track.tiempos if t < corte - 1e-9]
        track.fin_s = anteriores[-1] if anteriores else track.inicio_s
        track.observaciones = max(0, track.observaciones - nuevo.observaciones)
        track.corte_s, track.sucesor = corte, nuevo.uid
        track.pendientes.clear()
        nuevo.posiciones.extend(p for p in track.posiciones if p[0] >= corte - 1e-9)
        track.posiciones = deque((p for p in track.posiciones if p[0] < corte - 1e-9), maxlen=track.posiciones.maxlen)
        for t in (track, nuevo):
            t.primera_posicion = t.posiciones[0] if t.posiciones else None
            t.ultima_posicion = t.posiciones[-1] if t.posiciones else None
        self.stats["cambios_de_persona"] += 1
        self.sucias.add(nuevo.global_id)
        self.enlaces.append({"timestamp_s": corte, "event": "split", "global_id": nuevo.global_id,
                             "absorbed_global_id": track.global_id, "score": None, "average": None,
                             "tracklet_a": track.uid, "tracklet_b": nuevo.uid})

    def _proyectar(self, track, fila, timestamp):
        """Posición en el plano (si la fila trae `punto`) y movimiento de la fila."""
        fila.update(X=None, Y=None, speed=None, direction_deg=None, projection_valid=False)
        punto = fila.get("punto")
        if punto is None:
            return
        actual = (timestamp, float(punto[0]), float(punto[1]))
        if track.ultima_posicion is not None:
            previa = track.ultima_posicion
            if math.dist(actual[1:], previa[1:]) > self.max_speed * (timestamp - previa[0]) + self.max_distance:
                return  # salto imposible: se ignora la posición, no la fila
        track.posiciones.append(actual)
        track.primera_posicion = track.primera_posicion or actual
        track.ultima_posicion = actual
        fila.update(X=actual[1], Y=actual[2], projection_valid=True)
        velocidad = track.movimiento()
        if velocidad is not None:
            fila["speed"] = float(np.hypot(velocidad[0], velocidad[1]))
            if fila["speed"] > 0.05:
                fila["direction_deg"] = float(np.degrees(np.arctan2(velocidad[1], velocidad[0])) % 360.0)


class _GatingFisico:
    """Restricciones de cámara, tiempo y (con posición en el plano) posición, dirección y velocidad."""

    def _fisica(self, a, b):
        """None si a y b no pueden ser la misma persona; si pueden, términos time/pos/dir/vel en [0, 1]."""
        if a.camera_id == b.camera_id:
            if se_solapan(a, b):
                return None
            hueco = max(a.inicio_s, b.inicio_s) - min(a.fin_s, b.fin_s)
            return None if hueco > self.reentry else {"time": 1.0}
        if se_solapan(a, b):
            if frozenset((a.camera_id, b.camera_id)) not in self.solapes:
                return None
            terminos = {"time": 1.0}
            if self.mode == "calibrado" and a.posiciones and b.posiciones:
                clave = tuple(sorted((a.uid, b.uid)))
                pares = []
                for p in list(a.posiciones)[-30:]:
                    q = min(b.posiciones, key=lambda valor: abs(valor[0] - p[0]))
                    if abs(q[0] - p[0]) <= self.tolerance:
                        pares.append((math.dist(p[1:], q[1:]), self.max_distance + self.max_speed * abs(q[0] - p[0])))
                if not pares:
                    return self.evidencia_solapes.get(clave, terminos)
                if any(distancia > limite for distancia, limite in pares):
                    self.evidencia_solapes.pop(clave, None)
                    return None
                terminos["pos"] = max(0.0, 1 - float(np.mean([d / limite for d, limite in pares])))
                self.evidencia_solapes[clave] = terminos.copy()
            return self._movimiento(a, b, terminos)

        origen, destino = (a, b) if a.inicio_s <= b.inicio_s else (b, a)
        borde = self.transiciones.get((origen.camera_id, destino.camera_id))
        dt = destino.inicio_s - origen.fin_s
        if borde is None or not borde["t_min_s"] <= dt <= borde["t_max_s"]:
            return None
        ancho = max(borde["t_max_s"] - borde["t_min_s"], 1e-6) / 2
        terminos = {"time": float(math.exp(-0.5 * ((dt - borde["t_min_s"]) / ancho) ** 2))}
        p, q = origen.ultima_posicion, destino.primera_posicion
        con_posicion = (self.mode == "calibrado" and p is not None and q is not None
                        and abs(origen.fin_s - p[0]) <= self.gap and abs(q[0] - destino.inicio_s) <= self.gap)
        if con_posicion:
            distancia = math.dist(p[1:], q[1:])
            limite = min(borde["max_distance_m"], self.max_speed * dt + self.max_distance)
            if distancia > limite:
                return None
            velocidad = origen.movimiento()
            if velocidad is not None and np.linalg.norm(velocidad) > 0.3 and distancia > self.max_distance:
                delta = np.array(q[1:]) - p[1:]
                if float(velocidad @ delta / (np.linalg.norm(velocidad) * distancia)) < float(borde.get("min_direction_cos", -0.5)):
                    return None
            terminos["pos"] = max(0.0, 1 - distancia / max(limite, 1e-8))
        return self._movimiento(a, b, terminos)

    def _distancia_simultanea(self, a, b):
        """Distancia mediana en el plano entre dos tracklets de cámaras distintas en los instantes en que coinciden, o None."""
        if not a.posiciones or not b.posiciones:
            return None
        distancias = []
        for p in list(a.posiciones)[-30:]:
            q = min(b.posiciones, key=lambda valor: abs(valor[0] - p[0]))
            if abs(q[0] - p[0]) <= self.tolerance:
                distancias.append(math.dist(p[1:], q[1:]))
                clave = (a.uid, b.uid, round(p[0], 2))
                if clave not in self._vistos_rechazo:
                    self._vistos_rechazo.add(clave)
                    self.pares_rechazados.append((a.camera_id, p[1:], b.camera_id, q[1:]))
        return float(np.median(distancias)) if distancias else None

    def _cercania(self, grupo_a, grupo_b):
        """Menor distancia mediana en el plano entre tracklets de cámaras distintas vistos a la vez, o None. No deja huella."""
        mejor = None
        for a in grupo_a:
            for b in grupo_b:
                if a.camera_id == b.camera_id or not se_solapan(a, b) or not a.posiciones or not b.posiciones:
                    continue
                if frozenset((a.camera_id, b.camera_id)) not in self.solapes:
                    continue
                distancias = []
                for p in list(a.posiciones)[-30:]:
                    q = min(b.posiciones, key=lambda valor: abs(valor[0] - p[0]))
                    if abs(q[0] - p[0]) <= self.tolerance:
                        distancias.append(math.dist(p[1:], q[1:]))
                if distancias:
                    mediana = float(np.median(distancias))
                    mejor = mediana if mejor is None else min(mejor, mediana)
        return mejor

    def _anotar_rechazo_geometrico(self, ga, gb):
        """Una pareja con parecido suficiente rechazada por posición: guarda cuánto distan en el plano (diagnóstico)."""
        for a in self._miembros(ga):
            for b in self._miembros(gb):
                if a.camera_id != b.camera_id and se_solapan(a, b) and frozenset((a.camera_id, b.camera_id)) in self.solapes:
                    distancia = self._distancia_simultanea(a, b)
                    if distancia is not None:
                        self.rechazos_geometria[tuple(sorted((a.uid, b.uid)))] = (tuple(sorted((a.camera_id, b.camera_id))), distancia)

    def _movimiento(self, a, b, terminos):
        """Coherencia de velocidad y dirección entre dos tracklets (modo calibrado)."""
        if self.mode != "calibrado":
            return terminos
        va, vb = a.movimiento(), b.movimiento()
        if va is not None and vb is not None:
            sa, sb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
            if max(sa, sb) > self.max_speed:
                return None
            terminos["vel"] = math.exp(-abs(sa - sb) / self.max_speed)
            if min(sa, sb) > 0.3:
                terminos["dir"] = float((np.clip(va @ vb / (sa * sb), -1, 1) + 1) / 2)
        return terminos

    def _compatibles(self, grupo_a, grupo_b):
        """¿Pueden dos identidades ser la misma persona? Solo revisa pares nuevos (a en A, b en B)."""
        for a in grupo_a:
            for b in grupo_b:
                if (se_solapan(a, b) or a.camera_id == b.camera_id) and self._fisica(a, b) is None:
                    return False
        origen = {t.uid: 0 for t in grupo_a} | {t.uid: 1 for t in grupo_b}
        union = sorted(grupo_a + grupo_b, key=lambda t: (t.inicio_s, t.uid))
        for i, miembro in enumerate(union):
            if not i or any(o.fin_s >= miembro.inicio_s - 1e-8 for o in union[:i]):
                continue
            previo = max(union[:i], key=lambda t: t.fin_s)
            if origen[previo.uid] != origen[miembro.uid] and self._fisica(previo, miembro) is None:
                return False
        return True


class _FusionIdentidades:
    """Prototipos multivista, fusiones con emparejamiento mutuo y separación de tracklets en conflicto."""

    def _similitud(self, g1, g2):
        """(centroide, promedio, umbral): prototipo multivista de cada identidad, enlace promedio y umbral aplicable."""
        if self._n_vistas(g1) < self._minimo(g1, g2) or self._n_vistas(g2) < self._minimo(g2, g1):
            return None
        grupo_a, grupo_b = self._con_vistas(g1), self._con_vistas(g2)
        una_camara = len({t.camera_id for t in grupo_a + grupo_b}) == 1
        umbral = self.same_camera_threshold if una_camara else self.threshold
        if not una_camara and self.geometry_relief > 0:
            cercania = self._cercania(grupo_a, grupo_b)
            if cercania is not None and cercania <= self.geometry_close * self.max_distance:
                umbral -= self.geometry_relief      # la misma persona vista a la vez por dos cámaras y en el mismo punto del plano
        suma_a, suma_b = sum(t.suma for t in grupo_a), sum(t.suma for t in grupo_b)
        centroide = float(suma_a @ suma_b / (np.linalg.norm(suma_a) * np.linalg.norm(suma_b) + 1e-12))
        promedio = float((np.stack([t.prototipo() for t in grupo_a]) @ np.stack([t.prototipo() for t in grupo_b]).T).mean())
        return centroide, promedio, umbral

    def _con_vistas(self, gid):
        """Tracklets que aportan al enlace promedio: los que tienen vistas suficientes o, si no hay, todos los que tienen alguna."""
        miembros = [t for t in self._miembros(gid) if t.n_muestras]
        solidos = [t for t in miembros if t.n_muestras >= self.min_query_samples]
        return solidos or miembros

    def _asociar(self):
        """Propone y aplica las fusiones mutuas de las identidades con vistas nuevas."""
        sucias, self.sucias = self.sucias, set()
        self.vigentes = {g for g in self.vigentes if g in self.globales and self._fin(g) >= self.last_timestamp - self.window}
        listas = [g for g in sorted(self.vigentes) if self._n_vistas(g) >= self.min_query_samples]
        por_camara = {}
        for g in listas:
            for track in self._miembros(g):
                por_camara.setdefault(track.camera_id, set()).add(g)
        propuestas = []
        for gb in sorted(g for g in sucias if g in self.globales and self._n_vistas(g) >= self.min_query_samples):
            candidatas = []
            destinos = {t.camera_id for t in self._miembros(gb)}
            relacionadas = set(destinos)
            for destino in destinos:
                relacionadas.update(self.camera_neighbors.get(destino, ()))
            candidatas_grafo = set().union(*(por_camara.get(c, set()) for c in relacionadas))
            self.stats['candidatas_grafo_descartadas'] += len(set(listas) - candidatas_grafo)
            for ga in sorted(candidatas_grafo):
                if ga == gb:
                    continue
                # Descartar imposibilidades temporales antes de multiplicar embeddings.
                # La compuerta geométrica completa sigue aplicándose después.
                from .topology import allowed_groups
                def interval(track):
                    return {'camara': track.camera_id, 't0': track.inicio_s, 't1': track.fin_s}
                if not allowed_groups([interval(a) for a in self._miembros(ga)],
                                      [interval(b) for b in self._miembros(gb)],
                                      self.transiciones, self.solapes, self.reentry):
                    self.stats['candidatas_tiempo_descartadas'] += 1
                    continue
                self.stats['comparaciones_apariencia'] += 1
                similitud = self._similitud(ga, gb)
                if (similitud is None or similitud[0] < similitud[2]
                        or similitud[1] < self.average_threshold + similitud[2] - self.threshold):
                    self.stats['rechazos_apariencia'] += 1
                    continue
                if self._compatibles(self._miembros(ga), self._miembros(gb)):
                    candidatas.append((similitud[0], ga, similitud[1]))
                else:
                    self.stats['rechazos_fisicos'] += 1
                    self._anotar_rechazo_geometrico(ga, gb)
            if not candidatas:
                continue
            candidatas.sort(key=lambda c: -c[0])
            mejor = candidatas[0]
            if any(mejor[0] - c[0] < self.margin and not self._compatibles(self._miembros(mejor[1]), self._miembros(c[1]))
                   for c in candidatas[1:]):
                self.stats["ambiguos"] += 1
                self.dudosas[gb] = self.last_timestamp
                continue
            propuestas.append((mejor[0], gb, mejor[1], mejor[2]))
        if self.mutual:
            mejor_de = {}
            for propuesta in propuestas:
                if propuesta[0] > mejor_de.get(propuesta[2], (-2.0,))[0]:
                    mejor_de[propuesta[2]] = propuesta
            propuestas = [p for p in propuestas if mejor_de[p[2]] is p]
        usadas = set()
        for score, gb, ga, promedio in sorted(propuestas, key=lambda p: -p[0]):
            if gb not in usadas and ga not in usadas and self._fusionar(ga, gb, score, promedio):
                usadas.update((ga, gb))

    def _fusionar(self, g1, g2, score, promedio):
        """Une dos identidades en la más antigua si son físicamente compatibles."""
        if g1 not in self.globales or g2 not in self.globales or g1 == g2:
            return False
        destino, origen = min(g1, g2), max(g1, g2)
        if not self._compatibles(self._miembros(destino), self._miembros(origen)):
            return False
        absorbidos = sorted(self.globales[origen])
        publicos = [self.confirmadas.pop(g) for g in (destino, origen) if g in self.confirmadas]
        if publicos:
            self.confirmadas[destino] = min(publicos)
        for uid in self.globales[origen] | self.globales[destino]:
            track = self.tracklets[uid]
            track.match_score = max(score, track.match_score or -1.0)
            track.global_id = destino
        self.globales[destino] |= self.globales.pop(origen)
        self.vigentes.discard(origen)
        self.vigentes.add(destino)
        self.stats["fusiones"] += 1
        self.enlaces.append({"timestamp_s": self.last_timestamp, "event": "associate", "global_id": destino,
                             "absorbed_global_id": origen, "score": float(score), "average": float(promedio),
                             "tracklet_a": ", ".join(absorbidos), "tracklet_b": None})
        return True

    def _separar_conflictos(self, gids):
        """Separa los tracklets que ya no pueden ser la misma persona."""
        for gid in sorted(gids):
            uids = self.globales.get(gid)
            if not uids or len(uids) < 2:
                continue
            aceptados = []
            for track in sorted((self.tracklets[u] for u in uids), key=lambda t: (t.inicio_s, t.uid)):
                if not any(se_solapan(track, otro) and self._fisica(track, otro) is None for otro in aceptados):
                    aceptados.append(track)
                    continue
                uids.remove(track.uid)
                track.global_id, track.match_score = self.siguiente, None
                self.globales[self.siguiente] = {track.uid}
                self.vigentes.add(self.siguiente)
                self.sucias.add(self.siguiente)
                self.siguiente += 1
                self.stats["separaciones"] += 1
                self.enlaces.append({"timestamp_s": self.last_timestamp, "event": "separate",
                                     "global_id": track.global_id, "absorbed_global_id": gid, "score": None,
                                     "average": None, "tracklet_a": track.uid, "tracklet_b": None})


class _ReportesAsociador:
    """Tablas de lo que sabe la galería: personas contadas, identidades y tracklets."""

    def numeracion_final(self):
        """IDs públicos consecutivos (1..N) por orden de primera aparición de cada persona contada."""
        orden = sorted(self.confirmadas, key=lambda g: (min(self.tracklets[u].inicio_s for u in self.globales[g]), g))
        return {gid: i + 1 for i, gid in enumerate(orden)}

    def resumen(self):
        """Conteos de identidades, tracklets y decisiones del asociador."""
        sin_calibrar = sorted(c.camera_id for c in self.camaras.values() if not c.calibrada)
        return {"mode": self.mode, "geometria_validada": self.mode == "calibrado" and not sin_calibrar,
                "camaras_sin_calibracion": sin_calibrar,
                "identidades_globales": len(set(self.confirmadas.values())),
                "pasadas_breves_no_contadas": len(self.globales) - len(self.confirmadas),
                "tracklets": len(self.tracklets),
                "identidades_multicamara": sum(len({self.tracklets[u].camera_id for u in self.globales[g]}) > 1
                                               for g in self.confirmadas), **self.stats}

    def galeria(self, numeracion=None):
        """Metadata compartida por todas las cámaras: qué se sabe de cada persona contada."""
        numeracion = self.confirmadas if numeracion is None else numeracion
        filas = []
        for gid, publico in sorted(numeracion.items(), key=lambda kv: kv[1]):
            miembros = self._miembros(gid)
            orientaciones = {o: 0 for o in ("F", "E", "C", "?")}
            por_camara = {}
            for t in miembros:
                por_camara[t.camera_id] = por_camara.get(t.camera_id, 0) + t.n_muestras
                for o, cantidad in t.vistas.items():
                    orientaciones[o] += cantidad
            ultimo = max(miembros, key=lambda t: t.fin_s)
            filas.append({"global_id": publico, "vistas": sum(por_camara.values()), "vistas_por_camara": por_camara,
                          "frente": orientaciones["F"], "espalda": orientaciones["E"], "costado": orientaciones["C"],
                          "quieto": orientaciones["?"], "segundos_visible": round(self._duracion_visible(gid), 1),
                          "ultima_camara": ultimo.camera_id, "ultima_vez_s": round(ultimo.fin_s, 2)})
        return filas

    def identidades(self, numeracion=None):
        """Tracklets, cámaras e intervalo de cada persona contada."""
        numeracion = self.confirmadas if numeracion is None else numeracion
        return [{"global_id": publico, "global_uuid": self.global_uuid(publico),
                 "camaras": sorted({self.tracklets[u].camera_id for u in self.globales[gid]}),
                 "tracklets": sorted(self.globales[gid]),
                 "inicio_s": min(self.tracklets[u].inicio_s for u in self.globales[gid]),
                 "fin_s": max(self.tracklets[u].fin_s for u in self.globales[gid])}
                for gid, publico in sorted(numeracion.items(), key=lambda kv: kv[1])]

    def tabla_tracklets(self, numeracion=None):
        """Una fila por tracklet con su identidad y sus muestras."""
        numeracion = self.confirmadas if numeracion is None else numeracion
        return [{"tracklet_id": t.tracklet_uuid, "tracklet": t.uid, "camera_id": t.camera_id, "local_id": t.local_id,
                 "global_id": numeracion.get(t.global_id), "contado": t.global_id in numeracion,
                 "inicio_s": t.inicio_s, "fin_s": t.fin_s, "observations": t.observaciones, "samples": t.n_muestras,
                 "frente": t.vistas.get("F", 0), "espalda": t.vistas.get("E", 0),
                 "costado": t.vistas.get("C", 0), "entry": t.primera_posicion, "exit": t.ultima_posicion,
                 "association_score": t.match_score}
                for t in self.tracklets.values()]

    def prototipos(self):
        """Prototipo Re-ID de cada tracklet con vistas (lo usa la reagrupación con el mapa)."""
        return {uid: t.prototipo() for uid, t in self.tracklets.items() if t.suma is not None}


class AsociadorMulticamara(_GaleriaCompartida, _ObservacionesReID, _GatingFisico, _FusionIdentidades, _ReportesAsociador):
    """Asigna global_id a las filas locales de todas las cámaras con una galería compartida y Re-ID.

    `encoder` es opcional: callable que recibe una lista de recortes BGR y devuelve vectores (n, d).
    Sin encoder solo se usan los `embedding` que traigan las filas.
    """

    def __init__(self, encoder, config):
        self.config, self.camaras, self.transiciones, self.solapes = cargar_registro(config)
        self.camera_neighbors = {cid: set() for cid in self.camaras}
        for source, target in self.transiciones:
            self.camera_neighbors[source].add(target)
            self.camera_neighbors[target].add(source)
        for pair in self.solapes:
            for cid in pair:
                self.camera_neighbors[cid].update(pair - {cid})
        ajustes = self.config.get("association", {})
        self.mode = self.config.get("mode", "calibrado")
        self.encoder = encoder
        self.sample_s = float(ajustes.get("sample_interval_s", 0.4))
        self.tracklet_views_target = int(ajustes.get("tracklet_views_target", 8))
        self.identity_views_target = int(ajustes.get("identity_views_target", 30))
        self.verify_s = float(ajustes.get("verify_interval_s", 2.0))
        self.min_samples = int(ajustes.get("min_samples", 5))
        self.min_query_samples = int(ajustes.get("min_query_samples", 3))
        self.min_duration_s = float(ajustes.get("min_identity_duration_s", 2.0))
        self.threshold = float(ajustes.get("threshold", 0.60))
        self.average_threshold = float(ajustes.get("average_threshold", 0.55))
        self.same_camera_threshold = float(ajustes.get("same_camera_threshold", 0.70))
        self.margin = float(ajustes.get("ambiguity_margin", 0.05))
        self.geometry_relief = float(ajustes.get("geometry_relief", 0.0))
        self.geometry_close = float(ajustes.get("geometry_close", 0.6))
        self.mutual = bool(ajustes.get("mutual_best", True))
        self.split_threshold = float(ajustes.get("split_threshold", 0.40))
        self.split_strikes = int(ajustes.get("split_strikes", 2))
        self.window = float(ajustes.get("candidate_window_s", 90))
        self.reentry = float(ajustes.get("reentry_window_s", 120))
        self.gap = float(ajustes.get("tracklet_gap_s", 2))
        self.tolerance = float(ajustes.get("sync_tolerance_s", 0.15))
        self.max_distance = float(ajustes.get("overlap_distance_m", 1.5))
        self.max_speed = float(ajustes.get("max_speed_m_s", 4))
        self.quality = dict(min_conf=float(ajustes.get("min_conf", 0.55)),
                            min_alto=float(ajustes.get("min_height", 40)),
                            max_iou=float(ajustes.get("max_occlusion", 0.2)),
                            margen_borde=int(ajustes.get("edge_margin", 4)),
                            min_visible=None if ajustes.get("min_visible") is None else float(ajustes["min_visible"]))
        if self.quality["min_visible"] is not None and not 0 < self.quality["min_visible"] <= 1:
            raise ValueError("min_visible debe estar entre 0 y 1 (o ausente para usar max_occlusion).")
        if (not 1 <= self.min_query_samples <= self.min_samples or self.split_strikes < 1
                or self.tracklet_views_target < 1 or self.identity_views_target < 1 or self.min_duration_s < 0
                or any(not np.isfinite(v) or v <= 0 for v in (self.sample_s, self.verify_s, self.window, self.reentry,
                                                              self.gap, self.tolerance, self.max_distance, self.max_speed))):
            raise ValueError("Parámetros temporales, de muestras o físicos inválidos.")
        if not (np.isfinite(self.geometry_relief) and 0 <= self.geometry_relief <= 0.5 and np.isfinite(self.geometry_close) and 0 < self.geometry_close <= 1):
            raise ValueError("geometry_relief debe estar entre 0 y 0.5 y geometry_close entre 0 y 1.")
        if any(not np.isfinite(v) or not -1 <= v <= 1 for v in (
                self.threshold, self.average_threshold, self.same_camera_threshold, self.margin, self.split_threshold)):
            raise ValueError("Los umbrales de similitud deben estar entre -1 y 1.")
        self.reiniciar()
