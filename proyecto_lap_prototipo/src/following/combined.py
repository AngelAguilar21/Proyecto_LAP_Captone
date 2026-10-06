"""Analítica por cámara con los puntos de seguimiento: ocupación de zonas de la imagen y cruces de líneas."""
from types import SimpleNamespace
from .zone_counts import CountingAnalytics
from .line_counter import LineCounter


class CombinedAnalysis:
    def __init__(self, cameras, root=None, interval=.2):
        self.cameras = {c['id']: c for c in cameras}
        self.fast = {}
        self.lines = {}
        self.snapshots = {}
        for c in cameras:
            definition = {'interval': interval, 'cameraZone': c.get('detectionZone'), 'zones': [
                {'id': 'useful', 'name': 'Zona útil', 'points': c.get('detectionZone') or [[0,0],[1,0],[1,1],[0,1]],
                  'threshold': c.get('crowdThreshold', 10), 'dwell': c.get('crowdDwell', 3)},*(c.get('analysisZones') or [])]}
            self.fast[c['id']] = CountingAnalytics(definition)
            self.lines[c['id']] = LineCounter(c.get('countLines', []))

    def observe(self, camera, frame, people, t):
        cid = camera['id']; h, w = frame.shape[:2]
        normalized = [{'id': p.get('local',p['id']), 'pixel': [p['pixel'][0]/w, p['pixel'][1]/h]} for p in people]
        points = [SimpleNamespace(x=p['pixel'][0], y=p['pixel'][1]) for p in normalized]
        self.fast[cid].update(points, 1, 1, t)
        result = {'t': t, 'occupancy': self.fast[cid].snapshot(), 'crossings': self.lines[cid].update(normalized,t)}
        self.snapshots[cid]=result
        return result

    def close(self):
        for cid, snapshot in self.snapshots.items():
            self.fast[cid].finish(snapshot['t'],'análisis finalizado')
            snapshot['occupancy']=self.fast[cid].snapshot()
        return self.snapshots
