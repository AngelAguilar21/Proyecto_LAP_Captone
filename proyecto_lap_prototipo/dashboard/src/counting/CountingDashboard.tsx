import { useEffect, useRef, useState } from 'react';
import AnalysisSummary, { momentLabel } from './AnalysisSummary';
import VideoCanvas, { COLORS } from './VideoCanvas';
import { active, STATUS, timeLabel, wholeZone } from './types';
import type { Config, Point, Ready, State } from './types';
import './counting.css';
import ReplayWorkspace from '../aero/ReplayWorkspace';

const EMPTY: State = {status:'idle',t:0,samples:0,points:[],series:[]};

type Integration = { embedded?: boolean; reportMode?: boolean; reportSession?: string; cameras?: {id:string;name:string;source:string;detectionZone?:Point[]}[]; trackingActive?: boolean; onState?: (state:State)=>void; onReports?: ()=>void; onCameras?: ()=>void };
export default function CountingDashboard({embedded=false,reportMode=false,reportSession,cameras=[],trackingActive=false,onState,onReports,onCameras}:Integration) {
  const [tab,setTab] = useState<'setup'|'analysis'|'history'|'replay'>('setup');
  const [config,setConfig] = useState<Config|null>(null);
  const [ready,setReady] = useState<Ready|null>(null);
  const [files,setFiles] = useState<{name:string;path:string}[]>([]);
  const [state,setState] = useState<State>(EMPTY);
  const reportRef=useRef<HTMLDivElement>(null);
  const [reportSelection,setReportSelection]=useState<State|null>(null);
  useEffect(()=>{if(reportSelection)reportRef.current?.scrollIntoView({behavior:'smooth',block:'start'});},[reportSelection]);
  const [history,setHistory] = useState<State[]>([]);
  const [connected,setConnected] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [preview,setPreview] = useState<{source:string;width:number;height:number;duration:number|null;live:boolean}|null>(null);
  const [revision,setRevision] = useState(0);
  const [previewTime,setPreviewTime] = useState(0);
  const [drawing,setDrawing] = useState(false);
  const [draft,setDraft] = useState<Point[]>([]);
  const [zoneName,setZoneName] = useState('');
  const [heat,setHeat] = useState<'points'|'instant'|'heat'>('points');
  useEffect(()=>{if(reportSession)void read(`report?session=${encodeURIComponent(reportSession)}`).then(setReportSelection).catch(e=>setError(String(e)));},[reportSession]);
  const token = useRef('');
  const input = useRef<HTMLInputElement>(null);
  const sessionRef = useRef('');
  const locked = active(state.status);
  useEffect(()=>{onState?.(state);},[state,onState]);
  useEffect(()=>{if(embedded)setTab(reportMode?'history':'setup');},[embedded,reportMode]);

  async function read(path:string) {
    const r=await fetch(`/api/counting/${path}`,{signal:AbortSignal.timeout(10000)});
    if(!r.ok) throw new Error('No se pudo conectar con el servidor de conteo.');
    return r.json();
  }
  async function load() {
    const data=await read('config'); token.current=data.token;setReady(data.readiness);setFiles(data.files);
    setConfig(current=>current||{...data.config,...(!data.config.source&&data.files.length?{source:data.files[0].path,name:data.files[0].name}:{})});
  }
  useEffect(()=>{
    let alive=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{
      try {
        if(!token.current) await load();
        const next:State=await read('state');
        if(!alive)return;
        setState(next);setConnected(true);
        if(active(next.status)&&!sessionRef.current){if(next.config)setConfig(next.config);}
        sessionRef.current=next.session||'';
      } catch {if(alive)setConnected(false);}
      if(alive)timer=setTimeout(poll,900);
    };
    void poll();return()=>{alive=false;clearTimeout(timer);};
  },[]);
  useEffect(()=>{if(tab==='history')void read('history').then(setHistory).catch(e=>setError(String(e)));},[tab,state.status]);

  async function post(path:string, body:unknown) {
    const send=()=>fetch(`/api/counting/${path}`,{method:'POST',headers:{'Content-Type':'application/json','X-LAP-Token':token.current},body:JSON.stringify(body),signal:AbortSignal.timeout(60000)});
    let r=await send();
    if(r.status===403){await load();r=await send();}
    const data=await r.json();if(!r.ok)throw new Error(data.error||'No se pudo completar la operación.');return data;
  }
  async function action(fn:()=>Promise<void>) {setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  function changeSource(source:string,name:string) {
    if(!config)return;
    const camera=cameras.find(c=>c.source===source),zone=wholeZone();
    if(camera?.detectionZone){zone.points=camera.detectionZone;zone.name='Zona útil de la cámara';}
    setConfig({...config,source,name,recordedAt:undefined,zones:[zone]});setPreview(null);setDraft([]);setDrawing(false);setPreviewTime(0);
    setNotice('Fuente seleccionada. Las zonas se reinician porque pertenecen al encuadre de cada video.');
  }
  async function upload(file:File) {
    await action(async()=>{
      if(file.size>1024**3)throw new Error('El límite de carga es 1 GB. Para archivos mayores utiliza una ruta local.');
      const r=await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'X-LAP-Token':token.current},body:file,signal:AbortSignal.timeout(180000)});
      const result=await r.json();if(!r.ok)throw new Error(result.error);
      setFiles(f=>[...f,{path:result.path,name:file.name}]);changeSource(result.path,file.name);
    });
  }
  async function getPreview(){if(config)await action(async()=>{const r=await post('preview',{source:config.source,seconds:previewTime});setPreview({...r,source:config.source});setRevision(v=>v+1);});}
  async function start(){if(config)await action(async()=>{await post('start',config);setState({...EMPTY,status:'starting'});setTab('analysis');setNotice('Preparando el análisis. Los resultados aparecerán automáticamente.');});}
  function addZone(){
    if(!config||draft.length<3)return;
    const z={id:crypto.randomUUID(),name:zoneName.trim()||`Zona ${config.zones.length+1}`,points:draft,threshold:10,dwell:5};
    setConfig({...config,zones:[...config.zones.filter(z=>z.id!=='full'),z]});setDraft([]);setDrawing(false);setZoneName('');
  }
  async function download(sid:string,format:string){await action(async()=>{
    const r=await fetch(`/api/counting/report?session=${encodeURIComponent(sid)}&format=${format}`);
    if(!r.ok){const d=await r.json();throw new Error(d.error);}
    const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=`aerotrack-conteo-${sid}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
  });}

  const availableFiles=[...cameras.filter(c=>c.source).map(c=>({name:c.name,path:c.source})),...files.filter(f=>!cameras.some(c=>c.source===f.path))];
  const grid=heat==='points'?undefined:state[heat];
  const zones=state.config?.zones||config?.zones||[];
  return <div className={`count-app ${embedded?'count-embedded':''} ${tab==='analysis'?'count-results-page':''}`}>
    {!embedded&&<aside className="count-sidebar"><a className="count-brand" href="/?view=counting"><span className="count-brand-mark">A</span><span>AeroTrack<small>ANALÍTICA DE AFLUENCIA</small></span></a><div className="count-sidebar-label">ESPACIO DE TRABAJO</div>
      <nav>{([['setup','01','Preparar video'],['analysis','02','Análisis de ocupación'],['history','03','Sesiones y reportes']] as const).map(([id,n,label])=><button key={id} className={tab===id?'selected':''} onClick={()=>setTab(id)}><span>{n}</span>{label}</button>)}</nav>
      <div className="count-side-note"><span className="count-tag">MÓDULO DE CONTEO</span><h3>Entiende dónde se concentra la gente.</h3><p>Personas por zona y tiempo de permanencia de la concentración, sin asignar identidades.</p></div>
      <div className="count-sidebar-bottom"><a href="/?view=overview">Abrir módulo de tracking ↗</a><small>Prototipo académico · LAP</small></div>
    </aside>}
    <main className="count-main">{!embedded&&<header className="count-topbar"><span>Monitoreo / <strong>Conteo de multitudes</strong></span><span className={`count-connection ${connected?'online':''}`}><i/>{connected?'Servidor local conectado':'Sin conexión al servidor'}</span></header>}
      <div className="count-content">{embedded&&!reportMode&&<nav className="count-workflow" aria-label="Etapas de conteo"><button className={tab==='setup'?'selected':''} onClick={()=>setTab('setup')}>1 · Preparar análisis</button><button className={tab==='analysis'?'selected':''} onClick={()=>setTab('analysis')}>2 · Resultados y mapas</button><button className={tab==='replay'?'selected':''} onClick={()=>setTab('replay')}>Reproducir y comparar</button><button onClick={onReports}>Historial y reportes ↗</button><button onClick={onCameras}>Configurar cámaras ↗</button></nav>}{trackingActive&&<div className="count-notice">Hay tracking activo. Finaliza esa sesión antes de iniciar conteo.</div>}{tab!=='replay'&&<div className="count-page-title"><div><p className="count-eyebrow">CONCENTRACIÓN · ZONAS · TIEMPO</p><h1>{tab==='setup'?'Nuevo análisis de concentración':tab==='analysis'?'Resultados de concentración':'Historial de análisis'}</h1><p>{tab==='setup'?'Selecciona una fuente, delimita zonas y establece sus límites de ocupación.':tab==='analysis'?'Consulta dónde, cuándo y durante cuánto tiempo se concentraron las personas.':'Consulta los resultados guardados por fuente y periodo.'}</p></div></div>}
      {!connected&&<div className="count-notice error" role="alert">Conexión interrumpida. Los resultados se actualizarán cuando el servicio vuelva a estar disponible.</div>}
      {(error||state.error)&&<div className="count-notice error" role="alert">{error||state.error}<button onClick={()=>setError('')} aria-label="Cerrar aviso">×</button></div>}
      {notice&&(!notice.startsWith('Preparando el análisis')||state.status==='starting')&&<div className="count-notice" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Cerrar aviso">×</button></div>}
      {!config?<div className="count-card count-loading">Esperando configuración del servidor…</div>:<>
      {tab==='replay'&&<ReplayWorkspace module="counting"/>}{tab==='setup'&&<>
        <div className="count-steps"><span><b>1</b> Selecciona el video</span><span><b>2</b> Delimita tus zonas</span><span><b>3</b> Define reglas y analiza</span></div>
        {locked&&<div className="count-notice">Hay un análisis activo. Detén la sesión para cambiar su configuración.<button onClick={()=>setTab('analysis')}>Ver análisis →</button></div>}
        {ready&&!ready.ready&&<div className="count-notice error">El servicio de análisis no está disponible. Contacta al administrador.</div>}
        <div className="count-setup-grid"><section className="count-card count-source"><div className="count-card-title"><span className="count-step-number">01</span><div><h2>Fuente de video</h2><p>Cámaras y grabaciones disponibles para analizar.</p></div></div>
          <button className="count-upload" disabled={locked||busy||!connected} onClick={()=>input.current?.click()}><span>↑</span><strong>{busy?'Preparando…':'Cargar un video'}</strong><small>MP4, MOV, AVI, MKV o WebM · hasta 1 GB</small></button>
          <input hidden ref={input} type="file" accept="video/*,.mkv,.avi" onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)void upload(f);}}/>
          <label>Fuente de análisis<select disabled={locked||busy} value={config.source} onChange={e=>{const f=availableFiles.find(f=>f.path===e.target.value);if(f)changeSource(f.path,f.name);}}><option value="">Selecciona un video</option>{availableFiles.map(f=><option key={f.path} value={f.path}>{f.name}</option>)}</select></label>
          <label>Nombre del análisis<input maxLength={120} disabled={locked||busy} value={config.name} onChange={e=>setConfig({...config,name:e.target.value})}/></label>
          <label>Inicio de la grabación (opcional)<input type="datetime-local" step="1" disabled={locked||busy||/^(rtsp|https?|rtmp):/i.test(config.source)} value={config.recordedAt?new Date(new Date(config.recordedAt).getTime()-new Date(config.recordedAt).getTimezoneOffset()*60000).toISOString().slice(0,19):''} onChange={e=>setConfig({...config,recordedAt:e.target.value?new Date(e.target.value).toISOString():undefined})}/><small>Hora local del equipo. Sin esta fecha, los eventos se muestran como minutos y segundos del video.</small></label>
          <details><summary>Ruta local o conexión de cámara</summary><p>La fuente se abre desde el equipo del servidor. Para una cámara de LAP se necesita una URL autorizada y acceso a su red.</p><label>Ruta o URL RTSP<input disabled={locked||busy} value={config.source} onChange={e=>changeSource(e.target.value,config.name)} placeholder="Ruta local o rtsp://…"/></label></details>
          <div className="count-preview-controls"><label>Imagen en segundo<input type="number" min={0} max={86400} disabled={locked||busy} value={previewTime} onChange={e=>setPreviewTime(+e.target.value)}/></label><button className="count-secondary" disabled={locked||busy||!config.source||!connected} onClick={()=>void getPreview()}>Obtener imagen</button></div>
          {preview&&<p className="count-source-meta">{preview.width} × {preview.height} · {preview.live?'Fuente en vivo':`${timeLabel(preview.duration||0)} de video`}</p>}
        </section><section className="count-card count-editor"><div className="count-card-title"><span className="count-step-number">02</span><div><h2>Área que quieres observar</h2><p>Incluye personas y excluye reflejos, pantallas y sectores externos.</p></div></div>
          <VideoCanvas visible={!!preview&&preview.source===config.source} revision={`preview-${revision}`} zones={config.zones} drawing={drawing&&!locked} draft={draft} onPoint={p=>{if(draft.length<40)setDraft([...draft,p]);}}/>
          <p className="count-source-meta">Para comparar zonas y acumular calor, usa una cámara fija. Si cambia el encuadre, define nuevas zonas e inicia otra sesión.</p>
          <div className="count-editor-toolbar"><button className="count-secondary" disabled={!preview||locked||busy||config.zones.length>=20} onClick={()=>{setDrawing(true);setDraft([]);}}>+ Dibujar zona</button><button disabled={locked||busy} onClick={()=>{setConfig({...config,zones:[wholeZone()]});setDraft([]);setDrawing(false);}}>Usar toda la imagen</button><span>{config.zones.length} zona{config.zones.length!==1?'s':''}</span></div>
          {drawing&&<div className="count-draft"><label>Nombre de la nueva zona<input value={zoneName} maxLength={80} onChange={e=>setZoneName(e.target.value)} placeholder="Ej. Sala de espera"/></label><div><button disabled={!draft.length} onClick={()=>setDraft(draft.slice(0,-1))}>Deshacer punto</button><button onClick={()=>{setDrawing(false);setDraft([]);}}>Cancelar</button><button className="count-primary" disabled={draft.length<3} onClick={addZone}>Guardar zona</button></div><small>Marca al menos tres puntos y evita cruzar los bordes. La primera zona reemplaza el área completa.</small></div>}
        </section></div>
        <section className="count-card count-rules"><div className="count-card-title"><span className="count-step-number">03</span><div><h2>Cuándo marcar una concentración</h2><p>Una alerta se confirma si el conteo alcanza el umbral durante el tiempo indicado.</p></div></div>
          <div className="count-rule-head"><span>Zona de análisis</span><span>Límite de personas</span><span>Duración mínima (s)</span><span/></div>
          {config.zones.map((z,i)=><div className="count-rule-row" key={z.id}><label><i style={{background:COLORS[i%COLORS.length]}}/><input aria-label={`Nombre de zona ${i+1}`} disabled={locked||busy} value={z.name} maxLength={80} onChange={e=>setConfig({...config,zones:config.zones.map(v=>v.id===z.id?{...v,name:e.target.value}:v)})}/></label><input aria-label={`Umbral de ${z.name}`} disabled={locked||busy} type="number" min={1} value={z.threshold} onChange={e=>setConfig({...config,zones:config.zones.map(v=>v.id===z.id?{...v,threshold:+e.target.value}:v)})}/><input aria-label={`Permanencia de ${z.name}`} disabled={locked||busy} type="number" min={0} max={3600} value={z.dwell} onChange={e=>setConfig({...config,zones:config.zones.map(v=>v.id===z.id?{...v,dwell:+e.target.value}:v)})}/><button aria-label={`Eliminar ${z.name}`} disabled={locked||busy||config.zones.length===1} onClick={()=>setConfig({...config,zones:config.zones.filter(v=>v.id!==z.id)})}>×</button></div>)}
          <details className="count-advanced"><summary>Opciones avanzadas</summary><div className="count-options"><label>Una muestra cada (s)<input type="number" min={.2} max={30} step={.2} disabled={locked||busy} value={config.interval} onChange={e=>setConfig({...config,interval:+e.target.value})}/></label><label>Resolución de análisis<select disabled={locked||busy} value={config.maxSide} onChange={e=>setConfig({...config,maxSide:+e.target.value})}>{[512,768,1024,1536,1920].map(n=><option key={n} value={n}>{n} px</option>)}</select></label><label>Confianza mínima<input type="number" min={.05} max={.99} step={.05} disabled={locked||busy} value={config.confidence} onChange={e=>setConfig({...config,confidence:+e.target.value})}/></label></div><p>Una mayor resolución aumenta el detalle y el tiempo de procesamiento. El intervalo entre imágenes determina la precisión temporal de los resultados.</p></details>
          <div className="count-launch"><p>El análisis incluye las zonas seleccionadas. Las áreas superpuestas no duplican el conteo global.</p><button className="count-secondary" disabled={locked||busy||!config.source||!connected} onClick={()=>void action(async()=>{await post('config',config);setNotice('Configuración guardada.');})}>Guardar configuración</button><button className="count-primary" disabled={locked||trackingActive||busy||!connected||!config.source||!ready?.ready||drawing} onClick={()=>void start()}>Analizar video →</button></div>
        </section>
      </>}
      {tab==='analysis'&&<>
        <div className="count-session-bar"><div><span className={`count-status ${locked?'live':''}`}>{STATUS[state.status]||state.status}</span><strong>{state.name||'Sin análisis iniciado'}</strong></div><div>{state.status==='running'&&!state.live&&<button onClick={()=>void action(async()=>{await post('pause',{});})} disabled={busy}>Pausar</button>}{state.status==='paused'&&<button onClick={()=>void action(async()=>{await post('resume',{});})} disabled={busy}>Continuar</button>}{locked?<button className="count-stop" disabled={busy||state.status==='stopping'} onClick={()=>void action(async()=>{await post('stop',{});})}>Detener</button>:<button className="count-primary" onClick={()=>setTab('setup')}>Preparar otro análisis</button>}</div></div>
        <div className="count-analysis-grid analysis-workspace"><section className="count-card"><div className="count-card-title count-split"><div><h2>Lectura del video</h2><p>{timeLabel(state.t)}{state.duration?` / ${timeLabel(state.duration)}`:''} · {state.samples} muestras</p></div><div className="count-segmented">{([['points','Personas'],['instant','Concentración actual'],['heat','Zonas más ocupadas']] as const).map(([id,label])=><button key={id} className={heat===id?'selected':''} onClick={()=>setHeat(id)}>{label}</button>)}</div></div>
          <VideoCanvas fitHeight={330} revision={`${state.session}-${state.samples}`} visible={state.samples>0} zones={zones} points={state.points} grid={grid} showPoints={heat==='points'}/>
          {state.status==='starting'&&<p className="count-inline-info">Preparando análisis. Puedes detenerlo en cualquier momento.</p>}
          <div className="count-video-footer"><span>{state.count??'—'} personas en esta imagen · {momentLabel(state,state.t)}{!state.live&&!state.config?.recordedAt?' del video':''}</span>{heat!=='points'&&<span className="count-legend">Menor <i/> Mayor concentración</span>}</div>
          {heat==='heat'&&<p className="count-footnote">Resalta los lugares con más presencia de personas durante el periodo observado. Los colores muestran intensidad relativa, no un total de visitantes.</p>}
          <div className="count-progress"><span style={{width:`${state.duration?Math.min(100,(state.status==='ended'?state.duration:state.t)/state.duration*100):0}%`}}/></div>
          <div className="count-processing"><span>Periodo procesado <b>{timeLabel(state.status==='ended'?state.duration||state.t:state.t)}</b>{state.duration?` de ${timeLabel(state.duration)}`:''}</span><span>Estado <b>{STATUS[state.status]}</b></span></div>
        </section><aside className="analysis-kpis"><h2>Resumen del periodo</h2><p>{momentLabel(state,0)} — {momentLabel(state,state.status==='ended'?state.duration??state.t:state.t)}</p><AnalysisSummary state={state} mode="metrics"/>{state.status!=='ended'&&<small>Resultados del tramo procesado.</small>}</aside></div>
        <AnalysisSummary state={state} mode="details"/>
        <details className="count-trend"><summary>Evolución de la ocupación</summary><section className="count-card"><div className="count-card-title count-split"><div><h2>Evolución de la ocupación</h2><p>Personas presentes a lo largo del tramo mostrado. El reporte conserva el periodo completo.</p></div><span className="count-tag">TIEMPO TRANSCURRIDO</span></div>{state.series.length>0?<svg className="count-chart" viewBox="0 0 1000 180" role="img" aria-label="Gráfico de personas observadas a lo largo del tiempo del video">{[0,1,2,3].map(i=><g key={i}><line x1={45} y1={20+i*40} x2={980} y2={20+i*40} stroke="#e6eeee"/><text x={5} y={25+i*40} fill="#71828d" fontSize={11}>{Math.round(Math.max(1,...state.series.map(s=>s.count))*(1-i/3))}</text></g>)}<polyline points={state.series.map(s=>`${45+(s.t-state.series[0].t)/Math.max(1,state.series[state.series.length-1].t-state.series[0].t)*935},${140-s.count/Math.max(1,...state.series.map(v=>v.count))*120}`).join(' ')} fill="none" stroke="#3975a3" strokeWidth={3}/><text x={45} y={172} fill="#71828d" fontSize={12}>{timeLabel(state.series[0].t)}</text><text x={930} y={172} fill="#71828d" fontSize={12}>{timeLabel(state.t)}</text></svg>:<div className="count-small-empty">Inicia un análisis para ver su evolución.</div>}</section></details>
        {state.session&&<button className="count-secondary" onClick={()=>void download(state.session!,'csv')}>Descargar informe CSV</button>}
      </>}
      {tab==='history'&&<><section className="count-card"><div className="count-card-title"><div><h2>Análisis recientes</h2><p>Abre un análisis para consultar zonas, horarios e intervalos de concentración.</p></div></div><div className="count-table-wrap"><table><thead><tr><th>Análisis / fuente</th><th>Fecha de análisis</th><th>Estado</th><th>Imágenes analizadas</th><th>Máximo simultáneo</th><th>Resultados</th></tr></thead><tbody>{history.map(s=><tr key={s.session}><td><strong>{s.name}</strong></td><td>{s.created?new Date(s.created).toLocaleString('es-PE'):''}</td><td>{STATUS[s.status]||s.status}</td><td>{s.samples}</td><td>{s.peak??'—'}</td><td><button disabled={busy} onClick={()=>void action(async()=>{setReportSelection(await read(`report?session=${encodeURIComponent(s.session!)}`));})}>Ver resumen</button><button disabled={busy} onClick={()=>void download(s.session!,'csv')}>CSV ↓</button><button disabled={busy} onClick={()=>void download(s.session!,'json')}>JSON ↓</button></td></tr>)}</tbody></table></div>{!history.length&&<div className="count-small-empty">No hay análisis guardados.</div>}</section>{reportSelection&&<><div className="count-report-heading" ref={reportRef}><h2>{reportSelection.name}</h2><button onClick={()=>setReportSelection(null)}>Cerrar resumen</button></div><AnalysisSummary state={reportSelection}/></>}</>}
      </>}
      {!embedded&&<footer className="count-footer"><span>AeroTrack · Conteo de multitudes</span><span>Resultados estimados · valida muestras con conteo manual</span></footer>}</div>
    </main>
  </div>;
}
