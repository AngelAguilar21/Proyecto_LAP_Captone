"""Geometry, conservative camera handoffs and observed occupancy for the live UI.

Coordinates are always in a shared, user-defined plane. Association confidence is
a heuristic, not a calibrated probability. No biometric models are used here.
"""
from spatial_scope import validate_polygon
import json
import math
from collections import deque

import cv2
import numpy as np


def finite(value, low, high):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def valid_plan_id(value):
    return (isinstance(value, str) and value in ("custom", "lap-1", "lap-2", "lap-3", "lap-4")) or (
        isinstance(value, str) and value.startswith("floor-") and 7 < len(value) <= 48
        and all(char.isalnum() or char in "_-" for char in value)
    )


def pairs_hash(pairs):
    """Huella de las referencias del suelo de una cámara: la alineación entre cámaras solo vale con las mismas referencias."""
    import hashlib
    return hashlib.sha1(json.dumps([[round(float(v), 6) for v in p] for p in pairs]).encode()).hexdigest()[:16]


def validate_person_pairs(c):
    """Valida las parejas de personas marcadas en dos cámaras.

    Las parejas nuevas pueden guardar ``ta`` y ``tb``: el instante de la misma
    persona en cada fuente. ``t`` se conserva por compatibilidad con proyectos
    anteriores y representa ambos instantes cuando los videos ya estaban
    sincronizados. ``pa`` y ``pb`` son esos mismos instantes medidos en el archivo
    de video (sin el desfase de lectura), así que siguen valiendo si el desfase cambia.
    """
    ids = {cam["id"] for cam in c.get("cameras", []) if isinstance(cam, dict) and "id" in cam}
    pairs = c.get("personPairs", [])
    if not isinstance(pairs, list) or len(pairs) > 500:
        raise ValueError("Parejas de personas inválidas (máximo 500).")
    for item in pairs:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not 0 < len(item["id"]) <= 64:
            raise ValueError("Pareja de personas inválida.")
        tiempos = (item.get("ta", item.get("t")), item.get("tb", item.get("t")))
        if any(not finite(v, 0, 1e6) for v in tiempos) or any(key in item and not finite(item[key], 0, 1e6) for key in ("pa", "pb")):
            raise ValueError("Cada pareja necesita tiempos válidos para ambas cámaras.")
        sides = [item.get("a"), item.get("b")]
        if any(not isinstance(side, dict) or side.get("camera") not in ids or not isinstance(side.get("point"), list) or len(side["point"]) != 2
               or any(not finite(v, 0, 1) for v in side["point"])
               or (side.get("bbox") is not None and (not isinstance(side["bbox"], list) or len(side["bbox"]) != 4
                   or any(not finite(v, 0, 1) for v in side["bbox"]) or side["bbox"][0] >= side["bbox"][2] or side["bbox"][1] >= side["bbox"][3])) for side in sides) or sides[0]["camera"] == sides[1]["camera"]:
            raise ValueError("Cada pareja necesita dos cámaras distintas del proyecto y puntos dentro de la imagen.")


MIN_PAREJAS_RELACION = 4


def related_cameras(c, minimo=MIN_PAREJAS_RELACION):
    """Cámaras vecinas para la identidad entre cámaras: {id: [ids]}.

    Dos cámaras quedan relacionadas cuando el usuario marcó a la misma persona en ambas al menos `minimo` veces (las mismas
    parejas que miden su desfase de tiempo), o cuando el proyecto trae `links` manuales. No se deduce nada de la posición
    de las cámaras en el plano: la relación siempre sale de una acción del usuario.
    """
    ids = [cam["id"] for cam in c.get("cameras", []) if cam.get("active", True)]
    vecinas = {cid: set() for cid in ids}
    if c.get('cameraRoutes') is not None:
        for route in c['cameraRoutes']:
            a, b = route['from'], route['to']
            if a in vecinas and b in vecinas:
                vecinas[a].add(b)
        return {cid: sorted(v) for cid, v in vecinas.items()}
    conteo = {}
    for item in c.get("personPairs", []) or []:
        a, b = item.get("a", {}).get("camera"), item.get("b", {}).get("camera")
        if a in vecinas and b in vecinas and a != b:
            clave = tuple(sorted((a, b)))
            conteo[clave] = conteo.get(clave, 0) + 1
    for (a, b), n in conteo.items():
        if n >= minimo:
            vecinas[a].add(b)
            vecinas[b].add(a)
    for cam in c.get("cameras", []):
        for destino in cam.get("links", []) or []:
            if cam["id"] in vecinas and destino in vecinas and destino != cam["id"]:
                vecinas[cam["id"]].add(destino)
                vecinas[destino].add(cam["id"])
    return {cid: sorted(v) for cid, v in vecinas.items()}


def validate_config(c):
    if not isinstance(c, dict):
        raise ValueError("La configuración debe ser un objeto.")
    # Módulos retirados: alineación estimada, zonas de conexión automáticas, relaciones numeradas y motores de identidad
    # alternativos. Se limpian al validar para que proyectos antiguos abran y se guarden de nuevo sin ellos.
    for field in ("alignment", "connections", "cameraRelations", "identityEngine", "identityAlign", "reidModel"):
        c.pop(field, None)
    for name in ("width", "height"):
        if not finite(c.get(name), 1, 10000):
            raise ValueError(f"{name}: valor entre 1 y 10000.")
    if c.get("unit") not in ("relative", "meters"):
        raise ValueError("Unidad inválida.")
    for key, lo, hi in [("radius", .01, 1000), ("minPeople", 2, 1000), ("dwell", 0, 3600), ("handoffSeconds", .1, 120), ("matchDistance", .01, 1000)]:
        if not finite(c.get(key), lo, hi):
            raise ValueError(f"Valor inválido: {key}.")
    if int(c["minPeople"]) != c["minPeople"]:
        raise ValueError("El mínimo de personas debe ser entero.")
    if c.get("personHeight") is not None and not finite(c.get("personHeight"), 1.2, 2.2):
        raise ValueError("La estatura media debe estar entre 1.2 y 2.2 metros.")
    if not isinstance(c.get("clocksVerified"), bool):
        raise ValueError("Indicar si los relojes están verificados.")
    if c.get("workArea"):
        validate_polygon(c["workArea"], c["width"], c["height"], "Área de trabajo")
    lines=c.get("planLines",[])
    if not isinstance(lines,list) or len(lines)>6000 or any(not isinstance(line,list) or len(line)!=4 or any(not finite(x,0,1) for x in line) for line in lines):
        raise ValueError("Líneas del plano inválidas.")
    if c.get("planView") not in (None, "image", "lines"):
        raise ValueError("Vista del plano inválida.")
    cameras = c.get("cameras")
    plans=c.get("plans",{})
    if not isinstance(plans,dict) or len(plans)>8:
        raise ValueError("Catálogo de planos inválido.")
    for pid, plan in plans.items():
        if not valid_plan_id(pid) or not isinstance(plan,dict):
            raise ValueError("Plano desconocido.")
        validate_config({**c,**plan,"plans":{},"cameras":[],"personPairs":[],"cameraRoutes":[]})
    if not valid_plan_id(c.get("planId","custom")):
        raise ValueError("Nivel desconocido.")
    if c.get("mapAsset") and c["mapAsset"] not in [f"/maps/lap/{n}.json" for n in (1,2,3,4)]:
        raise ValueError("Referencia cartográfica inválida.")
    if not isinstance(cameras, list) or not 0 <= len(cameras) <= 32:
        raise ValueError("Configura como máximo 32 cámaras.")
    ids = set()
    for cam in cameras:
        if not isinstance(cam, dict):
            raise ValueError("Cámara inválida.")
        # Campos de módulos retirados (YOLO/equipaje y segunda inferencia densa).
        # Se limpian al validar para que configuraciones antiguas migren sin
        # romperse y se guarden de nuevo con el alcance comercial actual.
        for field in ("denseCounting", "denseInterval", "luggageWatch", "luggageDwell", "luggageInterval",
                      "calibrationResolution", "calibrationReview", "restrictCoverage", "coverageShape", "coverageWidth",
                      "coveragePolygon", "heading", "fov", "range", "tilt"):
            cam.pop(field, None)
        # Una cámara calibrada con personas vuelve a sus puntos del suelo medidos, si se guardaron al reemplazarlos.
        # Si no hay puntos medidos guardados, se conservan los puntos actuales: nunca se borran puntos marcados.
        people = cam.pop("peopleCalibration", None)
        if isinstance(people, dict) and isinstance(people.get("replaced"), list) and people["replaced"]:
            cam["pairs"] = people["replaced"]
        cid = cam.get("id", "")
        if not isinstance(cid, str) or not cid or len(cid) > 40 or not all(x.isalnum() or x in "_-" for x in cid) or cid in ids:
            raise ValueError("Cada cámara necesita un ID único, sin espacios ni símbolos especiales.")
        ids.add(cid)
        source = cam.get("source")
        if not ((isinstance(source, int) and not isinstance(source, bool) and 0 <= source <= 32) or (isinstance(source, str) and len(source) <= 2048)):
            raise ValueError(f"Fuente inválida: {cid}.")
        if not finite(cam.get("offset", 0), 0, 86400):
            raise ValueError("Offset debe ser no negativo (segundos que se omiten al inicio).")
        if not finite(cam.get("syncOffset", 0), -86400, 86400):
            raise ValueError("syncOffset debe ser un desfase temporal firmado entre cámaras.")
        pid=cam.get("planId","custom")
        if not valid_plan_id(pid) or (pid!=c.get("planId","custom") and pid not in plans):
            raise ValueError(f"Plano de cámara desconocido en {cid}.")
        cam_plan=c if cam.get("planId","custom")==c.get("planId","custom") else plans.get(cam.get("planId","custom"),c)
        for key, maximum in [("x", cam_plan["width"]), ("y", cam_plan["height"])]:
            if not finite(cam.get(key), 0, maximum):
                raise ValueError(f"Posición {key} inválida en {cid}.")
        if not isinstance(cam.get("links", []), list):
            raise ValueError("links debe ser una lista de cámaras de destino.")
        if "height" in cam and not finite(cam["height"], 0, 10000):
            raise ValueError(f"{cid}: height fuera de rango.")
        for field in ("name", "location"):
            if field in cam and (not isinstance(cam[field], str) or len(cam[field]) > 160):
                raise ValueError(f"{cid}: {field} inválido.")
        for field in ("active", "illustrative"):
            if field in cam and not isinstance(cam[field],bool):
                raise ValueError(f"{field}: debe ser booleano.")
        pairs = cam.get("pairs", [])
        if not isinstance(pairs, list) or len(pairs) > 30:
            raise ValueError("Usa como máximo 30 correspondencias de calibración.")
        for p in pairs:
            if not isinstance(p, list) or len(p) != 4 or not all(finite(v, -10000, 10000) for v in p):
                raise ValueError("Cada correspondencia contiene [u, v, x, y].")
            if not 0 <= p[0] <= 1 or not 0 <= p[1] <= 1 or not 0 <= p[2] <= cam_plan["width"] or not 0 <= p[3] <= cam_plan["height"]:
                raise ValueError("Puntos fuera del video o del plano.")
        if len(pairs) >= 4:
            calibration(pairs)
        for field, lo, hi in [('crowdThreshold',1,1000),('crowdDwell',0,3600)]:
            if field in cam and not finite(cam[field],lo,hi):
                raise ValueError(f'{cid}: {field} fuera de rango.')
        if cam.get('analysisZones'):
            from following.zone_counts import validate as validate_counting
            validate_counting({'source':'config-camera','confidence':.5,'interval':1,'maxSide':768,'zones':cam['analysisZones']})
        count_lines = cam.get('countLines',[])
        if not isinstance(count_lines,list) or len(count_lines)>20:
            raise ValueError('Máximo 20 líneas de entrada/salida por cámara.')
        line_ids=set()
        for line in count_lines:
            if not isinstance(line,dict) or not isinstance(line.get('id'),str) or not line['id'] or line['id'] in line_ids:
                raise ValueError('Cada línea necesita un identificador único.')
            line_ids.add(line['id'])
            place = line.get('place')
            if place is not None:
                if not isinstance(place, dict) or not isinstance(place.get('id'), str) or not isinstance(place.get('name'), str) or not 1 <= len(place['name']) <= 200:
                    raise ValueError('Local asociado inválido.')
                if place.get('planId') != cam.get('planId', 'custom'):
                    raise ValueError('El acceso debe asociarse a un local del mismo nivel que la cámara.')
                p = place.get('point')
                if not isinstance(p, list) or len(p) != 2 or not finite(p[0], 0, cam_plan['width']) or not finite(p[1], 0, cam_plan['height']):
                    raise ValueError('La ubicación del local está fuera del plano.')
            if not isinstance(line.get('name'),str) or not 1<=len(line['name'])<=80 or line.get('entrySide') not in (-1,1):
                raise ValueError('Indica nombre y dirección de entrada de la línea.')
            for key in ('a','b'):
                if not isinstance(line.get(key),list) or len(line[key])!=2 or not all(finite(v,0,1) for v in line[key]):
                    raise ValueError('Los extremos deben estar dentro de la imagen.')
            if math.dist(line['a'],line['b'])<.02:
                raise ValueError('Separa los extremos de la línea de entrada/salida.')
            if line.get('bands') is not None:
                bands=line['bands']
                if not isinstance(bands,dict): raise ValueError('Áreas del acceso inválidas.')
                a,b=line['a'],line['b'];dx,dy=b[0]-a[0],b[1]-a[1]
                for side,sign in [('negative',-1),('positive',1)]:
                    points=bands.get(side)
                    if not isinstance(points,list) or len(points)!=2: raise ValueError('Cada lado del acceso necesita dos puntos exteriores.')
                    for point in points:
                        if not isinstance(point,list) or len(point)!=2 or not all(finite(v,0,1) for v in point): raise ValueError('Los puntos del acceso deben estar dentro de la imagen.')
                        if sign*(dx*(point[1]-a[1])-dy*(point[0]-a[0]))<=.00001: raise ValueError('Mantén las áreas exterior e interior a lados opuestos de la línea de acceso.')
                    validate_polygon([a,b,points[1],points[0]],1,1,'Área de confirmación del acceso')
        zone = cam.get("detectionZone")
        if zone is not None:
            validate_polygon(zone,1,1,f"{cid}: zona de detección")
            if not isinstance(zone, list) or not 3 <= len(zone) <= 50:
                raise ValueError(f"{cid}: la zona de detección necesita entre 3 y 50 puntos.")
            for v in zone:
                if not isinstance(v, list) or len(v) != 2 or not finite(v[0], 0, 1) or not finite(v[1], 0, 1):
                    raise ValueError(f"{cid}: cada punto de la zona de detección es [u, v] normalizado entre 0 y 1.")
    for cam in cameras:
        if any(not isinstance(link, str) or link not in ids or link == cam["id"] for link in cam.get("links", [])):
            raise ValueError("Enlaces deben referirse a otras cámaras existentes.")
    zones = c.get("zones", [])
    context = c.get("commercialContext")
    if context is not None and (not isinstance(context, dict) or not isinstance(context.get("hasBusinesses"), bool)):
        raise ValueError("Indica si el piso contiene negocios.")
    if not isinstance(zones, list) or len(zones) > 100:
        raise ValueError("Máximo 100 zonas.")
    for z in zones:
        if not isinstance(z, dict) or not isinstance(z.get("name"), str) or not 1 <= len(z["name"]) <= 80:
            raise ValueError("Nombre de zona inválido.")
        pts = z.get("points")
        if not isinstance(pts, list) or not 3 <= len(pts) <= 100:
            raise ValueError("Una zona requiere de 3 a 100 puntos.")
        if any(not isinstance(p, list) or len(p) != 2 or not finite(p[0], 0, c["width"]) or not finite(p[1], 0, c["height"]) for p in pts):
            raise ValueError("Polígono fuera del plano.")
        if abs(cv2.contourArea(np.asarray(pts, dtype=np.float32))) < .000001:
            raise ValueError("El área dibujada es degenerada: separa sus vértices.")
        rule = z.get("rule")
        if rule is not None and (not isinstance(rule, dict) or not isinstance(rule.get("enabled"), bool) or not finite(rule.get("minPeople"),2,1000) or int(rule["minPeople"]) != rule["minPeople"] or not finite(rule.get("dwell"),0,3600)):
            raise ValueError("Regla de zona inválida.")
        if z.get("source") not in (None, "system", "operator"):
            raise ValueError("Origen de zona inválido.")
        business = z.get("business")
        if business is not None:
            if not isinstance(business, dict) or business.get("category") not in (None, "retail", "food", "service", "other"):
                raise ValueError("Información comercial inválida.")
            for key in ("widthM", "depthM", "areaM2", "capacity", "entranceWidthM"):
                if business.get(key) is not None and not finite(business[key], 0, 1000000):
                    raise ValueError(f"Medida comercial inválida: {key}.")
    bg = c.get("background", "")
    if not isinstance(bg, str) or len(bg) > 3000000 or (bg and not bg.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,"))):
        raise ValueError("El fondo debe ser una imagen PNG, JPEG o WebP de menos de 2 MB.")
    for field in ("airport", "floor", "planName"):
        if field in c and (not isinstance(c[field],str) or len(c[field])>200):
            raise ValueError(f"Campo {field} inválido.")
    if c.get("sourceMode", "recordings") not in ("recordings", "live", "demo"):
        raise ValueError("Modo de fuente inválido.")
    validate_person_pairs(c)
    for clave in ("appearanceMemory", "identityFinalize", "identityGroupCrops"):
        if not isinstance(c.get(clave, True), bool):
            raise ValueError(f"{clave} debe ser verdadero o falso.")
    if c.get("reidThreads") is not None and (not finite(c["reidThreads"], 1, 64) or int(c["reidThreads"]) != c["reidThreads"]):
        raise ValueError("reidThreads debe ser un entero entre 1 y 64.")
    if c.get("identityRetentionHours") is not None and not finite(c["identityRetentionHours"], 1, 168):
        raise ValueError("La retención de la memoria de apariencia va de 1 a 168 horas.")
    ajustes = c.get("identityV2")
    if ajustes is not None and (not isinstance(ajustes, dict) or any(
            not isinstance(k, str) or isinstance(v, str) or (not isinstance(v, bool) and not finite(v, -1000, 100000)) for k, v in ajustes.items())):
        raise ValueError("identityV2 debe ser un objeto de parámetros numéricos del asociador.")
    from identity.topology import validate_routes
    validate_routes(c)
    if c.get('reidModel', 'osnet.onnx') not in ('osnet.onnx', 'osnet_ain_msmt17.onnx'):
        raise ValueError('Modelo ReID no admitido.')
    if c.get('hardware', 'auto') not in ('auto', 'cpu', 'gpu'):
        raise ValueError('Hardware inválido: automático, CPU o GPU.')
    if c.get('reidProvider', 'auto') not in ('auto', 'cpu', 'cuda', 'openvino', 'directml'):
        raise ValueError('Proveedor ReID inválido.')
    return c


def _fit_calibration_homography(points):
    """Ajusta H y devuelve (H, mascara_de_inliers, umbral, metodo).

    Las cuatro referencias mínimas siempre determinan una homografía exacta,
    pero una referencia adicional mal marcada puede inclinar todo el plano.
    Con cinco o más puntos usamos RANSAC en el espacio del plano y luego
    reajustamos con los inliers. El umbral es relativo al tamaño del plano para
    que funcione igual con coordenadas relativas y con metros.
    """
    destino = points[:, 2:]
    span = max(float(np.ptp(destino, axis=0).max()), .01)
    if len(points) < 5:
        h, mask = cv2.findHomography(points[:, :2], destino, 0)
        return h, np.ones(len(points), dtype=bool), None, "exacta"
    threshold = max(.02, span * .018)
    h, mask = cv2.findHomography(points[:, :2], destino, cv2.RANSAC,
                                 threshold, maxIters=3000, confidence=.995)
    if h is None or mask is None:
        return h, np.zeros(len(points), dtype=bool), threshold, "ransac"
    inliers = mask.reshape(-1).astype(bool)
    if int(inliers.sum()) >= 4 and not np.all(inliers):
        # RANSAC encuentra el conjunto consistente; el reajuste exacto reduce
        # el sesgo introducido por el umbral y hace reproducible la proyección.
        refined, _ = cv2.findHomography(points[inliers, :2], destino[inliers], 0)
        if refined is not None:
            h = refined
    return h, inliers, threshold, "ransac"


def calibration(pairs):
    if len(pairs) < 4:
        return None
    points = np.asarray(pairs, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 4 or not np.isfinite(points).all():
        raise ValueError("Referencias inválidas.")
    for coords in (points[:, :2], points[:, 2:]):
        span = max(float(np.ptp(coords, axis=0).max()), .01)
        if len(np.unique(coords, axis=0)) != len(coords):
            raise ValueError("Hay referencias repetidas. Elimina el punto duplicado.")
        area = cv2.contourArea(cv2.convexHull(coords.astype(np.float32)))
        if area / (span * span) < .001:
            raise ValueError("Referencias casi alineadas: distribuye los puntos por el suelo visible.")
    h, inliers, _, _ = _fit_calibration_homography(points)
    if h is None or not np.isfinite(h).all() or np.linalg.matrix_rank(h) < 3:
        raise ValueError("Calibración degenerada: distribuye los puntos por el suelo visible.")
    projected = cv2.perspectiveTransform(points[:, :2].reshape(-1, 1, 2), h).reshape(-1, 2)
    span = max(float(np.ptp(points[:, 2:], axis=0).max()), .01)
    errors = np.linalg.norm(projected - points[:, 2:], axis=1)
    # Los outliers detectados por RANSAC se informan en diagnostics; no deben
    # invalidar una calibración que tiene suficientes referencias consistentes.
    inlier_errors = errors[inliers] if len(inliers) == len(errors) and inliers.any() else errors
    if float(np.max(inlier_errors)) > span * .08:
        raise ValueError("Correspondencias inconsistentes; revisa los puntos de calibración.")
    # A horizon through the reference polygon makes interior projections unstable.
    horizon_points = points[inliers] if len(inliers) == len(points) and int(inliers.sum()) >= 4 else points
    denominators = np.c_[horizon_points[:, :2], np.ones(len(horizon_points))] @ h[2]
    if np.min(denominators) <= 0 <= np.max(denominators):
        raise ValueError("La proyección se cruza dentro del área calibrada. Revisa el orden de las correspondencias.")
    return h


MIN_REFERENCE_COVERAGE = .06   # fracción del video que deben cubrir las referencias
MAX_SCALE_RATIO = 30.          # tolerancia entre la zona más y menos comprimida por la perspectiva


def plan_span(points):
    """Mayor extensión (en unidades del plano) que cubren los puntos de referencia del plano."""
    return float(np.ptp(points[:, 2:], axis=0).max())


PLAN_SPAN_WARN = .03  # aviso de escala, nunca prueba de degeneración


def blocking_calibration_issue(pairs, plan):
    """Bloquea degeneración geométrica, no una cámara que cubre poco del aeropuerto.

    La extensión global del plano no determina la validez de una homografía local.
    La escala física necesita referencias verificadas; no puede deducirse del tamaño del mapa.
    """
    try:
        calibration(pairs)
    except ValueError as exc:
        return str(exc)
    return None


def projection_issues(h, points, zone=None, grid=14, plan=None):
    """Problemas que hacen que una calibración exacta proyecte mal a las personas.

    Con cuatro referencias el ajuste es perfecto (error casi cero) aunque la
    proyección sea inservible fuera de ellas. Se revisa sobre la zona donde se
    detectará gente: horizonte dentro de la zona, perspectiva que comprime
    zonas enteras en un punto y referencias que cubren muy poco del video.
    """
    issues = []
    size = max(plan) if plan else 0
    if size > 0 and plan_span(points) < PLAN_SPAN_WARN * size:
        issues.append(f"Calibración de un área local: extensión {plan_span(points):.2f} en un plano de {size:g}. "
                      "Comprueba la escala y las correspondencias del suelo; cubrir poco del plano no invalida la calibración.")
    coverage = float(cv2.contourArea(cv2.convexHull(points[:, :2].astype(np.float32))))
    if coverage < MIN_REFERENCE_COVERAGE:
        issues.append(f"Las referencias cubren solo el {coverage * 100:.0f}% del video: repártelas por todo el suelo donde caminan las personas.")
    polygon = np.asarray(zone if zone else [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32).reshape(-1, 1, 2)
    us, vs = np.meshgrid(np.linspace(0, 1, grid), np.linspace(0, 1, grid))
    cells = [(u, v) for u, v in zip(us.ravel(), vs.ravel()) if cv2.pointPolygonTest(polygon, (float(u), float(v)), False) >= 0]
    if len(cells) < 6:
        return issues
    uv = np.asarray(cells, dtype=np.float64)
    denominators = np.c_[uv, np.ones(len(uv))] @ h[2]
    if np.min(denominators) <= 0 <= np.max(denominators):
        issues.append("La zona de detección incluye el horizonte de la calibración (zonas muy lejanas): delimita solo el suelo cercano y bien calibrado.")
        return issues
    plan = cv2.perspectiveTransform(uv.reshape(-1, 1, 2), h).reshape(-1, 2)
    step = 1. / (grid - 1)
    key = {(round(u / step), round(v / step)): i for i, (u, v) in enumerate(uv)}
    scales = []
    for (iu, iv), i in key.items():
        for du, dv in ((1, 0), (0, 1)):
            j = key.get((iu + du, iv + dv))
            if j is not None:
                scales.append(float(np.linalg.norm(plan[i] - plan[j])) / step)
    scales = np.asarray([x for x in scales if np.isfinite(x)])
    if len(scales) and np.percentile(scales, 5) > 0 and np.percentile(scales, 95) / np.percentile(scales, 5) > MAX_SCALE_RATIO:
        issues.append("La perspectiva comprime partes del video casi en un punto del plano: personas distintas caerían en el mismo sitio. Añade referencias en esa zona o acota la zona de detección.")
    elif len(scales) and np.percentile(scales, 95) < 1e-3:
        issues.append("Toda la zona de detección se proyecta casi a un solo punto del plano: revisa que cada referencia del video corresponda a su punto del plano.")
    return issues


def calibration_diagnostics(pairs, zone=None, plan=None):
    points = np.asarray(pairs, dtype=float)
    h = calibration(pairs)
    if h is None:
        raise ValueError("Se necesitan al menos cuatro referencias.")
    _, inliers, robust_threshold, fit_method = _fit_calibration_homography(points)
    predicted = cv2.perspectiveTransform(points[:, :2].reshape(-1, 1, 2), h).reshape(-1, 2)
    errors = np.linalg.norm(predicted - points[:, 2:], axis=1)
    spread = float(cv2.contourArea(cv2.convexHull(points[:, :2].astype(np.float32))))
    checks = []
    if len(points) > 4:
        for index in range(len(points)):
            try:
                other = calibration(np.delete(points, index, axis=0).tolist())
                result = project(other, *points[index, :2])
                if result is not None:
                    checks.append(float(np.linalg.norm(result - points[index, 2:])))
            except ValueError:
                pass
    issues = projection_issues(h, points, zone, plan=plan)
    outliers = [int(i) + 1 for i, ok in enumerate(inliers) if not ok]
    if outliers:
        issues.insert(0, "Las referencias " + ", ".join(map(str, outliers)) +
                      " no concuerdan con el resto y se excluyeron del ajuste; vuelve a marcarlas si representan el suelo.")
    caveat = ("Añade referencias adicionales para comprobar puntos no usados en cada ajuste." if not checks else
              "Comprobación dejando fuera una referencia cada vez; no sustituye una medición física independiente.")
    boundary = cv2.perspectiveTransform(
        np.asarray([[[0., 0.]], [[1., 0.]], [[1., 1.]], [[0., 1.]]], dtype=np.float64), h
    ).reshape(-1, 2)
    return {"rmse": float(np.sqrt(np.mean(errors**2))), "spread": spread,
            "maxError": float(errors.max()), "pointErrors": errors.tolist(),
            "validationError": max(checks) if checks else None, "validationPoints": len(checks),
            "fitMethod": fit_method, "inlierCount": int(inliers.sum()),
            "outlierIndices": outliers, "robustThreshold": robust_threshold,
            "predictedPoints": predicted.tolist(), "projectedBoundary": boundary.tolist(),
            "issues": issues, "warning": " ".join(issues) if issues else caveat}


def box_overlap(a, b):
    ix = max(0., min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0., min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.


def collapsed_pairs(people, radius=.15, max_overlap=.1):
    """Pares de personas distintas (recuadros separados) de una cámara que caen en el mismo punto del plano."""
    rows = [p for p in people if p.get("point") is not None and p.get("box") is not None]
    count = 0
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if math.dist(a["point"], b["point"]) < radius and box_overlap(a["box"], b["box"]) <= max_overlap:
                count += 1
    return count


def project(h, u, v):
    q = h @ np.array([u, v, 1.0])
    if abs(q[2]) < 1e-8:
        return None
    p = q[:2] / q[2]
    return tuple(map(float, p)) if np.isfinite(p).all() else None


ESTATURA_MEDIA = 1.7  # metros; supuesto explícito, configurable con personHeight


def ground_point(camera, u, v, person_height=ESTATURA_MEDIA):
    """Punto del plano bajo los pies de una detección: el centro inferior de la caja pasado por la homografía del suelo.

    `person_height` se conserva en la firma por compatibilidad; los pies ya están en el suelo y no necesitan corrección.
    """
    if camera.get("h") is None:
        return None
    return project(camera["h"], u, v)


def estimate_height(camera, box, width, height):
    """Estatura aproximada (m) de una persona con recuadro completo.

    Con la cámara a altura H, el rayo que pasa por la cabeza corta el suelo más
    lejos que el rayo que pasa por los pies. Por triángulos semejantes:

        estatura = H * (1 - d_pies / d_cabeza)

    con las distancias medidas desde la base de la cámara en el plano. Es una
    estimación ruidosa: solo se calcula si el recuadro no toca el borde de la
    imagen y el resultado cae en un rango humano; si no, devuelve None.
    """
    if box is None or camera.get("h") is None:
        return None
    cam_height = float(camera.get("height") or 0)
    x1, y1, x2, y2 = box
    if cam_height <= 0 or y1 < 2 or y2 > height - 2 or x1 < 2 or x2 > width - 2 or y2 <= y1:
        return None
    cx = (x1 + x2) / 2 / width
    foot = project(camera["h"], cx, y2 / height)
    head = project(camera["h"], cx, y1 / height)
    if foot is None or head is None:
        return None
    base = (camera["x"], camera["y"])
    d_foot, d_head = math.dist(base, foot), math.dist(base, head)
    if d_head < 1e-6 or d_head <= d_foot:
        return None
    estimate = cam_height * (1 - d_foot / d_head)
    return round(estimate, 3) if .8 <= estimate <= 2.4 else None


class Occupancy:
    def __init__(self, config):
        self.config = config
        self.cells = {}
        self.last_t = None
        self.zone_stats = {}
        self.zone_start = {}
        self.cell_visitors = {}

    def update(self, people, t):
        cfg = self.config
        # Count one observed global ID once, never extrapolated invisible people.
        unique = {p["id"]: p for p in people if p.get("point") is not None and not p.get("predicted")}
        points = list(unique.values())
        dt = 0 if self.last_t is None else max(0, min(t - self.last_t, 2))
        self.last_t = t
        size = cfg["radius"]
        grid_size = min(2.,cfg["width"]/24) if cfg.get("unit")=="meters" else cfg["width"]/24
        occupied = {}
        for p in points:
            x, y = p["point"]
            key = (int(x // grid_size), int(y // grid_size))
            occupied[key] = occupied.get(key, 0) + 1
            self.cell_visitors.setdefault(key, set()).add(p["id"])
        for key, n in occupied.items():
            cell = self.cells.setdefault(key, {"seconds": 0., "peak": 0})
            cell["seconds"] += n * dt
            cell["peak"] = max(cell["peak"], n)
            cell["visits"] = len(self.cell_visitors[key])
        # Circle candidates centered on observed people; suppress duplicate circles.
        candidates = []
        for p in points:
            group = [q for q in points if math.dist(p["point"], q["point"]) <= size]
            if len(group) >= cfg["minPeople"]:
                candidates.append((len(group), p["point"]))
        circles = []
        for n, center in sorted(candidates, reverse=True):
            if any(math.dist(center, c["center"]) < size for c in circles):
                continue
            circles.append({"center": center, "count": n, "radius": size})
        previous = getattr(self, "clusters", [])
        rules = (size, cfg["minPeople"], cfg["dwell"])
        if getattr(self, "rules", None) != rules:
            previous = []
        self.rules = rules
        used = set()
        for circle in circles:
            matches = [(math.dist(circle["center"], c["center"]), i, c) for i, c in enumerate(previous) if i not in used and math.dist(circle["center"], c["center"]) <= size]
            if matches:
                _, idx, old = min(matches, key=lambda item: item[0])
                used.add(idx)
                circle["since"] = old["since"]
            else:
                circle["since"] = t
            circle["duration"] = t - circle["since"]
            circle["alert"] = circle["duration"] >= cfg["dwell"]
        self.clusters = circles
        zones = []
        for index, zone in enumerate(cfg.get("zones", [])):
            if zone.get("kind") in ("wall", "door"):
                continue
            poly = np.asarray(zone["points"], dtype=np.float32)
            members = {p["id"] for p in points if cv2.pointPolygonTest(poly, tuple(p["point"]), False) >= 0}
            n = len(members)
            zkey = zone.get("id",str(index))
            stats = self.zone_stats.setdefault(zkey,{"seconds":0.,"peak":0,"visitors":set()})
            stats["seconds"] += n * dt
            stats["peak"] = max(stats["peak"],n)
            stats["visitors"].update(members)
            rule = zone.get("rule",{})
            if rule.get("enabled") and n >= rule["minPeople"]:
                self.zone_start.setdefault(zkey,t)
            else:
                self.zone_start.pop(zkey,None)
            duration = t-self.zone_start.get(zkey,t)
            zones.append({"name":zone["name"],"count":n,"seconds":stats["seconds"],"peak":stats["peak"],"visits":len(stats["visitors"]),"duration":duration,"alert":bool(rule.get("enabled") and zkey in self.zone_start and duration >= rule["dwell"])})
        ranked = sorted(self.cells.items(), key=lambda item: item[1]["seconds"], reverse=True)[:80]
        return {"clusters": circles, "zones": zones, "heat": [{"x": k[0] * grid_size, "y": k[1] * grid_size, "size": grid_size, **v} for k, v in ranked], "mappedCount": len(unique)}
