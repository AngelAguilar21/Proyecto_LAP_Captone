import SessionReports from './SessionReports';
import Notifications from './Notifications';
import { useEffect, useRef, useState } from 'react';
import { useSession } from './useSession';
import type { Person, View } from './types';
import { formatTime, isActive, labelAssociation, STATUS } from './types';
import Icon from './Icon';
import Metric from './Metric';
import MapCanvas from './MapCanvas';
import SetupFlow, { PROJECT_STEPS, readiness } from './SetupFlow';
import { CameraPanel } from './CameraPanel';
import './aero.css';
import './product.css';
import './operations.css';
import './refinements.css';
import './theme-dark.css';
import './overview-v2.css';
import './enterprise-theme.css';
import './ux-fixes.css';
import MonitoringWorkspace from './MonitoringWorkspace';
import ReplayWorkspace from './ReplayWorkspace';
import PlanSelector from './PlanSelector';
import BusinessDashboard from './BusinessDashboard';
import CommercialPanel from './CommercialPanel';
import InsightsPanel from './InsightsPanel';
import ProjectPicker from './ProjectPicker';
import ProjectsPanel from './ProjectsPanel';
import SecurityAlerts from './SecurityAlerts';
import Login from './Login';
import BusinessesPanel from './BusinessesPanel';


function explainError(msg: string): string {
  if(msg.includes('versión de seguimiento'))return 'No se pudo iniciar el seguimiento: el servidor usa un entorno incompatible. Reinicia AeroTrack con iniciar_sistema.ps1. Cerrar este aviso no inicia el análisis.';
  if (msg.includes('No se pudo abrir la fuente') || msg.includes('No se pudo abrir el video')) return `La cámara no entregó imágenes. Revisa que la ruta exista, que el archivo tenga permisos de lectura y que la fuente de red siga disponible. Si las demás cámaras funcionan, puedes relanzar esta cámara desde su tarjeta.\n${msg}`;
  if (msg.includes('se interrumpió la señal') || msg.includes('no entregó una imagen')) return `La fuente dejó de entregar frames dentro del tiempo esperado. Comprueba la conexión, el formato del video y la hora del sistema; el conteo no se interpretará como cero.\n${msg}`;
  if (msg.includes('relojes') || msg.includes('desfase de tiempo') || msg.includes('sincron')) return `Las cámaras no tienen un tiempo común validado. Marca a la misma persona en cuatro o más instantes distintos dentro de Homografía y revisa el desfase informado antes de iniciar el monitoreo multicámara.\n${msg}`;
  if (msg.includes('zona útil') || msg.includes('zona de detección')) return `La cámara necesita una zona útil dentro del video para excluir espejos y áreas externas. Vuelve a Configurar proyecto → Cámara y marca el área visible.\n${msg}`;
  if (msg.includes('YOLO') || msg.includes('detector')) return `No se pudo preparar el detector de personas. Comprueba que los pesos YOLO estén instalados y que el tamaño de inferencia sea 320, 480, 640 o 960 píxeles.\n${msg}`;
  if (msg.includes('zona de detección es [u, v]')) return `Uno de los puntos de la zona de detección quedó fuera del video (por ejemplo, al marcar justo en el borde de la imagen). Vuelve a "Marcar zona", usa "Deshacer punto" para quitar el último y márcalo de nuevo dentro del video.\n${msg}`;
  if (msg.includes('Correspondencias inconsistentes')) return `Los puntos de calibración no coinciden bien entre el video y el plano — probablemente están muy juntos o casi en línea recta. Bórralos con "Reiniciar calibración" y vuelve a marcar 6 a 8 puntos repartidos por toda el área visible.\n${msg}`;
  if (msg.includes('heading fuera de rango')) return `La dirección de la cámara quedó fuera de 0°-360°. Corrígela en "Configurar cámara", campo "Dirección de visión".\n${msg}`;
  if (msg.includes('Calibración degenerada')) return `Los puntos de calibración marcados están alineados o repetidos y no permiten calcular la posición real. Marca puntos que no estén todos sobre la misma línea.\n${msg}`;
  return msg;
}
const NAV: {id:View;label:string;icon:string}[] = [{id:'commercial',label:'Ventas y análisis',icon:'chart'},{id:'insights',label:'Exposición y captación',icon:'pin'},{id:'businesses',label:'Negocios y accesos',icon:'pin'},{id:'overview',label:'Vista general',icon:'grid'},{id:'setup',label:'Configurar proyecto',icon:'settings'},{id:'map',label:'Monitoreo en vivo',icon:'eye'},{id:'cameras',label:'Cámaras',icon:'camera'},{id:'lab',label:'Diagnóstico de cámara',icon:'lab'},{id:'replay',label:'Videos y resultados',icon:'camera'},{id:'dashboard',label:'Panel comercial',icon:'chart'},{id:'alerts',label:'Alertas',icon:'alert'},{id:'reports',label:'Reportes',icon:'report'},{id:'projects',label:'Proyectos',icon:'layers'},{id:'audit',label:'Auditoría',icon:'shield'}];

function PanelHeader({number,title,color='blue',children}:{number?:number;title:string;color?:string;children?:React.ReactNode}) {
  return <div className="panel-heading"><div>{number&&<span className={`panel-number ${color}`}>{number}</span>}<h2>{title}</h2></div>{children}</div>;
}

function BlockingError({message,onClose,onResolve}:{message:string;onClose:()=>void;onResolve?:()=>void}) {
  const calibration=message.includes('Correspondencias inconsistentes')||message.includes('Calibración degenerada');
  return <div className="blocking-error-backdrop" role="presentation">
    <section className="blocking-error-dialog" role="alertdialog" aria-modal="true" aria-labelledby="blocking-error-title" aria-describedby="blocking-error-copy">
      <div className="blocking-error-symbol"><Icon name="alert" size={28}/></div>
      <div className="blocking-error-content">
        <h2 id="blocking-error-title">{calibration?'No se puede guardar esta calibración':'No se pudo completar la acción'}</h2>
        <p id="blocking-error-copy">{explainError(message)}</p>
      </div>
      <div className="blocking-error-actions">
        <button autoFocus={!calibration} onClick={onClose}>Cerrar</button>
        {calibration&&onResolve&&<button className="primary" autoFocus onClick={onResolve}>Revisar homografía</button>}
      </div>
    </section>
  </div>;
}

export default function AeroTrack() {
  const session=useSession();
  const {config,state}=session;
  const initial=new URLSearchParams(location.search).get('view') as View;
  const [view,setView]=useState<View>(NAV.some(n=>n.id===initial)?initial:'overview');
  const [visited,setVisited]=useState<View[]>([initial]);
  useEffect(()=>{setVisited(p=>p.includes(view)?p:[...p,view]);},[view]);
  const [projectChosen,setProjectChosen]=useState(false);
  const [dismissedError,setDismissedError]=useState('');
  const blockingMessage=session.error||state.error||(!session.connected?'No hay conexión con la API local. Comprueba que el servidor de AeroTrack esté activo.':'');
  const errorKey=`${state.serverInstance}:${state.session}:${blockingMessage}`;
  const [selected,setSelected]=useState('');
  const [person,setPerson]=useState<Person|null>(null);
  const mapRef=useRef<HTMLElement>(null);
  const [step,setStep]=useState(2);
  // Preferencia de quien opera, no del proyecto: se guarda en el navegador.
  const [collapsed,setCollapsed]=useState(()=>{try{return localStorage.getItem('aero.sidebar')==='collapsed';}catch{return false;}});
  const [clock,setClock]=useState(new Date());
  useEffect(()=>{const id=setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(id);},[]);
  useEffect(()=>{if(config){const visible=config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom'));if(!visible.some(c=>c.id===selected))setSelected(visible[0]?.id||'');}},[config,selected]);
  useEffect(()=>{if(!['running','paused'].includes(state.status))setPerson(null);},[state.status]);
  function navigate(next:View) {setView(next);history.replaceState(null,'',`?view=${next}`);}
  if(session.auth.cargado&&!session.auth.usuario)return <Login session={session}/>;
  if(config&&session.projects.projects.length>1&&!projectChosen&&!isActive(state.status))return <ProjectPicker session={session} onEnter={()=>setProjectChosen(true)}/>;
  if(!config)return <div className="aero connection-screen"><div className="aero-logo"><Icon name="plane" size={38}/><strong>AeroTrack</strong></div><div className="connection-card"><span className="loader"/><h1>Conectando con el centro de monitoreo</h1><p>Inicia el servidor local para acceder al plano y las cámaras.</p><code>python live_server.py</code><small>Backend local · puerto 8765</small></div></div>;
  const busy=isActive(state.status);
  const current=session.connected&&['running','paused'].includes(state.status);
  const people=current?state.people:[];
  const observed=new Set(people.filter(p=>p.confirmed!==false&&!p.duplicate).map(p=>p.id)).size;
  const alerts=current?state.analytics.clusters.filter(c=>c.alert).length+state.analytics.zones.filter(z=>z.alert).length:0;
  const activeCameras=current?state.cameras.filter(c=>c.status==='live').length:0;
  const camera=config.cameras.find(c=>c.id===selected);
  const stages=readiness(config,session);
  const ready=stages.every(s=>s.done);
  const demo=state.mode==='demo';
 function start(id?:string, mode:'yolo'|'demo'='yolo') {void session.action(async()=>{await session.save();await session.post('start',{detector:mode,camera:id||null,requireUnified:!id,inferenceSize:640});session.setNotice(mode==='demo'?'Demostración sintética iniciada.':'Monitoreo iniciado: YOLO + BoT-SORT + reidentificación OSNet. Los IDs se consolidan al finalizar.');});}
  const openCameraSettings=()=>{setStep(2);navigate('setup');};
  const cameraPanel=(laboratory=false)=><CameraPanel session={session} selected={selected} onSelected={setSelected} laboratory={laboratory} onStart={()=>start(selected)} onConfigure={openCameraSettings}/>;
  const stats=<div className="metrics-row"><Metric label="Personas observadas" value={observed} icon="people" note="IDs de la sesión actual"/><Metric label="Aglomeraciones" value={alerts} icon="alert" tone={alerts?'red':'green'} note={`≥ ${config.minPeople} personas · ${config.dwell}s`}/><Metric label="Cámaras activas" value={`${activeCameras} / ${config.cameras.length}`} icon="camera" note={config.clocksVerified?'Sincronización declarada':'Sincronización por verificar'}/><Metric label="Tiempo de fuente" value={formatTime(state.t)} icon="clock" note={state.processingMs?`${state.processingMs} ms por ciclo`:'Esperando procesamiento'}/></div>;
  return <div className={`aero aero-shell${collapsed?' sidebar-collapsed':''}`}>
    {blockingMessage&&dismissedError!==errorKey&&<BlockingError message={blockingMessage} onClose={()=>setDismissedError(errorKey)} onResolve={()=>{setDismissedError(errorKey);setStep(PROJECT_STEPS.indexOf('calibrate'));navigate('setup');}}/>}
    <aside className="aero-sidebar" aria-label="Navegación principal">
      <div className="sidebar-brand"><span className="sidebar-logo-crop"><img src="/assets/aerotrack-logo.png" alt="" width="50" height="64" className="sidebar-logo-image"/></span><strong>AeroTrack</strong>
        <button className="ghost sidebar-toggle" aria-label={collapsed?'Expandir navegación':'Plegar navegación'} aria-expanded={!collapsed} title={collapsed?'Expandir navegación':'Plegar navegación'} onClick={()=>{setCollapsed(v=>{const next=!v;try{localStorage.setItem('aero.sidebar',next?'collapsed':'open');}catch{/* modo privado */}return next;});}}><Icon name={collapsed?'panelOpen':'panelClose'} size={17}/></button>
      </div>
      <nav className="sidebar-nav">{((session.auth.rol==='administrador'?['overview','map','alerts','replay','businesses','commercial','insights','reports','projects']:['overview','map','alerts','replay','businesses','commercial','insights','reports','projects','setup']) as View[]).map(id=>NAV.find(n=>n.id===id)!).map(n=><button key={n.id} title={n.label} className={(view===n.id||(n.id==='map'&&['lab','dashboard'].includes(view))||(n.id==='setup'&&['cameras','audit','lab'].includes(view)))?'active':''} onClick={()=>navigate(n.id)}><Icon name={n.icon} size={18}/><span>{n.label}</span></button>)}</nav>
      <div className="sidebar-user" title={`${session.auth.usuario||'Sin sesión'}${session.auth.rol?` · ${session.auth.rol}`:''}`}>
        <Icon name="user" size={16}/>
        <span><strong>{session.auth.usuario||'Sin sesión'}</strong><small>{session.auth.rol||'—'}</small></span>
        <button className="ghost logout" title="Cerrar sesión" aria-label="Cerrar sesión" onClick={()=>void session.logout()}><Icon name="logout" size={16}/></button>
      </div>
    </aside>
    <div className="aero-content">
    <header className="aero-header">
      <div className="aero-title"><h1>{config.airport||'Espacio sin nombre'}</h1><p>{['overview','replay'].includes(view)?'Monitoreo de ocupación y flujo':config.floor||'Espacio principal'}</p></div>
      {session.projects.projects.length>0&&<label className="header-project" title={busy?'Finaliza la sesión para cambiar de proyecto':'Proyecto abierto'}>
      <Icon name="layers" size={14}/>
      <select value={session.projects.active||''} disabled={busy||session.busy} onChange={e=>void session.action(async()=>{await session.projectAction('open',{id:e.target.value});setProjectChosen(true);session.setNotice('Proyecto abierto.');})}>
        {session.projects.projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </label>}
      {/* Indicadores del sistema: solo lo que de verdad está medido ahora.
          Sin sesión activa no se muestran cifras de personas ni de cámaras en
          vivo, porque un «0» ahí afirmaría una medición que nadie hizo. */}
      <div className="header-indicators">
        <span className="estado" title={session.connected?'El servidor local responde':'No hay conexión con el servidor local'}><i className={`dot ${session.connected?(current?'green':'blue'):'red'}`}/>{session.connected?(STATUS[state.status]||state.status):'Sin conexión'}</span>
        <span title="Cámaras con señal en vivo de las configuradas en este proyecto"><Icon name="camera" size={15}/> {current?`${activeCameras}/${config.cameras.length}`:`${config.cameras.length}`}</span>
        {current&&<span title="Personas observadas en este instante"><Icon name="people" size={15}/> {observed}</span>}
        {current&&alerts>0&&<span className="aviso" title="Zonas en alerta ahora mismo"><Icon name="alert" size={15}/> {alerts}</span>}
      </div>
      <button className="topbar-notifications" title="Abrir alertas" aria-label="Abrir alertas" onClick={()=>navigate('alerts')}><Icon name="bell" size={18}/>{alerts>0&&<span>{alerts}</span>}</button>
      <div className="topbar-user" title={`${session.auth.usuario||'Sin sesión'} · ${session.auth.rol||'Sin rol'}`}><b>{(session.auth.usuario||'A').slice(0,2).toUpperCase()}</b><span><strong>{session.auth.usuario||'Usuario'}</strong><small>{session.auth.rol||'Sin rol'}</small></span></div>
    </header>
    {['setup','cameras','audit','lab'].includes(view)&&<nav className="product-subnav" aria-label="Herramientas del proyecto">{(['setup','lab','audit'] as View[]).map(id=>NAV.find(n=>n.id===id)!).map(n=><button key={n.id} className={view===n.id?'selected':''} onClick={()=>navigate(n.id)}>{n.id==='setup'?'Configurar proyecto':n.label}</button>)}</nav>}
    <main id="main-content" className="aero-main" key={session.projects.active||'sin-proyecto'}>{['setup','lab','audit'].includes(view)&&<p className="settings-context">{{setup:'Configura únicamente el proyecto abierto: pisos, planos, cámaras, homografía, zonas y reglas.',lab:'Diagnóstico · Verifica la detección y la señal de cada cámara antes de monitorear.',audit:'Auditoría · Consulta las operaciones realizadas en el sistema.'}[view as 'setup'|'lab'|'audit']}</p>}
      <Notifications session={session}/>
      {demo&&<div className="notice warning"><Icon name="lab"/><span>SIMULACIÓN · Datos sintéticos para probar las pantallas. No representan mediciones de un aeropuerto.</span></div>}
      {!['commercial','businesses','overview','setup','audit','reports','replay','lab'].includes(view)&&!ready&&<div className="setup-banner"><div><Icon name="settings" size={21}/><span><strong>Prepara el análisis sobre el plano</strong><small>{stages.filter(s=>s.done).length}/{stages.length} etapas preparadas · {stages.filter(s=>!s.done).map(s=>s.title.toLowerCase()).join(', ')} pendientes</small></span></div><button onClick={()=>{const pending=stages.find(s=>!s.done);setStep(Math.max(0,pending?PROJECT_STEPS.indexOf(pending.step):0));navigate('setup');}}>Continuar configuración <Icon name="arrow" size={15}/></button></div>}
      {['map','dashboard'].includes(view)&&<div className="session-bar"><div className="inline"><i className={`dot ${state.status==='running'?'green':state.status==='error'?'red':'amber'}`}/><strong>{state.session?`Sesión ${state.session}`:'Sin sesión activa'}</strong><span>{config.sourceMode==='live'?'Cámaras en vivo':config.sourceMode==='demo'?'Demostración':'Grabaciones de prueba'}</span>{session.dirty&&<span className="unsaved">Cambios sin guardar</span>}</div><div className="inline"><time>{clock.toLocaleTimeString('es-PE',{timeZone:'America/Lima'})}</time>{busy?<>{state.status==='paused'?<button onClick={()=>void session.action(async()=>{await session.post('resume',{});})}>▶ Reanudar</button>:<button disabled={state.status!=='running'} onClick={()=>void session.action(async()=>{await session.post('pause',{});})}>Ⅱ Pausar</button>}<button className="danger" disabled={session.busy||state.status==='stopping'} onClick={()=>void session.action(async()=>{await session.post('stop',{});})}>Finalizar sesión</button></>:<><button disabled={session.busy||!config.cameras.length} onClick={()=>start(undefined,'demo')}>Ver simulación</button><button className="primary" disabled={session.busy||!session.connected||!config.cameras.length||!ready} onClick={()=>start(undefined,config.sourceMode==='demo'?'demo':'yolo')}>Iniciar {config.cameras.length} cámara{config.cameras.length===1?'':'s'}</button></>}</div></div>
      }
      {visited.includes('replay')&&<div hidden={view!=='replay'}><ReplayWorkspace active={view==='replay'} currentConfig={config}/></div>}{visited.includes('overview')&&<div hidden={view!=='overview'}><MonitoringWorkspace active={view==='overview'} session={session} onReplay={()=>navigate('replay')} onSetup={id=>{if(id)setSelected(id);setStep(2);navigate('setup');}}/></div>}
      {view==='setup'?<SetupFlow session={session} selected={selected} onSelected={setSelected} onNavigate={navigate} step={step} setStep={setStep} startTest={()=>void session.action(async()=>{await session.save();await session.post('camera-preview',{camera:selected,seconds:0});session.setNotice('Imagen disponible para configurar. No se inició un análisis.');})}/>:<>

      {view==='map'&&<><PlanSelector config={config} disabled={busy} onChange={session.setConfig}/>{stats}<section className="aero-panel map-live" ref={mapRef}><PanelHeader title="Plano vivo · posiciones y trayectorias"><span className="pill blue">{config.floor}</span><button title="Pantalla completa" onClick={()=>void mapRef.current?.requestFullscreen().catch(()=>{})}><Icon name="expand" size={15}/></button></PanelHeader><MapCanvas config={config} state={state} connected={session.connected} selectedCamera={selected} onCamera={setSelected} selectedPerson={person?.id} onPerson={setPerson}/></section></>}
      {(view==='cameras'||view==='lab')&&<><div className="page-heading"><div><span className="eyebrow">{view==='lab'?'VALIDACIÓN DE FUENTES':'RED DE CÁMARAS'}</span><h1>{view==='lab'?'Diagnóstico de cámara':'Todas las cámaras, una sesión'}</h1><p>{view==='lab'?'Prueba cada fuente antes de integrarla al sistema.':'Selecciona una cámara para inspeccionar el video y sus IDs temporales.'}</p></div><button disabled={busy} onClick={openCameraSettings}><Icon name="plus"/> Añadir o configurar cámaras</button></div>{view!=='lab'&&<div className="camera-selector-grid">{config.cameras.map(c=><button key={c.id} className={c.id===selected?'selected':''} onClick={()=>setSelected(c.id)}><Icon name="camera" size={25}/><span><strong>{c.name||c.id}</strong><small>{c.id} · {c.location||'Ubicación pendiente'}</small></span><i className={`dot ${state.cameras.find(s=>s.id===c.id)?.status==='live'&&current?'green':'amber'}`}/></button>)}</div>}<section className="aero-panel camera-full"><PanelHeader title={camera?.name||'Fuente de video'}><span className="pill muted">Sin identificación personal</span></PanelHeader>{cameraPanel(view==='lab')}</section>{view==='lab'&&<div className="lab-guidance"><div><Icon name="check"/><h3>Fuente y rendimiento</h3><p>Comprueba señal, resolución y tiempo de procesamiento. Los FPS de la fuente no son los FPS de inferencia.</p></div><div><Icon name="pin"/><h3>Calidad de calibración</h3><p>Usa referencias distribuidas en el suelo y comprueba el error con puntos adicionales.</p><button onClick={()=>{setStep(PROJECT_STEPS.indexOf('calibrate'));navigate('setup');}}>Calibrar esta cámara</button></div><div><Icon name="people"/><h3>Estabilidad del tracking</h3><p>Revisa cambios de ID y fragmentaciones contra anotaciones. La continuidad aparente no demuestra precisión.</p></div></div>}</>}
      {view==='projects'&&<section className="project-home"><div className="page-heading"><div><span className="eyebrow">ESPACIOS DE TRABAJO</span><h1>Proyectos</h1><p>Cada proyecto es un espacio distinto con su propio plano, sus cámaras, su calibración y sus incidentes. Nada se comparte entre ellos, así que dos no pueden llamarse igual.{session.auth.rol!=='operador'&&' Puedes crear y eliminar proyectos; cargar el plano y las cámaras le corresponde a un operador.'}</p></div></div><ProjectsPanel session={session} onConfigure={session.auth.rol==='operador'?()=>navigate('setup'):undefined} onCreated={session.auth.rol==='operador'?()=>navigate('setup'):undefined}/></section>}
      {view==='businesses'&&<BusinessesPanel session={session}/>}
      {view==='commercial'&&<CommercialPanel session={session}/>}
      {view==='insights'&&<InsightsPanel session={session}/>}
      {view==='dashboard'&&<BusinessDashboard config={config} state={state} demo={demo}/>}
      {view==='alerts'&&<SecurityAlerts session={session} onOpenCamera={id=>{setSelected(id);navigate('cameras');}}/>}
      {view==='reports'&&<SessionReports session={session}/>}
      {view==='audit'&&<><div className="page-heading"><div><span className="eyebrow">TRAZABILIDAD OPERATIVA</span><h1>Auditoría del sistema</h1><p>Acciones del operador durante la ejecución del servidor. No contiene identidades reales.</p></div></div><section className="aero-panel audit-panel"><table><thead><tr><th>Fecha y hora</th><th>Acción</th><th>Detalle</th></tr></thead><tbody>{state.audit?.map((event,i)=><tr key={i}><td>{new Date(event.at).toLocaleString('es-PE',{timeZone:'America/Lima'})}</td><td>{event.action}</td><td>{event.detail}</td></tr>)}</tbody></table>{!state.audit?.length&&<p className="empty-text">Las acciones aparecerán al guardar la configuración o iniciar una sesión.</p>}</section></>}
      </>}
      {person&&current&&<aside className="person-drawer"><button className="close-drawer" title="Cerrar recorrido" onClick={()=>setPerson(null)}>×</button><span className="eyebrow">RECORRIDO ANÓNIMO</span><h2>{person.id}</h2><span className={`pill ${person.association==='uncertain'?'warn':'blue'}`}>{labelAssociation(person)}</span><dl><div><dt>Cámara actual</dt><dd>{person.camera}</dd></div><div><dt>Posición observada</dt><dd>{person.point?.map(v=>v.toFixed(2)).join(', ')||'Sin calibración'}</dd></div><div><dt>Próxima cámara probable</dt><dd>{person.nextCamera||'Sin evidencia suficiente'}</dd></div></dl><p>La dirección futura es una estimación. No confirma la identidad en una zona sin cobertura.</p><div className="journey">{state.events.filter(e=>e.id===person.id).slice().reverse().map((e,i)=><div key={i}><span>{formatTime(e.t)}</span><b>{e.from} → {e.to}</b><small>Asociación estimada</small></div>)}</div><button onClick={()=>{setSelected(person.camera);navigate('cameras');setPerson(null);}}>Ver cámara <Icon name="arrow" size={14}/></button></aside>}
    </main><footer className="aero-footer"><span>AeroTrack · Monitoreo y analítica</span><span><Icon name="shield" size={13}/> Análisis de ocupación y flujo</span><span>{session.connected?'● Servidor local conectado':'○ Servidor desconectado'}</span></footer>
    </div>
  </div>;
}
