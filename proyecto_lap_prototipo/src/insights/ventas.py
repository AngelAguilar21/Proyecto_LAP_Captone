"""Insights guardados en SQLite y su relación con las ventas por hora.

Guarda los eventos espaciales y la exposición, visitas y permanencia por hora de cada negocio en la base del proyecto
(la misma de negocios y ventas), y las cruza con las ventas por hora del módulo comercial con tasas de captación y
conversión y una correlación entre horas. La correlación describe, no explica: no demuestra que la exposición cause
ventas, y con pocas horas no se calcula.
"""
import statistics

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS insights_events (
    session TEXT NOT NULL, negocio_id TEXT, zona TEXT NOT NULL, global_id TEXT NOT NULL, tipo TEXT NOT NULL,
    inicio REAL NOT NULL, fin REAL, confianza REAL, dataset TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_insights_events_session ON insights_events (session, negocio_id);
CREATE TABLE IF NOT EXISTS insights_hourly (
    session TEXT NOT NULL, negocio_id TEXT NOT NULL, fecha TEXT NOT NULL, hora INTEGER NOT NULL,
    exposicion INTEGER NOT NULL, visitas INTEGER NOT NULL, permanencia_s REAL, cobertura_s REAL NOT NULL, dataset TEXT NOT NULL,
    PRIMARY KEY (session, negocio_id, fecha, hora, dataset));
"""
MIN_HORAS_CORRELACION = 6
COBERTURA_COMPLETA_S = 3300   # igual que el pronóstico comercial: una hora cuenta con al menos 55 minutos observados


def setup(con):
    con.executescript(SCHEMA)


def guardar(con, sesion, dataset, resultado, eventos):
    """Reemplaza lo guardado de la sesión: eventos por zona y horas por negocio vinculado."""
    setup(con)
    zonas = {z["id"]: z for z in resultado["zonas_definidas"]}
    negocio_de = {z["id"]: next((l["negocio_id"] for l in resultado["locales"] if l["local_id"] == z["local_id"]), None) for z in zonas.values()}
    with con:
        con.execute("DELETE FROM insights_events WHERE session=?", (sesion,))
        con.execute("DELETE FROM insights_hourly WHERE session=?", (sesion,))
        con.executemany("INSERT INTO insights_events VALUES (?,?,?,?,?,?,?,?,?)",
                        [(sesion, negocio_de.get(e["zone_id"]), zonas[e["zone_id"]]["nombre"], e["global_id"], e["event_type"], e["inicio_s"], e["fin_s"],
                          e["confianza"], dataset) for e in eventos])
        con.executemany("INSERT OR REPLACE INTO insights_hourly VALUES (?,?,?,?,?,?,?,?,?)",
                        [(sesion, h["negocio_id"], h["fecha"], h["hora"], h["exposicion"], h["visitas"], h["permanencia_s"], h["cobertura_s"], dataset)
                         for h in resultado["por_hora"] if h["negocio_id"]])
    return len(eventos)


def _spearman(a, b):
    """Correlación de rangos de Spearman (None si una serie es constante)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    ra, rb = (np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(float) for v in (a, b))
    return round(float(np.corrcoef(ra, rb)[0, 1]), 3)


def relacion_con_ventas(con, negocio_id, dataset="real"):
    """Tasas de captación y conversión por hora y correlación exposición-ventas de un negocio.

    Solo cuentan horas con al menos 55 minutos observados y con ventas cargadas. Devuelve siempre el motivo cuando no hay
    datos suficientes, y el límite de lectura de la correlación.
    """
    setup(con)
    filas = con.execute(
        "SELECT h.fecha, h.hora, h.exposicion, h.visitas, h.permanencia_s, s.monto, s.transacciones FROM insights_hourly h "
        "JOIN commercial_sales s ON s.negocio_id=h.negocio_id AND s.fecha=h.fecha AND s.hora=h.hora AND s.dataset=h.dataset "
        "WHERE h.negocio_id=? AND h.dataset=? AND h.cobertura_s>=? ORDER BY h.fecha, h.hora", (negocio_id, dataset, COBERTURA_COMPLETA_S)).fetchall()
    horas = [{"fecha": f, "hora": h, "exposicion": e, "visitas": v, "permanencia_s": p, "ventas": m, "transacciones": t,
              "captacion": round(100 * v / e, 1) if e else None,
              "conversion": round(100 * t / v, 1) if t is not None and v else None,
              "ventas_por_visita": round(m / v, 2) if v else None} for f, h, e, v, p, m, t in filas]
    limite = ("Correlación entre horas observadas: describe cómo se mueven juntas, no demuestra que la exposición cause las ventas "
              "(influyen precios, promociones, clima y el día).")
    if len(horas) < MIN_HORAS_CORRELACION:
        return {"negocio_id": negocio_id, "horas": horas, "n": len(horas), "correlaciones": None, "limite": limite,
                "motivo": f"Se necesitan al menos {MIN_HORAS_CORRELACION} horas completas con ventas y observación; hay {len(horas)}."}
    ventas = [h["ventas"] for h in horas]
    return {"negocio_id": negocio_id, "horas": horas, "n": len(horas), "limite": limite, "motivo": None,
            "captacion_mediana": statistics.median(h["captacion"] for h in horas if h["captacion"] is not None) if any(h["captacion"] is not None for h in horas) else None,
            "correlaciones": {"exposicion_ventas": _spearman([h["exposicion"] for h in horas], ventas),
                              "visitas_ventas": _spearman([h["visitas"] for h in horas], ventas)}}
