import {useMemo} from 'react';
import MapCanvas from './MapCanvas';
import {EMPTY_STATE} from './types';
import type {Config,Point,SessionState} from './types';

type Observation={id:string;point?:Point|null;association?:string};
type Frame={t:number;cameras:{id:string;people?:Observation[];analysis?:any}[]};
export default function ReplayMap({config,time,analytics,cameras,samples=[],expanded=false,selectedCamera='',onCamera}:{config:Config;time:number;analytics:SessionState['analytics'];cameras:Frame['cameras'];samples?:Frame[];expanded?:boolean;selectedCamera?:string;onCamera?:(id:string)=>void}){
  const people=useMemo(()=>cameras.flatMap(c=>(c.people||[]).filter(p=>p.point).map(p=>{
    const recent=samples.filter(s=>s.t<=time+1e-6&&s.t>=time-6).flatMap(s=>{const q=s.cameras.find(v=>v.id===c.id)?.people?.find(v=>v.id===p.id);return q?.point?[{t:s.t,point:q.point}]:[];});
    const first=recent[recent.length-3],last=recent[recent.length-1],dt=first&&last?last.t-first.t:0;
    const velocity:Point|undefined=first&&last&&dt>0?[(last.point[0]-first.point[0])/dt,(last.point[1]-first.point[1])/dt]:undefined;
    return {id:p.id,camera:c.id,point:p.point!,association:p.association||'local',history:recent.map(q=>q.point),velocity,predicted:false};
  })),[samples,cameras,time]);
  const state:SessionState={...EMPTY_STATE,status:'paused',t:time,planId:config.planId,people,analytics,cameraAnalytics:Object.fromEntries(cameras.map(c=>[c.id,c.analysis]))};
  return <details className="aero-panel replay-map-panel" open={expanded||undefined}><summary>Mapa sincronizado · posiciones y recorridos en este instante</summary><MapCanvas config={config} state={state} connected selectedCamera={selectedCamera} onCamera={onCamera||(()=>{})}/>{!people.length&&<p className="subtle">Sin posiciones proyectadas en este instante. Las zonas de imagen requieren referencias del suelo para ubicarse en el plano.</p>}</details>;
}
