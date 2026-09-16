import {useEffect,useMemo,useState} from 'react';

const stamp=(t:number)=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
export default function ReplayAlerts({runs,time,level,cameraFilter,zoneFilter,active,notify,onTime}:{runs:any[];time:number;level:string;cameraFilter:string;zoneFilter:string;active:boolean;notify:boolean;onTime:(t:number)=>void}){
  const events=useMemo(()=>runs.flatMap(run=>run.cameras.filter((c:any)=>(cameraFilter==='all'||cameraFilter===c.id)&&(level==='all'||(c.planId||run.config.planId)===level)).flatMap((c:any)=>{
    const last=[...(run.samples||[])].reverse().find(s=>s.cameras.some((v:any)=>v.id===c.id));
    const analysis=run.cameraAnalytics?.[c.id]||last?.cameras.find((v:any)=>v.id===c.id)?.analysis;
    return (analysis?.occupancy?.episodes||[]).filter((e:any)=>zoneFilter==='all'||e.zone===zoneFilter).map((e:any)=>({...e,key:`${run.session}-${c.id}-${e.id}`,camera:c.name,confirmed:e.confirmed??e.start,end:e.end??last?.t??run.end}));
  })).sort((a:any,b:any)=>a.confirmed-b.confirmed),[runs,level,cameraFilter,zoneFilter]);
  const current=events.filter(e=>time>=e.confirmed&&time<=e.end);
  const signature=current.map(e=>e.key).join('|');
  const [dismissed,setDismissed]=useState('');
  useEffect(()=>{setDismissed('');},[signature]);
  useEffect(()=>{if(!signature||!active||!notify)return;const timer=window.setTimeout(()=>setDismissed(signature),12000);return()=>window.clearTimeout(timer);},[signature,active,notify]);
  if(!events.length)return null;
  return <>
    <details className="replay-events"><summary>Eventos de concentración <span>{events.length}</span></summary><div>{events.map(e=><button key={e.key} onClick={()=>onTime(e.confirmed)}><time>{stamp(e.confirmed)}</time><strong>{e.zone}</strong><span>{e.camera} · máximo {e.peak} personas</span></button>)}</div></details>
    {active&&notify&&current.length>0&&dismissed!==signature&&<aside className="recorded-alert" role="status"><div><strong>Concentración registrada · {stamp(time)}</strong><span>{current.map(e=>`${e.camera} / ${e.zone}`).join(' · ')}</span><small>Evento del análisis seleccionado</small></div><button aria-label="Cerrar alerta del análisis" onClick={()=>setDismissed(signature)}>×</button></aside>}
  </>;
}
