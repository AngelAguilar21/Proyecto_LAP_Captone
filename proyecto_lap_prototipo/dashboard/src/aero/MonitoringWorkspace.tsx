import { useEffect, useRef, useState } from 'react';
import type { Config, SessionState } from './types';
import { EMPTY_STATE, formatTime, isActive } from './types';
import type { Session } from './useSession';
import ExecutiveSummary from './ExecutiveSummary';
import MapCanvas from './MapCanvas';
import ReplayWorkspace from './ReplayWorkspace';
import { CameraVideo } from './CameraPanel';
import Metric from './Metric';
import Icon from './Icon';

export default function MonitoringWorkspace({ session, onSetup, onReplay, active = true }: {
  active?: boolean;
  session: Session;
  onSetup: (id?: string) => void;
  onReplay: () => void;
}) {
  const config = session.config!;
  const propio = config.planId || 'custom';
  const niveles = [...new Set([propio, ...Object.keys(config.plans || {}), ...config.cameras.map(c => c.planId || 'custom')])];
  const nombreNivel = (id: string) => id.startsWith('lap-')
    ? `LAP · Nivel ${id.split('-')[1]}`
    : (id === propio ? config.floor : config.plans?.[id]?.floor) || (id === 'custom' ? 'Plano del proyecto' : id);

  const [level, setLevel] = useState(propio);
  const [camera, setCamera] = useState('all');
  const [zone, setZone] = useState('all');
  const [plan, setPlan] = useState<Config | null>(null);
  const [archived, setArchived] = useState<any>(null);
  const [error, setError] = useState('');
  const [historyLoading, setHistoryLoading] = useState(true);
  const quality = 256;
  const [unified, setUnified] = useState(false);
  const [testRun,setTestRun]=useState(config.cameras.some(c=>c.illustrative));
  const [allLevels, setAllLevels] = useState(true);
  const [trend, setTrend] = useState<{ t: number; zones: any[] }[]>([]);
  const [pendientes, setPendientes] = useState<number | null>(null);
  const [detailSettings,setDetailSettings]=useState(false);
  const [detailColumns,setDetailColumns]=useState(()=>{try{return Math.max(1,Math.min(4,Number(localStorage.getItem('aero.camera.columns'))||2));}catch{return 2;}});
  const [detailCameraIds,setDetailCameraIds]=useState<string[]>(()=>{try{return JSON.parse(localStorage.getItem('aero.camera.visible')||'[]');}catch{return [];}});
  const mapRef = useRef<HTMLElement>(null);
  const busy = isActive(session.state.status);

  useEffect(()=>{
    setDetailCameraIds(current=>{
      const valid=current.filter(id=>config.cameras.some(c=>c.id===id));
      return valid.length?valid:config.cameras.map(c=>c.id);
    });
  },[config.cameras]);
  useEffect(()=>{try{localStorage.setItem('aero.camera.visible',JSON.stringify(detailCameraIds));localStorage.setItem('aero.camera.columns',String(detailColumns));}catch{/* preferencia opcional */}},[detailCameraIds,detailColumns]);

  useEffect(() => { setTrend([]); }, [session.state.session, level]);
  useEffect(() => {
    if (session.state.status !== 'running') return;
    const zones = (session.state as any).levelAnalytics?.[level]?.zones || session.state.analytics.zones;
    setTrend(rows => rows[rows.length - 1]?.t === session.state.t
      ? rows
      : [...rows.slice(-1799), { t: session.state.t, zones }]);
  }, [session.state.t, session.state.status, level]);

  useEffect(() => {
    let alive = true;
    const saved = level === propio ? config : config.plans?.[level];
    if (saved) {
      setPlan({ ...config, ...saved, planId: level });
      return;
    }
    if(!level.startsWith('lap-')) {
      setPlan({ ...config, planId: level });
      return;
    }
    void fetch(`/maps/lap/${level.split('-')[1]}.json`)
      .then(r => r.json())
      .then(m => {
        if (alive) setPlan({
          ...config,
          width: m.width,
          height: m.height,
          workArea: undefined,
          background: '',
          zones: [],
          mapAsset: `/maps/lap/${m.floor}.json`,
          floor: m.name,
          planId: level,
          mapConfigured: true,
        });
      })
      .catch(() => setError('No se pudo abrir este nivel.'));
    return () => { alive = false; };
  }, [config, level, propio]);

  useEffect(() => {
    let alive = true;
    setHistoryLoading(true);
    void fetch('/api/replay/history')
      .then(r => r.json())
      .then(async rows => {
        const relevant = rows.filter((r: any) => r.end > 0
          && ['unified', 'tracking'].includes(r.module)
          && r.cameras.some((v: any) => (v.planId || r.config?.planId || 'custom') === level
            && config.cameras.some(c => c.id === v.id)));
        if (!relevant.length) {
          if (alive) setArchived(null);
          return;
        }
        const latest: Record<string, any> = {};
        const metadata: Record<string, any> = {};
        for (const r of relevant) for (const c of r.cameras) {
          if (!latest[c.id] && r.cameraAnalytics?.[c.id]) {
            latest[c.id] = r.cameraAnalytics[c.id];
            metadata[c.id] = { created: r.created, session: r.session };
          }
        }
        const response = await fetch(`/api/replay/data?session=${relevant[0].session}`);
        const data = await response.json();
        if (alive) setArchived({
          ...data,
          cameraAnalytics: Object.keys(latest).length ? latest : data.cameraAnalytics,
          latestByCamera: metadata,
        });
      })
      .catch(() => setError('No se pudo recuperar el último análisis.'))
      .finally(() => { if (alive) setHistoryLoading(false); });
    return () => { alive = false; };
  }, [session.state.session, session.state.status, session.state.serverInstance, level]);

  useEffect(() => {
    let alive = true;
    const cargar = () => void fetch('/api/incidents?estado=pendiente')
      .then(r => r.json())
      .then(data => { if (alive) setPendientes(data.error ? null : (data.incidentes || []).length); })
      .catch(() => { if (alive) setPendientes(null); });
    cargar();
    const id = setInterval(cargar, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [session.state.session]);

  const cameras = config.cameras.filter(c => (c.planId || 'custom') === level && (camera === 'all' || c.id === camera));
  const nivelCameras = config.cameras.filter(c => (c.planId || 'custom') === level);
  const last = archived?.samples?.at(-1);
  const archivedPeople = (last?.cameras || []).flatMap((view:any)=>(view.people||[]).map((person:any)=>({
    ...person,
    camera:view.id,
    predicted:false,
    history:person.history||[],
  })));
  const cameraAnalytics = busy
    ? session.state.cameraAnalytics || {}
    : archived?.cameraAnalytics || Object.fromEntries((archived?.cameras || []).map((c: any) => {
      const row = [...(archived.samples || [])].reverse().find((r: any) => r.cameras.some((v: any) => v.id === c.id));
      return [c.id, row?.cameras.find((v: any) => v.id === c.id)?.analysis];
    }));
  const base: SessionState = busy
    ? session.state
    : { ...EMPTY_STATE, status: 'ended', planId: archived?.config?.planId, t: last?.t || 0, people:archivedPeople, analytics: last?.analytics || EMPTY_STATE.analytics };
  const levelAnalytics = busy ? (session.state as any).levelAnalytics?.[level] : last?.levels?.[level];
  const state = {
    ...base,
    planId: level,
    people: base.people.filter(p => cameras.some(c => c.id === p.camera)),
    analytics: levelAnalytics || EMPTY_STATE.analytics,
  };
  if (camera !== 'all') {
    state.analytics = cameraAnalytics[camera]?.map || {
      ...EMPTY_STATE.analytics,
      mappedCount: state.people.filter(p => p.point).length,
    };
  }

  const zoneNames = [...new Set(cameras.flatMap(c => cameraAnalytics[c.id]?.occupancy?.zones?.map((z: any) => z.name) || []))] as string[];
  const entries = cameras.reduce((n, c) => n + (cameraAnalytics[c.id]?.crossings || []).reduce((a: number, line: any) => a + line.entries, 0), 0);
  const exits = cameras.reduce((n, c) => n + (cameraAnalytics[c.id]?.crossings || []).reduce((a: number, line: any) => a + line.exits, 0), 0);
  const sinCamaras = !config.cameras.length;
  const hayDatos = busy || !!archived;
  const enVivo = session.state.cameras.filter(c => nivelCameras.some(v => v.id === c.id) && c.status === 'live').length;
  const availableCameras = camera === 'all' && allLevels ? config.cameras : cameras;
  const detailCameras = nivelCameras.filter(c=>detailCameraIds.includes(c.id));
  const canStart = availableCameras.some(c => c.active !== false);

  function toggleMonitoring() {
    void session.action(async () => {
      if (busy) {
        await session.post('stop', {});
        return;
      }
      await session.save();
      await session.post('start', {
        detector: 'p2pnet',
        combined: true,
        testRun,
        inferenceSize: quality,
        cameraIds: (camera === 'all' ? availableCameras : cameras).filter(c => c.active !== false).map(c => c.id),
        requireUnified: unified,
      });
    });
  }

  return <div className="monitoring-workspace overview-v2">
    <header className="monitor-page-header">
      <div className="monitor-title-group">
        <div className="monitor-title-line">
          <h1>Ocupación y flujo</h1>
          <span className={`monitor-session-status ${busy ? 'is-live' : ''}`}><i />{busy ? 'Monitoreo en vivo' : 'Sin sesión activa'}</span>
        </div>
        <strong>{config.airport || 'Proyecto AeroTrack'}</strong>
        <p>Monitoreo inteligente de ocupación, movimiento y flujo peatonal.</p>
      </div>
      <div className="monitor-header-actions">
        <button onClick={() => onSetup()}><Icon name="settings" size={16} />Configurar cámaras</button>
        <button onClick={onReplay}><Icon name="clock" size={16} />Ver resultados</button>
        <label className="check"><input type="checkbox" checked={testRun} disabled={busy} onChange={e=>setTestRun(e.target.checked)}/>Prueba con videos</label>
        {!sinCamaras && <button className={busy ? 'danger' : 'primary'} disabled={session.busy || (!busy && !canStart)} onClick={toggleMonitoring}>
          <Icon name={busy ? 'stop' : 'play'} size={16} />{busy ? 'Detener monitoreo' : testRun ? 'Analizar videos de prueba' : 'Iniciar monitoreo'}
        </button>}
      </div>
    </header>

    {error && <div className="notice error" role="alert">{error}</div>}
    {testRun&&<p className="commerce-test">Los videos se procesan con sus detecciones y accesos configurados. El plano es ilustrativo; los resultados comerciales se guardan en Datos de prueba.</p>}

    {sinCamaras ? <section className="monitor-onboarding">
      <span className="monitor-onboarding-icon"><Icon name="camera" size={28} /></span>
      <div><h2>Configura la primera cámara</h2><p>Añade el plano y una fuente de video para comenzar a medir ocupación y recorridos.</p></div>
      <button className="primary" onClick={() => onSetup()}><Icon name="plus" size={16} />Configurar espacio</button>
    </section> : <>
      <section className="monitor-kpi-grid" aria-label="Indicadores de monitoreo">
        <Metric label="Personas en el plano" value={hayDatos?state.people.length:'—'} icon="people" tone={busy ? 'blue' : 'muted'} note={busy ? 'Detectadas ahora' : archived ? 'Último resultado guardado' : 'Esperando monitoreo'} />
        <Metric label="Entradas" value={hayDatos?entries:'—'} icon="arrow" tone="blue" note={hayDatos ? 'Durante la sesión' : 'Esperando monitoreo'} />
        <Metric label="Salidas" value={hayDatos?exits:'—'} icon="arrow" tone="blue" note={hayDatos ? 'Durante la sesión' : 'Esperando monitoreo'} />
        <Metric label="Alertas activas" value={pendientes??'—'} icon="alert" tone={pendientes ? 'red' : pendientes === 0 ? 'green' : 'muted'} note={pendientes === null ? 'Sin lectura disponible' : pendientes ? 'Pendientes de revisión' : 'Operación normal'} />
        <Metric label="Cámaras activas" value={busy ? `${enVivo}/${nivelCameras.length}` : `${nivelCameras.filter(c => c.active !== false).length}/${nivelCameras.length}`} icon="camera" tone={busy && enVivo === nivelCameras.length ? 'green' : 'blue'} note={busy ? 'Con señal en vivo' : 'Configuradas en el nivel'} />
        <Metric label="Tiempo de análisis" value={hayDatos ? formatTime(base.t) : '--:--'} icon="clock" tone="muted" note={busy ? 'Sesión en curso' : archived ? 'Última duración' : 'Esperando monitoreo'} />
      </section>

      <section className="monitor-filter-toolbar" aria-label="Filtros del plano">
        <div className="filter-toolbar-title"><Icon name="sliders" size={17} /><span>Vista del plano</span></div>
        <label>Nivel<select value={level} onChange={e => { setLevel(e.target.value); setCamera('all'); setZone('all'); }}>{niveles.map(id => <option key={id} value={id}>{nombreNivel(id)}</option>)}</select></label>
        <label>Cámara<select value={camera} onChange={e => { setCamera(e.target.value); setZone('all'); }}><option value="all">Todas las cámaras</option>{config.cameras.filter(c => (c.planId || 'custom') === level).map(c => <option key={c.id} value={c.id}>{c.name || c.id}</option>)}</select></label>
        <label>Zona<select value={zone} onChange={e => setZone(e.target.value)}><option value="all">Todas las zonas</option>{zoneNames.map(name => <option key={name}>{name}</option>)}</select></label>
        <div className="toolbar-toggles">
          <label className="switch-control"><input disabled={busy} type="checkbox" checked={allLevels} onChange={e => setAllLevels(e.target.checked)} /><span />Procesar niveles</label>
          <label className="switch-control"><input disabled={busy} type="checkbox" checked={unified} onChange={e => setUnified(e.target.checked)} /><span />Asociar recorridos</label>
        </div>
      </section>

      <section className="monitor-map-card" ref={mapRef}>
        <header className="monitor-map-header">
          <div><span className="map-title-icon"><Icon name="map" size={19} /></span><div><h2>Plano operativo</h2><p>Distribución espacial y nodos detectados</p></div></div>
          <div className="map-header-status">
            {historyLoading && <span className="map-sync"><i />Sincronizando</span>}
            <span className="map-floor">{nombreNivel(level)}</span>
            <button className="icon-button" title="Pantalla completa" aria-label="Abrir plano en pantalla completa" onClick={() => void mapRef.current?.requestFullscreen().catch(() => {})}><Icon name="expand" size={17} /></button>
          </div>
        </header>
        <div className="monitor-map-shell">
          {plan && <MapCanvas key={level} config={plan} state={state} connected={session.connected} peopleFirst selectedCamera={camera === 'all' ? '' : camera} onCamera={id => setCamera(id)} />}
          {!plan && <div className="map-skeleton" role="status"><span /><span /><span /></div>}
          {!busy && !archived && plan && <div className="monitor-map-empty">
            <span><Icon name="people" size={24} /></span>
            <h3>Monitoreo no iniciado</h3>
            <p>Comienza el análisis para visualizar ocupación, nodos detectados y recorridos.</p>
            <button className="primary" disabled={session.busy || !canStart} onClick={toggleMonitoring}><Icon name="play" size={15} />Iniciar monitoreo</button>
            <small>Selecciona cámaras y activa el monitoreo para comenzar.</small>
          </div>}
        </div>
        <footer className="monitor-map-footer">
          <div><span className="legend-dot person" />Personas<span className="legend-dot camera" />Cámaras<span className="legend-dot zone" />Zonas<span className="legend-line" />Trayectorias</div>
          <span>{state.analytics.mappedCount || 0} posiciones proyectadas</span>
        </footer>
      </section>

      {busy && <ExecutiveSummary rows={trend} />}

      {!busy && archived && <section className="monitor-results-disclosure" aria-labelledby="saved-analysis-title">
        <header><h2 id="saved-analysis-title">Explorar el último análisis guardado</h2><p>Resultados, recorridos y oportunidades del análisis más reciente.</p></header>
        <ReplayWorkspace active={active} embedded selectedLevel={level} cameraFilter={camera} zoneFilter={zone} currentConfig={config} onCamera={id => { setCamera(id); setZone('all'); }} />
      </section>}

      <section className="camera-history-summary camera-detail-section" aria-labelledby="camera-detail-title">
        <header className="camera-detail-head"><div><h2 id="camera-detail-title">Detalle por cámara</h2><p>Vista permanente de las fuentes seleccionadas y su resultado más reciente.</p></div><button aria-expanded={detailSettings} onClick={()=>setDetailSettings(value=>!value)}><Icon name="sliders" size={16}/>{detailSettings?'Cerrar selección':'Personalizar'}</button></header>
        {detailSettings&&<div className="camera-detail-settings"><fieldset><legend>Cámaras visibles</legend>{nivelCameras.map(c=><label key={c.id}><input type="checkbox" checked={detailCameraIds.includes(c.id)} onChange={e=>setDetailCameraIds(ids=>e.target.checked?[...new Set([...ids,c.id])]:ids.filter(id=>id!==c.id))}/>{c.name||c.id}</label>)}</fieldset><label>Columnas<select value={detailColumns} onChange={e=>setDetailColumns(Number(e.target.value))}>{[1, 2, 3, 4].map(value=><option key={value} value={value}>{value}</option>)}</select></label></div>}
        {!detailCameras.length&&<div className="empty-state compact"><Icon name="camera" size={26}/><strong>No hay cámaras visibles</strong><p>Abre Personalizar y selecciona al menos una cámara de este piso.</p></div>}
        <div className="monitor-camera-grid" style={{gridTemplateColumns:`repeat(${detailColumns}, minmax(260px, 1fr))`}}>{detailCameras.map(c => {
          const status = session.state.cameras.find(v => v.id === c.id);
          const analytics = cameraAnalytics[c.id];
          const zones = analytics?.occupancy?.zones?.filter((z: any) => zone === 'all' || z.name === zone) || [];
          return <article className="aero-panel monitor-camera-card" key={c.id}>
            <div className="panel-heading"><h2>{c.name || c.id}</h2><button disabled={busy} onClick={() => onSetup(c.id)}>Configurar</button></div>
            {busy && <CameraVideo camera={c} state={session.state} connected={session.connected} />}
            {!busy && archived?.latestByCamera?.[c.id] && <small>Análisis: {new Date(archived.latestByCamera[c.id].created).toLocaleString('es-PE')}</small>}
            <p>{c.active === false ? 'Cámara desactivada · ' : ''}{analytics ? `Última muestra: ${formatTime(analytics.t)}` : 'Todavía no hay resultados de esta cámara'}</p>
            <div className="feed-metrics">{busy && status?.duration && <span>Video: {formatTime(status.sourceTime || 0)} / {formatTime(status.duration)}</span>}<span>{analytics?.occupancy?.count ?? '--'} personas</span><span>Máximo: {analytics?.occupancy?.peak ?? '--'}</span></div>
            {zones.map((z: any) => <p key={z.id}>{z.name}: {z.count} personas · máximo {z.peak}{z.alert ? ' · Concentración sostenida' : ''}</p>)}
            {analytics?.dense && <p>Puntos P2PNet: {analytics.dense.count} · muestra {formatTime(analytics.dense.t)}</p>}
            {analytics?.crossings?.map((line: any) => <p key={line.id}>{line.name}: {line.entries} entradas · {line.exits} salidas</p>)}
          </article>;
        })}</div>
      </section>
    </>}
  </div>;
}
