"""Shared geometric limits for observed people, never synthetic positions."""
import math
import cv2
import numpy as np


def inside(point, polygon):
    return bool(point is not None and polygon and cv2.pointPolygonTest(np.asarray(polygon, dtype=np.float32), tuple(map(float, point)), False) >= 0)


def coverage_contains(camera, point):
    if point is None:
        return False
    shape = camera.get('coverageShape', 'cone')
    if shape == 'free':
        return inside(point, camera.get('coveragePolygon'))
    dx, dy = point[0]-camera['x'], point[1]-camera['y']
    angle = math.radians(camera.get('heading', 90))
    forward = dx*math.cos(angle)+dy*math.sin(angle)
    sideways = -dx*math.sin(angle)+dy*math.cos(angle)
    radius = camera.get('range', 3)
    if shape == 'rectangle':
        return -1e-7 <= forward <= radius+1e-7 and abs(sideways) <= camera.get('coverageWidth', 2)/2+1e-7
    return math.hypot(dx,dy) <= radius+1e-7 and abs(math.atan2(sideways,forward)) <= math.radians(camera.get('fov',60)/2)+1e-7


def accepts(camera, config, u, v, ground):
    if camera.get('detectionZone') and not inside((u,v), camera['detectionZone']):
        return False
    if config.get('workArea') and not inside(ground, config['workArea']):
        return False
    if camera.get('restrictCoverage', False) and not coverage_contains(camera, ground):
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
