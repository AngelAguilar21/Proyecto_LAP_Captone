import {useEffect,useState} from 'react';
import type {State} from '../counting/types';
import {active,STATUS,timeLabel} from '../counting/types';
import {momentLabel} from '../counting/AnalysisSummary';
import type {Config,SessionState} from './types';
import MapCanvas from './MapCanvas';
import {STATUS as trackingStatus,formatTime,isActive} from './types';

export default function Overview({config,connected,onMap,onReplay,current,tracking:liveTracking,cameraCount,onAnalyze,onReport,onCameras,onTracking}:{config:Config;connected:boolean;onMap:()=>void;onReplay:()=>void;current:State|null;tracking:SessionState;cameraCount:number;onAnalyze:()=>void;onReport:(id:string)=>void;onCameras:()=>void;onTracking:()=>void}) {
  const [archivedTracking,setArchivedTracking]=useState<SessionState|null>(null);
  const tracking=liveTracking.session?liveTracking:archivedTracking||liveTracking;
  useEffect(()=>{let alive=true;void fetch('/api/replay/history').then(r=>{if(!r.ok)throw Error();return r.json();}).then(async rows=>{
    const run=rows.find((r:any)=>r.module==='tracking'&&r.status!=='running');if(!run)return;
    const response=await fetch(`/api/replay/data?session=${run.session}`);if(!response.ok)return;
    const data=await response.json(),last=data.samples?.at(-1);if(!last)return;
    const cameras=data.cameras.map((c:any)=>{const sample=[...data.samples].reverse().find((s:any)=>s.cameras.some((v:any)=>v.id===c.id));const view=sample?.cameras.find((v:any)=>v.id===c.id);return {id:c.id,status:'ended',lastCount:view?.people?.length??0};});
    if(alive)setArchivedTracking({status:run.status,session:run.session,planId:run.config?.planId,t:last.t,people:[],events:[],cameras,analytics:last.analytics});
  }).catch(()=>{});return()=>{alive=false;};},[liveTracking.session,liveTracking.status]);
  const [recent,setRecent]=useState<State[]>([]);
  const [last,setLast]=useState<State|null>(null);
  const [error,setError]=useState('');
  const [loaded,setLoaded]=useState(false);
  useEffect(()=>{
    let alive=true;
    async function load(){
      try{
        const r=await fetch('/api/counting/history',{signal:AbortSignal.timeout(8000)});
        if(!r.ok)throw Error('No se pudo consultar el historial.');
        const list:State[]=await r.json();
        let report:State|null=null;
        if(list.length){const result=await fetch(`/api/counting/report?session=${encodeURIComponent(list[0].session!)}`,{signal:AbortSignal.timeout(8000)});if(!result.ok)throw Error('No se pudo recuperar el último análisis.');report=await result.json();}
        if(alive){setRecent(list);setLast(report);setError('');setLoaded(true);}
      }catch(e){if(alive){setError(String(e));setLoaded(true);}}
    }
    void load();return()=>{alive=false;};
  },[current?.session,current?.status]);
  const live=!!current&&active(current.status);
  const selected=live?current:current?.samples?current:last;
  const events=selected?.episodes||[];
  const zones=[...(selected?.zones||[])].sort((a,b)=>b.peak-a.peak);
  const date=(value?:string)=>value?new Date(value).toLocaleString('es-PE',{timeZone:'America/Lima'}):'—';
  return <div className="overview-monitor">
    <div className="overview-heading"><div><span className="eyebrow">CENTRO DE MONITOREO</span><h1>Estado del espacio</h1><p>{live?'Análisis en curso':selected?'Últimos resultados disponibles':'Sin resultados disponibles'}</p></div><div><button onClick={onCameras}>Cámaras ({cameraCount})</button><button className="primary" onClick={onAnalyze}>{live?'Abrir análisis activo':'Nuevo análisis'}</button></div></div>
    <section className="aero-panel overview-space"><div className="panel-heading"><h2>{config.floor||'Espacio de monitoreo'}</h2><button onClick={onMap}>Explorar plano</button><button onClick={onReplay}>Comparar videos</button></div><p className="subtle">Las posiciones se muestran cuando las cámaras están calibradas. Los resultados de distintos niveles y cámaras sin asociación no se suman como personas únicas.</p><MapCanvas key={config.planId||'custom'} compact config={config} state={tracking} connected={connected} selectedCamera="" onCamera={onCameras}/><div className="overview-camera-list">{config.cameras.map(c=>{const status=tracking.cameras.find(s=>s.id===c.id);return <button key={c.id} onClick={onTracking}><strong>{c.name||c.id}</strong><span>{c.location||'Ubicación pendiente'}</span><small>{(c.planId||'custom')==='custom'?'Espacio de pruebas':c.planId?.replace('lap-','LAP · Nivel ')} · {status?.status==='live'&&isActive(tracking.status)?`${status.count??0} personas en la última muestra`:status?.lastCount!=null?`${status.lastCount} en la última muestra procesada`:'Sin análisis reciente'}</small></button>;})}</div></section>
    {error&&<div className="notice error">{error}</div>}
    <section className="aero-panel overview-tracking"><div className="panel-heading"><h2>Seguimiento de personas</h2><button onClick={onTracking}>{isActive(tracking.status)?'Abrir seguimiento':'Iniciar seguimiento'}</button></div><div className="overview-context"><div><strong>{trackingStatus[tracking.status]||tracking.status}</strong><span>{tracking.session?`Tiempo analizado: ${formatTime(tracking.t)}`:'Selecciona una cámara para observar recorridos y medir el flujo.'}</span></div><div>{tracking.cameras.map(c=><span key={c.id}>Cámara {c.id}: {['running','paused'].includes(tracking.status)?`${c.count??0} personas observadas`:`${c.lastCount??'—'} en la última imagen`}</span>)}</div></div>{tracking.error&&<p className="empty-text">{tracking.error}</p>}</section>
    {!loaded&&!selected?<div className="aero-panel overview-empty">Consultando resultados…</div>:!selected?<div className="aero-panel overview-empty"><h2>Aún no hay un análisis procesado</h2><p>Los conteos, zonas e intervalos aparecerán al analizar una fuente.</p><button className="primary" onClick={onAnalyze}>Crear análisis</button></div>:<>
      <div className="overview-context"><div><strong>{selected.name}</strong><span>{STATUS[selected.status]} · {momentLabel(selected,0)} — {momentLabel(selected,selected.status==='ended'?selected.duration??selected.t:selected.t)}{!selected.live&&!selected.config?.recordedAt?' del video':''}</span></div><span>Procesado: {date(selected.created)}<br/>{selected.live?'Hora de recepción':'Grabación'} · {live?'Actualizando resultados':'Resultado guardado; no es ocupación en vivo'}</span></div>
      <div className="overview-stats">{[['Máximo simultáneo',selected.peak??'—',momentLabel(selected,selected.peakAt)],['Promedio de personas',selected.mean?.toLocaleString('es-PE',{maximumFractionDigits:1})??'—','Durante el periodo observado'],['Zonas con concentración',zones.filter(z=>events.some(e=>e.zoneId===z.id||e.zone===z.name)).length,`De ${zones.length} zonas analizadas`],['Intervalos registrados',events.length,'En la fuente seleccionada']].map(([label,value,note])=><article key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</div>
      <div className="overview-panels"><section className="aero-panel"><div className="panel-heading"><h2>Zonas con mayor ocupación</h2><button disabled={!selected.samples} onClick={()=>onReport(selected.session!)}>Ver detalle</button></div><div className="overview-zones">{zones.slice(0,5).map(z=><div key={z.id}><div><strong>{z.name}</strong><span>{z.peak} personas como máximo</span></div><div className="overview-bar"><i style={{width:`${z.peak/Math.max(1,...zones.map(v=>v.peak))*100}%`}}/></div><small>Máximo en {momentLabel(selected,z.peakAt)}</small></div>)}{!zones.length&&<p>No se registraron zonas.</p>}</div></section>
      <section className="aero-panel"><div className="panel-heading"><h2>Intervalos de concentración</h2><span>{selected.name}</span></div><div className="overview-events">{events.length?events.slice(-4).reverse().map(e=><article key={e.id}><strong>{e.zone}</strong><b>{e.peak} personas máx.</b><span>{momentLabel(selected,e.start)} — {e.end==null?'En curso':momentLabel(selected,e.end)}</span><small>{timeLabel(e.duration)} de duración</small></article>):<p>No se registraron intervalos con los límites configurados.</p>}</div></section></div>
    </>}
    <section className="aero-panel overview-recent"><div className="panel-heading"><h2>Actividad reciente por fuente</h2><span>Últimos análisis · periodos independientes</span></div><div className="count-table-wrap"><table><thead><tr><th>Fuente</th><th>Fecha de análisis</th><th>Estado</th><th>Máximo simultáneo</th><th/></tr></thead><tbody>{recent.slice(0,4).map(s=><tr key={s.session}><td>{s.name}</td><td>{date(s.created)}</td><td>{STATUS[s.status]}</td><td>{s.peak??'—'}</td><td><button onClick={()=>onReport(s.session!)}>Abrir informe</button></td></tr>)}</tbody></table></div>{loaded&&!recent.length&&<p className="overview-empty">No hay análisis guardados.</p>}</section>
  </div>;
}
