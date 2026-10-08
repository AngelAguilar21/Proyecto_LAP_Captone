import { useState } from 'react';
import type { Session } from './useSession';
import type { Config, SourceMode, View } from './types';
import { freshCamera, isActive, isStream } from './types';
import Icon from './Icon';
import { CameraEditor, CameraPanel } from './CameraPanel';
import CameraRegionEditor from './CameraRegionEditor';
import CameraAccessEditor from './CameraAccessEditor';
import PreviewControls from './PreviewControls';
import PlanWorkspace from './PlanWorkspace';
import PlanSelector from './PlanSelector';
import ZoneWorkspace from './ZoneWorkspace';
import { calibrationMessage, isCalibrationError } from './calibration';
import { geometryReady, projectReadiness } from './setupReadiness';
import type { SetupStepId } from './setupReadiness';
import { saveStatusLabel } from './sessionSave';

export type { SetupStepId } from './setupReadiness';
export const PROJECT_STEPS: SetupStepId[] = ['project','plan','source','test','calibrate','zones','review'];
const CAMERA_STEPS: SetupStepId[] = ['source','test','calibrate','review'];

export function readiness(config: Config, session: Session) {
  const cameras=config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom'));
  const mode=config.sourceMode||'recordings';
  const tests=cameras.filter(c=>session.state.sourceChecks?.[c.id]?.valid&&session.state.sourceChecks[c.id].source===c.source);
  const calibrated=cameras.filter(c=>c.pairs.length>=4).length;
  const useful=cameras.filter(c=>!!c.detectionZone).length;
  const businesses=config.zones.filter(z=>z.kind==='commercial').length;
  const commercialReady=config.commercialContext?.hasBusinesses===false||(config.commercialContext?.hasBusinesses===true&&businesses>0);
  return [
    { step:'project' as SetupStepId, title:'Proyecto', subtitle:'Espacio y modo de trabajo', done:!!config.airport?.trim()&&!!config.floor?.trim(), icon:'grid' },
    { step:'source' as SetupStepId, title:'Cámaras', subtitle:`${cameras.length} cámaras · ${tests.length} probadas`, done:cameras.length>0&&cameras.every(c=>mode==='demo'||(c.source!==''&&isStream(c.source)===(mode==='live'))), icon:'camera' },
    { step:'calibrate' as SetupStepId, title:'Homografía y cámaras relacionadas', subtitle:!config.mapConfigured?'Falta el plano':mode==='demo'?'Plano preparado':`${useful}/${cameras.length} zonas útiles · ${calibrated}/${cameras.length} con referencias del suelo (opcional)${cameras.length>1?` · ${config.clocksVerified?'cámaras sincronizadas':'falta marcar la misma persona en dos cámaras'}`:''}`, done:!!config.mapConfigured&&(mode==='demo'||(cameras.length>0&&cameras.every(c=>!!c.detectionZone)&&(cameras.length===1||!!config.clocksVerified))), icon:'map' },
    { step:'zones' as SetupStepId, title:'Contexto comercial', subtitle:config.commercialContext?.hasBusinesses===false?'Piso sin negocios existentes':businesses?`${businesses} negocios registrados`:'Indica si existen negocios', done:commercialReady&&config.radius>0&&config.minPeople>=2&&config.dwell>=0, icon:'layers' },
    { step:'review' as SetupStepId, title:'Validación', subtitle:mode==='demo'?'Preparar demostración':'Validar antes de operar', done:mode==='demo'||(cameras.length>0&&tests.length===cameras.length&&(cameras.length===1||config.clocksVerified)), icon:'check' },
  ];
}

const LABELS: Record<SetupStepId,{title:string;hint:string}> = {
  project:{title:'Proyecto',hint:'Nombre del espacio y tipo de fuente'},
  plan:{title:'Plano',hint:'Importa un plano o dibújalo con figuras'},
  source:{title:'Conexión',hint:'Conecta la cámara y comprueba que responde'},
  test:{title:'Zona útil',hint:'Excluye espejos y deja solo el área real'},
  calibrate:{title:'Homografía y cámaras relacionadas',hint:'Puntos del suelo y, con 2 o más cámaras, la misma persona marcada en cada par'},
  zones:{title:'Contexto y oportunidades',hint:'Registra negocios; AeroTrack propondrá las nuevas zonas'},
  review:{title:'Revisión',hint:'Comprueba todo y abre el monitoreo'},
};

function AlertRules({ session }: { session: Session }) {
  const config=session.config!;
  const update=(patch:Partial<Config>)=>session.setConfig({...config,...patch});
  return <section className="aero-panel rules-panel">
    <div className="panel-heading"><div><h2>Alerta general</h2></div></div>
    <div className="rules-form">
      <label>Avisar desde<input type="number" min="2" step="1" value={config.minPeople} onChange={e=>update({minPeople:+e.target.value})}/><span>personas próximas</span></label>
      <label>Durante al menos<input type="number" min="0" value={config.dwell} onChange={e=>update({dwell:+e.target.value})}/><span>segundos</span></label>
    </div>
    <p className="subtle">Se aplica a todo el plano. Los ajustes técnicos conservan valores seguros por defecto.</p>
  </section>;
}

export default function SetupFlow({ session, selected, onSelected, onNavigate, step, setStep, startTest }: { session:Session;selected:string;onSelected:(s:string)=>void;onNavigate:(v:View)=>void;step:number;setStep:(v:number)=>void;startTest:()=>void }) {
  const config=session.config!;
  const [screen,setScreen]=useState<'home'|'wizard'>('home');
  const [mode,setMode]=useState<'project'|'camera'>('project');
  const steps=mode==='camera'?CAMERA_STEPS:PROJECT_STEPS;
  const index=Math.min(Math.max(0,step),steps.length-1);
  const id=steps[index];
  const visibleCameras=config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom'));
  const camera=config.cameras.find(c=>c.id===selected);
  const disabled=isActive(session.state.status);
  const stages=readiness(config,session);
  const update=(patch:Partial<Config>)=>session.setConfig({...config,...patch});
  const tested=!!camera&&session.state.sourceChecks?.[camera.id]?.source===camera.source;

  function addCamera() {
    const next=freshCamera();
    next.id=Array.from({length:26},(_,i)=>String.fromCharCode(65+i)).find(id=>!config.cameras.some(c=>c.id===id))||next.id;
    next.name=`Cámara ${next.id}`;next.planId=config.planId||'custom';
    next.x=config.width/2;next.y=config.height/2;
    if(config.sourceMode==='live')next.source=0;
    update({cameras:[...config.cameras,next],setupComplete:false});
    onSelected(next.id);
  }
  function openWizard(next:'project'|'camera') {
    setMode(next);
    if(next==='camera'&&!visibleCameras.length)addCamera();
    setStep(0);setScreen('wizard');
  }
  function startCameraTest() {
    if(!camera)return;
    void session.action(async()=>{
      await session.save();
      await session.post('start',{detector:'yolo',camera:camera.id,requireUnified:false,testRun:true,inferenceSize:640});
      session.setNotice('Prueba de fuente iniciada con YOLO (640). Comprueba señal y seguimiento; no ejecuta densidad P2PNet.');
    });
  }
  function finishSetup() {
    void session.action(async()=>{
      try {
        await session.save({...config,setupComplete:true});
      } catch (error) {
        const message=error instanceof Error?error.message:String(error);
        if(isCalibrationError(message))setStep(steps.indexOf('calibrate'));
        throw error;
      }
      onNavigate('overview');
    });
  }

  const done:Record<SetupStepId,boolean>={
    project:!!config.airport?.trim()&&!!config.floor?.trim(),
    plan:!!config.mapConfigured,
    source:!!camera&&camera.source!==''&&isStream(camera.source)===((config.sourceMode||'recordings')==='live'),
    test:tested&&!!camera&&!!camera.detectionZone,
    calibrate:!!camera,   // los puntos del suelo son opcionales; con 2 o más cámaras se pide la misma persona en cada par
    zones:(config.commercialContext?.hasBusinesses===false||(config.commercialContext?.hasBusinesses===true&&config.zones.some(z=>z.kind==='commercial')))&&config.radius>0&&config.minPeople>=2&&config.dwell>=0,
    review:stages.every(s=>s.done),
  };

  if(screen==='home')return <section className="setup-flow config-home">
    <header className="config-home-head"><div><h1>Configurar proyecto</h1><p>Ajusta el proyecto abierto. Para crear, abrir o eliminar espacios de trabajo usa la sección Proyectos.</p></div><span className="pill blue">{config.airport||'Proyecto sin nombre'}</span></header>
    <div className="config-home-grid">
      <button className="config-home-primary" disabled={disabled} onClick={()=>openWizard('project')}><Icon name="map" size={28}/><span><strong>Espacio completo</strong><small>Pisos, planos, fuentes, homografía, relaciones entre cámaras, zonas y validación.</small></span></button>
      <button className="config-home-primary" disabled={disabled} onClick={()=>openWizard('camera')}><Icon name="camera" size={28}/><span><strong>Añadir una cámara</strong><small>Conecta una fuente nueva al piso activo y calibra su posición.</small></span></button>
    </div>
    <section className="config-scope" aria-label="Contenido del proyecto abierto"><div><Icon name="layers"/><strong>{Math.max(1,Object.keys(config.plans||{}).length)} pisos</strong><small>Planos independientes por nivel</small></div><div><Icon name="camera"/><strong>{config.cameras.length} cámaras</strong><small>Fuentes asignadas por piso</small></div><div><Icon name="pin"/><strong>{config.zones.length} zonas</strong><small>Áreas y reglas operativas</small></div><div><Icon name="check"/><strong>{config.setupComplete&&stages.every(s=>s.done)?'Validado':'En configuración'}</strong><small>Estado del proyecto abierto</small></div></section>
  </section>;

  return <section className="setup-flow">
    <div className="wizard-top">
      <button className="ghost" onClick={()=>setScreen('home')}><Icon name="arrow" size={15} rotation={180}/> Configuración</button>
      <div><h1>{mode==='camera'?'Añadir una cámara':config.airport||'Proyecto nuevo'}</h1><p>Paso {index+1} de {steps.length} · {LABELS[id].hint}</p></div>
      <span className={`pill ${session.saveError?'warn':'muted'}`} role="status">{saveStatusLabel(session.saveError,session.saving,session.dirty)}</span>
    </div>

    <nav className="wizard-steps" aria-label="Pasos de configuración">
      {steps.map((s,i)=><button key={s} className={i===index?'current':done[s]?'done':''} onClick={()=>setStep(i)}>
        <span className="wizard-number">{done[s]&&i!==index?<Icon name="check" size={13}/>:i+1}</span>
        <span><strong>{LABELS[s].title}</strong></span>
      </button>)}
    </nav>

    {session.saveError&&<div className="notice warning"><Icon name="alert"/><span>{session.saveError}</span></div>}
    {disabled&&<div className="notice warning"><Icon name="alert"/>Hay una sesión activa. Finalízala para editar la configuración.</div>}

    <div className="wizard-body">
      {id==='project'&&<div className="project-step">
        <div className="step-intro"><span className="number-tile">1</span><h2>Datos del espacio</h2><p>Identifica el espacio y elige de dónde vienen las imágenes.</p>
          <div className="privacy-block"><Icon name="shield"/><div><strong>Privacidad</strong><p>Análisis de presencia y recorridos sin reconocimiento facial.</p></div></div></div>
        <div className="project-form"><div className="form-grid">
          <label>Aeropuerto o proyecto<input disabled={disabled} value={config.airport||''} placeholder="Nombre del aeropuerto" onChange={e=>update({airport:e.target.value})}/></label>
          <label>Terminal y nivel<input disabled={disabled} value={config.floor||''} placeholder="Terminal A · Nivel 1" onChange={e=>update({floor:e.target.value})}/></label>
        </div>
        <h3>Tipo de fuente</h3>
        <div className="mode-cards">{([{value:'recordings',title:'Videos grabados',icon:'report',text:'Analiza grabaciones y consulta sus resultados por periodo.'},{value:'live',title:'Cámaras en vivo',icon:'camera',text:'Conecta una o varias cámaras USB, RTSP o IP, incluido un celular por WiFi.'},{value:'demo',title:'Demostración',icon:'lab',text:'Datos de ejemplo para explorar el sistema. No representan mediciones reales.'}] as {value:SourceMode;title:string;icon:string;text:string}[]).filter(m=>m.value!=='demo'||config.sourceMode==='demo').map(m=>
          <button key={m.value} disabled={disabled} className={(config.sourceMode||'recordings')===m.value?'selected':''} onClick={()=>update({sourceMode:m.value,setupComplete:false})}>
            <Icon name={m.icon} size={25}/><strong>{m.title}</strong><span>{m.text}</span><i>{(config.sourceMode||'recordings')===m.value?'Seleccionado':'Elegir'}</i></button>)}
        </div></div>
      </div>}

      {id==='plan'&&<div className="wizard-step-block">
        <PlanSelector config={config} onChange={session.setConfig} disabled={disabled} manage/>
        <p className="wizard-help">Elige un plano del LAP, importa una imagen o PDF, o dibuja el espacio con las figuras de la barra de herramientas.</p>
        <PlanWorkspace embedded section="area" session={session} selected={selected} onSelected={onSelected} startTest={startTest}/>
      </div>}

      {id==='source'&&<div className="source-step">
        <aside className="source-list">
          <div className="section-label"><h3>Cámaras del proyecto</h3><span>{visibleCameras.length}</span></div>
          {visibleCameras.map(c=><button key={c.id} className={selected===c.id?'selected':''} onClick={()=>onSelected(c.id)}>
            <Icon name="camera"/><span><strong>{c.name||c.id}</strong><small>{c.id} · {c.source===''?'Sin fuente':isStream(c.source)?'En vivo':'Grabación'}</small></span>
            <i className={`dot ${session.state.sourceChecks?.[c.id]?.source===c.source?'green':'amber'}`}/></button>)}
          <button disabled={disabled||config.cameras.length>=32} onClick={addCamera}><Icon name="plus"/> Añadir otra cámara</button>
        </aside>
        <div className="source-editor">{camera?<>
          <div className="section-label"><h2>{camera.name||camera.id}</h2>
            <button disabled={disabled} className="danger ghost" onClick={()=>{const rest=config.cameras.filter(c=>c.id!==selected).map(c=>({...c,links:c.links.filter(id=>id!==selected)}));update({cameras:rest});onSelected(rest[0]?.id||'');}}><Icon name="trash" size={15}/> Quitar</button></div>
          <CameraEditor config={config} camera={camera} onChange={session.setConfig} session={session}/>
          <div className="inline end"><button disabled={session.busy||disabled||camera.source===''} className="primary" onClick={startTest}><Icon name="lab"/> Probar esta fuente</button></div>
        </>:<div className="empty-state"><Icon name="camera" size={36}/><h3>Comienza con tu primera cámara</h3><p>Agrega una fuente de video o una conexión en vivo.</p><button className="primary" onClick={addCamera}>Añadir cámara</button></div>}</div>
      </div>}

      {id==='test'&&<div className="wizard-step-block">
        <p className="wizard-help">Prueba la fuente y delimita solo el suelo real que deseas analizar. Deja fuera espejos, vidrios, pantallas y otros niveles.</p>
        {camera?<>
          <section className="aero-panel camera-full">
            <div className="panel-heading"><div><h2>{camera.name||camera.id}</h2></div><span className={`pill ${tested?'good':'warn'}`}>{tested?'Fuente comprobada':'Sin comprobar'}</span></div>
            <PreviewControls session={session} camera={camera}/>
            <CameraPanel session={session} selected={selected} onSelected={onSelected} laboratory onStart={startCameraTest} onConfigure={()=>setStep(steps.indexOf('source'))}/>
          </section>
          <section className="aero-panel">
            <div className="panel-heading"><div><h2>Zona útil de la imagen</h2></div></div>
            <CameraRegionEditor key={camera.id} camera={camera} config={config} session={session} onChange={session.setConfig}/>
            <CameraAccessEditor key={`access-${camera.id}`} camera={camera} config={config} session={session} onChange={session.setConfig}/>
          </section>
        </>:<p className="empty-text">Agrega una cámara en el paso anterior.</p>}
      </div>}

      {id==='calibrate'&&<div className="wizard-step-block">
        <p className="wizard-help">A: marca puntos visibles del suelo y su posición en el plano (4 o más; 6 a 8 repartidos es mejor) para ubicar a las personas. B: con varias cámaras, marca los pies de la misma persona en cada par de cámaras que se ven o se suceden; con 4 parejas quedan relacionadas y sincronizadas.</p>
        <PlanWorkspace embedded section="calibration" session={session} selected={selected} onSelected={onSelected} startTest={startTest}/>
      </div>}

      {id==='zones'&&<div className="wizard-step-block">
        <p className="wizard-help">Indica si existen negocios y registra únicamente sus medidas. Las nuevas zonas de oportunidad serán propuestas por AeroTrack después de analizar el flujo.</p>
        <ZoneWorkspace session={session}/>
        <AlertRules session={session}/>
      </div>}

      {id==='review'&&<div className="review-step">
        <div><h2>Comprueba el proyecto antes de iniciar</h2>
          <p className="subtle">Las verificaciones cambian con tus cámaras, fuentes y calibraciones. Una casilla completada no sustituye la validación de precisión.</p>
          <div className="readiness-list">{stages.map(s=><div key={s.title}>
            <span className={`check-circle ${s.done?'good':''}`}><Icon name={s.done?'check':'clock'} size={16}/></span>
            <span><strong>{s.title}</strong><small>{s.subtitle}</small></span><b>{s.done?'Preparado':'Pendiente'}</b></div>)}</div>
          {config.cameras.length>1&&<>
            {(config.sourceMode||'recordings')==='live'
              ? <label className="check"><input type="checkbox" disabled={disabled} checked={config.clocksVerified} onChange={e=>update({clocksVerified:e.target.checked})}/> Las cámaras en vivo comparten la misma hora (relojes sincronizados).</label>
              : <p className={`notice compact ${config.clocksVerified?'':'warning'}`}>{config.clocksVerified
                  ? 'Cámaras sincronizadas con la misma persona marcada en ambas.'
                  : 'Falta la sincronización entre cámaras. Marca a la misma persona en dos cámaras (Homografía, parte B): con 4 o más parejas el sistema calcula y corrige el desfase de tiempo.'}</p>}
            <p className="subtle">Si no está verificado, el sistema mantiene IDs locales y no asocia personas entre cámaras. La llegada de dos streams al mismo equipo no demuestra sincronización.</p>
          </>}
        </div>
        <div className="review-summary"><Icon name="shield" size={30}/><h3>{config.airport}</h3><p>{config.floor}</p>
          <dl>
            <div><dt>Cámaras</dt><dd>{config.cameras.length}</dd></div>
            <div><dt>Zonas dibujadas</dt><dd>{config.zones.length}</dd></div>
            <div><dt>Fuentes probadas</dt><dd>{config.cameras.filter(c=>session.state.sourceChecks?.[c.id]?.source===c.source).length}</dd></div>
            <div><dt>Escala</dt><dd>{config.unit==='meters'?'Metros':'Relativa'}</dd></div>
          </dl>
          <button className="primary" disabled={disabled||session.busy||!stages.every(s=>s.done)} onClick={finishSetup}>Guardar y abrir monitoreo</button>
          <button onClick={()=>onNavigate('lab')}>Continuar las pruebas en laboratorio</button>
        </div>
      </div>}
    </div>

    <footer className="wizard-footer">
      <button disabled={index===0} onClick={()=>setStep(index-1)}><Icon name="arrow" size={15} rotation={180}/> Atrás</button>
      <span className="wizard-progress">{steps.filter(s=>done[s]).length} de {steps.length} pasos listos</span>
      {index<steps.length-1
        ? <button className="primary" onClick={()=>setStep(index+1)}>Siguiente: {LABELS[steps[index+1]].title} <Icon name="arrow" size={15}/></button>
        : <button onClick={()=>setScreen('home')}>Volver a proyectos</button>}
    </footer>
  </section>;
}
