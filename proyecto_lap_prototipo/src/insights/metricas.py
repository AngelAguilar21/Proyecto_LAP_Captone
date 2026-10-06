"""Permanencia, visitas, exposición, captación, densidad y congestión por zona y por local.

Portado de AeroVision (historico/metricas.py) sin pandas. La tasa de captación sigue la definición de la metodología:
proporción de expuestos (cruzaron el frente de un local) que luego ingresan a él.
"""
from collections import defaultdict

import numpy as np

PASOS_SERIE_S = (5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400, 43200, 86400)


def _r(v, d=2):
    return None if v is None or not np.isfinite(v) else round(float(v), d)


def ocupacion_por_segundo(consolidado):
    """{(zona, segundo): (personas distintas, velocidad media)}: N(z, t)."""
    personas, velocidades = defaultdict(set), defaultdict(list)
    dentro = consolidado.zona >= 0
    segundos = np.floor(consolidado.t).astype(np.int64)
    for zona, segundo, gid, v in zip(consolidado.zona[dentro], segundos[dentro], consolidado.global_id[dentro], consolidado.velocidad[dentro]):
        personas[(int(zona), int(segundo))].add(str(gid))
        if np.isfinite(v):
            velocidades[(int(zona), int(segundo))].append(v)
    return {k: (len(g), float(np.mean(velocidades[k])) if velocidades[k] else None) for k, g in personas.items()}


def episodios_congestion(ocupacion, zonas, p):
    """Concentraciones persistentes y lentas: muchas personas, densidad alta y velocidad baja.

    Un segundo es congestionado si hay al menos `personas_min` personas, la densidad N(z, t)/Área(z) alcanza `densidad_min`
    y la velocidad media no supera `velocidad_max_mps`; un episodio exige `duracion_min_s` segundos seguidos.
    """
    episodios, por_zona = [], defaultdict(list)
    for (zona, segundo), (n, v) in ocupacion.items():
        por_zona[zona].append((segundo, n, v))
    for zona_id, filas in por_zona.items():
        z = zonas[zona_id]
        filas.sort()
        seg = np.array([f[0] for f in filas])
        personas = np.array([f[1] for f in filas])
        velocidad = np.array([0.0 if f[2] is None else f[2] for f in filas])
        densidad = personas / max(z.area, 1e-6)
        marca = (personas >= p["personas_min"]) & (densidad >= p["densidad_min"]) & (velocidad <= p["velocidad_max_mps"])
        inicio = None
        for i in range(len(seg) + 1):
            sigue = i < len(seg) and marca[i] and (inicio is None or seg[i] == seg[i - 1] + 1)
            if sigue and inicio is None:
                inicio = i
            elif not sigue and inicio is not None:
                fin = i
                if seg[fin - 1] + 1 - seg[inicio] >= p["duracion_min_s"]:
                    tramo = slice(inicio, fin)
                    episodios.append({"zone_id": z.id, "nombre": z.nombre, "inicio_s": float(seg[inicio]), "fin_s": float(seg[fin - 1] + 1),
                                      "personas_max": int(personas[tramo].max()), "densidad_max": _r(densidad[tramo].max(), 3),
                                      "velocidad_media": _r(velocidad[tramo].mean())})
                inicio = i if i < len(seg) and marca[i] else None
    return episodios


def metricas_zonas(zonas, estancias_por_persona, eventos, ocupacion, episodios):
    """Visitantes, eventos, permanencia, ocupación, densidad, velocidad y congestión de cada zona."""
    por_zona = {z: [] for z in zonas}
    for tramos in estancias_por_persona.values():
        for e in tramos:
            if e.zona in por_zona:
                por_zona[e.zona].append(e)
    por_zona_ocup = defaultdict(list)
    for (zona, _), valor in ocupacion.items():
        por_zona_ocup[zona].append(valor)
    salida = []
    for zid, z in zonas.items():
        tramos = por_zona[zid]
        duraciones = np.array([e.duracion_s for e in tramos])
        ocup = por_zona_ocup.get(zid, [])
        de_zona = [e for e in eventos if e["zone_id"] == zid]
        unicos = lambda tipo: len({e["global_id"] for e in de_zona if e["event_type"] == tipo})
        velocidades = [v for _, v in ocup if v is not None]
        maxima = max((n for n, _ in ocup), default=0)
        salida.append({
            "zone_id": zid, "nombre": z.nombre, "tipo": z.tipo, "local_id": z.local_id, "area": _r(z.area),
            "visitantes": len({e.global_id for e in tramos}), "visitas": unicos("ENTER"), "exposicion": unicos("EXPOSURE"),
            "retornos": sum(1 for e in de_zona if e["event_type"] == "RETURN"), "colas": sum(1 for e in de_zona if e["event_type"] == "QUEUE"),
            "permanencia_media_s": _r(duraciones.mean()) if len(duraciones) else None,
            "permanencia_mediana_s": _r(np.median(duraciones)) if len(duraciones) else None,
            "ocupacion_max": int(maxima), "densidad_max": _r(maxima / max(z.area, 1e-6), 3) if ocup else 0.0,
            "velocidad_media": _r(np.mean(velocidades)) if velocidades else None,
            "segundos_congestion": _r(sum(c["fin_s"] - c["inicio_s"] for c in episodios if c["zone_id"] == zid), 1),
        })
    return sorted(salida, key=lambda m: (-m["visitantes"], m["nombre"]))


def metricas_locales(locales, zonas, estancias_por_persona, eventos):
    """Exposición, visitas, tasa de captación, permanencia y retornos de cada local.

    Entre quienes cruzaron el FRONTAGE de un local, cuántos tuvieron un ENTER a su INTERIOR después de su primera
    exposición. Sin expuestos la tasa es no disponible (None).
    """
    salida = []
    for l in locales:
        propias = {zid for zid, z in zonas.items() if z.local_id == l["local_id"]}
        frentes = {zid for zid in propias if zonas[zid].tipo == "FRONTAGE"}
        interiores = {zid for zid in propias if zonas[zid].tipo == "INTERIOR"}
        primera_exposicion, entradas, retornos = {}, {}, 0
        for e in eventos:
            if e["zone_id"] in frentes and e["event_type"] == "EXPOSURE":
                primera_exposicion[e["global_id"]] = min(primera_exposicion.get(e["global_id"], np.inf), e["inicio_s"])
            elif e["zone_id"] in interiores and e["event_type"] == "ENTER":
                entradas.setdefault(e["global_id"], []).append(e["inicio_s"])
            elif e["zone_id"] in interiores and e["event_type"] == "RETURN":
                retornos += 1
        captados = sum(1 for g, t0 in primera_exposicion.items() if any(t >= t0 for t in entradas.get(g, [])))
        duraciones = [e.duracion_s for tramos in estancias_por_persona.values() for e in tramos if e.zona in interiores]
        salida.append({
            "local_id": l["local_id"], "nombre": l["name"], "negocio_id": l.get("negocio_id"), "categoria": l.get("categoria", ""),
            "exposicion": len(primera_exposicion), "visitas": len(entradas), "captados": captados,
            "tasa_captacion": _r(100 * captados / len(primera_exposicion), 1) if primera_exposicion else None,
            "permanencia_media_s": _r(np.mean(duraciones)) if duraciones else None, "retornos": retornos,
        })
    return sorted(salida, key=lambda m: (-m["visitas"], m["nombre"]))


def paso_serie(duracion_s, maximo=24):
    """Intervalo «redondo» más corto que deja como mucho `maximo` barras en la serie."""
    return next((p for p in PASOS_SERIE_S if duracion_s / p <= maximo), PASOS_SERIE_S[-1])


def series_temporales(consolidado, ocupacion, estancias_por_persona, eventos, zonas, locales, maximo=24):
    """Series por intervalo para el tablero, del sitio completo y de cada zona y local.

    - personas: máximo de personas distintas a la vez dentro del intervalo.
    - densidad: personas / área de la zona (en el total, la zona más densa del intervalo).
    - entradas: estancias en la zona que empiezan en el intervalo.
    - visitas y exposicion: eventos ENTER y EXPOSURE que empiezan en el intervalo.
    - permanencia_s: duración media de las estancias que empiezan en el intervalo (None si no hay).
    - captacion: tasa de captación acumulada hasta el final del intervalo (None sin expuestos).
    """
    fin = float(consolidado.t.max()) if len(consolidado) else 0.0
    paso = paso_serie(fin, maximo)
    n = max(1, int(np.ceil(fin / paso)))
    cubeta = lambda t: min(int(t // paso), n - 1)

    def base():
        return {"personas": [0] * n, "densidad": [0.0] * n, "entradas": [0] * n, "visitas": [0] * n, "exposicion": [0] * n,
                "permanencia_s": [None] * n}

    total, por_zona = base(), {zid: base() for zid in zonas}
    if len(consolidado):
        simultaneas = defaultdict(set)
        for t, gid in zip(consolidado.t, consolidado.global_id):
            simultaneas[int(np.floor(t))].add(str(gid))
        for s, gids in simultaneas.items():
            b = cubeta(s)
            total["personas"][b] = max(total["personas"][b], len(gids))
    for (zona, segundo), (personas, _) in ocupacion.items():
        z, b = por_zona[zona], cubeta(segundo)
        z["personas"][b] = max(z["personas"][b], int(personas))
    duraciones = {zid: [[] for _ in range(n)] for zid in zonas}
    for tramos in estancias_por_persona.values():
        for e in tramos:
            if e.zona in por_zona:
                b = cubeta(e.inicio_s)
                por_zona[e.zona]["entradas"][b] += 1
                duraciones[e.zona][b].append(e.duracion_s)
    for e in eventos:
        clave = {"ENTER": "visitas", "EXPOSURE": "exposicion"}.get(e["event_type"])
        if clave and e["zone_id"] in por_zona:
            por_zona[e["zone_id"]][clave][cubeta(e["inicio_s"])] += 1
    todas = [[] for _ in range(n)]
    for zid, z in por_zona.items():
        area = max(zonas[zid].area, 1e-6)
        z["densidad"] = [_r(k / area, 3) for k in z["personas"]]
        z["permanencia_s"] = [_r(np.mean(d)) if d else None for d in duraciones[zid]]
        for b in range(n):
            todas[b] += duraciones[zid][b]
            for clave in ("entradas", "visitas", "exposicion"):
                total[clave][b] += z[clave][b]
            total["densidad"][b] = max(total["densidad"][b], z["densidad"][b])
    total["permanencia_s"] = [_r(np.mean(d)) if d else None for d in todas]

    por_local, expuestos_total, captados_total = {}, [0] * n, [0] * n
    for l in locales:
        frentes = {zid for zid, z in zonas.items() if z.local_id == l["local_id"] and z.tipo == "FRONTAGE"}
        interiores = {zid for zid, z in zonas.items() if z.local_id == l["local_id"] and z.tipo == "INTERIOR"}
        exposicion, entradas = {}, {}
        for e in eventos:
            if e["zone_id"] in frentes and e["event_type"] == "EXPOSURE":
                exposicion[e["global_id"]] = min(exposicion.get(e["global_id"], np.inf), e["inicio_s"])
            elif e["zone_id"] in interiores and e["event_type"] == "ENTER":
                entradas.setdefault(e["global_id"], []).append(e["inicio_s"])
        tasa = []
        for b in range(n):
            corte = (b + 1) * paso if b < n - 1 else np.inf
            vistos = [g for g, t0 in exposicion.items() if t0 < corte]
            dentro = sum(1 for g in vistos if any(exposicion[g] <= t < corte for t in entradas.get(g, [])))
            expuestos_total[b] += len(vistos)
            captados_total[b] += dentro
            tasa.append(_r(100 * dentro / len(vistos), 1) if vistos else None)
        por_local[str(l["local_id"])] = {"captacion": tasa}
    total["captacion"] = [_r(100 * c / e, 1) if e else None for c, e in zip(captados_total, expuestos_total)]
    return {"paso_s": paso, "intervalos": n, "total": total, "zonas": {str(zid): z for zid, z in por_zona.items()}, "locales": por_local}
