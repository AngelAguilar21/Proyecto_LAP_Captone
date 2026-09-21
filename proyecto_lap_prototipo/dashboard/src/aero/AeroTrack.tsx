import ZoneWorkspace from './ZoneWorkspace';
import Notifications from './Notifications';
import { useEffect, useRef, useState } from 'react';
import { useSession, downloadFile } from './useSession';
import type { Person, View } from './types';
import { formatTime, isActive, labelAssociation, STATUS } from './types';
import Icon from './Icon';
import MapCanvas from './MapCanvas';
import SetupFlow, { readiness } from './SetupFlow';
import { CameraPanel } from './CameraPanel';
import CountingDashboard from '../counting/CountingDashboard';
import type { State as CountState } from '../counting/types';
import { active as countActive } from '../counting/types';
import './aero.css';
import './product.css';
import './operations.css';
import MonitoringWorkspace from './MonitoringWorkspace';
import ReplayWorkspace from './ReplayWorkspace';
import PlanSelector from './PlanSelector';
import BusinessDashboard from './BusinessDashboard';
import CommercialReportBoard from './CommercialReportBoard';


function explainError(msg: string): string {
  if(msg.includes('versión de seguimiento'))return 'No se pudo iniciar el seguimiento: el servidor usa un entorno incompatible. Reinicia AeroTrack con iniciar_sistema.ps1. Cerrar este aviso no inicia el análisis.';
  if (msg.includes('zona de detección es [u, v]')) return `Uno de los puntos de la zona de detección quedó fuera del video (por ejemplo, al marcar justo en el borde de la imagen). Vuelve a "Marcar zona", usa "Deshacer punto" para quitar el último y márcalo de nuevo dentro del video.\n${msg}`;
  if (msg.includes('Correspondencias inconsistentes')) return `Los puntos de calibración no coinciden bien entre el video y el plano — probablemente están muy juntos o casi en línea recta. Bórralos con "Reiniciar calibración" y vuelve a marcar 6 a 8 puntos repartidos por toda el área visible.\n${msg}`;
  if (msg.includes('heading fuera de rango')) return `La dirección de la cámara quedó fuera de 0°-360°. Corrígela en "Configurar cámara", campo "Dirección de visión".\n${msg}`;
  if (msg.includes('Calibración degenerada')) return `Los puntos de calibración marcados están alineados o repetidos y no permiten calcular la posición real. Marca puntos que no estén todos sobre la misma línea.\n${msg}`;
  return msg;
}
const NAV: {id:View;label:string;icon:string}[] = [{id:'overview',label:'Vista general',icon:'grid'},{id:'counting',label:'Conteo especializado',icon:'people'},{id:'setup',label:'Configuración',icon:'settings'},{id:'map',label:'Seguimiento',icon:'map'},{id:'cameras',label:'Cámaras',icon:'camera'},{id:'lab',label:'Diagnóstico de cámara',icon:'lab'},{id:'replay',label:'Videos y resultados',icon:'camera'},{id:'dashboard',label:'Panel comercial',icon:'chart'},{id:'zones',label:'Zonas del plano',icon:'pin'},{id:'rules',label:'Alertas del plano',icon:'alert'},{id:'reports',label:'Reportes',icon:'report'},{id:'audit',label:'Auditoría',icon:'shield'}];

function PanelHeader({number,title,color='blue',children}:{number?:number;title:string;color?:string;children?:React.ReactNode}) {
  return <div className="panel-heading"><div>{number&&<span className={`panel-number ${color}`}>{number}</span>}<h2>{title}</h2></div>{children}</div>;
}
function Metric({label,value,icon,note,tone='blue'}:{label:string;value:string|number;icon:string;note?:string;tone?:string}) {
  return <article className="metric-card"><Icon name={icon} size={25}/><div><span>{label}</span><strong className={`text-${tone}`}>{value}</strong>{note&&<small>{note}</small>}</div></article>;
}

export default function AeroTrack() {
  const session=useSession();
  const {config,state}=session;
  const initial=new URLSearchParams(location.search).get('view') as View;
  const [view,setView]=useState<View>(NAV.some(n=>n.id===initial)?initial:'overview');
  const [visited,setVisited]=useState<View[]>([initial]);
  useEffect(()=>{setVisited(p=>p.includes(view)?p:[...p,view]);},[view]);
  const [dismissedError,setDismissedError]=useState('');
  const errorKey=`${state.serverInstance}:${state.session}:${session.error||state.error||(!session.connected?'Sin conexión':'')}`;
  const [reportSession,setReportSession]=useState<string>();
  const [countState,setCountState]=useState<CountState|null>(null);
  const [reportModule,setReportModule]=useState<'counting'|'tracking'>('tracking');
  const countBusy=countState?countActive(countState.status):false;
  const countView=view==='counting'||(view==='reports'&&reportModule==='counting');
  const [selected,setSelected]=useState('');
  const [person,setPerson]=useState<Person|null>(null);
  const mapRef=useRef<HTMLElement>(null);
  const [step,setStep]=useState(2);
  const [detector,setDetector]=useState('yolo');
  const [weights,setWeights]=useState('');
  const [clock,setClock]=useState(new Date());
  useEffect(()=>{const id=setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(id);},[]);
  useEffect(()=>{if(config){const visible=config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom'));if(!visible.some(c=>c.id===selected))setSelected(visible[0]?.id||'');}},[config,selected]);
  useEffect(()=>{if(!['running','paused'].includes(state.status))setPerson(null);},[state.status]);
  function navigate(next:View) {if(next!=='reports')setReportSession(undefined);setView(next);history.replaceState(null,'',`?view=${next}`);}
  if(!config)return <div className="aero connection-screen"><div className="aero-logo"><Icon name="plane" size={38}/><strong>AeroTrack</strong></div><div className="connection-card"><span className="loader"/><h1>Conectando con el centro de monitoreo</h1><p>Inicia el servidor local para acceder al plano y las cámaras.</p><code>python live_server.py</code><small>Backend local · puerto 8765</small></div></div>;
  const busy=isActive(state.status);
  const current=session.connected&&['running','paused'].includes(state.status);
  const people=current?state.people:[];
  const observed=new Set(people.map(p=>p.id)).size;
  const alerts=current?state.analytics.clusters.filter(c=>c.alert).length+state.analytics.zones.filter(z=>z.alert).length:0;
  const activeCameras=current?state.cameras.filter(c=>c.status==='live').length:0;
  const camera=config.cameras.find(c=>c.id===selected);
  const stages=readiness(config,session);
  const ready=stages.every(s=>s.done);
  const demo=state.mode==='demo';
  function save() {void session.action(async()=>{await session.save();session.setNotice('Configuración guardada.');});}
  function start(id?:string, mode=detector) {void session.action(async()=>{await session.save();await session.post('start',{detector:mode,camera:id||null,weights,requireUnified:!id});session.setNotice(mode==='demo'?'Demostración sintética iniciada.':'Seguimiento iniciado. Puedes pausar la sesión para revisar las trayectorias.');});}
  const openCameraSettings=()=>{setStep(2);navigate('setup');};
  const cameraPanel=(laboratory=false)=><CameraPanel session={session} selected={selected} onSelected={setSelected} detector={detector} onDetector={setDetector} weights={weights} onWeights={setWeights} laboratory={laboratory} onStart={()=>start(selected)} onConfigure={openCameraSettings}/>;
function report(format:string) {void session.action(async()=>{const response=await fetch(`/api/report?format=${format}&kind=business`);if(!response.ok){const e=await response.json();throw new Error(e.error||'No se pudo exportar el reporte');}downloadFile(`aerotrack-reporte-comercial.${format}`,await response.blob());session.setNotice('Reporte exportado con los datos disponibles de esta sesión.');});}
  const stats=<div className="metrics-row"><Metric label="Personas observadas" value={observed} icon="people" note="IDs de la sesión actual"/><Metric label="Aglomeraciones" value={alerts} icon="alert" tone={alerts?'red':'green'} note={`≥ ${config.minPeople} personas · ${config.dwell}s`}/><Metric label="Cámaras activas" value={`${activeCameras} / ${config.cameras.length}`} icon="camera" note={config.clocksVerified?'Sincronización declarada':'Sincronización por verificar'}/><Metric label="Tiempo de fuente" value={formatTime(state.t)} icon="clock" note={state.processingMs?`${state.processingMs} ms por ciclo`:'Esperando procesamiento'}/></div>;
  return <div className="aero"><header className="aero-header"><div className="aero-logo"><Icon name="plane" size={31}/><strong>AeroTrack</strong></div><div className="aero-title"><h1>Monitoreo de ocupación y flujo de personas</h1><p>{config.airport||'Aeropuerto'}{!['overview','replay'].includes(view)&&` · ${config.floor||'Espacio principal'}`}</p></div><div className="header-indicators"><span><Icon name="clock" size={15}/> {session.connected?(countBusy?'Conteo en curso':STATUS[state.status]):'Sin conexión'}</span><span><Icon name="shield" size={15}/> Privacidad</span><span className="operator"><Icon name="user" size={15}/> Administrador local</span></div></header>
    <nav className="aero-nav" aria-label="Navegación principal">{(['overview','replay','reports','setup'] as View[]).map(id=>NAV.find(n=>n.id===id)!).map(n=><button key={n.id} className={(view===n.id||(n.id==='map'&&['lab','dashboard'].includes(view))||(n.id==='setup'&&['cameras','zones','rules','audit','counting','lab'].includes(view)))?'active':''} onClick={()=>navigate(n.id)}><Icon name={n.icon} size={17}/>{n.label}</button>)}</nav>
    {['setup','cameras','zones','rules','audit','counting','lab'].includes(view)&&<nav className="product-subnav" aria-label="Secciones de configuración">{(['setup','zones','rules','lab','counting','audit'] as View[]).map(id=>NAV.find(n=>n.id===id)!).map(n=><button key={n.id} className={view===n.id?'selected':''} onClick={()=>navigate(n.id)}>{n.id==='setup'?'Mapa y cámaras':n.label}</button>)}</nav>}
    <main className="aero-main">{['setup','zones','rules','lab','counting','audit'].includes(view)&&<p className="settings-context">{{setup:'Mapa y cámaras · Ubica las fuentes, delimita su imagen y calibra el suelo.',zones:'Zonas del plano · Define sectores físicos compartidos por las cámaras.',rules:'Alertas del plano · Establece cantidad y duración para avisar de concentraciones.',lab:'Diagnóstico · Prueba una cámara y revisa su señal antes de monitorear.',counting:'Análisis especializado · Herramienta avanzada para evaluar multitudes por separado.',audit:'Auditoría · Consulta las operaciones realizadas en el sistema.'}[view as 'setup'|'zones'|'rules'|'lab'|'counting'|'audit']}</p>}
      {countBusy&&!countView&&<div className="notice"><Icon name="people"/><span>Conteo en ejecución. Puedes navegar; el procesamiento continúa.</span><button onClick={()=>navigate('counting')}>Ver conteo</button></div>}
      {(!session.connected||session.error||state.error)&&dismissedError!==errorKey&&<div className="toast toast-error app-error" role="alert"><Icon name="alert"/><span>{explainError(session.error||state.error||'Backend desconectado. Las posiciones no se presentan como actuales.')}</span><button aria-label="Cerrar aviso de error" onClick={()=>{setDismissedError(errorKey);}}>Cerrar</button></div>}
      <Notifications session={session}/>
      {!countView&&demo&&<div className="notice warning"><Icon name="lab"/><span>SIMULACIÓN · Datos sintéticos para probar las pantallas. No representan mediciones de un aeropuerto.</span></div>}
      {!countView&&!['overview','setup','audit','reports','replay','lab','zones','rules'].includes(view)&&!ready&&<div className="setup-banner"><div><Icon name="settings" size={21}/><span><strong>Prepara el tracking sobre plano</strong><small>{stages.filter(s=>s.done).length}/{stages.length} pasos preparados · {stages.filter(s=>!s.done).map(s=>s.title.toLowerCase()).join(', ')} pendientes</small></span></div><button onClick={()=>{setStep(Math.max(0,stages.findIndex(s=>!s.done)));navigate('setup');}}>Continuar configuración <Icon name="arrow" size={15}/></button></div>}
      {!countView&&['map','dashboard'].includes(view)&&<div className="session-bar"><div className="inline"><i className={`dot ${state.status==='running'?'green':state.status==='error'?'red':'amber'}`}/><strong>{state.session?`Sesión ${state.session}`:'Sin sesión activa'}</strong><span>{config.sourceMode==='live'?'Cámaras en vivo':config.sourceMode==='demo'?'Demostración':'Grabaciones de prueba'}</span>{session.dirty&&<span className="unsaved">Cambios sin guardar</span>}</div><div className="inline"><time>{clock.toLocaleTimeString('es-PE',{timeZone:'America/Lima'})}</time>{busy?<>{state.status==='paused'?<button onClick={()=>void session.action(async()=>{await session.post('resume',{});})}>▶ Reanudar</button>:<button disabled={state.status!=='running'} onClick={()=>void session.action(async()=>{await session.post('pause',{});})}>Ⅱ Pausar</button>}<button className="danger" disabled={session.busy||state.status==='stopping'} onClick={()=>void session.action(async()=>{await session.post('stop',{});})}>Finalizar sesión</button></>:<><button disabled={session.busy||!config.cameras.length} onClick={()=>start(undefined,'demo')}>Ver simulación</button><button className="primary" disabled={countBusy||session.busy||!session.connected||!config.cameras.length} onClick={()=>start(undefined,config.sourceMode==='demo'?'demo':detector)}>Iniciar {config.cameras.length} cámara{config.cameras.length===1?'':'s'}</button></>}</div></div>
      }
      {view==='reports'&&<div className="module-report-tabs" role="group" aria-label="Tipo de reportes"><button className={reportModule==='counting'?'selected':''} onClick={()=>setReportModule('counting')}>Conteo especializado</button><button className={reportModule==='tracking'?'selected':''} onClick={()=>setReportModule('tracking')}>Monitoreo integrado</button></div>}
      <div hidden={!countView}><CountingDashboard embedded reportSession={reportSession} reportMode={view==='reports'} cameras={config.cameras.filter(c=>typeof c.source==='string').map(c=>({id:c.id,name:c.name||`Cámara ${c.id}`,source:String(c.source),detectionZone:c.detectionZone}))} trackingActive={busy} onState={setCountState} onReports={()=>{setReportModule('counting');navigate('reports');}} onCameras={openCameraSettings}/></div>
      {visited.includes('replay')&&<div hidden={view!=='replay'}><ReplayWorkspace active={view==='replay'} currentConfig={config}/></div>}{visited.includes('overview')&&<div hidden={view!=='overview'}><MonitoringWorkspace active={view==='overview'} session={session} onReplay={()=>navigate('replay')} onSetup={id=>{if(id)setSelected(id);setStep(2);navigate('setup');}}/></div>}
      {view==='setup'?<SetupFlow session={session} selected={selected} onSelected={setSelected} onNavigate={navigate} step={step} setStep={setStep} startTest={()=>void session.action(async()=>{await session.save();await session.post('camera-preview',{camera:selected,seconds:0});session.setNotice('Imagen disponible para configurar. No se inició un análisis.');})}/>:<>

      {view==='map'&&<><PlanSelector config={config} disabled={busy} onChange={session.setConfig}/>{stats}<section className="aero-panel map-live" ref={mapRef}><PanelHeader title="Plano vivo · posiciones y trayectorias"><span className="pill blue">{config.floor}</span><button title="Pantalla completa" onClick={()=>void mapRef.current?.requestFullscreen().catch(()=>{})}><Icon name="expand" size={15}/></button></PanelHeader><MapCanvas config={config} state={state} connected={session.connected} selectedCamera={selected} onCamera={setSelected} selectedPerson={person?.id} onPerson={setPerson}/></section></>}
      {(view==='cameras'||view==='lab')&&<><div className="page-heading"><div><span className="eyebrow">{view==='lab'?'VALIDACIÓN DE FUENTES':'RED DE CÁMARAS'}</span><h1>{view==='lab'?'Diagnóstico de cámara':'Todas las cámaras, una sesión'}</h1><p>{view==='lab'?'Prueba cada fuente antes de integrarla al sistema.':'Selecciona una cámara para inspeccionar el video y sus IDs temporales.'}</p></div><button disabled={busy} onClick={openCameraSettings}><Icon name="plus"/> Añadir o configurar cámaras</button></div>{view!=='lab'&&<div className="camera-selector-grid">{config.cameras.map(c=><button key={c.id} className={c.id===selected?'selected':''} onClick={()=>setSelected(c.id)}><Icon name="camera" size={25}/><span><strong>{c.name||c.id}</strong><small>{c.id} · {c.location||'Ubicación pendiente'}</small></span><i className={`dot ${state.cameras.find(s=>s.id===c.id)?.status==='live'&&current?'green':'amber'}`}/></button>)}</div>}<section className="aero-panel camera-full"><PanelHeader title={camera?.name||'Fuente de video'}><span className="pill muted">Sin identificación personal</span></PanelHeader>{cameraPanel(view==='lab')}</section>{view==='lab'&&<div className="lab-guidance"><div><Icon name="check"/><h3>Fuente y rendimiento</h3><p>Comprueba señal, resolución y tiempo de procesamiento. Los FPS de la fuente no son los FPS de inferencia.</p></div><div><Icon name="pin"/><h3>Calidad de calibración</h3><p>Usa referencias distribuidas en el suelo y comprueba el error con puntos adicionales.</p><button onClick={()=>{setStep(2);navigate('setup');}}>Calibrar esta cámara</button></div><div><Icon name="people"/><h3>Estabilidad del tracking</h3><p>Revisa cambios de ID y fragmentaciones contra anotaciones. La continuidad aparente no demuestra precisión.</p></div></div>}</>}
      {view==='dashboard'&&<BusinessDashboard config={config} state={state} demo={demo}/>}
      {view==='zones'&&<ZoneWorkspace session={session}/>}
      {view==='rules'&&<><PlanSelector config={config} disabled={busy} onChange={session.setConfig}/><div className="page-heading"><div><span className="eyebrow">ALERTAS CONFIGURABLES</span><h1>Reglas de aglomeración</h1><p>Ajusta cantidad, cercanía y permanencia. Las reglas globales se pueden aplicar durante el procesamiento.</p></div></div><section className="aero-panel rules-panel"><PanelHeader title="Agrupaciones automáticas"/><div className="rules-form"><label>Radio ({config.unit==='meters'?'metros':'unidades relativas'})<input type="number" min="0.01" step="0.1" value={config.radius} onChange={e=>session.setConfig({...config,radius:+e.target.value})}/></label><label>Personas mínimas<input type="number" min="2" step="1" value={config.minPeople} onChange={e=>session.setConfig({...config,minPeople:+e.target.value})}/></label><label>Permanencia (segundos)<input type="number" min="0" value={config.dwell} onChange={e=>session.setConfig({...config,dwell:+e.target.value})}/></label><button className="primary" disabled={session.busy} onClick={()=>void session.action(async()=>{if(busy)await session.post('settings',{radius:config.radius,minPeople:config.minPeople,dwell:config.dwell});else await session.save();session.setNotice('Reglas aplicadas.');})}>Aplicar reglas</button></div><p className="subtle">Una fila y una aglomeración pueden parecerse geométricamente. Define límites apropiados al uso de cada zona.</p></section><section className="aero-panel zone-rules"><PanelHeader title="Reglas por zona"/>{config.zones.filter(z=>!['wall','door'].includes(z.kind||'')).map(z=>{const index=config.zones.indexOf(z);const rule=z.rule||{enabled:false,minPeople:config.minPeople,dwell:config.dwell};const update=(patch:Partial<typeof rule>)=>session.setConfig({...config,zones:config.zones.map((v,i)=>i===index?{...v,rule:{...rule,...patch}}:v)});return <div className="zone-rule" key={index}><label className="check"><input type="checkbox" disabled={busy} checked={rule.enabled} onChange={e=>update({enabled:e.target.checked})}/>{z.name}</label><label>Personas<input type="number" disabled={busy} min="2" value={rule.minPeople} onChange={e=>update({minPeople:+e.target.value})}/></label><label>Segundos<input type="number" disabled={busy} min="0" value={rule.dwell} onChange={e=>update({dwell:+e.target.value})}/></label></div>})}{!config.zones.length&&<p className="empty-text">Dibuja una zona para asignarle una regla particular.</p>}<button disabled={busy||session.busy} onClick={save}>Guardar reglas por zona</button></section></>}
      {view==='reports'&&reportModule==='tracking'&&<><div className="page-heading"><div><span className="eyebrow">REPORTE COMERCIAL</span><h1>Panel comercial para LAP</h1><p>Lectura en vivo de la sesión, pensada para decisiones comerciales. Descarga el mismo contenido como documento cuando lo necesites.</p></div></div>
        <div className="report-dark-page">
          <div className="report-download-bar">
            <div><h2>Descargar reporte</h2><p>KPIs, ranking de zonas, tráfico por acceso y recomendaciones, en un documento.</p><span className="pill">{state.session?`Sesión ${state.session}`:'Sin sesión'} · {demo?'Sintético':'Fuente real'} · {config.unit==='meters'?'Metros':'Unidades relativas'}</span></div>
            <div className="export-buttons"><button className="primary" disabled={session.busy||!state.session} onClick={()=>report('pdf')}><Icon name="download"/> PDF</button><button disabled={session.busy||!state.session} onClick={()=>report('xlsx')}><Icon name="download"/> Excel</button><button disabled={session.busy||!state.session} onClick={()=>report('csv')}><Icon name="download"/> CSV</button><button disabled={!state.session} onClick={()=>downloadFile('aerotrack-reporte-comercial.json',JSON.stringify({session:state.session,mode:state.mode,unit:config.unit,totals:state.totals,analytics:state.analytics},null,2))}>JSON</button></div>
          </div>
          <CommercialReportBoard config={config} state={state} demo={demo}/>
        </div>
        </>}
      {view==='audit'&&<><div className="page-heading"><div><span className="eyebrow">TRAZABILIDAD OPERATIVA</span><h1>Auditoría del sistema</h1><p>Acciones del operador durante la ejecución del servidor. No contiene identidades reales.</p></div></div><section className="aero-panel audit-panel"><table><thead><tr><th>Fecha y hora</th><th>Acción</th><th>Detalle</th></tr></thead><tbody>{state.audit?.map((event,i)=><tr key={i}><td>{new Date(event.at).toLocaleString('es-PE',{timeZone:'America/Lima'})}</td><td>{event.action}</td><td>{event.detail}</td></tr>)}</tbody></table>{!state.audit?.length&&<p className="empty-text">Las acciones aparecerán al guardar la configuración o iniciar una sesión.</p>}</section></>}
      </>}
      {person&&current&&<aside className="person-drawer"><button className="close-drawer" title="Cerrar recorrido" onClick={()=>setPerson(null)}>×</button><span className="eyebrow">RECORRIDO ANÓNIMO</span><h2>{person.id}</h2><span className={`pill ${person.association==='uncertain'?'warn':'blue'}`}>{labelAssociation(person)}</span><dl><div><dt>Cámara actual</dt><dd>{person.camera}</dd></div><div><dt>Posición observada</dt><dd>{person.point?.map(v=>v.toFixed(2)).join(', ')||'Sin calibración'}</dd></div><div><dt>Próxima cámara probable</dt><dd>{person.nextCamera||'Sin evidencia suficiente'}</dd></div></dl><p>La dirección futura es una estimación. No confirma la identidad en una zona sin cobertura.</p><div className="journey">{state.events.filter(e=>e.id===person.id).slice().reverse().map((e,i)=><div key={i}><span>{formatTime(e.t)}</span><b>{e.from} → {e.to}</b><small>Asociación estimada</small></div>)}</div><button onClick={()=>{setSelected(person.camera);navigate('cameras');setPerson(null);}}>Ver cámara <Icon name="arrow" size={14}/></button></aside>}
    </main><footer className="aero-footer"><span>AeroTrack · Monitoreo y analítica</span><span><Icon name="shield" size={13}/> Análisis de ocupación y flujo</span><span>{session.connected?'● Servidor local conectado':'○ Servidor desconectado'}</span></footer>
  </div>;
}
