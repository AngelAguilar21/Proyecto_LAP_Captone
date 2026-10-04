"""Geometry, conservative camera handoffs and observed occupancy for the live UI.

Coordinates are always in a shared, user-defined plane. Association confidence is
a heuristic, not a calibrated probability. No biometric models are used here.
"""
from spatial_scope import validate_polygon
import copy
import math
from collections import deque
from zone_episodes import ZoneEpisodes, ensure_zone_ids

import cv2
import numpy as np


def finite(value, low, high):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def valid_plan_id(value):
    return (isinstance(value, str) and value in ("custom", "lap-1", "lap-2", "lap-3", "lap-4")) or (
        isinstance(value, str) and value.startswith("floor-") and 7 < len(value) <= 48
        and all(char.isalnum() or char in "_-" for char in value)
    )


def validate_calibration_pairs(pairs, plan=None, *, require_complete=False):
    """Shared geometry and contextual bounds used by save and calibration-check."""
    if not isinstance(pairs, list) or len(pairs)>30 or (require_complete and len(pairs)<4):
        raise ValueError("Usa entre 4 y 30 correspondencias para comprobar la calibración.")
    if plan is not None and (not isinstance(plan,dict) or
            any(not finite(plan.get(k),1,10000) for k in ('width','height'))):
        raise ValueError("Dimensiones del plano inválidas para comprobar calibración.")
    for p in pairs:
        if not isinstance(p,list) or len(p)!=4 or not all(finite(v,-10000,10000) for v in p):
            raise ValueError("Cada correspondencia contiene [u, v, x, y].")
        if not (0<=p[0]<=1 and 0<=p[1]<=1) or (plan is not None and not (0<=p[2]<=plan['width'] and 0<=p[3]<=plan['height'])):
            raise ValueError("Puntos fuera del video o del plano.")
    if len(pairs)>=4:
        calibration(pairs)
        points=np.asarray(pairs,dtype=np.float32)
        if cv2.contourArea(cv2.convexHull(points[:,:2].copy()))<.005:
            raise ValueError("Referencias casi alineadas: distribuye los nodos por todo el suelo visible.")


def validate_config(c):
    if not isinstance(c, dict):
        raise ValueError("La configuración debe ser un objeto.")
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
        validate_config(copy.deepcopy({**c,**plan,"planId":pid,"plans":{},"cameras":[]}))
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
        for field in ("denseCounting", "denseInterval", "luggageWatch", "luggageDwell", "luggageInterval"):
            cam.pop(field, None)
        cid = cam.get("id", "")
        if not isinstance(cid, str) or not cid or len(cid) > 40 or not all(x.isalnum() or x in "_-" for x in cid) or cid in ids:
            raise ValueError("Cada cámara necesita un ID único, sin espacios ni símbolos especiales.")
        ids.add(cid)
        source = cam.get("source")
        if not ((isinstance(source, int) and not isinstance(source, bool) and 0 <= source <= 32) or (isinstance(source, str) and len(source) <= 2048)):
            raise ValueError(f"Fuente inválida: {cid}.")
        if not finite(cam.get("offset", 0), 0, 86400):
            raise ValueError("Offset debe ser no negativo (segundos que se omiten al inicio).")
        pid=cam.get("planId","custom")
        if not valid_plan_id(pid) or (pid!=c.get("planId","custom") and pid not in plans):
            raise ValueError(f"Plano de cámara desconocido en {cid}.")
        cam_plan=c if cam.get("planId","custom")==c.get("planId","custom") else plans.get(cam.get("planId","custom"),c)
        for key, maximum in [("x", cam_plan["width"]), ("y", cam_plan["height"])]:
            if not finite(cam.get(key), 0, maximum):
                raise ValueError(f"Posición {key} inválida en {cid}.")
        if not isinstance(cam.get("links", []), list):
            raise ValueError("links debe ser una lista de cámaras de destino.")
        for field, low, high in [("heading",0,360),("fov",5,170),("range",.01,10000),("height",0,10000),("tilt",0,90)]:
            if field in cam and not finite(cam[field], low, high):
                raise ValueError(f"{cid}: {field} fuera de rango.")
        for field in ("name", "location"):
            if field in cam and (not isinstance(cam[field], str) or len(cam[field]) > 160):
                raise ValueError(f"{cid}: {field} inválido.")
        for field in ("active", "restrictCoverage", "illustrative"):
            if field in cam and not isinstance(cam[field],bool):
                raise ValueError(f"{field}: debe ser booleano.")
        if cam.get("coveragePolygon"):
            validate_polygon(cam["coveragePolygon"],cam_plan["width"],cam_plan["height"],"Cobertura")
        if cam.get("coverageShape", "cone") not in ("cone","rectangle","free"):
            raise ValueError("Forma de cobertura inválida.")
        if "coverageWidth" in cam and not finite(cam["coverageWidth"],.01,10000):
            raise ValueError("Ancho de cobertura inválido.")
        pairs = cam.get("pairs", [])
        validate_calibration_pairs(pairs, cam_plan)
        for field, lo, hi in [('crowdThreshold',1,1000),('crowdDwell',0,3600)]:
            if field in cam and not finite(cam[field],lo,hi):
                raise ValueError(f'{cid}: {field} fuera de rango.')
        if cam.get('analysisZones'):
            from counting.analytics import validate as validate_counting
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
    ensure_zone_ids(c)
    return c


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
    h, _ = cv2.findHomography(points[:, :2], points[:, 2:], 0)
    if h is None or not np.isfinite(h).all() or np.linalg.matrix_rank(h) < 3:
        raise ValueError("Calibración degenerada: distribuye los puntos por el suelo visible.")
    projected = cv2.perspectiveTransform(points[:, :2].reshape(-1, 1, 2), h).reshape(-1, 2)
    span = max(float(np.ptp(points[:, 2:], axis=0).max()), .01)
    if float(np.linalg.norm(projected - points[:, 2:], axis=1).max()) > span * .08:
        raise ValueError("Correspondencias inconsistentes; revisa los puntos de calibración.")
    # A horizon through the reference polygon makes interior projections unstable.
    denominators = np.c_[points[:, :2], np.ones(len(points))] @ h[2]
    if np.min(denominators) <= 0 <= np.max(denominators):
        raise ValueError("La proyección se cruza dentro del área calibrada. Revisa el orden de las correspondencias.")
    return h


def calibration_diagnostics(pairs):
    h = calibration(pairs)
    if h is None:
        raise ValueError("Se necesitan al menos cuatro referencias.")
    points = np.asarray(pairs, dtype=float)
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
    return {"rmse": float(np.sqrt(np.mean(errors**2))), "spread": spread,
            "maxError": float(errors.max()), "pointErrors": errors.tolist(),
            "validationError": max(checks) if checks else None, "validationPoints": len(checks),
            "warning": "Añade referencias adicionales para comprobar puntos no usados en cada ajuste." if not checks else
                       "Comprobación dejando fuera una referencia cada vez; no sustituye una medición física independiente."}


def project(h, u, v):
    q = h @ np.array([u, v, 1.0])
    if abs(q[2]) < 1e-8:
        return None
    p = q[:2] / q[2]
    return tuple(map(float, p)) if np.isfinite(p).all() else None


ESTATURA_MEDIA = 1.7  # metros; supuesto explícito, configurable con personHeight


def head_to_ground(h, u, v, camera_x, camera_y, camera_height, person_height=ESTATURA_MEDIA):
    """Lleva un punto de cabeza al punto del suelo donde está la persona.

    P2PNet marca la cabeza, no los pies. Pasar la cabeza por la homografía del
    suelo la deja demasiado lejos de la cámara, porque el rayo que la ve sigue
    hasta cortar el piso más allá de la persona. Ese corte es G. Como los pies
    están justo debajo de la cabeza, quedan sobre el segmento que une la base de
    la cámara con G, a una fracción exacta del camino:

        pies = base + (G - base) * (1 - estatura / altura_de_camara)

    No es una aproximación: sale de intersectar el mismo rayo con z=0 y con
    z=estatura. Solo depende de que la altura de la cámara supere la estatura
    supuesta; si no la supera, el rayo nunca vuelve al suelo por delante y la
    conversión no existe, así que devolvemos None en vez de inventar un punto.

    La fracción es un cociente de alturas reales, así que no cambia si el plano
    está en metros o en unidades relativas.
    """
    if not finite(camera_height, 0, 10000) or camera_height <= person_height:
        return None
    g = project(h, u, v)
    if g is None:
        return None
    keep = 1. - person_height / camera_height
    return (camera_x + (g[0] - camera_x) * keep, camera_y + (g[1] - camera_y) * keep)


def body_box(h_inv, head_px, head_py, ground, width, height, ratio=.4):
    """Recuadro aproximado del cuerpo a partir de un punto de cabeza.

    P2PNet no entrega recuadros, y sin uno no se puede mirar la ropa para
    distinguir a dos personas vistas por cámaras distintas. Invirtiendo la
    homografía se sabe en qué píxel caen los pies que ya ubicamos en el suelo, y
    la distancia cabeza-pies da la altura de la persona en la imagen sin suponer
    ninguna escala fija. El ancho sí es un supuesto (ratio), tolerable porque el
    recorte solo se usa para muestrear color, no para medir ni para mostrar.
    """
    if h_inv is None or ground is None:
        return None
    foot = project(h_inv, ground[0], ground[1])
    if foot is None:
        return None
    foot_py = foot[1] * height
    tall = foot_py - head_py
    if not (4 < tall < height * 2):   # los pies han de caer debajo de la cabeza
        return None
    half = tall * ratio / 2
    return [head_px - half, head_py, head_px + half, foot_py]


def ground_point(camera, u, v, person_height=ESTATURA_MEDIA):
    """Punto en el plano de una detección, según lo que marque el detector.

    P2PNet entrega la cabeza y hay que corregirla antes de usar la homografía
    del suelo. El modo directo se conserva solo para datos geométricos de prueba.
    """
    if camera.get("h") is None:
        return None
    if camera.get("headPoints"):
        return head_to_ground(camera["h"], u, v, camera["x"], camera["y"],
                              camera.get("height"), person_height)
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
    if box is None or camera.get("h") is None or camera.get("headPoints"):
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


def height_penalty(person, observation, tolerance=.12, span=.3, weight=.25):
    """Penaliza una diferencia de estatura, sin descartar: la medida es ruidosa."""
    a, b = person.get("height"), observation.get("height")
    if a is None or b is None:
        return 0.
    return min(max(abs(a - b) - tolerance, 0.) / span, 1.) * weight


def color_distance(a, b):
    if a is None or b is None:
        return .5
    return float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))


def identity_appearance_distance(person, current):
    """Compara contra una galería de vistas, no solo contra el último frame.

    Una persona de espaldas o con otra orientación puede cambiar mucho su
    histograma. Conservar varias muestras evita que la última pose reemplace
    una firma útil obtenida en otra cámara o instante.
    """
    if current is None:
        return .5
    gallery = person.get("appearanceGallery") or []
    if not gallery and person.get("color") is not None:
        gallery = [person["color"]]
    return min((color_distance(item, current) for item in gallery), default=.5)


# Pesos iniciales de la puntuación de asociación; deben calibrarse con video real
# (se pueden sobrescribir con config["reidWeights"]).
REID_WEIGHTS = {"appearance": .40, "spatial": .30, "motion": .15, "time": .10, "size": .05}
REID_MAX_EMBEDDING_DISTANCE = .45   # distancia coseno máxima aceptable con OSNet
REID_MAX_CROSS_VIEW_DISTANCE = .65   # entre cámaras (otro ángulo) el embedding varía mucho: veto solo si es muy distinto
REID_OVERLAP_VETO_DISTANCE = .85     # en solape solo una apariencia radicalmente distinta descarta la coincidencia
REID_ACCEPT_SCORE = .40             # por debajo, la evidencia es débil: no se reutiliza el ID
REID_AMBIGUITY_MARGIN = .04         # diferencia mínima de puntuación entre el 1.º y el 2.º candidato
EMBEDDING_GALLERY_SIZE = 12
EMBEDDING_NEW_VIEW = .12            # distancia mínima para guardar una vista nueva


def embedding_distance(a, b):
    """Distancia coseno entre vectores L2-normalizados, acotada a [0, 1]."""
    return float(min(max(1. - float(np.dot(a, b)), 0.), 1.))


def appearance_distance(person, observation):
    """Distancia de apariencia contra la mejor vista de la galería.

    Usa OSNet cuando ambos lados tienen embedding; si no, la firma de color.
    Devuelve (distancia, usa_embedding).
    """
    embedding = observation.get("embedding")
    gallery = person.get("embeddingGallery")
    if embedding is not None and gallery:
        return min(embedding_distance(item, embedding) for item in gallery), True
    return identity_appearance_distance(person, observation.get("color")), False


def height_agreement(person, observation, tolerance=.12, span=.3):
    """1 si las estaturas coinciden, 0 si difieren mucho, None si falta el dato."""
    a, b = person.get("height"), observation.get("height")
    if a is None or b is None:
        return None
    return 1. - min(max(abs(a - b) - tolerance, 0.) / span, 1.)


def association_score(cfg, appearance, distance_ratio, alignment, time_ratio, size):
    """Puntuación de asociación en [0, 1]; mayor es más probable la misma persona.

    appearance: distancia de apariencia; distance_ratio: distancia/umbral;
    alignment: coseno entre desplazamiento y velocidad (None si se desconoce);
    time_ratio: tiempo transcurrido/ventana; size: coincidencia de estatura.
    """
    weights = {**REID_WEIGHTS, **(cfg.get("reidWeights") or {})}
    parts = {
        "appearance": 1. - min(max(appearance, 0.), 1.),
        "spatial": max(0., 1. - distance_ratio),
        "motion": .5 if alignment is None else (max(-1., min(1., alignment)) + 1.) / 2.,
        "time": 1. - min(max(time_ratio, 0.), 1.),
        "size": .5 if size is None else size,
    }
    total = sum(weights.values()) or 1.
    return sum(weights[key] * parts[key] for key in parts) / total


def update_appearance(previous, current, weight=.25):
    """Suaviza la firma visual para que un reflejo o un frame no cambie el ID."""
    if current is None:
        return previous
    if previous is None or previous.shape != current.shape:
        return current
    blended = previous * (1 - weight) + current * weight
    return cv2.normalize(blended, blended, alpha=1, norm_type=cv2.NORM_L1)


class IdentityStore:
    """One assignment per global ID per camera per tick, with ambiguity rejection.

    Overlap compares simultaneous ground positions. Non-overlap uses declared
    directed camera links, elapsed time, velocity, and a clothing-color gate.
    Both are explicitly labelled 'estimated' camera associations.
    """
    def __init__(self, config):
        self.config = config
        self.people = {}
        self.local = {}
        self.serial = 0
        self.events = deque(maxlen=150)
        self.overlap_evidence = {}

    def reconcile_overlap(self, observations, t):
        """Reconcilia IDs ya creados solo con coincidencia mutua y evidencia sostenida."""
        if not self.config['clocksVerified']:
            return
        known = [o for o in observations if o.get('point') is not None and (o['camera'],o['local']) in self.local]
        nearest = {}
        for i,a in enumerate(known):
            cam = next(c for c in self.config['cameras'] if c['id']==a['camera'])
            scores=[]
            for j,b in enumerate(known):
                if a['camera']==b['camera'] or b['camera'] not in cam.get('links',[]):continue
                other=next(c for c in self.config['cameras'] if c['id']==b['camera'])
                if cam.get('planId','custom')!=other.get('planId','custom'):continue
                if self.local[a['camera'],a['local']]==self.local[b['camera'],b['local']]:continue
                # Dos homografías reales rara vez coinciden al centímetro. La
                # cercanía mutua y sostenida permite absorber ese error sin
                # fusionar una multitud completa por proximidad.
                gate=self.config['matchDistance']*1.6
                distance=math.dist(a['point'],b['point'])/gate
                if a.get('embedding') is not None and b.get('embedding') is not None:
                    # Entre cámaras el ángulo cambia el embedding: en solape la posición
                    # manda y la apariencia solo desempata o veta una diferencia enorme.
                    appearance=embedding_distance(a['embedding'],b['embedding'])
                    if appearance>REID_OVERLAP_VETO_DISTANCE:continue
                    if distance<=1:scores.append((distance+appearance*.25,j))
                    continue
                appearance=color_distance(a.get('color'),b.get('color'))
                if distance<=1 and (appearance<.6 or distance<=.3):scores.append((distance+appearance*.25,j))
            scores.sort()
            if scores and (len(scores)==1 or scores[1][0]-scores[0][0]>.12):nearest[i]=scores[0][1]
        evidence={}
        for i,j in nearest.items():
            if j<=i or nearest.get(j)!=i:continue
            a,b=known[i],known[j]
            ids=tuple(sorted([self.local[a['camera'],a['local']],self.local[b['camera'],b['local']]]))
            if ids[0]==ids[1] or any(gid not in self.people for gid in ids):continue
            old=self.overlap_evidence.get(ids,{'t':-100,'n':0})
            evidence[ids]={'t':t,'n':old['n']+1 if t-old['t']<=1.5 else 1}
            if evidence[ids]['n']<3:continue
            cameras=[{o['camera'] for o in known if self.local[o['camera'],o['local']]==gid} for gid in ids]
            if cameras[0]&cameras[1]:continue
            keep,drop=ids
            self.local={key:keep if value==drop else value for key,value in self.local.items()}
            self.people[keep]['association']='estimated'
            self.people.pop(drop,None)
            self.events.appendleft({'type':'handoff','id':keep,'from':a['camera'],'to':b['camera'],'t':t,'reason':'coincidencia mutua sostenida'})
        self.overlap_evidence=evidence

    def update(self, observations, t):
        cfg = self.config
        self.reconcile_overlap(observations,t)
        claimed = set()
        grouped = {}
        for o in observations:
            gid = self.local.get((o["camera"],o["local"]))
            if gid is not None and o.get("point") is not None:
                grouped.setdefault(gid,[]).append(o)
        for group in grouped.values():
            anchor=group[0]
            for o in group[1:]:
                if o["camera"]!=anchor["camera"] and math.dist(o["point"],anchor["point"])>cfg["matchDistance"]*1.75:
                    self.local.pop((o["camera"],o["local"]),None)
        observed_keys = {(o["camera"], o["local"]) for o in observations}
        mapped = {self.local[k] for k in observed_keys if k in self.local}
        output = []
        # Existing tracks first: this makes handoffs independent of camera ordering.
        ordered = sorted(observations, key=lambda o: (o["camera"], o["local"]) not in self.local)
        for o in ordered:
            key = (o["camera"], o["local"])
            gid = self.local.get(key)
            if gid is not None and (gid, o["camera"]) in claimed:
                gid = None
            association = "local"
            reid_score = None
            weak_evidence = False
            # Recupera una identidad cuando ByteTrack pierde una detección y
            # crea otro ID local en la misma cámara. Esto ocurre por oclusiones,
            # saltos de confianza o cambios bruscos de escala; no debe generar
            # una nueva persona global si la posición y la apariencia siguen
            # siendo compatibles.
            if gid is None and o.get("point") is not None:
                candidates = []
                for pid, p in self.people.items():
                    if (pid, o["camera"]) in claimed or p["point"] is None:
                        continue
                    dt = t - p["t"]
                    if dt < 0 or dt > cfg["handoffSeconds"]:
                        continue
                    same_camera = p["camera"] == o["camera"]
                    if same_camera:
                        # En una misma cámara no dependemos de clocksVerified ni
                        # de enlaces entre cámaras. La posición se compara con
                        # la predicción de movimiento y se usa un margen algo
                        # mayor para absorber una detección perdida.
                        target = (p["point"][0] + p["velocity"][0] * dt,
                                  p["point"][1] + p["velocity"][1] * dt)
                        gate = cfg["matchDistance"] * (2.2 + min(dt, 2) * .35)
                        dist = math.dist(o["point"], target)
                        appearance, by_embedding = appearance_distance(p, o)
                        if dist <= gate and by_embedding and appearance > REID_MAX_EMBEDDING_DISTANCE:
                            weak_evidence = True
                            continue
                        if dist <= gate and (by_embedding or appearance <= .78 or dist <= gate * .35):
                            shift = (o["point"][0] - p["point"][0], o["point"][1] - p["point"][1])
                            shift_len, speed = math.hypot(*shift), math.hypot(*p["velocity"])
                            alignment = (sum(shift[i] * p["velocity"][i] for i in (0, 1)) / (shift_len * speed)
                                         if shift_len > .01 and speed > .05 else None)
                            score = association_score(cfg, appearance, dist / gate, alignment,
                                                      dt / max(float(cfg["handoffSeconds"]), .1), height_agreement(p, o))
                            candidates.append((1. - score, pid, True, score))
                        continue
                    # Entre cámaras distintas solo se asocia identidad si el
                    # operador declaró verificada la sincronización de relojes
                    # (RF-04). Sin esa declaración cada cámara conserva su ID.
                    if not cfg["clocksVerified"]:
                        continue
                    old_cam = next(c for c in cfg["cameras"] if c["id"] == p["camera"])
                    new_cam=next(c for c in cfg["cameras"] if c["id"]==o["camera"])
                    if new_cam.get("planId","custom")!=old_cam.get("planId","custom"):continue
                    if o["camera"] not in old_cam.get("links", []):
                        continue
                    # A track still observed elsewhere can only match as an overlap.
                    overlap = pid in mapped or dt <= .5
                    if overlap:
                        target = p["point"]
                        gate = cfg["matchDistance"] * 1.6
                    else:
                        target = (p["point"][0] + p["velocity"][0] * dt, p["point"][1] + p["velocity"][1] * dt)
                        speed = math.hypot(*p["velocity"])
                        # El margen crece con el tiempo oculto y con la velocidad
                        # estimada por Kalman. Así una persona puede atravesar el
                        # espacio sin cobertura sin recibir un ID nuevo.
                        gate = cfg["matchDistance"] * (2.0 + min(dt, 5) * .55) + speed * dt * .35
                    dist = math.dist(o["point"], target)
                    appearance, by_embedding = appearance_distance(p, o)
                    alignment = None
                    displacement = (o["point"][0] - p["point"][0], o["point"][1] - p["point"][1])
                    displacement_length = math.hypot(*displacement)
                    velocity_length = math.hypot(*p["velocity"])
                    if not overlap and displacement_length > .01 and velocity_length > .05:
                        alignment = sum(displacement[i] * p["velocity"][i] for i in (0, 1)) / (displacement_length * velocity_length)
                        if alignment < -.35 and appearance > .45:
                            continue
                    # Con solape la posición simultánea es la evidencia fuerte; sin solape
                    # (traspaso con tiempo oculto) la apariencia pesa más, con tolerancia al ángulo.
                    veto = REID_OVERLAP_VETO_DISTANCE if overlap else REID_MAX_CROSS_VIEW_DISTANCE
                    if dist <= gate and by_embedding and appearance > veto:
                        weak_evidence = True
                        continue
                    if dist <= gate and (by_embedding or appearance <= .82 or (overlap and dist <= gate*.3)):
                        score = association_score(cfg, appearance, dist / gate, alignment,
                                                  dt / max(float(cfg["handoffSeconds"]), .1), height_agreement(p, o))
                        candidates.append((1. - score, pid, False, score))
                candidates.sort()
                accept = float(cfg.get("reidAcceptScore", REID_ACCEPT_SCORE))
                margin = float(cfg.get("reidAmbiguityMargin", REID_AMBIGUITY_MARGIN))
                unambiguous = candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] > margin)
                if unambiguous and 1. - candidates[0][0] >= accept:
                    gid = candidates[0][1]
                    reid_score = candidates[0][3]
                    # "reidentified": recupera un track perdido en la misma cámara.
                    association = "reidentified" if candidates[0][2] else "estimated"
                    self.events.appendleft({"type": "reidentification" if candidates[0][2] else "handoff", "id": gid, "from": self.people[gid]["camera"], "to": o["camera"], "t": t, "score": round(reid_score, 3)})
                elif candidates or weak_evidence:
                    # Ambigua o con evidencia débil: no se fuerza la coincidencia.
                    association = "uncertain"
            if gid is None:
                self.serial += 1
                gid = f"P{self.serial:05d}"
                self.people[gid] = {"history": deque(maxlen=180), "velocity": (0., 0.), "t": t, "point": None, "association": association, "appearanceGallery": deque(maxlen=12)}
            self.local[key] = gid
            claimed.add((gid, o["camera"]))
            p = self.people[gid]
            if o["point"] is not None and p["point"] is not None and t > p["t"]:
                dt = t - p["t"]
                p["velocity"] = tuple(.5 * p["velocity"][i] + .5 * (o["point"][i] - p["point"][i]) / dt for i in (0, 1))
            if association != "local":
                p["association"] = association
                p["reidScore"] = reid_score
            embedding = o.get("embedding")
            if embedding is not None:
                views = p.setdefault("embeddingGallery", deque(maxlen=EMBEDDING_GALLERY_SIZE))
                if not views or min(embedding_distance(item, embedding) for item in views) > EMBEDDING_NEW_VIEW:
                    views.append(embedding)
            appearance = update_appearance(p.get("color"), o.get("color"))
            gallery = p.setdefault("appearanceGallery", deque(maxlen=12))
            current_color = o.get("color")
            if current_color is not None and not gallery:
                gallery.append(current_color)
            elif current_color is not None and min((color_distance(item, current_color) for item in gallery), default=1.) > .08:
                gallery.append(current_color)
            p.update(camera=o["camera"], point=o["point"], t=t, color=appearance)
            if o.get("height") is not None:
                heights = p.setdefault("heights", deque(maxlen=15))
                heights.append(o["height"])
                p["height"] = float(sorted(heights)[len(heights) // 2])
            if o["point"] is not None:
                if not p["history"] or p["history"][-1][2] != t:
                    p["history"].append([*o["point"], t])
            neighbors = next(c for c in cfg["cameras"] if c["id"]==o["camera"]).get("links",[])
            next_camera = None
            if o["point"] is not None and math.hypot(*p["velocity"]) > .05 and neighbors:
                future = (o["point"][0]+p["velocity"][0]*2,o["point"][1]+p["velocity"][1]*2)
                next_camera = min((c for c in cfg["cameras"] if c["id"] in neighbors),key=lambda c:math.dist(future,(c["x"],c["y"])))["id"]
            output.append({**{k: v for k, v in o.items() if k not in ("color", "embedding")}, "id": gid, "association": p["association"], "reidScore": p.get("reidScore"), "history": list(p["history"]), "predicted": False, "velocity": list(p["velocity"]), "nextCamera": next_camera, "height": p.get("height")})
        # Bound retention to the declared handoff window; no indefinite identities.
        expired = {pid for pid, p in self.people.items() if t - p["t"] > cfg["handoffSeconds"]}
        for pid in expired:
            del self.people[pid]
        # Local IDs no longer seen must expire even when another camera keeps
        # the same global identity alive indefinitely.
        last_seen = getattr(self, "last_seen", {})
        for key in observed_keys:
            last_seen[key] = t
        self.local = {k: v for k, v in self.local.items() if v not in expired and t - last_seen.get(k, t) <= cfg["handoffSeconds"]}
        self.last_seen = {k: last_seen[k] for k in self.local}
        return output


class Occupancy:
    def __init__(self, config, scope=None, episode_namespace=None):
        ensure_zone_ids(config)
        self.config = config
        self.cells = {}
        self.last_t = None
        self.zone_stats = {}
        self.zone_episodes = ZoneEpisodes(scope or "plan:" + config.get("planId", "custom"), episode_namespace)
        self.cell_visitors = {}

    def update(self, people, t, observation_valid=True):
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
        configured = [z for z in cfg.get("zones", []) if z.get("kind") not in ("wall", "door")]
        self.zone_episodes.retain([z["id"] for z in configured], t)
        for zone in configured:
            poly = np.asarray(zone["points"], dtype=np.float32)
            members = {p["id"] for p in points if cv2.pointPolygonTest(poly, tuple(p["point"]), False) >= 0}
            n = len(members)
            zkey = zone["id"]
            stats = self.zone_stats.setdefault(zkey,{"seconds":0.,"peak":0,"visitors":set()})
            if observation_valid:
                stats["seconds"] += n * dt
                stats["peak"] = max(stats["peak"],n)
                stats["visitors"].update(members)
            episode = self.zone_episodes.observe(zone, n, t, observation_valid,
                context=[cfg.get(k) for k in ("width", "height", "unit", "workArea")])
            zones.append({"id":zkey,"name":zone["name"],"count":n if observation_valid else None,"seconds":stats["seconds"],"peak":stats["peak"],"visits":len(stats["visitors"]),
                          "duration":episode["duration"] if episode else 0.,
                          "alert":bool(episode and episode["alert"] and observation_valid),
                          "observed":bool(observation_valid), "scope":self.zone_episodes.scope,
                          "episodeId":episode["id"] if episode else None,
                          "start":episode["start"] if episode else None})
        ranked = sorted(self.cells.items(), key=lambda item: item[1]["seconds"], reverse=True)[:80]
        return {"clusters": circles, "zones": zones, "heat": [{"x": k[0] * grid_size, "y": k[1] * grid_size, "size": grid_size, **v} for k, v in ranked], "mappedCount": len(unique),
                "zoneEpisodes": self.zone_episodes.snapshot()}
