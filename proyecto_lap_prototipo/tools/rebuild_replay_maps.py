"""Recalcula mapas derivados desde observaciones; conserva originales y conteos."""
from pathlib import Path
import json,sys,shutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from live_core import Occupancy
from following.flow import FlowField


def rebuild(directory):
    manifest=directory/'manifest.json'
    meta=json.loads(manifest.read_text(encoding='utf-8'))
    if meta.get('module')!='unified' or meta.get('status') not in ('ended','stopped') or meta.get('derivedMapVersion')==2:return False
    backup=ROOT/'data/replay-map-v1'/directory.name
    backup.mkdir(parents=True,exist_ok=True)
    for name in ('manifest.json','samples.jsonl'):
        if not (backup/name).exists():shutil.copy2(directory/name,backup/name)
    cfg=meta['config'];levels={c['id']:c.get('planId','custom') for c in meta['cameras']}
    configs={pid:cfg if pid==cfg.get('planId','custom') else {**cfg,**cfg.get('plans',{}).get(pid,{})} for pid in levels.values()}
    counters={pid:Occupancy(c) for pid,c in configs.items()};fields={pid:FlowField(c) for pid,c in configs.items()}
    cameras={cid:Occupancy(configs[pid]) for cid,pid in levels.items()}
    summary=meta.get('cameraAnalytics',{})
    updated={}
    temporary=directory/'samples.rebuild.tmp'
    with (directory/'samples.jsonl').open(encoding='utf-8') as source,temporary.open('w',encoding='utf-8') as output:
        for line in source:
            row=json.loads(line);people=[{**p,'camera':v['id']} for v in row['cameras'] for p in v.get('people',[])]
            updated={}
            for pid,counter in counters.items():
                group=[p for p in people if levels[p['camera']]==pid]
                updated[pid]={**counter.update(group,row['t']),'flow':row.get('levels',{}).get(pid,{}).get('flow',[]),'flowVectors':fields[pid].update(group,row['t'])}
            row['levels']=updated;row['analytics']=updated.get(cfg.get('planId','custom'),row['analytics'])
            for view in row['cameras']:
                cid=view['id'];mapped=cameras[cid].update(view.get('people',[]),row['t'])
                if view.get('analysis'):
                    view['analysis']['map']=mapped
                    if cid not in meta.get('cameraAnalytics',{}):summary[cid]=view['analysis']
                    if cid in summary:summary[cid]['map']=mapped
            output.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    temporary.replace(directory/'samples.jsonl')
    meta.update(cameraAnalytics=summary,levelAnalytics=updated,derivedMapVersion=2)
    temporary=manifest.with_suffix('.tmp');temporary.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8');temporary.replace(manifest)
    return True


if __name__=='__main__':
    for directory in (ROOT/'data/replays').iterdir():
        if directory.is_dir() and rebuild(directory):print(directory.name)
