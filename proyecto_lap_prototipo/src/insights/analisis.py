"""Insights espaciales de una sesión: eventos, KDE, rutas frecuentes, grafo origen-destino, captación y congestión.

Portado de AeroVision (Insights Modelo/insights_historicos.py). Trabaja solo con datos ya guardados (la grabación de la
sesión y las zonas y negocios del proyecto), sin volver a correr los modelos de visión:

    piso transitable -> consolidación -> zonas -> estancias y eventos -> KDE, rutas (PrefixSpan), origen-destino,
    permanencia, exposición, captación, densidad y congestión

Unidades: los umbrales de AeroVision están en metros. Con un plano en metros se usan tal cual; con un plano en unidades
relativas se escalan con `matchDistance` (la distancia de coincidencia del proyecto, que hace de metro).
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .espacial import kde_grilla, origen_destino, prefixspan, secuencias_semanticas
from .eventos import estancias, generar_eventos
from .metricas import episodios_congestion, metricas_locales, metricas_zonas, ocupacion_por_segundo, series_temporales
from .piso import piso_desde_config
from .trayectorias import consolidar, desde_replay
from .zonas import asignar_zonas, desde_config

# Parámetros de AeroVision (config_insights.json). Distancias en metros, velocidades en m/s, densidad en personas/m2.
PARAMETROS = {
    "piso": {"margen": 0.2},
    "consolidacion": {"paso_s": 0.2, "velocidad_max": 4.0},
    "eventos": {"tolerancia_s": 1.0, "dwell_min_s": 5.0, "retorno_min_s": 10.0, "cola_min_s": 8.0,
                "cola_velocidad_max_mps": 0.35, "confianza_sin_transicion": 0.5},
    "kde": {"celda": 0.5, "h": 1.0, "radio_h": 4.0, "max_celdas": 80},
    "rutas": {"soporte_min_personas": 2, "soporte_min_fraccion": 0.1, "longitud_min": 2, "longitud_max": 5, "maximo": 15},
    "congestion": {"personas_min": 3, "densidad_min": 0.25, "velocidad_max_mps": 0.5, "duracion_min_s": 5.0},
}
MAX_EVENTOS_EN_RESULTADO = 2000


def escala_del_plano(config):
    """Cuántas unidades del plano mide un metro de AeroVision."""
    return 1.0 if config.get("unit") == "meters" else max(float(config.get("matchDistance", 1.0)), 1e-6)


def parametros_escalados(config, base=None):
    """Parámetros de AeroVision llevados a las unidades del plano del proyecto."""
    p = json.loads(json.dumps(base or PARAMETROS))
    k = escala_del_plano(config)
    p["piso"]["margen"] *= k
    p["consolidacion"]["velocidad_max"] *= k
    p["eventos"]["cola_velocidad_max_mps"] *= k
    p["kde"]["celda"] *= k
    p["kde"]["h"] *= k
    p["congestion"]["velocidad_max_mps"] *= k
    p["congestion"]["densidad_min"] /= k * k
    p["escala_del_plano"] = k
    return p


def origen_sesion(meta):
    """Fecha y hora de inicio de la grabación (zona de Lima) con la misma regla que el módulo comercial, o None."""
    from commercial import LIMA
    config = meta.get("config", {})
    dataset_demo = meta.get("module") == "demo" or config.get("testRun")
    inicio = meta.get("created") if config.get("sourceMode") == "live" or dataset_demo else config.get("recordingStartedAt")
    if not inicio:
        return None
    try:
        origen = datetime.fromisoformat(inicio.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return origen.astimezone(LIMA) if origen.tzinfo else None


def por_hora(eventos, tramos, zonas, locales, origen, duracion_s):
    """Exposición, visitas y permanencia de cada local por hora civil: [{negocio_id, fecha, hora, ...}]."""
    if origen is None:
        return []
    fin = origen + timedelta(seconds=duracion_s)
    filas = []
    for l in locales:
        interiores = {zid for zid, z in zonas.items() if z.local_id == l["local_id"] and z.tipo == "INTERIOR"}
        frentes = {zid for zid, z in zonas.items() if z.local_id == l["local_id"] and z.tipo == "FRONTAGE"}
        horas = {}
        cursor = origen.replace(minute=0, second=0, microsecond=0)
        while cursor <= fin:
            derecha = cursor + timedelta(hours=1)
            horas[(cursor.date().isoformat(), cursor.hour)] = {"expuestos": set(), "visitantes": set(), "duraciones": [],
                                                              "cobertura_s": max(0.0, (min(fin, derecha) - max(origen, cursor)).total_seconds())}
            cursor = derecha
        clave = lambda s: (lambda d: (d.date().isoformat(), d.hour))(origen + timedelta(seconds=s))
        for e in eventos:
            fila = horas.get(clave(e["inicio_s"]))
            if fila is None:
                continue
            if e["zone_id"] in frentes and e["event_type"] == "EXPOSURE":
                fila["expuestos"].add(e["global_id"])
            elif e["zone_id"] in interiores and e["event_type"] == "ENTER":
                fila["visitantes"].add(e["global_id"])
        for lista in tramos.values():
            for e in lista:
                if e.zona in interiores and clave(e.inicio_s) in horas:
                    horas[clave(e.inicio_s)]["duraciones"].append(e.duracion_s)
        for (fecha, hora), f in horas.items():
            filas.append({"local_id": l["local_id"], "negocio_id": l.get("negocio_id"), "nombre": l["name"], "fecha": fecha, "hora": hora,
                          "exposicion": len(f["expuestos"]), "visitas": len(f["visitantes"]),
                          "permanencia_s": round(float(np.mean(f["duraciones"])), 2) if f["duraciones"] else None,
                          "cobertura_s": round(f["cobertura_s"], 1)})
    return filas


def analizar(config, filas, negocios=(), params=None, origen=None, duracion_s=None):
    """Toda la Parte III sobre las observaciones (global_id, t, x, y) de una sesión.

    Devuelve el resultado completo (JSON serializable) y, aparte, los eventos para guardarlos en la base.
    """
    p = params or parametros_escalados(config)
    zonas, locales = desde_config(config, negocios, frente=config.get("insightsFrente"))
    paso, k = p["consolidacion"]["paso_s"], p["escala_del_plano"]
    aviso = []
    if not zonas:
        aviso.append("El plano no tiene zonas de medición: dibuja locales (kind comercial), colas o zonas para obtener eventos.")
    if not any(z.tipo == "INTERIOR" for z in zonas.values()):
        aviso.append("No hay locales dibujados: no se calculan exposición ni captación.")

    # 0. Piso transitable: nadie camina a través de una pared o fuera del plano.
    piso = piso_desde_config(config, p["piso"]["margen"])
    x, y, movidos = piso.ajustar_trayectorias(filas["global_id"], filas["t"], filas["x"], filas["y"], paso)
    # 1. Consolidación: una posición por persona e instante, sin saltos imposibles; y la zona de cada una.
    cons = consolidar(filas["global_id"], filas["t"], x, y, None, paso, p["consolidacion"]["velocidad_max"])
    cons.zona = asignar_zonas(cons.x, cons.y, zonas.values())
    # 2. Estancias por zona y eventos espaciales.
    interiores = {z.id for z in zonas.values() if z.tipo == "INTERIOR"}
    tramos = estancias(cons, paso, p["eventos"]["tolerancia_s"], interiores)
    eventos = [e for gid in tramos for e in generar_eventos(tramos[gid], zonas, p["eventos"])]

    # 3. KDE: ocupación (pondera el tiempo) y visitantes únicos (1 por persona).
    ancho, alto = float(config.get("width", 0)), float(config.get("height", 0))
    kde = {"celda": p["kde"]["celda"], "h": p["kde"]["h"], "origen": [0, 0], "columnas": 0, "filas": 0, "ocupacion": [], "visitantes": []}
    if ancho > 0 and alto > 0 and len(cons):
        celda = max(p["kde"]["celda"], max(ancho, alto) / p["kde"]["max_celdas"])
        columnas, filas_n = math.ceil(ancho / celda), math.ceil(alto / celda)
        por_persona = np.concatenate([np.full(sl.stop - sl.start, sl.stop - sl.start) for _, sl in cons.personas()])
        comun = dict(origen=[0.0, 0.0], columnas=columnas, filas=filas_n, celda=celda, h=p["kde"]["h"], radio_h=p["kde"]["radio_h"])
        kde.update(celda=round(celda, 4), columnas=columnas, filas=filas_n,
                   ocupacion=np.round(kde_grilla(cons.x, cons.y, np.full(len(cons), paso), **comun), 4).tolist(),
                   visitantes=np.round(kde_grilla(cons.x, cons.y, 1.0 / por_persona, **comun), 5).tolist())

    # 4. Rutas frecuentes (PrefixSpan) y grafo origen-destino entre zonas.
    secuencias = list(secuencias_semanticas(tramos).values())
    soporte = max(p["rutas"]["soporte_min_personas"], math.ceil(p["rutas"]["soporte_min_fraccion"] * max(len(secuencias), 1)))
    patrones = [(pat, sop) for pat, sop in prefixspan(secuencias, soporte, p["rutas"]["longitud_min"], p["rutas"]["longitud_max"])
                if all(a != b for a, b in zip(pat, pat[1:]))]
    patrones.sort(key=lambda ps: (-ps[1], -len(ps[0])))
    rutas = [{"secuencia": [zonas[z].nombre for z in pat], "zonas": pat, "frecuencia": sop,
              "porcentaje": round(100 * sop / max(len(secuencias), 1), 1)} for pat, sop in patrones[:p["rutas"]["maximo"]]]
    od = [{"desde": a, "hacia": b, "desde_nombre": zonas[a].nombre, "hacia_nombre": zonas[b].nombre, "personas": n}
          for (a, b), n in origen_destino(secuencias).most_common()]

    # 5. Densidad, congestión y métricas por zona y por local.
    ocupacion = ocupacion_por_segundo(cons)
    congestion = episodios_congestion(ocupacion, zonas, p["congestion"])
    m_zonas = metricas_zonas(zonas, tramos, eventos, ocupacion, congestion)
    m_locales = metricas_locales(locales, zonas, tramos, eventos)
    series = series_temporales(cons, ocupacion, tramos, eventos, zonas, locales)
    duracion = float(cons.t.max()) if len(cons) and duracion_s is None else float(duracion_s or 0)
    horas = por_hora(eventos, tramos, zonas, locales, origen, duracion)

    marca = lambda s: None if s is None or origen is None else (origen + timedelta(seconds=s)).isoformat()
    resultado = {
        "version": 1, "parametros": p, "aviso": aviso, "unidad": config.get("unit", "relative"),
        "plano": {"ancho": ancho, "alto": alto, "planId": config.get("planId", "custom")},
        "zonas_definidas": [{"id": z.id, "nombre": z.nombre, "tipo": z.tipo, "local_id": z.local_id, "area": round(z.area, 3),
                             "vertices": np.round(z.vertices, 3).tolist()} for z in zonas.values()],
        "resumen": {"personas": len(set(cons.global_id.tolist())), "posiciones": int(len(cons)), "con_zona": int((cons.zona >= 0).sum()),
                    "zonas": len(zonas), "locales": len(locales), "ajustadas_al_piso": int(movidos.sum()),
                    "obstaculos": len(piso.obstaculos), "eventos": {t: sum(1 for e in eventos if e["event_type"] == t)
                                                                     for t in sorted({e["event_type"] for e in eventos})},
                    "con_fecha": origen is not None},
        "kde": kde, "rutas": rutas, "origen_destino": od, "zonas": m_zonas, "locales": m_locales, "congestion": congestion,
        "series": series, "por_hora": horas,
        "eventos": [{"global_id": e["global_id"], "zone_id": int(e["zone_id"]), "event_type": e["event_type"], "inicio_s": round(e["inicio_s"], 2),
                     "fin_s": None if e["fin_s"] is None else round(e["fin_s"], 2), "hora": marca(e["inicio_s"]),
                     "confianza": round(float(e["confianza"]), 4)} for e in eventos[:MAX_EVENTOS_EN_RESULTADO]],
        "eventos_total": len(eventos),
        "limites": ["Con pocas personas o una sola escena las tasas varían mucho: léelas como descripción, no como medida de precisión.",
                    "La captación mide quien cruzó el frente de un local y luego entró; la exposición depende del ancho de franja y de la calibración.",
                    "Las rutas y el origen-destino cuentan IDs anónimos de sesión; si el motor de identidad rompe una persona en dos, se cuenta dos veces."],
    }
    return resultado, eventos


def analizar_replay(raiz, sesion, config, negocios=()):
    """Calcula los insights de una grabación guardada y los deja en data/replays/<sesion>/insights.json."""
    directorio = Path(raiz) / "data" / "replays" / sesion
    meta, filas = desde_replay(directorio)
    origen = origen_sesion(meta)
    plan = {**config, **(config.get("plans", {}).get(meta.get("config", {}).get("planId"), {}) if meta.get("config", {}).get("planId") != config.get("planId") else {})}
    resultado, eventos = analizar(plan, filas, negocios, origen=origen, duracion_s=meta.get("end"))
    resultado["sesion"] = sesion
    resultado["identidad"] = meta.get("identity") or {"engine": "legacy"}
    resultado["creado"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    destino = directorio / "insights.json"
    temporal = destino.with_suffix(".tmp")
    temporal.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
    temporal.replace(destino)
    return resultado, eventos, meta
