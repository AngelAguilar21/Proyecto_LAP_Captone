"""Señal experimental de objeto nuevo al salir; nunca confirma una compra."""
import math
import os
import numpy as np
from following.appearance import torso_histogram
from following.line_counter import LineCounter


class VisitMatcher:
    def __init__(self, ttl=3600, threshold=.94, margin=.08):
        self.ttl, self.threshold, self.margin = ttl, threshold, margin
        self.entries = []

    def observe(self, business, direction, t, signature, bags, identity, reliable=True):
        self.entries = [e for e in self.entries if 0 <= t-e['t'] <= self.ttl]
        if direction == 'entries':
            if signature is not None and reliable:
                self.entries.append(dict(business=business,t=t,signature=np.asarray(signature).ravel(),bags=set(bags),identity=identity))
            return None
        candidates = []
        if signature is not None and reliable:
            v = np.asarray(signature).ravel()
            for index, entry in enumerate(self.entries):
                if entry['business'] != business or t-entry['t'] < 2:
                    continue
                score = float(np.dot(v,entry['signature'])/(np.linalg.norm(v)*np.linalg.norm(entry['signature']) or 1))
                candidates.append((score,index))
        candidates.sort(reverse=True)
        matched = bool(candidates and candidates[0][0]>=self.threshold and (len(candidates)==1 or candidates[0][0]-candidates[1][0]>=self.margin))
        result = dict(t=t,business=business,matched=matched,changed=False,similarity=candidates[0][0] if candidates else None,reason='Sin correspondencia visual suficiente o correspondencia ambigua.')
        if matched:
            entry = self.entries.pop(candidates[0][1])
            # Solo handbag como señal; mochila/maleta nunca se interpretan como compra.
            result.update(changed=26 in bags and 26 not in entry['bags'],reason='Correspondencia visual conservadora; objeto handbag nuevo. No confirma compra.' if 26 in bags and 26 not in entry['bags'] else 'Correspondencia visual sin objeto nuevo.')
        return result


class BagSignal:
    def __init__(self, root, cameras):
        self.root = root
        self.cameras = {c['id']:c for c in cameras if c.get('bagSignal') and any(l.get('place') for l in c.get('countLines',[]))}
        self.models, self.counters, self.seen, self.last, self.features = {}, {}, {}, {}, {}
        self.matcher = VisitMatcher()

    def observe(self, cid, frame, t):
        if cid not in self.cameras or t-self.last.get(cid,-100)<.5:
            return []
        self.last[cid] = t
        if cid not in self.models:
            os.environ.setdefault('YOLO_CONFIG_DIR',str(self.root/'data/ultralytics'))
            from ultralytics import YOLO
            weights = self.root/'models/yolo11n.pt'
            if not weights.is_file():
                raise ValueError('Falta models/yolo11n.pt para la señal experimental de objetos.')
            self.models[cid] = YOLO(str(weights))
            self.counters[cid] = LineCounter(self.cameras[cid]['countLines'], include_identity=True)
            self.seen[cid] = {}
        result = self.models[cid].track(frame,persist=True,tracker='bytetrack.yaml',classes=[0,24,26,28],conf=.45,imgsz=640,verbose=False)[0]
        h,w = frame.shape[:2]
        boxes = result.boxes
        if boxes is None:
            return []
        detections = [(box.xyxy[0].cpu().numpy(),int(box.cls[0]),int(box.id[0]) if box.id is not None else None) for box in boxes]
        people = []
        for box,cls,ident in detections:
            if cls!=0 or ident is None:
                continue
            x1,y1,x2,y2 = box
            signature = torso_histogram(frame,box)
            objects = set()
            reliable = (y2-y1)>=80 and x1>2 and x2<w-2 and y1>2 and y2<h-2
            for object_box,object_cls,_ in detections:
                if object_cls==0:
                    continue
                ox,oy = (object_box[0]+object_box[2])/2,(object_box[1]+object_box[3])/2
                owners = [person_id for person_box,person_cls,person_id in detections if person_cls==0 and person_box[0]-.1*(person_box[2]-person_box[0])<=ox<=person_box[2]+.1*(person_box[2]-person_box[0]) and person_box[1]<=oy<=person_box[3]]
                if len(owners)==1 and owners[0]==ident:
                    objects.add(object_cls)
                elif ident in owners:
                    reliable=False
            key = f'{cid}:{ident}'
            # Requiere varias observaciones para no interpretar una detección fugaz.
            previous = self.features.get(key,dict(n=0,bags=set()))
            previous.update(n=previous['n']+1,bags=objects,signature=signature,reliable=reliable,t=t)
            self.features[key]=previous
            people.append({'id':key,'pixel':[(x1+x2)/(2*w),y2/h]})
        self.features = {k:v for k,v in self.features.items() if t-v.get('t',t)<30}
        self.seen[cid] = {k:v for k,v in self.seen[cid].items() if t-v<5}
        totals = self.counters[cid].update(people,t)
        events = []
        for line in totals:
            if not line.get('place'):
                continue
            for event in line['events']:
                if t-event['t']>1:
                    continue
                key=(line['id'],event['t'],event.get('person'))
                if key in self.seen[cid]:
                    continue
                self.seen[cid][key]=t
                feature=self.features.get(event.get('person'),{})
                sample=self.matcher.observe(line['place']['id'],event['direction'],t,feature.get('signature'),feature.get('bags',set()),event.get('person'),feature.get('reliable',False) and feature.get('n',0)>=3)
                if sample:
                    events.append(sample)
        return events
