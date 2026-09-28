"""Cruces direccionales de un segmento de imagen; no cuenta simples apariciones."""
import math
import cv2
import numpy as np


class LineCounter:
    def __init__(self, lines, include_identity=False):
        self.lines = lines
        self.include_identity = include_identity
        self.previous = {}
        self.totals = {line['id']: {'id': line['id'], 'name': line['name'], 'place': line.get('place'), 'entries': 0, 'exits': 0, 'lastCrossing': None, 'events': [], 'hours': {}} for line in lines}

    def update(self, people, t):
        self.previous = {k: v for k, v in self.previous.items() if t-v['t'] <= 2}
        for line in self.lines:
            a, b = line['a'], line['b']
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = math.hypot(dx, dy)
            if length < .001:
                continue
            for person in people:
                p = person['pixel']
                distance = (dx*(p[1]-a[1])-dy*(p[0]-a[0]))/length
                if abs(distance) < .008:
                    continue
                side = 1 if distance > 0 else -1
                if line.get('bands'):
                    band=line['bands']['positive' if side==1 else 'negative']
                    polygon=np.asarray([a,b,band[1],band[0]],dtype=np.float32)
                    if cv2.pointPolygonTest(polygon,tuple(p),False)<0:
                        continue
                key = (line['id'], person['id'])
                old = self.previous.get(key)
                if old and old['side'] != side and t-old['t'] <= 2:
                    q = old['point']
                    old_d = (dx*(q[1]-a[1])-dy*(q[0]-a[0]))/length
                    alpha = old_d/(old_d-distance)
                    cross = (q[0]+alpha*(p[0]-q[0]), q[1]+alpha*(p[1]-q[1]))
                    along = ((cross[0]-a[0])*dx+(cross[1]-a[1])*dy)/(length*length)
                    if 0 <= along <= 1 and t-old.get('crossed', -100) >= 1:
                        entering = side == line.get('entrySide', 1)
                        self.totals[line['id']]['entries' if entering else 'exits'] += 1
                        self.totals[line['id']]['lastCrossing'] = t
                        old['crossed'] = t
                        total=self.totals[line['id']]
                        direction='entries' if entering else 'exits'
                        event = {'t':t,'direction':direction}
                        if self.include_identity:
                            event['person'] = person['id']
                        total['events'].append(event)
                        total['events']=total['events'][-1000:]
                        hour=total['hours'].setdefault(str(int(t//3600)),{'entries':0,'exits':0})
                        hour[direction]+=1
                self.previous[key] = {'point': p, 'side': side, 't': t, 'crossed': (old or {}).get('crossed', -100)}
        return list(self.totals.values())
