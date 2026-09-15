"""Una fuente produce ocupación, calor, episodios y cruces, además de trayectorias."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import cv2
from counting.analytics import CountingAnalytics
from .line_counter import LineCounter


class CombinedAnalysis:
    def __init__(self, cameras, root, interval=.2):
        self.cameras = {c['id']: c for c in cameras}
        self.fast = {}
        self.lines = {}
        self.dense = {}
        self.last_dense = {c['id']: -100. for c in cameras}
        self.root = root
        self.model = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='conteo-denso')
        self.pending = None
        self.error = None
        self.results = {}
        self.snapshots = {}
        for c in cameras:
            definition = {'interval': interval, 'cameraZone': c.get('detectionZone'), 'zones': [
                {'id': 'useful', 'name': 'Zona útil', 'points': c.get('detectionZone') or [[0,0],[1,0],[1,1],[0,1]],
                 'threshold': c.get('crowdThreshold', 10), 'dwell': c.get('crowdDwell', 3)},*(c.get('analysisZones') or [])]}
            self.fast[c['id']] = CountingAnalytics(definition)
            self.lines[c['id']] = LineCounter(c.get('countLines', []))
            self.dense[c['id']] = CountingAnalytics({**definition, 'interval': c.get('denseInterval', 5)})

    def _density(self, cid, frame, t):
        if self.model is None:
            from detection import DetectorP2PNet
            self.model = DetectorP2PNet(str(self.root/'external/P2PNet/weights/SHTechA.pth'), umbral=.5, device='cpu')
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (round(w*min(1,768/max(h,w))), round(h*min(1,768/max(h,w)))))
        points = self.model.detectar(frame)
        normalized = self.dense[cid].update(points, frame.shape[1], frame.shape[0], t)
        return cid, {'t': t, 'points': normalized, **self.dense[cid].snapshot()}

    def observe(self, camera, frame, people, t):
        cid = camera['id']; h, w = frame.shape[:2]
        normalized = [{'id': p.get('local',p['id']), 'pixel': [p['pixel'][0]/w, p['pixel'][1]/h]} for p in people]
        points = [SimpleNamespace(x=p['pixel'][0], y=p['pixel'][1]) for p in normalized]
        self.fast[cid].update(points, 1, 1, t)
        if self.pending and self.pending.done():
            try:
                key, result = self.pending.result()
                self.results[key] = result
            except Exception as exc:
                self.error = str(exc)
            self.pending = None
        if camera.get('denseCounting', False) and self.pending is None and t-self.last_dense[cid] >= camera.get('denseInterval',5):
            # Cola de tamaño uno: el conteo especializado no bloquea la lectura en vivo.
            due = [key for key,c in self.cameras.items() if c.get('denseCounting')]
            if not due or cid == min(due, key=lambda key:self.last_dense[key]):
                self.last_dense[cid] = t
                self.pending = self.pool.submit(self._density, cid, frame.copy(), t)
        result = {'t': t, 'occupancy': self.fast[cid].snapshot(), 'crossings': self.lines[cid].update(normalized,t),
                'dense': self.results.get(cid), 'denseError': self.error, 'denseEnabled':camera.get('denseCounting',False)}
        self.snapshots[cid]=result
        return result

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.pending and not self.pending.cancelled():
            try:
                cid,result=self.pending.result();self.results[cid]=result
            except Exception as exc:self.error=str(exc)
        for cid, snapshot in self.snapshots.items():
            self.fast[cid].finish(snapshot['t'],'análisis finalizado')
            snapshot['occupancy']=self.fast[cid].snapshot()
            if cid in self.results:
                result=self.results[cid]
                self.dense[cid].finish(result['t'],'análisis finalizado')
                snapshot['dense']={**result,**self.dense[cid].snapshot()}
            snapshot['denseError']=self.error
        return self.snapshots
