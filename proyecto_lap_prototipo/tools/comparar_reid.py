"""Compare encoders on identical saved detections. No accuracy without labels.

Optional --labels JSON: [{a:0,b:1,same:true},...], referring to the exported crops.
Use different frames/cameras and verified positive AND negative pairs.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from following.reid import OSNetEmbedder


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session')
    parser.add_argument('--labels',type=Path)
    args=parser.parse_args()
    folder=ROOT/'data/replays'/args.session
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    samples=[json.loads(s) for s in (folder/'samples.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    output=ROOT/'data/commercial-tests'/args.session/'comparacion_reid';output.mkdir(parents=True,exist_ok=True)
    crops=[]; description=[]
    for camera in meta['cameras']:
        cap=cv2.VideoCapture(camera['source'])
        try:
            for second in (5,15):
                sample=min(samples,key=lambda s:abs(s['t']-second))
                observed=next((c for c in sample['cameras'] if c['id']==camera['id']),None)
                if not observed: continue
                cap.set(cv2.CAP_PROP_POS_MSEC,max(0,sample['t']+camera.get('offset',0)+camera.get('syncOffset',0))*1000)
                ok,frame=cap.read()
                if not ok:continue
                h,w=frame.shape[:2]
                for person in [p for p in observed.get('people',[]) if p.get('box')][:3]:
                    x1,y1,x2,y2=[int(v*size) for v,size in zip(person['box'],[w,h,w,h])]
                    crop=frame[max(0,y1):min(h,y2),max(0,x1):min(w,x2)]
                    if min(crop.shape[:2])<12:continue
                    index=len(crops);crops.append(crop)
                    cv2.imwrite(str(output/f'crop_{index:02d}.jpg'),crop)
                    description.append(dict(index=index,camera=camera['id'],time=sample['t'],automaticId=person['id']))
        finally:cap.release()
    if not crops:raise ValueError('No se pudieron extraer recortes de la sesión.')
    report={'session':args.session,'threads':2,'precisionEvaluated':False,'crops':description,'models':[]}
    pairs=json.loads(args.labels.read_text()) if args.labels else []
    if pairs and {bool(p['same']) for p in pairs}!={True,False}:raise ValueError('Incluye positivos y negativos verificados.')
    for name in ['osnet.onnx','osnet_ain_msmt17.onnx','fastreid_msmt17.onnx']:
        model=OSNetEmbedder(ROOT/'models'/name,threads=2)
        if not model.available:raise RuntimeError(model.error)
        def encode(crop):return model.embed(crop,[[0,0,crop.shape[1],crop.shape[0]]])[0]
        encode(crops[0]);durations=[];vectors=[]
        for crop in crops:
            start=time.perf_counter();vectors.append(encode(crop));durations.append((time.perf_counter()-start)*1000)
        row={'name':name,'fingerprint':model.fingerprint,'dimension':model.dimension,'medianMsPerCall':statistics.median(durations),'fixedBatch':model.batch,'calls':len(crops)}
        if pairs:
            scored=[dict(**p,similarity=float(vectors[p['a']]@vectors[p['b']])) for p in pairs]
            row['labeledPairs']=scored
            row['thresholdEvaluation']=[]
            for threshold in (.5,.6,.7,.8,.9):
                tp=sum(p['same'] and p['similarity']>=threshold for p in scored)
                fp=sum(not p['same'] and p['similarity']>=threshold for p in scored)
                fn=sum(p['same'] and p['similarity']<threshold for p in scored)
                row['thresholdEvaluation'].append(dict(threshold=threshold,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None))
            report['precisionEvaluated']=True
        report['models'].append(row)
    (output/'comparacion.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['models']))

if __name__=='__main__':main()
