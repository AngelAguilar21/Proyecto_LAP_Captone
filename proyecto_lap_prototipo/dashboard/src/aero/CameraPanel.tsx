import { useEffect, useRef, useState } from 'react';
import type { Camera, Config, Point, SessionState } from './types';
import { COLORS, isActive, isStream, labelAssociation, STATUS } from './types';
import type { Session } from './useSession';
import Icon from './Icon';

export function CameraVideo({ camera, state, connected, onPoint, mode, pending, zonePoints, pairPoints, onPairChange }: { camera?: Camera; state: SessionState; connected: boolean; onPoint?: (p: Point) => void; mode?: 'calibration' | 'zone'; pending?: Point | null; zonePoints?: Point[]; pairPoints?: Point[];onPairChange?:(index:number,p:Point)=>void }) {
  const pairDrag=useRef<number|null>(null);
  const [tick, setTick] = useState(0);
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ w: number; h: number; x: number; y: number } | null>(null);
  const status = state.cameras.find(c => c.id === camera?.id);
  useEffect(()=>{ setFailed(false); setTick(Date.now()); },[camera?.id,state.session]);
  const previewSelected=state.preview?.camera===camera?.id&&!state.preview?.error;
  const previewing=previewSelected&&!!state.preview?.playing;
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
  const available = state.mode !== 'demo' && (previewSelected || !!status && ['ready','live','paused','stopped','ended'].includes(status.status));
  // Entre pulsar "Iniciar" y que llegue la primera imagen, el servidor abre la
  // fuente y carga el detector; eso puede tardar unos segundos y hasta ese
  // momento no hay ningún dato nuevo de la cámara, así que un cuadro anterior
  // se seguiría mostrando como si nada estuviera pasando. No hay forma honesta
  // de medir cuánto falta (depende de la cámara y del detector), así que se
  // muestra un aviso de progreso indeterminado en vez de inventar un porcentaje.
  const starting = connected && state.status==='starting';
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
      {starting && <div className="video-starting" role="status"><i className="loader"/><strong>Iniciando la prueba…</strong><span>Conectando con la fuente{camera?.location?` (${camera.location})`:''} y preparando el detector. La primera vez que se usa un modelo tarda más porque hay que cargarlo; las siguientes veces es más rápido.</span><div className="indeterminate-bar"><i/></div></div>}
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
    <div className="video-top"><span>{camera?.id||'SIN CÁMARA'}{camera?.location?` · ${camera.location}`:''}</span><span className={`pill ${current?'good':'muted'}`}>{starting?'Iniciando…':current?'● Procesando':state.status==='paused'?'Ⅱ Pausado':available?'Imagen retenida':'Sin señal'}</span></div>
    <div className="video-bottom"><span><Icon name="shield" size={13}/> Solo operador · servidor local</span><span>{status?.width?`${status.width} × ${status.height}`:'—'} · {status?.fps?`${status.fps.toFixed(1)} FPS fuente`:'FPS no disponible'}</span><button title="Pantalla completa" onClick={()=>void ref.current?.requestFullscreen().catch(()=>{})}><Icon name="expand" size={15}/></button></div>
  </div>;
}

export function CameraEditor({ config, camera, onChange, session }: { config: Config; camera?: Camera; onChange: (c: Config) => void; session: Session }) {
  const fileRef=useRef<HTMLInputElement>(null);
  if(!camera)return <p className="empty-text">Añade una cámara para configurar su fuente.</p>;
  const disabled=isActive(session.state.status);
  const cameraId=camera.id;
  function update(patch: Partial<Camera>) { onChange({...config,cameras:config.cameras.map(c=>c.id===cameraId?{...c,...patch}:c)}); }
  const reset={pairs:[],detectionZone:undefined,countLines:[],analysisZones:[]};
  return <div className="camera-editor basic-camera-editor">
    <div className="form-grid">
      <label>Nombre de la cámara<input disabled={disabled} value={camera.name||camera.id} maxLength={80} placeholder="Ej. Pabellón A" onChange={e=>update({name:e.target.value})}/></label>
      <label>Tipo de fuente<select disabled={disabled} value={typeof camera.source==='number'?'usb':isStream(camera.source)?'network':'file'} onChange={e=>update({source:e.target.value==='usb'?0:e.target.value==='network'?'rtsp://':'',...reset})}><option value="file">Video grabado</option><option value="usb">Cámara USB</option><option value="network">Cámara IP / RTSP</option></select></label>
    </div>
      <label>{typeof camera.source==='number'?'Número de cámara USB':'Archivo o URL de la cámara'}<div className="input-action"><input disabled={disabled} value={camera.source} placeholder={isStream(camera.source)?'rtsp://… o https://youtube.com/watch?v=…':'Selecciona un video'} onChange={e=>update({source:typeof camera.source==='number'?Number(e.target.value):e.target.value,...reset})}/>{!isStream(camera.source)&&<button disabled={disabled||session.busy} title="Seleccionar video" onClick={()=>fileRef.current?.click()}><Icon name="upload" size={16}/></button>}</div></label>
    <input ref={fileRef} hidden type="file" accept="video/*,.mp4,.avi,.mov,.mkv" onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void session.action(async()=>{const result=await session.post(`upload?name=${encodeURIComponent(file.name)}`,file,true);update({source:result.path,...reset});session.setNotice('Video cargado. Continúa con la prueba de la fuente.');});}}/>
    <p className="subtle">{isStream(camera.source)?'La fuente debe estar disponible desde el equipo que ejecuta AeroTrack. Las URLs de YouTube se resuelven como transmisión en vivo.':'El video se usa como fuente de prueba y calibración.'}</p>
  </div>;
}
export function CameraPanel({ session, selected, onSelected, laboratory, onStart, onConfigure, onPoint, pending, mode }: {
  session: Session; selected: string; onSelected:(s:string)=>void;
  laboratory?:boolean;onStart:()=>void;onConfigure:()=>void;onPoint?:(p:Point)=>void;pending?:Point|null;mode?:'calibration'|'zone';
}) {
  const config=session.config!;
  const camera=config.cameras.find(c=>c.id===selected);
  const status=session.state.cameras.find(c=>c.id===selected);
  const people=session.connected&&['running','paused'].includes(session.state.status)?session.state.people.filter(p=>p.camera===selected):[];
  const starting=session.connected&&session.state.status==='starting';
  return <div className={`camera-workspace ${laboratory?'laboratory':''}`}><div className="camera-controls"><label>Seleccionar cámara<select value={selected} onChange={e=>onSelected(e.target.value)}>{config.cameras.map(c=><option key={c.id} value={c.id}>{c.name||c.location||c.id}</option>)}</select></label><dl className="technical-list"><div><dt>Estado</dt><dd className={status?.status==='live'?'text-green':''}>{status?STATUS[status.status]||status.status:'Sin probar'}</dd></div><div><dt>Resolución</dt><dd>{status?.width?`${status.width} × ${status.height}`:'—'}</dd></div><div><dt>FPS de fuente</dt><dd>{status?.fps?.toFixed(1)||'—'}</dd></div><div><dt>Procesamiento</dt><dd>{status?.processingMs?`${status.processingMs} ms`:session.state.processingMs?`${session.state.processingMs} ms/ciclo`:'—'}</dd></div><div><dt>Calibración</dt><dd>{camera?.pairs.length&&camera.pairs.length>=4?'Referencias guardadas':'Pendiente'}</dd></div><div><dt>Sincronización</dt><dd>{config.clocksVerified?'Declarada verificada':'Por verificar'}</dd></div></dl>
    {laboratory&&<><button disabled={isActive(session.state.status)||session.busy||!camera||!session.connected} onClick={()=>void session.action(async()=>{await session.save();await session.post('camera-preview',{camera:camera!.id,seconds:0});session.setNotice('Imagen inicial disponible.');})}>Ver imagen inicial</button><button className="primary" disabled={session.busy||!camera||!session.connected} onClick={()=>{if(isActive(session.state.status))void session.action(async()=>{await session.post('stop',{});});else onStart();}}>{starting?<i className="loader small"/>:<Icon name="play" size={15}/>} {starting?'Iniciando…':isActive(session.state.status)?'Detener prueba':'Probar esta fuente'}</button><div className="small-note"><Icon name="camera" size={15}/><div><strong>Modelo operativo</strong><p>Detecta personas, mantiene sus IDs temporales y proyecta sus posiciones sobre el plano mediante la homografía.</p></div></div></>}

    <button onClick={onConfigure}><Icon name="settings" size={14}/> Configurar cámara</button>
  </div><div className="camera-feed"><CameraVideo camera={camera} state={session.state} connected={session.connected} onPoint={onPoint} pending={pending} mode={mode}/><div className="feed-metrics"><span>{['running','paused'].includes(session.state.status)?'Personas en esta imagen':'Personas en la última imagen'}: <b>{['running','paused'].includes(session.state.status)?people.length:status?.lastCount??'—'}</b></span><span>Tiempo de video: <b>{(status?.sourceTime??session.state.t).toFixed(1)} s</b></span></div>{!laboratory&&<div className="tracking-chips">{people.slice(0,8).map(p=><span key={p.id} title={labelAssociation(p)} className={p.association==='uncertain'?'uncertain':''}>{p.id}{p.association==='estimated'?' ~':p.association==='uncertain'?' ?':''}</span>)}{!people.length&&<span>Esperando observaciones de esta cámara</span>}</div>}</div></div>;
}
