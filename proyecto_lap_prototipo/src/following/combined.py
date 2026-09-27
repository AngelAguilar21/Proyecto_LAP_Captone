"""Analítica por cámara reutilizando la única inferencia P2PNet del ciclo."""
from types import SimpleNamespace
from counting.analytics import CountingAnalytics
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
        p2p_points = self.fast[cid].update(points, 1, 1, t)
        snapshot = self.fast[cid].snapshot()
        result = {'t': t, 'occupancy': self.fast[cid].snapshot(), 'crossings': self.lines[cid].update(normalized,t),
                  'dense': {'t': t, 'points': p2p_points, **snapshot}, 'denseEnabled': True}
        self.snapshots[cid]=result
        return result

    def close(self):
        for cid, snapshot in self.snapshots.items():
            self.fast[cid].finish(snapshot['t'],'análisis finalizado')
            snapshot['occupancy']=self.fast[cid].snapshot()
            snapshot['dense']={**snapshot['dense'],**snapshot['occupancy']}
        return self.snapshots
