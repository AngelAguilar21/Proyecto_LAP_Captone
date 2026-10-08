"""Shared geometric limits for observed people, never synthetic positions."""
import math
import cv2
import numpy as np


def inside(point, polygon, margin=0.):
    if point is None or not polygon:
        return False
    contour = np.asarray(polygon, dtype=np.float32)
    if margin > 0:
        return bool(cv2.pointPolygonTest(contour, tuple(map(float, point)), True) >= -margin)
    return bool(cv2.pointPolygonTest(contour, tuple(map(float, point)), False) >= 0)


MARGEN_CONTORNO = .03      # fracción del lado mayor del plano que se tolera fuera del contorno dibujado


def plan_outline(plan, snap=1e-3):
    """Contorno cerrado que dibujan las líneas del plano, en unidades del plano, o None si no hay uno solo y simple.

    Las líneas del plano (`planLines`, coordenadas 0..1) a veces son justo el borde del espacio: una cadena de segmentos que
    vuelve al primer punto. Solo se reconoce ese caso. Un plano con muchas líneas sueltas (muros, puertas, mobiliario) no
    delimita un área y no se usa como límite."""
    lines = plan.get('planLines') or []
    width, height = plan.get('width'), plan.get('height')
    if not isinstance(lines, list) or not 3 <= len(lines) <= 200 or not width or not height:
        return None
    nodes, adjacent = [], {}

    def node(x, y):
        for i, (nx, ny) in enumerate(nodes):
            if abs(nx - x) <= snap and abs(ny - y) <= snap:
                return i
        nodes.append((x, y))
        return len(nodes) - 1

    for line in lines:
        if not isinstance(line, (list, tuple)) or len(line) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in line):
            return None
        a, b = node(line[0], line[1]), node(line[2], line[3])
        if a != b:
            adjacent.setdefault(a, set()).add(b)
            adjacent.setdefault(b, set()).add(a)
    if len(adjacent) < 3 or any(len(v) != 2 for v in adjacent.values()):
        return None
    order, previous, current = [], None, next(iter(adjacent))
    while current not in order:
        order.append(current)
        following = [n for n in adjacent[current] if n != previous]
        if not following:
            return None
        previous, current = current, following[0]
    if len(order) != len(adjacent):
        return None
    polygon = [[nodes[i][0] * width, nodes[i][1] * height] for i in order]
    try:
        validate_polygon(polygon, width, height, 'Contorno del plano')
    except ValueError:
        return None
    return polygon


def outline_scope(plan):
    """Límite de trabajo implícito: el contorno del plano, si no hay uno dibujado a propósito. {} si no aplica."""
    if plan.get('workArea') or plan.get('mapAsset'):
        return {}
    polygon = plan_outline(plan)
    if not polygon:
        return {}
    return {'workArea': polygon, 'workAreaMargin': MARGEN_CONTORNO * max(plan['width'], plan['height'])}


def accepts(camera, config, u, v, ground, image_only=False):
    if camera.get('detectionZone') and not inside((u,v), camera['detectionZone']):
        return False
    # Sin homografía solo se puede evaluar la máscara de la imagen.
    if image_only:
        return True
    if not config.get('mapAsset') and config.get('workArea') and not inside(ground, config['workArea'], config.get('workAreaMargin', 0.)):
        return False
    return True


def validate_polygon(points, width, height, label):
    if not isinstance(points,list) or not 3 <= len(points) <= 100:
        raise ValueError(f'{label}: requiere de 3 a 100 vértices.')
    for p in points:
        if not isinstance(p,list) or len(p)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) or not 0 <= p[0] <= width or not 0 <= p[1] <= height:
            raise ValueError(f'{label}: punto fuera del área.')
    if abs(cv2.contourArea(np.asarray(points,dtype=np.float32))) < 1e-6:
        raise ValueError(f'{label}: área degenerada.')
    # Reject crossing non-adjacent edges instead of interpreting a bow-tie mask.
    def cross(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for i,a in enumerate(points):
        b=points[(i+1)%len(points)]
        for j in range(i+2,len(points)):
            if i==0 and j==len(points)-1:
                continue
            c,d=points[j],points[(j+1)%len(points)]
            if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:
                raise ValueError(f'{label}: los bordes se cruzan.')
