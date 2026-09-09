"""
Persistencia del historial de nodos-persona. SQLite para este prototipo:
suficiente para el volumen de un pasillo y permite consultas simples por
zona/tiempo sin montar infraestructura adicional. No se guarda ningun dato
biometrico: solo posiciones, zonas, timestamps y el id temporal no reversible.
"""
import csv
import sqlite3
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS personas (
    id_global TEXT PRIMARY KEY,
    primera_deteccion REAL,
    ultima_deteccion REAL
);

CREATE TABLE IF NOT EXISTS posiciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona TEXT NOT NULL,
    camara TEXT,
    x REAL,
    y REAL,
    t REAL,
    zona TEXT,
    predicha INTEGER DEFAULT 0,
    FOREIGN KEY (id_persona) REFERENCES personas (id_global)
);

CREATE INDEX IF NOT EXISTS idx_posiciones_persona ON posiciones (id_persona);
CREATE INDEX IF NOT EXISTS idx_posiciones_tiempo ON posiciones (t);
"""


def crear_bd(ruta_bd: str) -> sqlite3.Connection:
    Path(ruta_bd).parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta_bd)
    conexion.executescript(ESQUEMA)
    conexion.commit()
    return conexion


def guardar_posicion(conexion: sqlite3.Connection, id_persona: str, camara, x, y, t,
                      zona, predicha: bool = False):
    """No hace commit: con decenas de detecciones por frame, confirmar cada
    una por separado es costoso y, si data/ vive en una carpeta sincronizada
    (OneDrive/Drive), genera contencion de archivo con el proceso de
    sincronizacion. El llamador debe confirmar (ver commit_periodico) una
    vez por frame en vez de una vez por deteccion."""
    conexion.execute(
        "INSERT OR IGNORE INTO personas (id_global, primera_deteccion, ultima_deteccion) VALUES (?, ?, ?)",
        (id_persona, t, t),
    )
    conexion.execute(
        "UPDATE personas SET ultima_deteccion = ? WHERE id_global = ?",
        (t, id_persona),
    )
    conexion.execute(
        "INSERT INTO posiciones (id_persona, camara, x, y, t, zona, predicha) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (id_persona, camara, x, y, t, zona, int(predicha)),
    )


def fusionar_persona(conexion: sqlite3.Connection, id_viejo: str, id_nuevo: str, t: float):
    """Renombra retroactivamente todas las posiciones ya guardadas bajo
    id_viejo a id_nuevo. Hace falta porque la fusion entre camaras puede
    confirmarse unos frames despues de crear el id provisional (ver
    main.py: ventana de gracia de reintento), cuando ya se guardaron
    posiciones bajo el id viejo. No hace commit (ver guardar_posicion)."""
    conexion.execute("UPDATE posiciones SET id_persona = ? WHERE id_persona = ?", (id_nuevo, id_viejo))
    conexion.execute("DELETE FROM personas WHERE id_global = ?", (id_viejo,))
    conexion.execute("UPDATE personas SET ultima_deteccion = MAX(ultima_deteccion, ?) WHERE id_global = ?",
                      (t, id_nuevo))


def cargar_historial(conexion: sqlite3.Connection, id_persona: str) -> list:
    cursor = conexion.execute(
        "SELECT camara, x, y, t, zona, predicha FROM posiciones WHERE id_persona = ? ORDER BY t",
        (id_persona,),
    )
    return cursor.fetchall()


def cargar_todas_las_posiciones(conexion: sqlite3.Connection) -> list:
    cursor = conexion.execute(
        "SELECT id_persona, camara, x, y, t, zona, predicha FROM posiciones ORDER BY t"
    )
    return cursor.fetchall()


def exportar_csv(conexion: sqlite3.Connection, ruta_csv: str):
    filas = cargar_todas_las_posiciones(conexion)
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["id_persona", "camara", "x", "y", "t", "zona", "predicha"])
        escritor.writerows(filas)
