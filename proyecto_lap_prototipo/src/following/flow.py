"""Cruces de zonas del plano, confirmados en dos observaciones consecutivas."""
import cv2
import numpy as np
import math


class ZoneFlow:
    def __init__(self, config):
        self.zones = [(z.get("id", str(i)), z["name"], np.asarray(z["points"], np.float32))
                      for i, z in enumerate(config.get("zones", [])) if z.get("kind") != "wall"]
        self.members = {}
        self.totals = {key: {"name": name, "entries": 0, "exits": 0, "lastCrossing": None}
                       for key, name, _ in self.zones}

    def update(self, people, t):
        unique = {p["id"]: p for p in people if p.get("point") is not None and not p.get("predicted")}
        # Tras perder una trayectoria no se interpreta la reaparición como un cruce.
        self.members = {k: v for k, v in self.members.items() if 0 <= t-v["t"] <= 1}
        for key, _, polygon in self.zones:
            for pid, person in unique.items():
                inside = cv2.pointPolygonTest(polygon, tuple(person["point"]), False) >= 0
                state = self.members.setdefault((key, pid), {"inside": inside, "candidate": inside, "n": 0, "t": t})
                state["n"] = state["n"]+1 if inside == state["candidate"] else 1
                state.update(candidate=inside, t=t)
                if inside != state["inside"] and state["n"] >= 2:
                    self.totals[key]["entries" if inside else "exits"] += 1
                    self.totals[key]["lastCrossing"] = t
                    state["inside"] = inside
        return [dict(value) for value in self.totals.values()]


class FlowField:
    """Direcciones recorridas por celda; intensidad de movimiento, no visitantes únicos."""
    def __init__(self, config):
        self.size=max(.1,config.get('radius',2))
        self.previous={}
        self.cells={}

    def update(self,people,t):
        self.previous={k:v for k,v in self.previous.items() if 0<=t-v[1]<=2}
        unique={p['id']:p for p in people if p.get('point') is not None and not p.get('predicted')}
        for pid,p in unique.items():
            xy=p['point'];old=self.previous.get(pid)
            if old and 0<t-old[1]<=2:
                dx,dy=xy[0]-old[0][0],xy[1]-old[0][1];length=math.hypot(dx,dy)
                if .02<length<=5*(t-old[1]):
                    direction=round(math.atan2(dy,dx)/(math.pi/4))%8
                    key=(int(xy[0]//self.size),int(xy[1]//self.size),direction)
                    cell=self.cells.setdefault(key,{'x':(key[0]+.5)*self.size,'y':(key[1]+.5)*self.size,'dx':math.cos(direction*math.pi/4),'dy':math.sin(direction*math.pi/4),'distance':0.,'samples':0,'size':self.size})
                    cell['distance']+=length;cell['samples']+=1
            self.previous[pid]=(xy,t)
        if len(self.cells)>10000:
            self.cells=dict(sorted(self.cells.items(),key=lambda item:item[1]['distance'],reverse=True)[:10000])
        return [dict(v) for v in self.cells.values()]
