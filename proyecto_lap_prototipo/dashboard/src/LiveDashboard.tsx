import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, MouseEvent } from 'react';
import './live.css';

type Point = [number, number];
type Camera = { id: string; source: string | number; x: number; y: number; offset: number; links: string[]; pairs: number[][] };
type Config = { width: number; height: number; unit: 'relative' | 'meters'; background: string; radius: number; minPeople: number; dwell: number; handoffSeconds: number; matchDistance: number; clocksVerified: boolean; cameras: Camera[]; zones: { name: string; points: Point[] }[] };
type Person = { id: string; camera: string; point: Point | null; history: number[][]; association: string; predicted: boolean; score?: number };
type CameraState = { id: string; status: string; count?: number; calibrated?: boolean; error?: string; timestamp?: number };
type Cluster = { center: Point; radius: number; count: number; duration: number; alert: boolean };
type State = { status: string; mode?: string; session?: string; configRevision?: number; t: number; processingMs?: number; updatedAt?: number; error?: string; people: Person[]; cameras: CameraState[]; events: { id: string; from: string; to: string; t: number }[]; analytics: { clusters: Cluster[]; zones: { name: string; count: number }[]; heat: { x: number; y: number; size: number; seconds: number; peak: number }[]; mappedCount: number } };
const STATUS: Record<string, string> = { idle: 'Sin sesión', starting: 'Iniciando detector', running: 'Procesando', stopping: 'Deteniendo', stopped: 'Detenida', ended: 'Finalizada', error: 'Error', live: 'Imagen disponible', ready: 'Preparada' };
const COLORS = ['#72e8ba', '#74b9ff', '#ffca83', '#b5a1ff', '#ff99b3'];
const assoc = (p: Person) => p.association === 'estimated' ? 'Asociación estimada' : p.association === 'uncertain' ? 'Asociación incierta' : p.association === 'synthetic' ? 'Dato sintético' : 'ID de seguimiento local';

export default function LiveDashboard() {
  const [config, setConfig] = useState<Config | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [tab, setTab] = useState(new URLSearchParams(location.search).get('view') === 'lab' ? 'lab' : 'map');
  const [selected, setSelected] = useState('');
  const [personId, setPersonId] = useState('');
  const [settings, setSettings] = useState(false);
  const [detector, setDetector] = useState('p2pnet');
  const [weights, setWeights] = useState('');
  const [tool, setTool] = useState('select');
  const [polygon, setPolygon] = useState<Point[]>([]);
  const [zoneName, setZoneName] = useState('Nueva zona');
  const [pendingPoint, setPendingPoint] = useState<Point | null>(null);
  const [trails, setTrails] = useState(true);
  const [heat, setHeat] = useState(true);
  const [frameTick, setFrameTick] = useState(0);
  const [freeze, setFreeze] = useState(false);
  const [busy, setBusy] = useState(false);
  const token = useRef('');
  const revision = useRef(-1);
  const savedConfig = useRef('');
  const currentConfig = useRef(config);
  currentConfig.current = config;
  const imageRef = useRef<HTMLImageElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const bgRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        if (!token.current) {
          const response = await fetch('/api/config', { signal: AbortSignal.timeout(5000) });
          if (!response.ok) throw new Error('No se pudo leer la configuración');
          const data = await response.json();
          if (!alive) return;
          token.current = data.token;
          revision.current = data.revision;
          savedConfig.current = JSON.stringify(data.config);
          setConfig(data.config);
          setSelected(data.config.cameras[0]?.id || '');
        }
        const response = await fetch('/api/state', { signal: AbortSignal.timeout(5000) });
        if (!response.ok) throw new Error('Servidor no disponible');
        const data = await response.json();
        if (data.configRevision !== revision.current) {
          const updated = await fetch('/api/config', { signal: AbortSignal.timeout(5000) });
          if (!updated.ok) throw new Error('No se pudo sincronizar el plano');
          const fresh = await updated.json();
          if (!alive) return;
          token.current = fresh.token;
          revision.current = fresh.revision;
          if (['starting', 'running', 'stopping'].includes(data.status) || JSON.stringify(currentConfig.current) === savedConfig.current) {
            setConfig(fresh.config);
            setSelected(old => fresh.config.cameras.some((c: Camera) => c.id === old) ? old : fresh.config.cameras[0].id);
          } else {
            setNotice('La configuración guardada cambió. Tu borrador local sigue visible; guárdalo o recarga para usar la versión del servidor.');
          }
          savedConfig.current = JSON.stringify(fresh.config);
        }
        if (alive) { setState(data); setConnected(true); }
      } catch { if (alive) setConnected(false); }
      if (alive) timer = setTimeout(poll, 450);
    };
    void poll();
    return () => { alive = false; clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (freeze || state?.status !== 'running') return;
    const id = setInterval(() => setFrameTick(Date.now()), 650);
    return () => clearInterval(id);
  }, [freeze, state?.status]);

  async function post(path: string, data: unknown) {
    const response = await fetch(`/api/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-LAP-Token': token.current }, body: JSON.stringify(data), signal: AbortSignal.timeout(10000) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación');
    return result;
  }
  async function action(fn: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const running = ['starting', 'running', 'stopping'].includes(state?.status || '');
  const camera = config?.cameras.find(c => c.id === selected);
  const selectedCameraState = state?.cameras.find(c => c.id === selected);
  const simulated = state?.mode === 'demo';
  const people = connected && state?.status === 'running' ? state.people : [];
  const mapped = Array.from(new Map(people.filter(p => p.point).map(p => [p.id, p] as const)).values());
  const person = people.find(p => p.id === personId);
  const color = (cid: string) => COLORS[Math.max(0, config?.cameras.findIndex(c => c.id === cid) || 0) % COLORS.length];
  const updateCamera = (patch: Partial<Camera>) => setConfig(c => c ? { ...c, cameras: c.cameras.map(cam => cam.id === selected ? { ...cam, ...patch } : cam) } : c);
  const save = () => action(async () => { await post('config', config); savedConfig.current = JSON.stringify(config); setNotice('Configuración guardada en este equipo.'); });
  const start = (scope?: string, mode = 'p2pnet') => action(async () => {
    await post('config', config);
    savedConfig.current = JSON.stringify(config);
    await post('start', { detector: mode, camera: scope || null });
    setFreeze(false); setTool('select'); setPendingPoint(null);
  });
  function download(name: string, content: string, mime: string) {
    const url = URL.createObjectURL(new Blob([content], { type: mime }));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function importConfig(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = '';
    if (!file) return;
    await action(async () => {
      if (file.size > 4000000) throw new Error('Archivo demasiado grande.');
      const draft = JSON.parse(await file.text());
      await post('config', draft);
      setConfig(draft); setSelected(draft.cameras[0].id); setPolygon([]); setPendingPoint(null);
      setNotice('Plano y configuración importados.');
    });
  }
  function background(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = '';
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2000000) { setError('Usa PNG, JPEG o WebP de menos de 2 MB.'); return; }
    const reader = new FileReader();
    reader.onload = () => setConfig(c => c ? { ...c, background: String(reader.result) } : c);
    reader.readAsDataURL(file);
  }
  function mapClick(e: MouseEvent<SVGSVGElement>) {
    if (!config || running || !svgRef.current) return;
    const matrix = svgRef.current.getScreenCTM();
    if (!matrix) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse());
    const point: Point = [Math.max(0, Math.min(config.width, p.x)), Math.max(0, Math.min(config.height, p.y))];
    if (tool === 'camera') updateCamera({ x: point[0], y: point[1] });
    if (tool === 'zone') setPolygon(v => [...v, point]);
    if (tool === 'calibrate' && pendingPoint && camera) {
      updateCamera({ pairs: [...camera.pairs, [...pendingPoint, ...point]] });
      setPendingPoint(null); setNotice(`Correspondencia ${camera.pairs.length + 1} añadida. Marca el siguiente punto en el video.`);
    }
  }
  function imageClick(e: MouseEvent<HTMLImageElement>) {
    if (tool !== 'calibrate' || running || !imageRef.current) return;
    const r = imageRef.current.getBoundingClientRect();
    setPendingPoint([(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]);
    setNotice('Ahora marca ese mismo lugar del suelo en el plano.');
  }
  if (!config) return <div className="lap loading"><div className="brand-symbol">L</div><h1>Conectando con LAP</h1><p>Inicia el servidor: <code>python live_server.py</code></p><p>La interfaz consulta el backend local en el puerto 8765.</p></div>;
  const unit = config.unit === 'meters' ? 'm' : 'u';
  const scale = config.width / 850;
  const alerts = connected && running ? state?.analytics.clusters.filter(c => c.alert) || [] : [];
  const hasFrame = state?.mode !== 'demo' && selectedCameraState && ['live', 'stopped', 'ended'].includes(selectedCameraState.status);
  return <div className="lap">
    <aside className="rail"><div className="brand-symbol">L<span>•</span></div><span className="rail-label">LAP<br/>FLOW</span><button className={tab === 'map' ? 'active' : ''} title="Plano general" onClick={() => setTab('map')}>⌘</button><button className={tab === 'lab' ? 'active' : ''} title="Laboratorio de cámaras" onClick={() => setTab('lab')}>▣</button><div className="rail-bottom">PE<br/><span>01</span></div></aside>
    <div className="workspace">
      <header className="topbar"><div><span className="eyebrow">INTELIGENCIA DE FLUJOS / PROTOTIPO</span><h1>{tab === 'map' ? 'Centro de operaciones' : 'Laboratorio de cámaras'}</h1></div><div className="top-actions"><span className={`badge ${connected ? 'green' : 'red'}`}><i/>{connected ? STATUS[state?.status || 'idle'] : 'Backend desconectado'}</span><button onClick={() => setSettings(!settings)}>⚙ Configuración</button><span className="avatar" title="Sesión local; sin autenticación de producción">L</span></div></header>
      <nav className="tabs"><button className={tab === 'map' ? 'active' : ''} onClick={() => setTab('map')}>01 &nbsp; Plano general</button><button className={tab === 'lab' ? 'active' : ''} onClick={() => setTab('lab')}>02 &nbsp; Prueba con cámara</button><button className="popout" onClick={() => window.open(`/?view=${tab === 'map' ? 'lab' : 'map'}`, `lap-${tab === 'map' ? 'lab' : 'map'}`, 'width=1400,height=900')}>Abrir otra vista en ventana ↗</button></nav>
      {(!connected || error || state?.error) && <div role="alert" className="message error">{error || state?.error || 'Se perdió la conexión. Las posiciones ya no se muestran como actuales.'}<button onClick={() => setError('')}>×</button></div>}
      {notice && <div role="status" className="message">{notice}<button onClick={() => setNotice('')}>×</button></div>}
      {simulated && <div className="message demo">DEMOSTRACIÓN SINTÉTICA · Los nodos y recorridos son generados para probar la interfaz; no provienen de cámaras.</div>}
      <section className="metrics"><article><span>PERSONAS OBSERVADAS</span><strong>{new Set(people.map(p => p.id)).size.toString().padStart(2, '0')}</strong><small>IDs actuales · sujetos a validación</small></article><article><span>CÁMARAS CON IMAGEN</span><strong>{connected && running ? state?.cameras.filter(c => c.status === 'live').length || 0 : 0}<em> / {config.cameras.length}</em></strong><small>{config.clocksVerified ? 'Sincronización declarada por operador' : 'Sincronización por verificar'}</small></article><article><span>AGLOMERACIONES</span><strong className={alerts.length ? 'amber-text' : ''}>{alerts.length.toString().padStart(2, '0')}</strong><small>≥ {config.minPeople} personas · {config.dwell}s</small></article><article><span>POSICIONES EN PLANO</span><strong>{mapped.length.toString().padStart(2, '0')}</strong><small>{config.unit === 'meters' ? 'Escala métrica declarada' : 'Coordenadas relativas · sin escala métrica'}</small></article></section>
      <section className="session-controls"><div className="session-title"><i className={running ? 'pulse' : ''}/><span>{simulated ? 'Sesión de demostración' : 'Sesión de análisis'}<small>{state?.session ? `#${state.session} · ${state.t.toFixed(1)} s de fuente` : 'Selecciona una fuente para comenzar'}</small></span></div><select aria-label="Detector" value={detector} disabled={running} onChange={e => setDetector(e.target.value)}><option value="hog">OpenCV HOG · prueba básica</option><option value="p2pnet">P2PNet · cabezas</option><option value="yolo">YOLO · pesos locales</option></select>{detector === 'yolo' && <input aria-label="Ruta de pesos YOLO" placeholder="C:\modelos\modelo.pt" value={weights} disabled={running} onChange={e => setWeights(e.target.value)}/>}{running ? <button className="danger" disabled={busy || state?.status === 'stopping'} onClick={() => action(async () => { await post('stop', {}); })}>■ Detener sesión</button> : <><button disabled={busy || !connected} onClick={() => start(undefined, 'demo')}>Ver demo</button><button className="primary" disabled={busy || !connected} onClick={() => start(tab === 'lab' ? selected : undefined)}>▶ {tab === 'lab' ? 'Probar esta cámara' : 'Iniciar cámaras'}</button></>}</section>
      {settings && <section className="settings panel"><div className="panel-title"><h2>Plano y reglas de análisis</h2><span>Guarda los cambios antes de abrir otra ventana</span></div><div className="settings-grid"><label>Ancho ({unit})<input type="number" min="1" max="10000" value={config.width} disabled={running} onChange={e => setConfig({ ...config, width: +e.target.value })}/></label><label>Alto ({unit})<input type="number" min="1" max="10000" value={config.height} disabled={running} onChange={e => setConfig({ ...config, height: +e.target.value })}/></label><label>Unidad<select value={config.unit} disabled={running} onChange={e => setConfig({ ...config, unit: e.target.value as Config['unit'] })}><option value="relative">Relativa (u)</option><option value="meters">Metros medidos (m)</option></select></label><label>Radio de agrupación ({unit})<input type="number" step="0.1" min="0.01" value={config.radius} disabled={running} onChange={e => setConfig({ ...config, radius: +e.target.value })}/></label><label>Mínimo de personas<input type="number" min="2" value={config.minPeople} disabled={running} onChange={e => setConfig({ ...config, minPeople: +e.target.value })}/></label><label>Permanencia para alertar (s)<input type="number" min="0" value={config.dwell} disabled={running} onChange={e => setConfig({ ...config, dwell: +e.target.value })}/></label><label>Ventana de asociación (s)<input type="number" min="0.1" max="120" value={config.handoffSeconds} disabled={running} onChange={e => setConfig({ ...config, handoffSeconds: +e.target.value })}/></label><label>Distancia de asociación ({unit})<input type="number" min="0.01" step="0.1" value={config.matchDistance} disabled={running} onChange={e => setConfig({ ...config, matchDistance: +e.target.value })}/></label></div><label className="check"><input type="checkbox" disabled={running} checked={config.clocksVerified} onChange={e => setConfig({ ...config, clocksVerified: e.target.checked })}/> Verifiqué que las fuentes comparten tiempo y configuré sus desfases. Habilitar asociaciones entre cámaras.</label><div className="button-row"><button disabled={running} onClick={() => bgRef.current?.click()}>Subir imagen del plano</button><button disabled={running} onClick={() => setConfig({ ...config, background: '' })}>Plano en blanco</button><button disabled={running} onClick={() => importRef.current?.click()}>Importar configuración</button><button onClick={() => download('lap-plano.json', JSON.stringify(config, null, 2), 'application/json')}>Exportar configuración</button><button className="primary" disabled={running || busy} onClick={save}>Guardar configuración</button></div><p className="muted">Al cambiar el plano, su escala o la orientación de una cámara, revisa su calibración. El área visible se obtiene marcando correspondencias del suelo; colocar el icono de cámara no calibra su alcance.</p><input hidden ref={bgRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={background}/><input hidden ref={importRef} type="file" accept="application/json" onChange={importConfig}/></section>}
      {running && <section className="live-thresholds panel"><span>Reglas en vivo</span><label>Radio ({unit})<input type="number" min="0.01" step="0.1" value={config.radius} onChange={e => setConfig({ ...config, radius: +e.target.value })}/></label><label>Personas<input type="number" min="2" value={config.minPeople} onChange={e => setConfig({ ...config, minPeople: +e.target.value })}/></label><label>Permanencia (s)<input type="number" min="0" value={config.dwell} onChange={e => setConfig({ ...config, dwell: +e.target.value })}/></label><button disabled={busy} onClick={() => action(async () => { await post('settings', { radius: config.radius, minPeople: config.minPeople, dwell: config.dwell }); setNotice('Reglas aplicadas a la sesión. Guarda la configuración al detenerla para conservarlas.'); })}>Aplicar reglas</button></section>}
      <div className={`main-grid ${tab === 'lab' ? 'lab-view' : ''}`}>
        <section className="panel map-panel"><div className="panel-title"><div><h2>Plano de desplazamientos <span className="badge">{unit === 'u' ? 'RELATIVO' : 'MÉTRICO'}</span></h2><p>Vista superior · {config.width} × {config.height} {unit}</p></div><div className="button-row"><button className={heat ? 'selected' : ''} onClick={() => setHeat(!heat)}>Densidad</button><button className={trails ? 'selected' : ''} onClick={() => setTrails(!trails)}>Recorridos</button></div></div>
          <div className="map-tools"><button disabled={running} className={tool === 'select' ? 'selected' : ''} onClick={() => { setTool('select'); setPendingPoint(null); }}>Seleccionar</button><button disabled={running} className={tool === 'camera' ? 'selected' : ''} onClick={() => setTool('camera')}>Colocar cámara {selected}</button><button disabled={running} className={tool === 'zone' ? 'selected' : ''} onClick={() => { setTool('zone'); setPolygon([]); }}>Dibujar zona</button><span>{tool === 'calibrate' ? pendingPoint ? '↓ Marca el mismo punto en el plano' : 'Marca un punto del suelo en el video →' : tool === 'camera' ? 'Haz clic en el plano' : tool === 'zone' ? 'Marca al menos 3 vértices' : 'Selecciona un nodo para ver su recorrido'}</span></div>
          <div className="map-canvas"><svg ref={svgRef} viewBox={`0 0 ${config.width} ${config.height}`} onClick={mapClick} aria-label="Plano interactivo de personas y cámaras" role="img"><defs><pattern id="grid" width={config.width / 24} height={config.height / 16} patternUnits="userSpaceOnUse"><path d={`M ${config.width / 24} 0 L 0 0 0 ${config.height / 16}`} fill="none" stroke="#26353b" strokeWidth={scale * .55}/></pattern></defs><rect width={config.width} height={config.height} fill="#111c22"/>{config.background && <image href={config.background} width={config.width} height={config.height} preserveAspectRatio="none" opacity=".55"/>}<rect width={config.width} height={config.height} fill="url(#grid)"/>
            {heat && state?.analytics.heat.map((cell, i) => <rect key={i} x={cell.x} y={cell.y} width={cell.size} height={cell.size} fill="#66e2b7" opacity={Math.min(.4, cell.seconds / Math.max(1, state.analytics.heat[0]?.seconds || 1) * .4)}/>)}
            {config.zones.map((z, i) => <g key={i}><polygon points={z.points.map(p => p.join(',')).join(' ')} fill="#77baff1a" stroke="#77baff" strokeDasharray={`${scale * 4} ${scale * 4}`} strokeWidth={scale}/><text x={z.points[0][0]} y={z.points[0][1]} fontSize={scale * 11} fill="#a4cfff">{z.name}</text></g>)}
            {polygon.length > 0 && <polyline points={polygon.map(p => p.join(',')).join(' ')} fill="#e6be6233" stroke="#e6be62" strokeWidth={scale * 2}/>}
            {trails && mapped.map(p => <polyline key={p.id} points={p.history.map(v => `${v[0]},${v[1]}`).join(' ')} fill="none" stroke={color(p.camera)} strokeWidth={scale * (p.id === personId ? 2.5 : 1.2)} opacity={p.id === personId ? .95 : .35}/>)}
            {connected && running && state?.analytics.clusters.map((cluster, i) => <g key={i}><circle cx={cluster.center[0]} cy={cluster.center[1]} r={cluster.radius} fill={cluster.alert ? '#f0ad4822' : '#68dfbd11'} stroke={cluster.alert ? '#ffc479' : '#72e8ba'} strokeDasharray={`${scale * 5} ${scale * 4}`} strokeWidth={scale * 1.3}/><text x={cluster.center[0]} y={cluster.center[1] - cluster.radius + scale * 16} textAnchor="middle" fill="#ffce8e" fontSize={scale * 11}>{cluster.count} personas · {cluster.duration.toFixed(0)}s</text></g>)}
            {config.cameras.map(c => <g key={c.id} transform={`translate(${c.x}, ${c.y})`} className="clickable" onClick={e => { e.stopPropagation(); setSelected(c.id); }}><circle r={scale * 15} fill={c.id === selected ? '#304b48' : '#203239'} stroke={color(c.id)} strokeWidth={scale}/><path d={`M ${-scale*6} ${-scale*4} h ${scale*8} v ${scale*8} h ${-scale*8} z M ${scale*3} 0 l ${scale*5} ${-scale*4} v ${scale*8} z`} fill={color(c.id)}/><text y={scale * 30} textAnchor="middle" fill="#cee3df" fontSize={scale * 11}>CAM {c.id}</text></g>)}
            {camera?.pairs.map((p, i) => <g key={i}><circle cx={p[2]} cy={p[3]} r={scale * 4} fill="#ffd18b"/><text x={p[2]+scale*6} y={p[3]-scale*4} fill="#ffd18b" fontSize={scale * 10}>{i+1}</text></g>)}
            {mapped.map(p => <g key={p.id} transform={`translate(${p.point![0]}, ${p.point![1]})`} className="clickable" onClick={e => { e.stopPropagation(); setPersonId(p.id); setSelected(p.camera); }}><circle r={scale * (personId === p.id ? 10 : 6)} fill={color(p.camera)} stroke="#10231f" strokeWidth={scale * 2}/><text x={scale * 10} y={-scale * 8} fontSize={scale * 10} fill="#e2f6ee">{p.id}{p.association === 'estimated' ? ' ~' : ''}</text></g>)}
          </svg>{!mapped.length && <div className="empty-map"><span>◎</span><strong>{running && !simulated ? 'Esperando posiciones calibradas' : 'Tu espacio, en una sola vista'}</strong><p>{running ? 'El video puede mostrar detecciones aunque la cámara aún no tenga calibración de suelo.' : 'Configura las cámaras o abre la demostración para explorar el plano.'}</p></div>}</div>
          {tool === 'zone' && <div className="zone-editor"><input aria-label="Nombre de zona" value={zoneName} onChange={e => setZoneName(e.target.value)} maxLength={80}/><button disabled={polygon.length < 3 || !zoneName.trim()} onClick={() => { setConfig({ ...config, zones: [...config.zones, { name: zoneName.trim(), points: polygon }] }); setPolygon([]); setTool('select'); }}>Cerrar polígono</button><button onClick={() => setPolygon(p => p.slice(0, -1))}>Deshacer punto</button></div>}
          <footer className="map-legend"><span><i style={{ background: '#72e8ba' }}/>Posición observada</span><span><i style={{ background: '#ffbd70' }}/>Aglomeración</span><span>~ Asociación estimada</span><span>Sin extrapolar nodos en zonas ciegas</span></footer>
        </section>
        <aside className="right-column"><section className="panel camera-panel"><div className="panel-title"><div><h2>Video de cámara</h2><p>Imagen real con ID de seguimiento</p></div><span className={`badge ${selectedCameraState?.status === 'live' && running ? 'green' : ''}`}>{selectedCameraState ? STATUS[selectedCameraState.status] : 'SIN FUENTE ACTIVA'}</span></div><div className="camera-tabs">{config.cameras.map(c => <button key={c.id} className={selected === c.id ? 'selected' : ''} onClick={() => { setSelected(c.id); setPendingPoint(null); }}>CAM {c.id}</button>)}</div>
            <div className="video-wrap">{hasFrame ? <><img key={selected} ref={imageRef} className={tool === 'calibrate' ? 'calibrating' : ''} src={`/api/frame?camera=${encodeURIComponent(selected)}&v=${frameTick}`} alt={`Video procesado de cámara ${selected}`} onClick={imageClick}/><span className="video-caption">{running && !freeze && connected ? 'ÚLTIMO FRAME PROCESADO' : 'IMAGEN RETENIDA · NO EN VIVO'} · CAM {selected}</span>{pendingPoint && <i className="calibration-point" style={{ left: `${pendingPoint[0]*100}%`, top: `${pendingPoint[1]*100}%` }}/>}</> : <div className="empty-video"><span>▣</span><strong>{simulated ? 'La demo no contiene video real' : 'Cámara lista para configurar'}</strong><p>{selectedCameraState?.error || 'Usa una cámara USB, una fuente RTSP o un video propio.'}</p></div>}</div>
            <div className="camera-summary"><span>{people.filter(p => p.camera === selected).length} observaciones</span><span>{selectedCameraState?.calibrated ? 'Proyección de suelo' : 'Sin proyección validada'}</span></div>
            {tab === 'lab' && <div className="lab-note">HOG es una referencia funcional básica. P2PNet detecta cabezas y las baja al suelo con la altura de la cámara para ubicarlas en el plano, por lo que esa altura debe superar la estatura media. YOLO requiere una dependencia y pesos locales.</div>}
            <details open={tab === 'lab' || tool === 'calibrate'}><summary>Fuente y calibración de CAM {selected}</summary>{camera && <div className="camera-form"><label>Fuente (USB, ruta de video o RTSP)<input disabled={running} value={camera.source} onChange={e => updateCamera({ source: /^\d+$/.test(e.target.value) ? +e.target.value : e.target.value })} placeholder="0 = primera cámara USB"/></label><div className="two-cols"><label>Omitir al inicio (s)<input disabled={running} type="number" min="0" step="0.1" value={camera.offset} onChange={e => updateCamera({ offset: +e.target.value })}/></label><label>Cámaras de destino<input disabled={running} value={camera.links.join(',')} onChange={e => updateCamera({ links: e.target.value.split(',').map(v => v.trim()).filter(Boolean) })}/></label></div><div className="button-row"><button disabled={running || !hasFrame} className={tool === 'calibrate' ? 'selected' : ''} onClick={() => { setFreeze(true); setTool('calibrate'); setNotice('Sobre la imagen detenida, marca un punto del suelo. Luego marca su correspondencia en el plano. Repite con al menos 4 puntos distribuidos.'); }}>Calibrar suelo</button><button disabled={running || !camera.pairs.length} onClick={() => updateCamera({ pairs: camera.pairs.slice(0, -1) })}>Deshacer punto</button><button disabled={running} onClick={() => updateCamera({ pairs: [] })}>Limpiar</button></div><p className="muted">{camera.pairs.length} correspondencias · mínimo 4, recomendado 6–8. Primero inicia y detén una prueba para obtener una imagen. Usa referencias del suelo, sin personas.</p><button disabled={running || busy} className="primary" onClick={save}>Guardar cámara y plano</button></div>}</details>
          </section>
          <section className="panel insights"><div className="panel-title"><h2>{person ? `Recorrido · ${person.id}` : 'Lectura del espacio'}</h2><span className="eyebrow">ANÁLISIS</span></div>{person ? <div className="person-card"><span className="badge">{assoc(person)}</span><p>Cámara {person.camera} · {person.history.length} posiciones recientes</p><p>{person.point ? `${person.point[0].toFixed(2)}, ${person.point[1].toFixed(2)} ${unit}` : 'Sin coordenadas de suelo'}</p><button onClick={() => setPersonId('')}>Cerrar selección</button></div> : <><p className="muted">Acumulación de personas × segundos observados. Las zonas son candidatas para estudiar, no decisiones comerciales.</p>{state?.analytics.heat.slice(0, 3).map((cell, i) => <div className="roi-row" key={i}><span className="roi-rank">0{i+1}</span><div><strong>Sector ({cell.x.toFixed(1)}, {cell.y.toFixed(1)})</strong><small>Pico de {cell.peak} personas observadas</small></div><b>{cell.seconds.toFixed(0)}<small>pers·s</small></b></div>)}{!state?.analytics.heat.length && <p className="muted">Las zonas aparecerán al acumular observaciones en el plano.</p>}</>}{state?.analytics.zones.map((z, i) => <div className="zone-count" key={i}><span>{z.name}</span><b>{z.count} personas</b></div>)}<button disabled={!state?.analytics.heat.length} onClick={() => download('lap-zonas-observadas.json', JSON.stringify({ session: state?.session, mode: state?.mode, unit: config.unit, sourceSeconds: state?.t, cells: state?.analytics.heat }, null, 2), 'application/json')}>Exportar análisis ↓</button></section>
        </aside>
      </div>
      <section className="bottom-grid"><div className="panel camera-list"><div className="panel-title"><h2>Red de cámaras</h2><button disabled={running} onClick={() => { let n = config.cameras.length + 1; while (config.cameras.some(c => c.id === `C${n}`)) n++; const id = `C${n}`; setConfig({ ...config, cameras: [...config.cameras, { id, source: 0, x: config.width / 2, y: config.height / 2, offset: 0, links: [], pairs: [] }] }); setSelected(id); setTab('lab'); }}>+ Añadir cámara</button></div>{config.cameras.map(c => <div className="camera-row" key={c.id}><i style={{ background: color(c.id) }}/><button onClick={() => { setSelected(c.id); setTab('lab'); }}>CAM {c.id} ↗</button><span>{c.pairs.length >= 4 ? `${c.pairs.length} referencias de suelo` : 'Pendiente de calibración'}</span><span>{typeof c.source === 'number' ? `USB ${c.source}` : c.source.includes('://') ? 'Fuente de red' : 'Archivo de video'}</span><button disabled={running || config.cameras.length <= 1} onClick={() => { const remaining = config.cameras.filter(cam => cam.id !== c.id).map(cam => ({ ...cam, links: cam.links.filter(id => id !== c.id) })); setConfig({ ...config, cameras: remaining }); if (selected === c.id) setSelected(remaining[0].id); }}>Quitar</button></div>)}</div><div className="panel events"><div className="panel-title"><h2>Asociaciones entre cámaras</h2><span className="badge">ESTIMADAS</span></div>{state?.events.slice(0, 6).map((event, i) => <div className="event-row" key={i}><span>{event.t.toFixed(1)} s</span><b>{event.id}</b><span>CAM {event.from} → CAM {event.to}</span></div>)}{!state?.events.length && <p className="muted">Se mostrarán al asociar trayectorias entre cámaras enlazadas y sincronizadas. Un ID temporal no confirma la identidad de una persona.</p>}<div className="privacy-note">Sesión local · sin reconocimiento facial · IDs temporales. No se guardan grabaciones automáticamente.</div></div></section>
      {settings && config.zones.length > 0 && <div className="panel zone-management"><h2>Zonas dibujadas</h2>{config.zones.map((z, i) => <button disabled={running} key={i} onClick={() => setConfig({ ...config, zones: config.zones.filter((_, index) => index !== i) })}>Eliminar {z.name} ×</button>)}</div>}
      <footer className="page-footer"><span>LAP FLOW / CAPSTONE</span><span>{state?.processingMs ? `${state.processingMs} ms por ciclo · ` : ''}Análisis de recorridos y ocupación · prototipo local</span></footer>
    </div>
  </div>;
}
