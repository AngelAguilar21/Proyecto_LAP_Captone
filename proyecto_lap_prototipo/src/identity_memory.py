"""Memoria de identidad temporal: posición, ropa y aspecto físico, sin identidad.

Guarda, por cada ID temporal de una sesión (P00001, P00002...), su posición en
el plano, una firma de color de ropa y medidas físicas aproximadas (tamaño del
recuadro y estatura estimada). No guarda rostros, imágenes, nombres ni datos
biométricos, y el ID se reinicia en cada sesión, así que no permite reconocer a
la misma persona otro día.

La retención es corta y automática: al abrir la base y de forma periódica se
borran las filas más antiguas que `retention_hours`.
"""
import sqlite3
import threading
import time
from pathlib import Path

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_observations (
    session TEXT NOT NULL,
    pid TEXT NOT NULL,
    camera TEXT NOT NULL,
    t REAL NOT NULL,
    x REAL,
    y REAL,
    association TEXT,
    color BLOB,
    box_w REAL,
    box_h REAL,
    height_m REAL,
    speed REAL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_session ON identity_observations (session, pid, t);
CREATE INDEX IF NOT EXISTS idx_identity_created ON identity_observations (created);
"""

MIN_RETENTION_HOURS, MAX_RETENTION_HOURS = 1, 168


def encode_signature(color):
    """Comprime el histograma a float16: suficiente para comparar y ocupa la mitad."""
    if color is None:
        return None
    return np.asarray(color, dtype=np.float16).ravel().tobytes()


def decode_signature(blob):
    return None if blob is None else np.frombuffer(blob, dtype=np.float16).astype(np.float32)


def clamp_retention(hours):
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        hours = 24.
    return max(MIN_RETENTION_HOURS, min(hours, MAX_RETENTION_HOURS))


class IdentityMemory:
    def __init__(self, path, retention_hours=24, sample_interval=1.0, purge_every=600.):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.retention_seconds = clamp_retention(retention_hours) * 3600
        self.sample_interval = max(.1, float(sample_interval))
        self.purge_every = purge_every
        self._lock = threading.Lock()
        self._last = {}
        self._last_purge = 0.
        self.enabled = True
        self.con = sqlite3.connect(str(path), check_same_thread=False)
        self.con.executescript(SCHEMA)
        self.purge()

    def purge(self, now=None):
        """Borra lo que superó la retención. Devuelve las filas eliminadas."""
        now = time.time() if now is None else now
        with self._lock:
            cursor = self.con.execute('DELETE FROM identity_observations WHERE created < ?', (now - self.retention_seconds,))
            self.con.commit()
        self._last_purge = now
        return cursor.rowcount

    def purge_all(self):
        """Borrado inmediato de todo lo almacenado (derecho de supresión)."""
        with self._lock:
            cursor = self.con.execute('DELETE FROM identity_observations')
            self.con.commit()
        self._last.clear()
        return cursor.rowcount

    def record(self, session, people, store, t, now=None):
        """Guarda una muestra por persona como máximo cada `sample_interval` segundos.

        `people` son las filas que devuelve IdentityStore.update y `store` aporta
        la firma de color suavizada. Un fallo de disco desactiva la memoria pero
        nunca detiene el monitoreo.
        """
        if not self.enabled:
            return 0
        now = time.time() if now is None else now
        rows = []
        for person in people:
            pid, point = person.get('id'), person.get('point')
            if pid is None or point is None or person.get('predicted'):
                continue
            key = (session, pid)
            if t - self._last.get(key, -1e9) < self.sample_interval:
                continue
            self._last[key] = t
            box = person.get('box')
            velocity = person.get('velocity') or (0., 0.)
            stored = store.people.get(pid, {})
            rows.append((session, pid, person['camera'], float(t), float(point[0]), float(point[1]),
                         person.get('association'), encode_signature(stored.get('color')),
                         float(box[2] - box[0]) if box else None, float(box[3] - box[1]) if box else None,
                         stored.get('height'), float(np.hypot(*velocity)), now))
        try:
            if rows:
                with self._lock:
                    self.con.executemany('INSERT INTO identity_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
                    self.con.commit()
            if now - self._last_purge >= self.purge_every:
                self.purge(now)
        except sqlite3.Error:
            self.enabled = False
            return 0
        return len(rows)

    def summary(self, session):
        with self._lock:
            people, rows, with_color, with_height = self.con.execute(
                'SELECT COUNT(DISTINCT pid), COUNT(*), COUNT(color), COUNT(height_m) FROM identity_observations WHERE session=?',
                (session,)).fetchone()
        return {'people': people, 'rows': rows, 'withColor': with_color, 'withHeight': with_height,
                'retentionHours': self.retention_seconds / 3600}

    def trajectory(self, session, pid):
        with self._lock:
            return self.con.execute(
                'SELECT camera,t,x,y,association,height_m FROM identity_observations WHERE session=? AND pid=? ORDER BY t',
                (session, pid)).fetchall()

    def close(self):
        with self._lock:
            self.con.close()
