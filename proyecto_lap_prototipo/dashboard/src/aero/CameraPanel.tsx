import { useEffect, useRef, useState } from 'react';
import type { Camera, Config, Point, SessionState } from './types';
import { COLORS, isActive, isStream, labelAssociation, STATUS } from './types';
import type { Session } from './useSession';
import Icon from './Icon';
import CameraRegionEditor from './CameraRegionEditor';

export function CameraVideo({ camera, state, connected, onPoint, mode, pending, zonePoints, pairPoints, onPairChange }: { camera?: Camera; state: SessionState; connected: boolean; onPoint?: (p: Point) => void; mode?: 'calibration' | 'zone'; pending?: Point | null; zonePoints?: Point[]; pairPoints?: Point[];onPairChange?:(index:number,p:Point)=>void }) {
  const pairDrag=useRef<number|null>(null);
  const [tick, setTick] = useState(0);
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ w: number; h: number; x: number; y: number } | null>(null);
  const status = state.cameras.find(c => c.id === camera?.id);
  useEffect(()=>{ setFailed(false); setTick(Date.now()); },[camera?.id,state.session]);
  const previewing=state.preview?.camera===camera?.id&&!!state.preview?.playing;
  const nextFrame=useRef<number>();
  // En vista en vivo se pide la siguiente imagen cuando termina de cargar la
  // anterior: a intervalo fijo se encolarían peticiones y se sumaría retraso.
  useEffect(()=>{if(mode||!connected)return;
    if(previewing){setFailed(false);setTick(Date.now());return;}
    if(state.status!=='running')return;
    const id=setInterval(()=>{if(!document.hidden){setTick(Date.now());setFailed(false);}},400);
    return()=>clearInterval(id);},[state.status,mode,connected,previewing]);
  useEffect(()=>()=>window.clearTimeout(nextFrame.current),[]);
  const chainFrame=()=>{if(!previewing)return;window.clearTimeout(nextFrame.current);nextFrame.current=window.setTimeout(()=>{if(!document.hidden)setTick(Date.now());},40);};
  const available = state.mode !== 'demo' && status && ['ready','live','paused','stopped','ended'].includes(status.status);
  const current = connected && state.status==='running' && status?.status==='live';
  const ratio = status?.width && status?.height ? status.width / status.height : null;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const recompute = () => {
      const cw = el.clientWidth, ch = el.clientHeight;
      if (!cw || !ch) return;
      const ar = ratio ?? cw / ch;
      let w = cw, h = cw / ar;
      if (h > ch) { h = ch; w = ch * ar; }
      setBox({ w, h, x: (cw - w) / 2, y: (ch - h) / 2 });
    };
    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(el);
    document.addEventListener('fullscreenchange', recompute);
    return () => { ro.disconnect(); document.removeEventListener('fullscreenchange', recompute); };
  }, [ratio]);
  const frameStyle = box ? { left: box.x, top: box.y, width: box.w, height: box.h } : { inset: 0 };
  const drawnZone = zonePoints && zonePoints.length > 0 ? zonePoints : (mode !== 'zone' ? camera?.detectionZone : undefined);
  return <div className="camera-video" ref={ref}>
    <div className="video-frame" style={frameStyle}>
      {available && !failed ? <img src={`/api/frame?camera=${encodeURIComponent(camera?.id||'')}&v=${tick}`} alt={`Seguimiento de ${camera?.name||camera?.id}`} onError={()=>setFailed(true)} onLoad={chainFrame} className={mode?'calibration-cursor':''} onClick={e=>{if(!mode||!onPoint)return;const r=e.currentTarget.getBoundingClientRect();if(!r.width||!r.height)return;const clamp=(v:number)=>Math.min(1,Math.max(0,v));onPoint([clamp((e.clientX-r.left)/r.width),clamp((e.clientY-r.top)/r.height)]);}}/> : <div className="video-empty"><Icon name="camera" size={38}/><strong>{!camera?'Añade una cámara':state.mode==='demo'?'Simulación de nodos':status?.status==='error'?'Cámara sin señal':state.status==='starting'?'Conectando con la fuente':'Vista de cámara'}</strong><span>{status?.error || (state.mode==='demo'?'No contiene grabación de personas. Prueba una fuente para ver video.':'Al iniciar una prueba verás el video procesado y los IDs temporales.')}</span></div>}
      {pending && mode==='calibration' && <span className="calibration-marker" style={{left:`${pending[0]*100}%`,top:`${pending[1]*100}%`}}/>}
      {drawnZone && drawnZone.length>0 && <svg className="zone-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
        {drawnZone.length>1 && <polygon points={drawnZone.map(p=>`${p[0]*100},${p[1]*100}`).join(' ')}/>}
        {drawnZone.map((p,i)=><circle key={i} cx={p[0]*100} cy={p[1]*100} r="0.9"/>)}
      </svg>}
      {pairPoints && pairPoints.length>0 && <svg className="pair-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" onPointerMove={e=>{if(pairDrag.current===null||!onPairChange)return;const r=e.currentTarget.getBoundingClientRect();onPairChange(pairDrag.current,[Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]);}} onPointerUp={()=>{pairDrag.current=null;}} onPointerCancel={()=>{pairDrag.current=null;}}>
        {pairPoints.map((p,i)=><circle key={i} cx={p[0]*100} cy={p[1]*100} r="1.3" fill={COLORS[i%COLORS.length]} style={onPairChange?{pointerEvents:'all',cursor:'grab'}:undefined} onPointerDown={e=>{if(!onPairChange)return;e.preventDefault();e.stopPropagation();pairDrag.current=i;e.currentTarget.ownerSVGElement?.setPointerCapture(e.pointerId);}}/>)}
      </svg>}
    </div>
    <div className="video-top"><span>{camera?.id||'SIN CÁMARA'}{camera?.location?` · ${camera.location}`:''}</span><span className={`pill ${current?'good':'muted'}`}>{current?'● Procesando':state.status==='paused'?'Ⅱ Pausado':available?'Imagen retenida':'Sin señal'}</span></div>
    <div className="video-bottom"><span><Icon name="shield" size={13}/> Solo operador · servidor local</span><span>{status?.width?`${status.width} × ${status.height}`:'—'} · {status?.fps?`${status.fps.toFixed(1)} FPS fuente`:'FPS no disponible'}</span><button title="Pantalla completa" onClick={()=>void ref.current?.requestFullscreen().catch(()=>{})}><Icon name="expand" size={15}/></button></div>
  </div>;
}

export function CameraEditor({ config, camera, onChange, session }: { config: Config; camera?: Camera; onChange: (c: Config) => void; session: Session }) {
  const fileRef=useRef<HTMLInputElement>(null);
  if(!camera)return <p className="empty-text">Añade una cámara para configurar su fuente.</p>;
  const disabled=isActive(session.state.status);
  function update(patch: Partial<Camera>) { onChange({...config,cameras:config.cameras.map(c=>c.id===camera!.id?{...c,...patch}:c)}); }
  return <div className="camera-editor"><div className="form-grid"><label>Plano asociado<select disabled={disabled} value={camera.planId||'custom'} onChange={e=>{const pid=e.target.value;const plan=pid===(config.planId||'custom')?config:config.plans?.[pid];if(plan)update({planId:pid,x:plan.width/2,y:plan.height/2,pairs:[],coveragePolygon:undefined});}}>{(!config.planId||config.planId==='custom'||config.plans?.custom)&&<option value="custom">Espacio de pruebas</option>}{Object.keys(config.plans||{}).filter(p=>p!=='custom').map(p=><option key={p} value={p}>{config.plans![p].floor}</option>)}{config.planId&&config.planId!=='custom'&&!config.plans?.[config.planId]&&<option value={config.planId}>{config.floor}</option>}</select></label><label>Nombre visible en el mapa<input disabled={disabled} value={camera.name||camera.id} maxLength={80} onChange={e=>update({name:e.target.value})}/></label><label>Ubicación<input disabled={disabled} value={camera.location||''} placeholder="Terminal A / Piso 1" onChange={e=>update({location:e.target.value})}/></label><label>Orientación<select disabled={disabled} value={camera.type||'tilted'} onChange={e=>update({type:e.target.value as Camera['type']})}><option value="fixed">Frontal</option><option value="overhead">Cenital</option><option value="tilted">Inclinada</option></select></label><label>Fuente<select disabled={disabled} value={typeof camera.source==='number'?'usb':isStream(camera.source)?'network':'file'} onChange={e=>update({source:e.target.value==='usb'?0:e.target.value==='network'?'rtsp://':'',pairs:[],detectionZone:undefined,countLines:[],analysisZones:[]})}><option value="file">Video grabado</option><option value="usb">Cámara USB</option><option value="network">RTSP / Cámara IP</option></select></label></div>
    <label>{typeof camera.source==='number'?'Índice USB (0 = primera cámara)':'Ruta del video o URL de cámara'}<div className="input-action"><input disabled={disabled} value={camera.source} placeholder="Selecciona un archivo o escribe una ruta local" onChange={e=>update({source:typeof camera.source==='number'?Number(e.target.value):e.target.value,pairs:[],detectionZone:undefined,countLines:[],analysisZones:[]})}/>{!isStream(camera.source)&&<button disabled={disabled||session.busy} title="Subir video" onClick={()=>fileRef.current?.click()}><Icon name="upload" size={16}/></button>}</div></label>
    <p className="subtle">Subir archivo guarda una copia en el proyecto. Escribir una ruta local permite leer el original sin copiarlo; ese archivo debe permanecer disponible en el servidor.</p><input ref={fileRef} hidden type="file" accept="video/*,.mp4,.avi,.mov,.mkv" onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void session.action(async()=>{const result=await session.post(`upload?name=${encodeURIComponent(file.name)}`,file,true);update({source:result.path,pairs:[],detectionZone:undefined,countLines:[],analysisZones:[]});session.setNotice('Video cargado. Guarda la cámara para iniciar la prueba.');});}}/>
    <section className="camera-map-options"><h3>Ocupación y alertas</h3><p>El monitoreo incluye ocupación, recorridos y cruces. Activa el conteo especializado cuando las personas estén muy juntas o parcialmente ocultas.</p><label className="check"><input type="checkbox" disabled={disabled} checked={!!camera.denseCounting} onChange={e=>update({denseCounting:e.target.checked})}/> Complementar con conteo de multitudes</label><div className="form-grid"><label>Alerta desde (personas)<input disabled={disabled} type="number" min="1" max="1000" value={camera.crowdThreshold??10} onChange={e=>update({crowdThreshold:+e.target.value})}/></label><label>Concentración sostenida (s)<input disabled={disabled} type="number" min="0" max="3600" value={camera.crowdDwell??3} onChange={e=>update({crowdDwell:+e.target.value})}/></label>{camera.denseCounting&&<label>Intervalo de conteo especializado (s)<input disabled={disabled} type="number" min="2" max="60" value={camera.denseInterval??5} onChange={e=>update({denseInterval:+e.target.value})}/></label>}</div><small>Ambas estimaciones se muestran por separado: no se suman. El conteo especializado se actualiza cuando termina cada muestra.</small></section>
    <CameraRegionEditor key={camera.id+String(camera.source)} camera={camera} config={config} session={session} onChange={onChange}/>
    <details className="camera-map-options"><summary>Ubicación y cobertura sobre el plano · opcional para empezar</summary><div className="form-grid"><label>Desfase al inicio (segundos)<input disabled={disabled||isStream(camera.source)} type="number" min="0" step="0.1" value={camera.offset} onChange={e=>update({offset:+e.target.value})}/></label><label>Cobertura orientativa en el suelo<select disabled={disabled} value={camera.coverageShape??'rectangle'} onChange={e=>update({coverageShape:e.target.value as Camera['coverageShape']})}><option value="cone">Sector de visión (no es la forma del video)</option><option value="rectangle">Rectángulo (pasillo/corredor)</option><option value="free">Libre (dibujar en el plano)</option></select></label>{camera.coverageShape!=='free'&&<label>Dirección de visión (°)<input type="number" min="0" max="360" value={Math.round(camera.heading??90)} onChange={e=>update({heading:+e.target.value})}/></label>}{camera.coverageShape==='rectangle'?<label>Ancho del rectángulo ({config.unit==='meters'?'m':'u'})<input type="number" min="0.2" step="0.1" value={camera.coverageWidth??2} onChange={e=>update({coverageWidth:+e.target.value})}/></label>:camera.coverageShape!=='free'&&<label>Ángulo de visión (°)<input disabled={disabled} type="number" min="5" max="170" value={camera.fov??60} onChange={e=>update({fov:+e.target.value})}/></label>}{camera.coverageShape!=='free'&&<label>Alcance orientativo ({config.unit==='meters'?'m':'u'})<input disabled={disabled} type="number" min="0.1" step="0.5" value={Number((camera.range??3).toFixed(2))} onChange={e=>update({range:+e.target.value})}/></label>}<label>Altura de montaje (m)<input disabled={disabled} type="number" min="0" step="0.1" value={camera.height??3} onChange={e=>update({height:+e.target.value})}/></label><label>Inclinación (°)<input disabled={disabled} type="number" min="0" max="90" value={camera.tilt??45} onChange={e=>update({tilt:+e.target.value})}/></label></div>
    {camera.coverageShape==='free'&&<p className="subtle">Ve al paso "Plano", selecciona esta cámara y usa el botón "Forma libre" de la barra de herramientas para dibujar su contorno punto por punto.</p>}
    <label className="check"><input disabled={disabled} type="checkbox" checked={!!camera.illustrative} onChange={e=>update({illustrative:e.target.checked})}/> Ubicación ilustrativa de prueba</label><small>Desactiva esta marca solo después de establecer referencias reales del mismo suelo. Una ubicación ilustrativa no valida identidades entre cámaras.</small><fieldset disabled={disabled}><legend>Cámaras vecinas del mismo nivel</legend>{config.cameras.filter(c=>c.id!==camera.id&&(c.planId||'custom')===(camera.planId||'custom')).map(c=><label className="check" key={c.id}><input type="checkbox" checked={camera.links.includes(c.id)} onChange={e=>update({links:e.target.checked?[...camera.links,c.id]:camera.links.filter(id=>id!==c.id)})}/>{c.id} · {c.name||'Cámara'}</label>)}{config.cameras.length<2&&<p className="subtle">Agrega otra cámara para definir transiciones.</p>}</fieldset>
    <p className="subtle">La cobertura dibujada es orientativa. La zona útil delimita qué parte de la imagen se analiza. Para ubicar personas necesitas calibrar puntos del suelo. El índice USB pertenece al equipo que ejecuta el servidor.</p>
    </details>
  </div>;
}

export function CameraPanel({ session, selected, onSelected, detector, onDetector, weights, onWeights, laboratory, onStart, onConfigure, onPoint, pending, mode }: {
  session: Session; selected: string; onSelected:(s:string)=>void; detector:string;onDetector:(s:string)=>void;weights:string;onWeights:(s:string)=>void;
  laboratory?:boolean;onStart:()=>void;onConfigure:()=>void;onPoint?:(p:Point)=>void;pending?:Point|null;mode?:'calibration'|'zone';
}) {
  const config=session.config!;
  const camera=config.cameras.find(c=>c.id===selected);
  const status=session.state.cameras.find(c=>c.id===selected);
  const people=session.connected&&['running','paused'].includes(session.state.status)?session.state.people.filter(p=>p.camera===selected):[];
  return <div className={`camera-workspace ${laboratory?'laboratory':''}`}><div className="camera-controls"><label>Seleccionar cámara<select value={selected} onChange={e=>onSelected(e.target.value)}>{config.cameras.map(c=><option key={c.id} value={c.id}>{c.name||c.location||c.id}</option>)}</select></label><dl className="technical-list"><div><dt>Estado</dt><dd className={status?.status==='live'?'text-green':''}>{status?STATUS[status.status]||status.status:'Sin probar'}</dd></div><div><dt>Resolución</dt><dd>{status?.width?`${status.width} × ${status.height}`:'—'}</dd></div><div><dt>FPS de fuente</dt><dd>{status?.fps?.toFixed(1)||'—'}</dd></div><div><dt>Procesamiento</dt><dd>{status?.processingMs?`${status.processingMs} ms`:session.state.processingMs?`${session.state.processingMs} ms/ciclo`:'—'}</dd></div><div><dt>Calibración</dt><dd>{camera?.pairs.length&&camera.pairs.length>=4?'Referencias guardadas':'Pendiente'}</dd></div><div><dt>Sincronización</dt><dd>{config.clocksVerified?'Declarada verificada':'Por verificar'}</dd></div></dl>
    {laboratory&&<><button disabled={isActive(session.state.status)||session.busy||!camera||!session.connected} onClick={()=>void session.action(async()=>{await session.save();await session.post('camera-preview',{camera:camera!.id,seconds:0});session.setNotice('Imagen inicial disponible.');})}>Ver imagen inicial</button><button className="primary" disabled={session.busy||!camera||!session.connected} onClick={()=>{if(isActive(session.state.status))void session.action(async()=>{await session.post('stop',{});});else onStart();}}><Icon name="play" size={15}/> {isActive(session.state.status)?'Detener prueba':'Iniciar prueba de seguimiento'}</button><div className="small-note"><Icon name="camera" size={15}/><div><strong>Seguimiento por cámara</strong><p>Observa personas, IDs y recorridos sobre el video. Puedes comenzar sin calibrar el plano.</p></div></div><details className="tracking-advanced"><summary>Configuración avanzada</summary><label>Detector<select disabled={isActive(session.state.status)} value={detector} onChange={e=>onDetector(e.target.value)}><option value="yolo">YOLO11n + ByteTrack</option><option value="hog">HOG · referencia comparativa</option></select></label>{detector==='yolo'&&<label>Modelo alternativo (opcional)<input disabled={isActive(session.state.status)} value={weights} onChange={e=>onWeights(e.target.value)} placeholder="Modelo preinstalado por defecto"/></label>}<p className="subtle">Para personas parcialmente visibles en multitudes utiliza Conteo y aglomeraciones.</p></details></>}

    <button onClick={onConfigure}><Icon name="settings" size={14}/> Configurar cámara</button>
  </div><div className="camera-feed"><CameraVideo camera={camera} state={session.state} connected={session.connected} onPoint={onPoint} pending={pending} mode={mode}/><div className="feed-metrics"><span>{['running','paused'].includes(session.state.status)?'Personas en esta imagen':'Personas en la última imagen'}: <b>{['running','paused'].includes(session.state.status)?people.length:status?.lastCount??'—'}</b></span><span>Tiempo de video: <b>{(status?.sourceTime??session.state.t).toFixed(1)} s</b></span></div>{!laboratory&&<div className="tracking-chips">{people.slice(0,8).map(p=><span key={p.id} title={labelAssociation(p)} className={p.association==='uncertain'?'uncertain':''}>{p.id}{p.association==='estimated'?' ~':p.association==='uncertain'?' ?':''}</span>)}{!people.length&&<span>Esperando observaciones de esta cámara</span>}</div>}</div></div>;
}
