"""Memoria de apariencia de largo plazo: la misma persona conserva su ID anónimo al reaparecer.

El AsociadorMulticamara une a una persona entre cámaras y en regresos cortos dentro de una sesión
(ventana de `candidate_window_s`). Esta capa le agrega memoria entre sesiones:

* Una identidad nueva se compara con todas las personas ya vistas (prototipo Re-ID y enlace promedio
  de sus tramos, con los mismos umbrales del asociador). Si coincide sin ambigüedad recupera su ID;
  solo si no coincide con nadie recibe uno nuevo.
* Si un ID recién creado resulta ser alguien ya visto (al juntar más vistas), se fusionan y queda el antiguo.
* Mientras una persona no tiene ID se toma una vista cada tick (sin esperar `sample_interval_s`) para
  reconocer en menos de un segundo a quien ya se vio.
* Se compara en RAM (una multiplicación de matrices por consulta). La escritura ocurre en un hilo
  aparte: PostgreSQL en instalaciones migradas, SQLite en modo local. Un fallo de escritura
  desactiva la persistencia de esa memoria y se informa en su estado; la inferencia sigue en RAM.

Qué se guarda: vectores de apariencia (no rostros ni imágenes), cuándo y en qué cámara se vio. Nada que
diga quién es la persona. La retención es configurable (1 a 168 h, 24 por defecto), se purga sola y
`purgar_todo()` borra todo al instante. Los vectores de un encoder distinto no se mezclan.

Portado de AeroVision (Test Modelo/memoria_identidades.py): sin servidor HTTP externo, sin género.
"""
import json
import math
import sqlite3
import threading
import time
from pathlib import Path

import numpy as np

from .associator import AsociadorMulticamara

DIMENSION = 512
MAX_VISTAS = 16           # prototipos de tramo guardados por persona (enlace promedio)
ESCRIBIR_CADA_S = 2.0     # una persona que cambia se escribe en la base como mucho cada 2 s
PURGAR_CADA_S = 600.0     # revisión periódica de la retención
REGRESO_S = 30.0          # sin verse más que esto, volver a verla cuenta como una reaparición
REVISAR_NUEVAS_S = 60.0   # durante este tiempo un ID nuevo se sigue comparando con los antiguos
REVISAR_CADA_S = 2.0
MUESTREO_INICIAL_S = 0.1  # una vista cada 0,1 s mientras la persona no tiene ID
DURACION_NUEVA_S = 1.0    # visible este tiempo sin parecerse a nadie: recibe un ID nuevo
ESPERA_DUDA_S = 3.0       # si se parece a alguien ya visto, se espera hasta aquí antes de darle un ID nuevo
DUDA = 0.1                # a menos de esto del umbral, una persona ya vista es «parecida»
MIN_RETENCION_H, MAX_RETENCION_H = 1, 168

ESQUEMA = """
CREATE TABLE IF NOT EXISTS appearance_meta (clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS appearance_people (
    id INTEGER PRIMARY KEY, suma BLOB NOT NULL, muestras INTEGER NOT NULL, camaras TEXT,
    apariciones INTEGER NOT NULL, primera_vez REAL NOT NULL, ultima_vez REAL NOT NULL);
CREATE TABLE IF NOT EXISTS appearance_views (
    persona INTEGER NOT NULL, tramo TEXT NOT NULL, camara TEXT, prototipo BLOB NOT NULL, muestras INTEGER NOT NULL,
    PRIMARY KEY (persona, tramo));
CREATE INDEX IF NOT EXISTS idx_appearance_last ON appearance_people (ultima_vez);
"""


def limitar_retencion(horas):
    """Retención en horas, acotada a [1, 168]; 24 si el valor no es válido."""
    try:
        horas = float(horas)
    except (TypeError, ValueError):
        horas = 24.
    return max(MIN_RETENCION_H, min(horas, MAX_RETENCION_H))


def _normal(vector):
    return vector / (np.linalg.norm(vector) + 1e-12)


def _blob(vector):
    return np.asarray(vector, dtype="<f4").tobytes()


def _vector(blob):
    return np.frombuffer(blob, dtype="<f4").astype(np.float32)


class Persona:
    """Alguien ya visto: suma de sus vistas Re-ID, prototipos de sus tramos, cámaras y horas."""

    def __init__(self, pid, suma, muestras, primera_vez, ultima_vez, camaras=(), vistas=None, apariciones=1):
        self.id, self.suma, self.muestras = pid, np.asarray(suma, np.float32), int(muestras)
        self.primera_vez, self.ultima_vez = primera_vez, ultima_vez
        self.camaras, self.vistas = set(camaras), dict(vistas or {})  # tramo -> (camara, prototipo, muestras)
        self.apariciones = int(apariciones)
        self.vistas_sucias = vistas is None  # una persona nueva manda sus vistas; una cargada ya las tiene
        self._banco = None

    def banco(self):
        """Prototipos de sus tramos (o su prototipo único si no tiene)."""
        if self._banco is None:
            prototipos = [prototipo for _, prototipo, _ in self.vistas.values()]
            self._banco = np.stack(prototipos) if prototipos else _normal(self.suma)[None]
        return self._banco


class MemoriaApariencia:
    """Personas ya vistas, comparadas en RAM y guardadas en SQLite en segundo plano.

    Todo cambio ocurre en el hilo del modelo; el hilo escritor solo lee (con el candado) y escribe en el disco.
    `ruta=None` deja la memoria solo en RAM (dura lo que dure el proceso).
    """

    def __init__(self, ruta=None, asociacion=None, dimension=DIMENSION, encoder="osnet", retencion_horas=24):
        asociacion = asociacion or {}
        umbral = float(asociacion.get("threshold", 0.6))
        promedio = float(asociacion.get("average_threshold", 0.55))
        misma = float(asociacion.get("same_camera_threshold", 0.7))
        # (centroide, promedio) mínimos: más estrictos si todo se vio con una sola cámara, como en el asociador.
        self.umbrales = {False: (umbral, promedio), True: (misma, promedio + misma - umbral)}
        self.margen = float(asociacion.get("ambiguity_margin", 0.05))
        self.min_muestras = int(asociacion.get("min_query_samples", 4))
        self.dimension, self.encoder = int(dimension), str(encoder)
        self.retencion_s = limitar_retencion(retencion_horas) * 3600
        self.personas, self.siguiente, self.persistente = {}, 1, False
        self.epoca = 0  # sube con purgar_todo(): quien la consulte sabe que debe olvidar
        self.error = None
        self.backend = 'RAM'
        self._ids, self._matriz, self._fila = [], np.zeros((0, self.dimension), np.float32), {}
        self._hay = threading.Condition()
        self._db_lock = threading.Lock()
        self._pendientes, self._cerrado = {}, False
        self._ultima_purga = 0.
        self._con, self._hilo = None, None
        if ruta is not None:
            self._abrir(Path(ruta))

    # ---------- Base (SQLite) ----------

    def _abrir(self, ruta):
        """Abre la base y carga lo vigente. Un fallo deja la memoria solo en RAM, sin detener nada."""
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            from storage.operational import appearance_connect
            self._con = appearance_connect(ruta, self.encoder, self.dimension)
            self.backend = 'PostgreSQL' if self._con is not None else 'SQLite'
            if self._con is None:
                self._con = sqlite3.connect(str(ruta), check_same_thread=False)
            self._con.executescript(ESQUEMA)
            meta = dict(self._con.execute("SELECT clave, valor FROM appearance_meta").fetchall())
            if meta and (meta.get("encoder") != self.encoder or meta.get("dimension") != str(self.dimension)):
                # Vectores de otro encoder no se pueden comparar: se descartan, no se mezclan.
                self._con.executescript("DELETE FROM appearance_people; DELETE FROM appearance_views;")
                meta = {}
            self._con.executemany("INSERT OR REPLACE INTO appearance_meta VALUES (?,?)",
                                  [("encoder", self.encoder), ("dimension", str(self.dimension))])
            self._con.commit()
            limite = time.time() - self.retencion_s
            self._con.execute("DELETE FROM appearance_views WHERE persona IN (SELECT id FROM appearance_people WHERE ultima_vez < ?)", (limite,))
            self._con.execute("DELETE FROM appearance_people WHERE ultima_vez < ?", (limite,))
            self._con.commit()
            vistas = {}
            for persona, tramo, camara, proto, n in self._con.execute("SELECT persona, tramo, camara, prototipo, muestras FROM appearance_views"):
                vistas.setdefault(persona, {})[tramo] = (camara, _vector(proto), n)
            for pid, suma, muestras, camaras, apariciones, primera, ultima in self._con.execute(
                    "SELECT id, suma, muestras, camaras, apariciones, primera_vez, ultima_vez FROM appearance_people"):
                self.personas[pid] = Persona(pid, _vector(suma), muestras, primera, ultima, json.loads(camaras or "[]"),
                                             vistas.get(pid, {}), apariciones)
            maximo = self._con.execute("SELECT MAX(id) FROM appearance_people").fetchone()[0] or 0
            guardado = int(meta.get("siguiente", 1)) if meta else 1
            self.siguiente = max(maximo + 1, guardado)
            self._reconstruir()
            self.persistente = True
            self._hilo = threading.Thread(target=self._escribir, daemon=True, name="memoria-apariencia")
            self._hilo.start()
        except Exception as exc:
            from storage.operational import is_database_error
            if not isinstance(exc, (OSError, sqlite3.Error, ValueError)) and not is_database_error(exc):
                raise
            self.error = f"Memoria de apariencia solo en RAM: {type(exc).__name__}"
            if self._con is not None:
                self._con.close()
            self.persistente, self._con = False, None

    def _marcar(self, pid, operacion="guardar"):
        if self.persistente:
            with self._hay:
                self._pendientes[pid] = operacion

    def _escribir(self):
        """Hilo escritor: cada ESCRIBIR_CADA_S guarda lo que cambió y cada PURGAR_CADA_S aplica la retención."""
        while True:
            with self._hay:
                if not self._cerrado:
                    self._hay.wait(timeout=ESCRIBIR_CADA_S)
                cerrado, epoca = self._cerrado, self.epoca
                lote, self._pendientes = self._pendientes, {}
                fotos = {}
                for pid, operacion in lote.items():
                    persona = self.personas.get(pid)
                    if operacion == "guardar" and persona is not None and persona.muestras > 0:
                        vistas = [(pid, t, c, _blob(p), n) for t, (c, p, n) in persona.vistas.items()] if persona.vistas_sucias else None
                        fotos[pid] = ((pid, _blob(persona.suma), persona.muestras, json.dumps(sorted(persona.camaras)[-16:]),
                                       persona.apariciones, persona.primera_vez, max(persona.ultima_vez, persona.primera_vez)), vistas)
                        persona.vistas_sucias = False
                siguiente = self.siguiente
            try:
                with self._db_lock:
                    if epoca == self.epoca and self._con is not None:
                        for pid, operacion in lote.items():
                            if operacion == "borrar":
                                self._con.execute("DELETE FROM appearance_views WHERE persona=?", (pid,))
                                self._con.execute("DELETE FROM appearance_people WHERE id=?", (pid,))
                            elif pid in fotos:
                                fila, vistas = fotos[pid]
                                self._con.execute("INSERT OR REPLACE INTO appearance_people VALUES (?,?,?,?,?,?,?)", fila)
                                if vistas is not None:
                                    self._con.execute("DELETE FROM appearance_views WHERE persona=?", (pid,))
                                    self._con.executemany("INSERT INTO appearance_views VALUES (?,?,?,?,?)", vistas)
                        self._con.execute("INSERT OR REPLACE INTO appearance_meta VALUES (?, ?)", ('siguiente', str(siguiente)))
                        self._con.commit()
            except sqlite3.Error as exc:
                self.error, self.persistente = f"Memoria de apariencia solo en RAM: {exc}", False
                return
            if cerrado and not self._pendientes:
                return
            if time.time() - self._ultima_purga >= PURGAR_CADA_S:
                self.purgar()

    def cerrar(self):
        """Escribe lo pendiente y cierra la base antes de salir."""
        if self._hilo is not None:
            with self._hay:
                self._cerrado = True
                self._hay.notify()
            self._hilo.join(timeout=15)
        with self._db_lock:
            if self._con is not None:
                try:
                    self._con.close()
                except sqlite3.Error:
                    pass
                self._con = None

    # ---------- Retención y borrado ----------

    def purgar(self, ahora=None):
        """Quita de la RAM y de la base a quien no se vio en `retencion_horas`. Devuelve cuántas personas."""
        ahora = time.time() if ahora is None else ahora
        limite = ahora - self.retencion_s
        with self._hay:
            vencidas = [pid for pid, p in self.personas.items() if p.ultima_vez < limite]
            for pid in vencidas:
                del self.personas[pid]
            if vencidas:
                self._reconstruir()
        self._ultima_purga = ahora
        for pid in vencidas:
            self._marcar(pid, "borrar")
        return len(vencidas)

    def purgar_todo(self):
        """Borrado inmediato de todo lo guardado (derecho de supresión). Los IDs vuelven a empezar en 1."""
        with self._hay:
            cantidad = len(self.personas)
            self.personas.clear()
            self._pendientes.clear()
            self.siguiente, self.epoca = 1, self.epoca + 1
            self._reconstruir()
        with self._db_lock:
            if self._con is not None:
                try:
                    self._con.executescript("DELETE FROM appearance_views; DELETE FROM appearance_people;")
                    self._con.execute("INSERT OR REPLACE INTO appearance_meta VALUES (?,?)", ('siguiente','1'))
                    self._con.commit()
                except sqlite3.Error as exc:
                    self.error = f"No se pudo vaciar la base: {exc}"
        return cantidad

    def resumen(self):
        """Estado público de la memoria: cuántas personas, retención y si persiste en disco."""
        return {"personas": len(self.personas), "retencionHoras": self.retencion_s / 3600,
                "persistente": self.persistente, "backend": self.backend, "encoder": self.encoder, "error": self.error}

    # ---------- Comparación en RAM ----------

    def _reconstruir(self):
        self._ids = [pid for pid, p in self.personas.items() if p.muestras > 0]
        self._fila = {pid: i for i, pid in enumerate(self._ids)}
        self._matriz = (np.stack([_normal(self.personas[pid].suma) for pid in self._ids])
                        if self._ids else np.zeros((0, self.dimension), np.float32))

    def reconocer(self, suma, prototipos, camaras, ocupadas=(), ignorar=()):
        """(id de la persona ya vista que coincide sin ambigüedad o None, duda).

        Hay duda si alguna quedó cerca del umbral, si hay dos parecidas o si la mejor la ve ahora otra cámara
        (`ocupadas`: ahí decide el asociador de la sesión). Con duda conviene juntar más vistas antes de dar
        un ID nuevo. `ignorar` se salta del todo.
        """
        with self._hay:   # el hilo escritor puede purgar y reconstruir la matriz mientras se consulta
            return self._reconocer(suma, prototipos, camaras, ocupadas, ignorar)

    def _reconocer(self, suma, prototipos, camaras, ocupadas, ignorar):
        if not self._ids:
            return None, False
        # Filtrar antes del top-k: una identidad excluida no debe desplazar
        # candidatas válidas ni ocultar la segunda mejor (ambigüedad).
        filas = [i for i, pid in enumerate(self._ids) if pid not in ignorar
                 and self.personas[pid].muestras >= self.min_muestras]
        if not filas:
            return None, False
        similitudes = self._matriz[filas] @ _normal(np.asarray(suma, np.float32))
        candidatas, duda = [], False
        for i in np.argsort(-similitudes)[:8]:
            pid = self._ids[filas[i]]
            persona = self.personas.get(pid)
            if persona is None or pid in ignorar or persona.muestras < self.min_muestras:
                continue
            centroide = float(similitudes[i])
            minimo, minimo_promedio = self.umbrales[len(set(camaras) | persona.camaras) == 1]
            if centroide < minimo:
                duda |= centroide >= minimo - DUDA
                continue
            promedio = float((prototipos @ persona.banco().T).mean())
            if promedio >= minimo_promedio:
                candidatas.append((centroide, pid, promedio))
            else:
                duda |= promedio >= minimo_promedio - DUDA
        if not candidatas:
            return None, duda
        candidatas.sort(reverse=True)
        mejor = candidatas[0]
        if mejor[1] in ocupadas or (len(candidatas) > 1 and mejor[0] - candidatas[1][0] < self.margen):
            return None, True
        return mejor[1], False

    # ---------- Cambios (hilo del modelo) ----------

    def nueva(self, ahora):
        with self._hay:
            pid = self.siguiente
            self.siguiente += 1
            self.personas[pid] = Persona(pid, np.zeros(self.dimension, np.float32), 0, ahora, ahora)
        return pid

    def sumar(self, pid, delta, muestras, camara, ahora):
        persona = self.personas.get(pid)
        if persona is None:   # purgada por la retención mientras se la reforzaba
            return
        with self._hay:
            persona.suma = persona.suma + np.asarray(delta, np.float32)
            persona.muestras += int(muestras)
            persona.camaras.add(camara)
            persona.ultima_vez = ahora
            if pid in self._fila:
                self._matriz[self._fila[pid]] = _normal(persona.suma)
            else:
                self._reconstruir()
        self._marcar(pid)

    def vista(self, pid, tramo, camara, prototipo, muestras):
        persona = self.personas.get(pid)
        if persona is None:
            return
        with self._hay:
            persona.vistas.pop(tramo, None)
            persona.vistas[tramo] = (camara, np.asarray(prototipo, np.float32), int(muestras))
            while len(persona.vistas) > MAX_VISTAS:
                persona.vistas.pop(next(iter(persona.vistas)))
            persona._banco, persona.vistas_sucias = None, True
        self._marcar(pid)

    def visto(self, pid, ahora):
        persona = self.personas.get(pid)
        if persona is not None and ahora - persona.ultima_vez >= 1:
            persona.ultima_vez = ahora
            self._marcar(pid)

    def reaparecio(self, pid):
        persona = self.personas.get(pid)
        if persona is not None:
            persona.apariciones += 1
            self._marcar(pid)

    def fusionar(self, queda, sale):
        """`sale` era la misma persona que `queda`: se juntan en `queda` (el ID más antiguo)."""
        with self._hay:
            if queda not in self.personas or sale not in self.personas:
                return
            a, b = self.personas[queda], self.personas.pop(sale)
            a.suma, a.muestras = a.suma + b.suma, a.muestras + b.muestras
            a.camaras |= b.camaras
            a.primera_vez, a.ultima_vez = min(a.primera_vez, b.primera_vez), max(a.ultima_vez, b.ultima_vez)
            a.apariciones = max(a.apariciones, b.apariciones)
            for tramo, vista in b.vistas.items():
                a.vistas.setdefault(tramo, vista)
            while len(a.vistas) > MAX_VISTAS:
                a.vistas.pop(next(iter(a.vistas)))
            a._banco, a.vistas_sucias = None, True
            self._reconstruir()
        self._marcar(queda)
        self._marcar(sale, "borrar")


class AsociadorConMemoria(AsociadorMulticamara):
    """AsociadorMulticamara cuyos IDs públicos son los de la memoria de apariencia."""

    def __init__(self, encoder, config, memoria, reloj=time.time):
        self.memoria, self.reloj = memoria, reloj
        super().__init__(encoder, config)

    def reiniciar(self, session_uuid=None):
        super().reiniciar(session_uuid)
        self.reiniciar_numeracion()

    def reiniciar_numeracion(self):
        """Olvida qué persona es cada identidad de la sesión (al vaciarse la memoria se vuelve a numerar desde 1)."""
        self.confirmadas.clear()
        self._aportes = {}     # uid del tramo -> (muestras, suma) ya sumadas a su persona
        self._creadas = {}     # IDs creados en esta sesión -> instante (se siguen revisando un rato)
        self._revisado = {}
        self.reconocidas = set()
        self._epoca = self.memoria.epoca

    def personas_contadas(self):
        return len(set(self.confirmadas.values()))

    def _grupo(self, gid):
        grupo = self._con_vistas(gid)
        return (np.sum([t.suma for t in grupo], axis=0), np.stack([t.prototipo() for t in grupo]),
                {t.camera_id for t in grupo})

    def _ocupadas(self, excepto=None):
        """Personas que otra identidad visible ahora (o hace < tracklet_gap_s) ya tiene asignadas."""
        limite = self.last_timestamp - self.gap
        return {pid for gid, pid in self.confirmadas.items()
                if gid != excepto and gid in self.globales and self._fin(gid) >= limite}

    def _confirmar(self, gids):
        """Da a cada identidad el ID de la persona que ya se vio o, si no coincide con nadie, uno nuevo."""
        if self.memoria.epoca != self._epoca:
            self.reiniciar_numeracion()
        ahora = self.reloj()
        ocupadas = None
        for gid in sorted(gids):
            if gid not in self.globales:
                continue
            pid = self.confirmadas.get(gid)
            if pid is not None and pid not in self.memoria.personas:
                del self.confirmadas[gid]
                pid = None
            if pid is None:
                if ocupadas is None:
                    ocupadas = self._ocupadas()
                pid = self._identificar(gid, ocupadas, ahora)
                if pid is None:
                    continue
                ocupadas.add(pid)
            self._reforzar(gid, pid, ahora)
            self._revisar(gid, ahora)

    def _debe_muestrear(self, track, fila, timestamp):
        """Mientras la persona no tiene ID, una vista por tick para reconocerla en el primer segundo."""
        if track.global_id not in self.confirmadas:
            return timestamp - track.ultimo_muestreo + 1e-8 >= MUESTREO_INICIAL_S
        return super()._debe_muestrear(track, fila, timestamp)

    def _fuera_del_grafo(self, camaras, ahora, gid=None):
        """No recuperar IDs de componentes desconectados ni memoria ya vencida.

        La memoria histórica no tiene tiempo de contenido por cámara: aquí se
        aplica conectividad dirigida; el motor de sesión valida los tránsitos.
        """
        origenes = set(camaras)
        pendientes = list(camaras)
        while pendientes:
            destino = pendientes.pop()
            anteriores = {a for a, b in self.transiciones if b == destino}
            for par in self.solapes:
                if destino in par:
                    anteriores.update(par)
            for origen in anteriores - origenes:
                origenes.add(origen)
                pendientes.append(origen)
        excluidas = {pid for pid, p in self.memoria.personas.items()
                if not p.camaras.intersection(origenes) or ahora - p.ultima_vez > self.memoria.retencion_s}
        if gid is not None:
            for otra, pid in self.confirmadas.items():
                if otra != gid and otra in self.globales:
                    # En la misma cámara la memoria permite regresos largos;
                    # la ventana corta solo gobierna las transiciones entre cámaras.
                    pares = [(x, y) for x in self._miembros(gid) for y in self._miembros(otra)]
                    if any((x.camera_id != y.camera_id or max(x.inicio_s, y.inicio_s) <= min(x.fin_s, y.fin_s))
                           and self._fisica(x, y) is None for x, y in pares):
                        excluidas.add(pid)
        return excluidas

    def _identificar(self, gid, ocupadas, ahora):
        if self._n_vistas(gid) < self.min_query_samples:
            return None
        suma, prototipos, camaras = self._grupo(gid)
        pid, duda = self.memoria.reconocer(suma, prototipos, camaras, ocupadas=ocupadas,
                                         ignorar=self._fuera_del_grafo(camaras, ahora, gid))
        persona = self.memoria.personas.get(pid) if pid is not None else None
        if persona is not None:
            self.confirmadas[gid] = pid
            if ahora - persona.ultima_vez > REGRESO_S:
                self.reconocidas.add(pid)
                self.memoria.reaparecio(pid)
            return pid
        espera = ESPERA_DUDA_S if duda else DURACION_NUEVA_S
        if self._n_vistas(gid) >= self.min_samples and self._duracion_visible(gid) >= espera:
            pid = self.memoria.nueva(ahora)
            self.confirmadas[gid] = pid
            self._creadas[pid] = self.last_timestamp
            return pid
        return None

    def _reforzar(self, gid, pid, ahora):
        """Suma a la persona las vistas nuevas de sus tramos y guarda el prototipo de cada tramo."""
        for t in self._miembros(gid):
            if t.suma is None:
                continue
            muestras, suma = self._aportes.get(t.uid, (0, None))
            if t.n_muestras <= muestras:
                continue
            self.memoria.sumar(pid, t.suma if suma is None else t.suma - suma, t.n_muestras - muestras, t.camera_id, ahora)
            self._aportes[t.uid] = (t.n_muestras, t.suma.copy())
            if t.n_muestras >= self.min_query_samples:
                self.memoria.vista(pid, f"{self.session_uuid}/{t.uid}", t.camera_id, t.prototipo(), t.n_muestras)
        self.memoria.visto(pid, ahora)

    def _revisar(self, gid, ahora):
        """Un ID recién creado se sigue comparando con los antiguos: si era alguien ya visto, queda el antiguo."""
        pid = self.confirmadas.get(gid)
        creada = self._creadas.get(pid)
        if (creada is None or self.last_timestamp - creada > REVISAR_NUEVAS_S
                or self.last_timestamp - self._revisado.get(gid, -math.inf) < REVISAR_CADA_S):
            return
        self._revisado[gid] = self.last_timestamp
        suma, prototipos, camaras = self._grupo(gid)
        antigua, _ = self.memoria.reconocer(suma, prototipos, camaras, ocupadas=self._ocupadas(excepto=gid),
                                          ignorar={pid} | self._fuera_del_grafo(camaras, ahora, gid))
        if antigua is None or antigua > pid or antigua not in self.memoria.personas:
            return
        regreso = ahora - self.memoria.personas[antigua].ultima_vez > REGRESO_S
        self._unir_personas(antigua, pid)
        if regreso:
            self.reconocidas.add(antigua)
            self.memoria.reaparecio(antigua)

    def _unir_personas(self, queda, sale):
        self.memoria.fusionar(queda, sale)
        for gid, pid in list(self.confirmadas.items()):
            if pid == sale:
                self.confirmadas[gid] = queda
        self._creadas.pop(sale, None)
        self.reconocidas.discard(sale)

    def _fusionar(self, g1, g2, score, promedio):
        """Al unir dos identidades de la sesión, sus personas también se unen en la memoria (queda la más antigua)."""
        personas = {self.confirmadas.get(g1), self.confirmadas.get(g2)} - {None}
        if not super()._fusionar(g1, g2, score, promedio):
            return False
        if len(personas) == 2:
            self._unir_personas(min(personas), max(personas))
        return True
