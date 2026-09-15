import { useState } from 'react';
import type { State } from './types';
import { active, timeLabel } from './types';

export function momentLabel(state: State, seconds?: number | null) {
  if(seconds==null)return 'No disponible';
  const origin=state.live?(state.timeOrigin||state.created):state.config?.recordedAt;
  if(!origin)return timeLabel(seconds);
  const date=new Date(new Date(origin).getTime()+seconds*1000);
  return date.toLocaleString('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}

export default function AnalysisSummary({state,mode='full'}:{state:State;mode?:'full'|'metrics'|'details'}) {
  const [detail,setDetail]=useState<'zones'|'intervals'>('zones');
  const events=state.episodes||[];
  const zones=[...(state.zones||[])].map(z=>({...z,events:events.filter(e=>e.zoneId?e.zoneId===z.id:e.zone===z.name)}))
    .map(z=>({...z,congested:z.events.reduce((n,e)=>n+e.duration,0)})).sort((a,b)=>b.congested-a.congested||b.peak-a.peak);
  const partial=state.status!=='ended';
  const peakAt=state.peakAt??state.series.find(s=>s.count===state.peak)?.t;
  const periodEnd=state.status==='ended'?state.duration??state.t:state.t;
  const fmt=(n:number)=>n.toLocaleString('es-PE',{maximumFractionDigits:1});
  if(!state.samples)return <section className="count-card count-small-empty">El resumen estará disponible cuando se procese la primera imagen.</section>;
  return <section className="count-summary" aria-label="Resumen de concentración">
    {mode==='full'&&<div className="count-period"><div><h2>{partial?'Resumen parcial':'Resumen del análisis'}</h2><p>{state.name} · {momentLabel(state,0)} — {momentLabel(state,periodEnd)}</p></div><span>{state.live?'Hora de recepción · Lima':state.config?.recordedAt?'Hora de grabación · Lima':'Tiempo transcurrido del video'}</span></div>}
    {mode==='full'&&!active(state.status)&&partial&&<p className="count-coverage">El análisis no abarca todo el video. Los resultados corresponden únicamente al tramo procesado.</p>}
    {mode!=='details'&&<div className="count-metrics">{[
      ['Máximo simultáneo',fmt(state.peak||0),`${momentLabel(state,peakAt)} · personas presentes a la vez`],
      ['Promedio de personas',fmt(state.mean||0),'Durante el tiempo observado'],
      ['Zonas con concentración',`${zones.filter(z=>z.events.length).length} de ${zones.length}`,'Con al menos un intervalo confirmado'],
      ['Intervalos de concentración',String(events.length),'Según los límites definidos para cada zona'],
    ].map(([label,value,note])=><article key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</div>}
    {mode==='details'&&<nav className="detail-tabs" aria-label="Detalle del análisis"><button className={detail==='zones'?'selected':''} onClick={()=>setDetail('zones')}>Zonas</button><button className={detail==='intervals'?'selected':''} onClick={()=>setDetail('intervals')}>Intervalos de concentración ({events.length})</button></nav>}
    {mode!=='metrics'&&(mode==='full'||detail==='zones')&&<section className="count-card"><div className="count-card-title"><div><h2>Concentración por zona</h2><p>Ordenadas por tiempo en concentración y máximo de personas presentes.</p></div></div>
      <div className="count-table-wrap"><table><thead><tr><th>Zona</th><th>Máximo de personas</th><th>Momento del máximo</th><th>Promedio</th><th>Tiempo en concentración</th><th>Intervalos</th></tr></thead><tbody>{zones.map(z=><tr key={z.id}><td><strong>{z.name}</strong></td><td>{z.peak}</td><td>{momentLabel(state,z.peakAt??state.series.find(s=>s.zones.some(v=>v.id===z.id&&v.count===z.peak))?.t)}</td><td>{fmt(state.observedSeconds?z.personSeconds/state.observedSeconds:z.count)}</td><td>{timeLabel(z.congested)}</td><td>{z.events.length}</td></tr>)}</tbody></table></div>
      <div className="count-applied-rules"><strong>Límites aplicados</strong>{state.config?.zones.map(z=><span key={z.id}>{z.name}: {z.threshold} personas durante al menos {z.dwell} s</span>)}</div>
      <p className="count-footnote">El máximo y el promedio indican personas presentes, no visitantes diferentes a lo largo del video. Una persona puede permanecer en varias imágenes.</p>
    </section>}
    {mode!=='metrics'&&(mode==='full'||detail==='intervals')&&<section className="count-card"><div className="count-card-title"><div><h2>Cuándo se concentraron las personas</h2><p>Periodos en que una zona alcanzó el límite de personas durante la duración mínima configurada.</p></div></div>
      {events.length?<div className="count-table-wrap"><table><thead><tr><th>Zona</th><th>Desde</th><th>Hasta</th><th>Duración</th><th>Máximo de personas</th><th>Estado</th></tr></thead><tbody>{events.map(e=><tr key={e.id}><td>{e.zone}</td><td>{momentLabel(state,e.start)}</td><td>{e.end==null?'En curso':momentLabel(state,e.end)}</td><td>{timeLabel(e.duration)}</td><td>{e.peak}</td><td>{e.end==null?'Activo':e.reason==='umbral despejado'?'Concentración finalizada':e.reason==='fin del video'?'Fin de grabación':e.reason==='detenido por operador'?'Análisis detenido':'Observación interrumpida'}</td></tr>)}</tbody></table></div>:<p className="count-small-empty">No se registraron intervalos de concentración con los límites definidos en el tramo analizado.</p>}
      <p className="count-footnote">Los tiempos corresponden a las imágenes analizadas. Zonas superpuestas pueden registrar el mismo evento; no se suman como personas diferentes.</p>
    </section>}
  </section>;
}
