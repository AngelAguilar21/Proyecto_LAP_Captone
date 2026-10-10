import {useMemo} from 'react';
import MapCanvas from './MapCanvas';
import type {Trail} from './MapCanvas';
import {EMPTY_STATE} from './types';
import type {Config,Point,SessionState} from './types';

type Observation={id:string;point?:Point|null;association?:string;history?:number[][];duplicate?:boolean};
type Frame={t:number;cameras:{id:string;people?:Observation[];analysis?:any}[]};
export default function ReplayMap({config,time,analytics,cameras,samples=[],expanded=true,selectedCamera='',onCamera,viewMode}:{config:Config;time:number;analytics:SessionState['analytics'];cameras:Frame['cameras'];samples?:Frame[];expanded?:boolean;viewMode?:'tracks'|'heat';selectedCamera?:string;onCamera?:(id:string)=>void}){
  const people=useMemo(()=>cameras.flatMap(c=>(c.people||[]).filter(p=>p.point&&!p.duplicate).map(p=>{
    const recent=samples.filter(s=>s.t<=time+1e-6&&s.t>=time-6).flatMap(s=>{const q=s.cameras.find(v=>v.id===c.id)?.people?.find(v=>v.id===p.id);return q?.point?[{t:s.t,point:q.point}]:[];});
    const first=recent[recent.length-3],last=recent[recent.length-1],dt=first&&last?last.t-first.t:0;
    const velocity:Point|undefined=first&&last&&dt>0?[(last.point[0]-first.point[0])/dt,(last.point[1]-first.point[1])/dt]:undefined;
    const stored=(p.history||[]).map(value=>[value[0],value[1]] as Point);
    return {id:p.id,camera:c.id,point:p.point!,association:p.association||'local',history:stored.length?stored:recent.map(q=>q.point),velocity,predicted:false};
  })),[samples,cameras,time]);
  const trails=useMemo(()=>{
    const allowed=new Set(config.cameras.map(c=>c.id)),found=new Map<string,Trail>();
    for(const s of [...samples].sort((a,b)=>a.t-b.t)){
      if(s.t>time+1e-6)break;
      const seen=new Set<string>();
      for(const c of s.cameras){
        if(!allowed.has(c.id))continue;
        for(const p of c.people||[]){
          if(!p.point||p.duplicate||seen.has(p.id))continue;
          seen.add(p.id);
          const trail=found.get(p.id)||{id:p.id,association:'local',points:[]};
          trail.points.push([p.point[0],p.point[1],s.t]);
          trail.association=p.association||trail.association;
          found.set(p.id,trail);
        }
      }
    }
    return Array.from(found.values());
  },[samples,time,config.cameras]);
  const state:SessionState={...EMPTY_STATE,status:'paused',t:time,planId:config.planId,people,analytics,cameraAnalytics:Object.fromEntries(cameras.map(c=>[c.id,c.analysis]))};
  return <details className="aero-panel replay-map-panel" open={expanded||undefined}><summary>Mapa del monitoreo</summary><MapCanvas peopleFirst trails={trails} viewMode={viewMode} config={config} state={state} connected selectedCamera={selectedCamera} onCamera={onCamera||(()=>{})}/>{!people.length&&<p className="subtle">Sin posiciones proyectadas en este instante. Las zonas de imagen requieren referencias del suelo para ubicarse en el plano.</p>}</details>;
}
