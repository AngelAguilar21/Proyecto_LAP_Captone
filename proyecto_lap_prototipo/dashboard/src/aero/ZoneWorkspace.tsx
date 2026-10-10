import {useEffect,useState} from 'react';
import type {Session} from './useSession';
import {EMPTY_STATE,isActive} from './types';
import type {HeatCell,Point,Zone} from './types';
import MapCanvas from './MapCanvas';
import type {MapTool} from './MapCanvas';
import PlanSelector from './PlanSelector';

function inside(point:Point,polygon:Point[]){
 let hit=false;
 for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
  const [xi,yi]=polygon[i],[xj,yj]=polygon[j];
  if(((yi>point[1])!==(yj>point[1]))&&(point[0]<(xj-xi)*(point[1]-yi)/(yj-yi)+xi))hit=!hit;
 }
 return hit;
}

function suggestions(heat:HeatCell[],zones:Zone[]){
 const occupied=zones.filter(zone=>zone.kind==='commercial'||zone.source==='system');
 const remaining=heat.filter(cell=>!occupied.some(zone=>inside([cell.x+cell.size/2,cell.y+cell.size/2],zone.points)))
  .sort((a,b)=>(b.seconds+(b.visits||0)*4+b.peak*2)-(a.seconds+(a.visits||0)*4+a.peak*2)).slice(0,40);
 const groups:HeatCell[][]=[];
 while(remaining.length){
  const group=[remaining.shift()!];let changed=true;
  while(changed){changed=false;for(let i=remaining.length-1;i>=0;i--){const cell=remaining[i];if(group.some(other=>Math.abs(other.x-cell.x)<=Math.max(other.size,cell.size)*1.01&&Math.abs(other.y-cell.y)<=Math.max(other.size,cell.size)*1.01)){group.push(cell);remaining.splice(i,1);changed=true;}}}
  groups.push(group);
 }
 return groups.map(group=>{
  const x=Math.min(...group.map(cell=>cell.x)),y=Math.min(...group.map(cell=>cell.y));
  const right=Math.max(...group.map(cell=>cell.x+cell.size)),bottom=Math.max(...group.map(cell=>cell.y+cell.size));
  const seconds=group.reduce((total,cell)=>total+cell.seconds,0),visits=Math.max(...group.map(cell=>cell.visits||0)),peak=Math.max(...group.map(cell=>cell.peak));
  return {points:[[x,y],[right,y],[right,bottom],[x,bottom]] as Point[],cells:group.length,seconds,visits,peak,area:(right-x)*(bottom-y),score:seconds+visits*4+peak*2};
 }).sort((a,b)=>b.score-a.score).slice(0,5);
}

const categories={retail:'Tienda',food:'Alimentos y bebidas',service:'Servicios',other:'Otro'} as const;

export default function ZoneWorkspace({session}:{session:Session}){
 const config=session.config!,busy=isActive(session.state.status),pid=config.planId||'custom';
 const [tool,setTool]=useState<MapTool>('select'),[selected,setSelected]=useState(''),[selectedBusinessId,setSelectedBusinessId]=useState('');
 const [heat,setHeat]=useState<HeatCell[]>([]),[zoneMetrics,setZoneMetrics]=useState<any[]>([]),[source,setSource]=useState(''),[loading,setLoading]=useState(false);
 const businesses=config.zones.filter(zone=>zone.kind==='commercial');
 const recommended=config.zones.filter(zone=>zone.source==='system');
 const legacyRois=config.zones.filter(zone=>zone.kind==='roi'&&zone.source!=='system');
 const hasBusinesses=config.commercialContext?.hasBusinesses??businesses.length>0;
 const opportunities=suggestions(heat,config.zones);
 const analysisState={...EMPTY_STATE,status:'ended',planId:pid,analytics:{...EMPTY_STATE.analytics,heat}};
 useEffect(()=>{
  setSelectedBusinessId(current=>businesses.some(zone=>zone.id===current)?current:(businesses[0]?.id||''));
 },[businesses.map(zone=>zone.id).join('|')]);

 useEffect(()=>{let alive=true;setHeat([]);setZoneMetrics([]);setSource('');if(busy){const analytics=(session.state as any).levelAnalytics?.[pid]||(session.state.planId===pid?session.state.analytics:EMPTY_STATE.analytics);setHeat(analytics.heat||[]);setZoneMetrics(analytics.zones||[]);setSource('Monitoreo en curso');return;}
  setLoading(true);void fetch('/api/replay/history').then(r=>r.json()).then(async list=>{const run=list.find((row:any)=>row.end>0&&row.module==='unified'&&row.cameras.some((camera:any)=>(camera.planId||row.config.planId)===pid));if(!run)return;const response=await fetch(`/api/replay/data?session=${run.session}&projection=current&last=1`);if(!response.ok)throw Error();const data=await response.json(),last=data.samples?.[data.samples.length-1],analytics=last?.levels?.[pid]||(data.config.planId===pid?last?.analytics:EMPTY_STATE.analytics);if(alive){setHeat(analytics?.heat||[]);setZoneMetrics(analytics?.zones||[]);setSource(`Análisis del ${new Date(run.created).toLocaleString('es-PE')}`);}}).catch(()=>{if(alive)setSource('No se pudo cargar el análisis para generar oportunidades.');}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};
 },[pid,busy,session.state.session]);

 function updateBusiness(zone:Zone,patch:NonNullable<Zone['business']>){
  const zoneIndex=config.zones.indexOf(zone);
  session.setConfig({...config,zones:config.zones.map((item,i)=>i===zoneIndex?{...item,business:{...item.business,...patch}}:item)});
 }
 function numberValue(zone:Zone,key:keyof NonNullable<Zone['business']>,value:string){
  const parsed=value===''?undefined:Math.max(0,Number(value));
  updateBusiness(zone,{[key]:Number.isFinite(parsed)?parsed:undefined});
 }
 function accept(points:Point[]){
  const ordinal=recommended.length+1;
  session.setConfig({...config,zones:[...config.zones,{id:crypto.randomUUID(),name:`Oportunidad detectada ${ordinal}`,kind:'roi',shape:'polygon',source:'system',points:points.map(point=>[Math.max(0,Math.min(config.width,point[0])),Math.max(0,Math.min(config.height,point[1]))])}]});
  session.setNotice('Oportunidad guardada desde el análisis. Puedes revisar su posición, pero su origen seguirá identificado como recomendación del sistema.');
 }

 return <div className="zone-workspace opportunity-workspace">
  <div className="page-heading"><div><h1>Oportunidades recomendadas</h1><p>AeroTrack encuentra nuevos puntos de interés a partir del flujo observado. Tú solo aportas el contexto comercial conocido.</p></div></div>
  <PlanSelector config={config} disabled={busy} onChange={session.setConfig}/>
  <section className="aero-panel commercial-context">
   <header><div><h2>Contexto comercial del piso</h2><p>Indica si ya existen negocios. Sus medidas ayudan a separar locales actuales de oportunidades nuevas.</p></div><div className="context-choice" role="group" aria-label="¿Este piso tiene negocios?"><button className={!hasBusinesses?'selected':''} disabled={busy} onClick={()=>session.setConfig({...config,commercialContext:{hasBusinesses:false}})}>No hay negocios</button><button className={hasBusinesses?'selected':''} disabled={busy} onClick={()=>session.setConfig({...config,commercialContext:{hasBusinesses:true}})}>Sí hay negocios</button></div></header>
   {hasBusinesses&&<p className="commercial-instruction">Dibuja únicamente la huella de cada negocio existente con Polígono o Rectángulo. Las zonas ROI no se dibujan aquí: AeroTrack las propone después del análisis.</p>}
  </section>
  <div className="opportunity-layout">
   <section className="aero-panel opportunity-map"><MapCanvas zonesOnly zoneMode="business" config={config} state={analysisState} connected selectedCamera={selected} onCamera={setSelected} onZoneSelect={zone=>setSelectedBusinessId(zone.id||'')} editable={!busy&&hasBusinesses} onChange={session.setConfig} tool={tool} onTool={setTool}/></section>
   <section className="aero-panel business-register">
    <header><div><h2>Negocios existentes</h2><p className="selected-business-caption">{businesses.find(zone=>zone.id===selectedBusinessId)?.name||'Selecciona un negocio en el plano o en la lista.'}</p></div><span>{businesses.length} registrados</span></header>
    {!hasBusinesses&&<p className="empty-text">Marcaste que este piso no contiene negocios. El sistema buscará oportunidades usando únicamente el flujo peatonal.</p>}
    {hasBusinesses&&!businesses.length&&<p className="empty-text">Dibuja el primer negocio sobre el plano. Después completa sus medidas y capacidad.</p>}
    {!!businesses.length&&<div className="business-tabs" role="tablist" aria-label="Negocios del plano">{businesses.map((zone,index)=><button key={zone.id||index} role="tab" aria-selected={zone.id===selectedBusinessId} className={zone.id===selectedBusinessId?'selected':''} onClick={()=>setSelectedBusinessId(zone.id||'')}>{zone.name||`Negocio ${index+1}`}</button>)}</div>}
    {businesses.filter(zone=>!selectedBusinessId||zone.id===selectedBusinessId).map((zone,index)=>{const measured=zoneMetrics.find(metric=>metric.name===zone.name);return <article className="business-record is-selected" key={zone.id||index}>
     <div className="business-record-head"><input aria-label="Nombre del negocio" value={zone.name} onChange={event=>session.setConfig({...config,zones:config.zones.map(item=>item===zone?{...item,name:event.target.value}:item)})}/><button disabled={busy} onClick={()=>session.setConfig({...config,zones:config.zones.filter(item=>item!==zone)})}>Eliminar</button></div>
     <div className="business-fields">
      <label>Tipo<select value={zone.business?.category||'other'} onChange={event=>updateBusiness(zone,{category:event.target.value as NonNullable<Zone['business']>['category']})}>{Object.entries(categories).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label>
      <label>Ancho (m)<input type="number" min="0" step="0.1" value={zone.business?.widthM??''} onChange={event=>numberValue(zone,'widthM',event.target.value)}/></label>
      <label>Fondo (m)<input type="number" min="0" step="0.1" value={zone.business?.depthM??''} onChange={event=>numberValue(zone,'depthM',event.target.value)}/></label>
      <label>Área útil (m²)<input type="number" min="0" step="0.1" value={zone.business?.areaM2??''} onChange={event=>numberValue(zone,'areaM2',event.target.value)}/></label>
      <label>Capacidad<input type="number" min="0" step="1" value={zone.business?.capacity??''} onChange={event=>numberValue(zone,'capacity',event.target.value)}/></label>
      <label>Acceso (m)<input type="number" min="0" step="0.1" value={zone.business?.entranceWidthM??''} onChange={event=>numberValue(zone,'entranceWidthM',event.target.value)}/></label>
     </div>
     <p className="business-observation">{measured?`Flujo observado: ${measured.visits||0} visitas · pico ${measured.peak||0}${zone.business?.capacity?` de ${zone.business.capacity} personas de capacidad`:''}`:'El próximo monitoreo calculará visitas, pico y permanencia dentro de esta huella.'}</p>
    </article>})}
   </section>
  </div>
  <section className="aero-panel system-opportunities">
   <header><div><h2>Nuevos puntos sugeridos por AeroTrack</h2><p>{loading?'Analizando resultados…':source||'Aún no hay un análisis compatible.'}</p></div><span>{opportunities.length} propuestas</span></header>
   {!!legacyRois.length&&<div className="legacy-zones"><div><strong>{legacyRois.length} ROI manuales heredadas</strong><p>No se presentan como recomendaciones de AeroTrack. Puedes retirarlas para trabajar únicamente con hallazgos automáticos.</p></div>{legacyRois.map(zone=><button key={zone.id||zone.name} disabled={busy} onClick={()=>session.setConfig({...config,zones:config.zones.filter(item=>item!==zone)})}>Retirar {zone.name}</button>)}</div>}
   <div className="opportunity-cards">{opportunities.map((item,index)=><article key={`${item.points[0][0]}-${item.points[0][1]}`}><div><strong>Oportunidad {index+1}</strong><span>Prioridad {index===0?'alta':index<3?'media':'exploratoria'}</span></div><dl><div><dt>Visitas estimadas</dt><dd>{item.visits||'—'}</dd></div><div><dt>Pico observado</dt><dd>{item.peak}</dd></div><div><dt>Presencia acumulada</dt><dd>{Math.round(item.seconds)} persona-s</dd></div><div><dt>Superficie analizada</dt><dd>{item.area.toFixed(1)} {config.unit==='meters'?'m²':'u²'}</dd></div></dl><button className="primary" disabled={busy} onClick={()=>accept(item.points)}>Guardar recomendación</button></article>)}</div>
   {!loading&&!heat.length&&<p className="empty-text">Procesa las cámaras calibradas de este piso. AeroTrack agrupará automáticamente los sectores con más visitas, permanencia y concentración.</p>}
   {!loading&&heat.length&&!opportunities.length&&<p className="empty-text">Los sectores con actividad ya pertenecen a negocios u oportunidades guardadas. Se necesitan nuevas observaciones para proponer otro punto.</p>}
   {!!recommended.length&&<div className="saved-opportunities"><strong>Recomendaciones guardadas</strong>{recommended.map(zone=><span key={zone.id}>{zone.name} · generada por el sistema</span>)}</div>}
  </section>
 </div>;
}
