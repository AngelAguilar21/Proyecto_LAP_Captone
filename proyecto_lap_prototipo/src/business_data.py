"""Base de datos de negocios, ventas e incidentes.

Es la pieza que faltaba para cruzar tráfico con ventas (fases 1 y 2) y para
llevar una bitácora de alertas persistente (fase 3), en vez de que cada
funcionalidad invente su propio almacenamiento por separado.

Vive junto al archivo del proyecto (config/projects/<id>.negocios.sqlite), no
en un archivo único de todo el sistema: cada proyecto es un espacio distinto
(otro aeropuerto, otro nivel) y sus negocios e incidentes no deben mezclarse
con los de otro proyecto, igual que ya pasa con su plano y sus cámaras.
"""
import json
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS negocios (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    camara_id TEXT,
    linea_id TEXT,
    creado REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora INTEGER,
    monto REAL NOT NULL,
    origen TEXT,
    cargado REAL NOT NULL,
    FOREIGN KEY (negocio_id) REFERENCES negocios (id)
);
CREATE INDEX IF NOT EXISTS idx_ventas_negocio_fecha ON ventas (negocio_id, fecha);

CREATE TABLE IF NOT EXISTS incidentes (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    zona TEXT,
    camara_id TEXT,
    inicio REAL NOT NULL,
    pico REAL,
    duracion REAL,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    detalle TEXT,
    creado REAL NOT NULL,
    actualizado REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidentes_estado ON incidentes (estado);

CREATE TABLE IF NOT EXISTS trafico_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zona TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora INTEGER NOT NULL,
    dia_semana INTEGER NOT NULL,
    conteo_total INTEGER NOT NULL DEFAULT 0,
    muestras INTEGER NOT NULL DEFAULT 0,
    pico INTEGER NOT NULL DEFAULT 0,
    UNIQUE(zona, fecha, hora)
);
CREATE INDEX IF NOT EXISTS idx_trafico_zona_hora_dia ON trafico_historico (zona, hora, dia_semana);
"""

ESTADOS_VALIDOS = {"pendiente", "revisado", "falsa_alarma", "resuelto"}
TIPOS_VALIDOS = {"aglomeracion", "equipaje"}


def path_for(project_path):
    """El archivo vive junto al del proyecto, con el mismo nombre base."""
    project_path = Path(project_path)
    return project_path.with_name(project_path.stem + ".negocios.sqlite")


def connect(project_path):
    path = path_for(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(path, timeout=15)
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(ESQUEMA)
    return conexion


# --- Negocios ---

def crear_negocio(conexion, id_negocio, nombre, camara_id=None, linea_id=None):
    if not nombre or not nombre.strip():
        raise ValueError("El negocio necesita un nombre.")
    conexion.execute(
        "INSERT INTO negocios (id, nombre, camara_id, linea_id, creado) VALUES (?,?,?,?,?)",
        (id_negocio, nombre.strip(), camara_id, linea_id, time.time()))
    conexion.commit()


def listar_negocios(conexion):
    filas = conexion.execute(
        "SELECT id, nombre, camara_id, linea_id FROM negocios ORDER BY nombre").fetchall()
    return [{"id": f[0], "nombre": f[1], "camaraId": f[2], "lineaId": f[3]} for f in filas]


def eliminar_negocio(conexion, id_negocio):
    conexion.execute("DELETE FROM ventas WHERE negocio_id = ?", (id_negocio,))
    conexion.execute("DELETE FROM negocios WHERE id = ?", (id_negocio,))
    conexion.commit()


# --- Ventas ---

def cargar_ventas(conexion, filas, origen="csv"):
    """filas: iterable de (negocio_id, fecha, hora_o_none, monto).

    No hace commit por fila: una carga de CSV puede traer miles de filas, y
    confirmar una por una sería costoso. Si alguna fila es inválida, no se
    guarda nada de la carga (todo o nada), para no dejar un CSV a medio
    procesar sin que el usuario se entere."""
    negocios_validos = {n[0] for n in conexion.execute("SELECT id FROM negocios").fetchall()}
    ahora = time.time()
    filas = list(filas)
    for negocio_id, fecha, hora, monto in filas:
        if negocio_id not in negocios_validos:
            raise ValueError(f"El negocio '{negocio_id}' no existe en este proyecto.")
        if not isinstance(monto, (int, float)) or isinstance(monto, bool) or monto < 0:
            raise ValueError(f"Monto inválido para {negocio_id} en {fecha}: {monto}")
    conexion.executemany(
        "INSERT INTO ventas (negocio_id, fecha, hora, monto, origen, cargado) VALUES (?,?,?,?,?,?)",
        [(n, f, h, float(m), origen, ahora) for n, f, h, m in filas])
    conexion.commit()
    return len(filas)


def ventas_por_fecha(conexion, negocio_id, fecha):
    filas = conexion.execute(
        "SELECT hora, monto FROM ventas WHERE negocio_id = ? AND fecha = ? ORDER BY hora",
        (negocio_id, fecha)).fetchall()
    return [{"hora": f[0], "monto": f[1]} for f in filas]


# --- Incidentes ---

def registrar_incidente(conexion, id_incidente, tipo, zona, camara_id, inicio,
                        pico=None, duracion=None, detalle=None):
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de incidente inválido: {tipo}")
    ahora = time.time()
    conexion.execute(
        "INSERT OR IGNORE INTO incidentes "
        "(id, tipo, zona, camara_id, inicio, pico, duracion, estado, detalle, creado, actualizado) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (id_incidente, tipo, zona, camara_id, inicio, pico, duracion, "pendiente",
         json.dumps(detalle or {}, ensure_ascii=False), ahora, ahora))
    # Mientras el incidente sigue en curso (pendiente), se actualiza su pico y
    # duración en cada llamada; una vez que alguien lo revisó, ya no se toca
    # para no perder el estado que el personal dejó.
    conexion.execute(
        "UPDATE incidentes SET pico = ?, duracion = ?, actualizado = ? "
        "WHERE id = ? AND estado = 'pendiente'",
        (pico, duracion, ahora, id_incidente))
    conexion.commit()


def actualizar_estado_incidente(conexion, id_incidente, estado):
    if estado not in ESTADOS_VALIDOS:
        raise ValueError(f"Estado inválido: {estado}")
    cursor = conexion.execute(
        "UPDATE incidentes SET estado = ?, actualizado = ? WHERE id = ?",
        (estado, time.time(), id_incidente))
    conexion.commit()
    if cursor.rowcount == 0:
        raise ValueError("El incidente no existe.")


def listar_incidentes(conexion, estado=None, limite=200):
    consulta = ("SELECT id, tipo, zona, camara_id, inicio, pico, duracion, estado, detalle, creado "
                "FROM incidentes")
    parametros = []
    if estado:
        consulta += " WHERE estado = ?"
        parametros.append(estado)
    consulta += " ORDER BY creado DESC LIMIT ?"
    parametros.append(limite)
    filas = conexion.execute(consulta, parametros).fetchall()
    return [{"id": f[0], "tipo": f[1], "zona": f[2], "camaraId": f[3], "inicio": f[4],
             "pico": f[5], "duracion": f[6], "estado": f[7], "detalle": json.loads(f[8] or "{}"),
             "creado": f[9]} for f in filas]


def recurrencia(conexion, zona, ventana_horas=2, minimo_dias=2):
    """Agrupa los incidentes de aglomeración de una zona por franja horaria y
    cuenta en cuántos días distintos aparecieron. Un solo día no es un
    patrón; varios días a la misma franja sí lo son."""
    filas = conexion.execute(
        "SELECT creado FROM incidentes WHERE zona = ? AND tipo = 'aglomeracion'", (zona,)).fetchall()
    por_franja = defaultdict(set)
    for (creado,) in filas:
        momento = datetime.fromtimestamp(creado, tz=timezone.utc)
        bucket = momento.hour - (momento.hour % ventana_horas)
        por_franja[bucket].add(momento.date().isoformat())
    return {
        f"{bucket:02d}:00-{bucket + ventana_horas:02d}:00": sorted(dias)
        for bucket, dias in por_franja.items() if len(dias) >= minimo_dias
    }


# --- Tráfico histórico ---

def registrar_trafico(conexion, zona, fecha, hora, dia_semana, conteo):
    conexion.execute(
        "INSERT INTO trafico_historico (zona, fecha, hora, dia_semana, conteo_total, muestras, pico) "
        "VALUES (?,?,?,?,?,1,?) "
        "ON CONFLICT(zona, fecha, hora) DO UPDATE SET "
        "conteo_total = conteo_total + excluded.conteo_total, "
        "muestras = muestras + 1, "
        "pico = MAX(pico, excluded.pico)",
        (zona, fecha, hora, dia_semana, conteo, conteo))
    conexion.commit()


def promedio_historico(conexion, zona, hora, dia_semana, excluir_fecha=None):
    """Promedio de tráfico para esa zona, a esa hora y ese día de la semana,
    sobre todo el historial guardado. excluir_fecha evita comparar la hora
    de hoy contra sí misma cuando hoy ya se guardó parcialmente."""
    consulta = ("SELECT SUM(conteo_total), SUM(muestras), MAX(pico), COUNT(DISTINCT fecha) "
                "FROM trafico_historico WHERE zona = ? AND hora = ? AND dia_semana = ?")
    parametros = [zona, hora, dia_semana]
    if excluir_fecha:
        consulta += " AND fecha != ?"
        parametros.append(excluir_fecha)
    total, muestras, pico, dias = conexion.execute(consulta, parametros).fetchone()
    if not muestras:
        return None
    return {"promedio": total / muestras, "picoHistorico": pico, "diasConDatos": dias}
