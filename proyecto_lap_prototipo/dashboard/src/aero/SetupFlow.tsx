import { useState } from 'react';
import type { Session } from './useSession';
import type { Config, SourceMode, View } from './types';
import { freshCamera, isActive, isStream } from './types';
import Icon from './Icon';
import { CameraEditor, CameraPanel } from './CameraPanel';
import CameraRegionEditor from './CameraRegionEditor';
import PreviewControls from './PreviewControls';
import PlanWorkspace from './PlanWorkspace';
import PlanSelector from './PlanSelector';
import ProjectHome from './ProjectHome';
import ZoneWorkspace from './ZoneWorkspace';

export function readiness(config: Config, session: Session) {
  const cameras=config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom'));
  const mode=config.sourceMode||'recordings';
  const tests=cameras.filter(c=>session.state.sourceChecks?.[c.id]?.valid&&session.state.sourceChecks[c.id].source===c.source);
  const calibrated=cameras.filter(c=>c.pairs.length>=4).length;
  return [
    { title:'Proyecto', subtitle:'Espacio y modo de trabajo', done:!!config.airport?.trim()&&!!config.floor?.trim(), icon:'grid' },
    { title:'Cámaras', subtitle:`${cameras.length} cámaras · ${tests.length} probadas`, done:cameras.length>0&&cameras.every(c=>mode==='demo'||(c.source!==''&&isStream(c.source)===(mode==='live'))), icon:'camera' },
    { title:'Espacio y calibración', subtitle:!config.mapConfigured?'Falta el plano':mode==='demo'?'Espacio definido · sin calibración':`Espacio definido · ${calibrated}/${cameras.length} calibradas`, done:!!config.mapConfigured&&(mode==='demo'||(cameras.length>0&&cameras.every(c=>c.pairs.length>=4))), icon:'map' },
    { title:'Validación', subtitle:mode==='demo'?'Preparar demostración':'Validar antes de operar', done:mode==='demo'||(cameras.length>0&&tests.length===cameras.length&&(cameras.length===1||config.clocksVerified)), icon:'check' },
  ];
}

type StepId = 'project' | 'plan' | 'source' | 'test' | 'place' | 'calibrate' | 'zones' | 'review';
const PROJECT_STEPS: StepId[] = ['project','plan','source','test','place','calibrate','zones','review'];
const CAMERA_STEPS: StepId[] = ['source','test','place','calibrate','review'];
const LABELS: Record<StepId,{title:string;hint:string}> = {
  project:{title:'Proyecto',hint:'Nombre del espacio y tipo de fuente'},
  plan:{title:'Plano',hint:'Importa un plano o dibújalo con figuras'},
  source:{title:'Conexión',hint:'Conecta la cámara y comprueba que responde'},
  test:{title:'Prueba',hint:'Revisa la imagen y marca la zona útil'},
  place:{title:'Ubicación',hint:'Coloca la cámara sobre el plano'},
  calibrate:{title:'Calibración',hint:'Relaciona el suelo del video con el plano'},
  zones:{title:'Zonas y alertas',hint:'Sectores a medir y umbrales de aglomeración'},
  review:{title:'Revisión',hint:'Comprueba todo y abre el monitoreo'},
};

function AlertRules({ session }: { session: Session }) {
  const config=session.config!;
  const busy=isActive(session.state.status);
  const update=(patch:Partial<Config>)=>session.setConfig({...config,...patch});
  return <section className="aero-panel rules-panel">
    <div className="panel-heading"><div><h2>Cuándo avisar de una aglomeración</h2></div></div>
    <div className="rules-form">
      <label>Radio ({config.unit==='meters'?'metros':'unidades relativas'})<input type="number" min="0.01" step="0.1" value={config.radius} onChange={e=>update({radius:+e.target.value})}/></label>
      <label>Personas mínimas<input type="number" min="2" step="1" value={config.minPeople} onChange={e=>update({minPeople:+e.target.value})}/></label>
      <label>Permanencia (segundos)<input type="number" min="0" value={config.dwell} onChange={e=>update({dwell:+e.target.value})}/></label>
    </div>
    <p className="subtle">Una fila y una aglomeración pueden parecerse geométricamente. Define límites apropiados al uso de cada zona.</p>
    {!!config.zones.length&&<div className="zone-rules">
      <div className="panel-heading"><div><h2>Reglas por zona</h2></div></div>
      {config.zones.filter(z=>!['wall','door'].includes(z.kind||'')).map(z=>{
        const index=config.zones.indexOf(z);const rule=z.rule||{enabled:false,minPeople:config.minPeople,dwell:config.dwell};
        const patch=(value:Partial<typeof rule>)=>update({zones:config.zones.map((v,i)=>i===index?{...v,rule:{...rule,...value}}:v)});
        return <div className="zone-rule" key={index}>
          <label className="check"><input type="checkbox" disabled={busy} checked={rule.enabled} onChange={e=>patch({enabled:e.target.checked})}/>{z.name}</label>
          <label>Personas<input type="number" disabled={busy} min="2" value={rule.minPeople} onChange={e=>patch({minPeople:+e.target.value})}/></label>
          <label>Segundos<input type="number" disabled={busy} min="0" value={rule.dwell} onChange={e=>patch({dwell:+e.target.value})}/></label>
        </div>;
      })}
    </div>}
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

  const done:Record<StepId,boolean>={
    project:!!config.airport?.trim()&&!!config.floor?.trim(),
    plan:!!config.mapConfigured,
    source:!!camera&&camera.source!==''&&isStream(camera.source)===((config.sourceMode||'recordings')==='live'),
    test:tested,
    place:!!camera&&(camera.x!==0||camera.y!==0),
    calibrate:!!camera&&camera.pairs.length>=4,
    zones:config.zones.length>0,
    review:stages.every(s=>s.done),
  };

  if(screen==='home')return <section className="setup-flow">
    <ProjectHome session={session} onNewProject={()=>openWizard('project')} onAddCamera={()=>openWizard('camera')}/>
  </section>;

  return <section className="setup-flow">
    <div className="wizard-top">
      <button className="ghost" onClick={()=>setScreen('home')}><Icon name="arrow" size={15} rotation={180}/> Proyectos</button>
      <div><h1>{mode==='camera'?'Añadir una cámara':config.airport||'Proyecto nuevo'}</h1><p>Paso {index+1} de {steps.length} · {LABELS[id].hint}</p></div>
      <span className={`pill ${session.saveError?'warn':'muted'}`}>{session.saveError?'No se pudo guardar':session.saving?'Guardando…':'Guardado'}</span>
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
        <PlanSelector config={config} onChange={session.setConfig} disabled={disabled}/>
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
        <p className="wizard-help">Mira la cámara en movimiento para comprobar el encuadre, la luz y el retardo. Si es una grabación puedes pausarla y moverte por el video; si es una cámara en vivo verás la imagen tal como llega. Después marca la zona útil: el área donde sí quieres detectar personas, dejando fuera espejos, vidrios y otros niveles.</p>
        {camera?<>
          <section className="aero-panel camera-full">
            <div className="panel-heading"><div><h2>{camera.name||camera.id}</h2></div><span className={`pill ${tested?'good':'warn'}`}>{tested?'Fuente comprobada':'Sin comprobar'}</span></div>
            <PreviewControls session={session} camera={camera}/>
            <CameraPanel session={session} selected={selected} onSelected={onSelected} detector="yolo" onDetector={()=>{}} weights="" onWeights={()=>{}} laboratory onStart={()=>{}} onConfigure={()=>setStep(steps.indexOf('source'))}/>
          </section>
          <section className="aero-panel">
            <div className="panel-heading"><div><h2>Zona útil de la imagen</h2></div></div>
            <CameraRegionEditor key={camera.id} camera={camera} config={config} session={session} onChange={session.setConfig}/>
          </section>
          <section className="aero-panel">
            <div className="panel-heading"><div><h2>Equipaje sin custodia</h2></div></div>
            <div className="rules-form">
              <label className="check"><input type="checkbox" disabled={disabled} checked={!!camera.luggageWatch} onChange={e=>update({cameras:config.cameras.map(c=>c.id===camera.id?{...c,luggageWatch:e.target.checked}:c)})}/> Avisar si un bulto queda quieto en esta cámara</label>
              <label>Tiempo antes de avisar (segundos)<input type="number" min="10" max="7200" step="10" disabled={disabled||!camera.luggageWatch} value={camera.luggageDwell??90} onChange={e=>update({cameras:config.cameras.map(c=>c.id===camera.id?{...c,luggageDwell:+e.target.value}:c)})}/></label>
              <label>Cada cuánto revisar (segundos)<input type="number" min="2" max="60" step="1" disabled={disabled||!camera.luggageWatch} value={camera.luggageInterval??4} onChange={e=>update({cameras:config.cameras.map(c=>c.id===camera.id?{...c,luggageInterval:+e.target.value}:c)})}/></label>
            </div>
            <p className="subtle">Detecta maletas, mochilas y bolsos con el mismo modelo del seguimiento, revisándolos cada pocos segundos para no quitarle rendimiento al conteo de personas. El aviso es para que alguien vaya a mirar, no una conclusión de seguridad: también salta con el equipaje que un pasajero deja a su lado mientras espera.</p>
          </section>
        </>:<p className="empty-text">Agrega una cámara en el paso anterior.</p>}
      </div>}

      {id==='place'&&<div className="wizard-step-block">
        <p className="wizard-help">Arrastra la cámara hasta el punto del plano donde está instalada y gírala hacia donde apunta. La cobertura dibujada es orientativa, la precisión real viene de la calibración del paso siguiente.</p>
        <PlanWorkspace embedded section="cameras" session={session} selected={selected} onSelected={onSelected} startTest={startTest}/>
      </div>}

      {id==='calibrate'&&<div className="wizard-step-block">
        <PlanWorkspace embedded section="calibration" session={session} selected={selected} onSelected={onSelected} startTest={startTest}/>
      </div>}

      {id==='zones'&&<div className="wizard-step-block">
        <p className="wizard-help">Las zonas son los sectores del plano que quieres medir por separado: salas, pasillos, áreas comerciales. Las reglas definen cuándo una concentración se considera aglomeración.</p>
        <ZoneWorkspace session={session}/>
        <AlertRules session={session}/>
      </div>}

      {id==='review'&&<div className="review-step">
        <div><h2>Comprueba el proyecto antes de iniciar</h2>
          <p className="subtle">Las verificaciones cambian con tus cámaras, fuentes y calibraciones. Una casilla completada no sustituye la validación de precisión.</p>
          <div className="readiness-list">{stages.slice(0,3).map(s=><div key={s.title}>
            <span className={`check-circle ${s.done?'good':''}`}><Icon name={s.done?'check':'clock'} size={16}/></span>
            <span><strong>{s.title}</strong><small>{s.subtitle}</small></span><b>{s.done?'Preparado':'Pendiente'}</b></div>)}</div>
          {config.cameras.length>1&&<>
            <label className="check"><input type="checkbox" disabled={disabled} checked={config.clocksVerified} onChange={e=>update({clocksVerified:e.target.checked})}/> Verifiqué el mismo tiempo de contenido en las cámaras y ajusté sus desfases.</label>
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
          <button className="primary" disabled={disabled||session.busy||!stages.every(s=>s.done)} onClick={()=>void session.action(async()=>{await session.save({...config,setupComplete:true});onNavigate('overview');})}>Guardar y abrir monitoreo</button>
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
