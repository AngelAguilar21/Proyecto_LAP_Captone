import { useState } from 'react';
import type { Session } from './useSession';
import type { CameraRoute } from './types';
import { isActive } from './types';
import './camera-routes.css';

export default function CameraRoutes({ session }: { session: Session }) {
  const c = session.config!;
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [kind, setKind] = useState<CameraRoute['kind']>('overlap');
  const [min, setMin] = useState(0);
  const [max, setMax] = useState(120);
  const [both, setBoth] = useState(true);
  const [storage, setStorage] = useState('');
  const [checking, setChecking] = useState(false);
  const [graph, setGraph] = useState<{nodes:{id:string;kind:string;name:string}[];edges:{source:string;target:string;kind:string}[];warnings:string[]} | null>(null);
  const checkGraph = async () => {
    await session.action(async () => {
      const response = await fetch('/api/spatial-graph', {headers:{'X-LAP-Session':localStorage.getItem('aero.session') || ''}});
      if (!response.ok) throw Error('No se pudo consultar el grafo del proyecto.');
      setGraph(await response.json());
    });
  };
  const checkStorage = async () => {
    setChecking(true);
    try {
      const response = await fetch('/api/storage', { headers: { 'X-LAP-Session': localStorage.getItem('aero.session') || '' }, signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error('No se pudo consultar el almacenamiento.');
      const result = await response.json();
      setStorage(`${result.connected ? 'PostgreSQL conectado' : result.configured ? 'PostgreSQL no disponible' : 'PostgreSQL sin configurar'}. ${result.archived} sesiones archivadas · ${result.pending} pendientes. ${result.operationalStorage}.`);
    } catch { setStorage('No se pudo comprobar la conexión. Reintenta cuando el servidor esté disponible.'); }
    finally { setChecking(false); }
  };
  const disabled = isActive(session.state.status) || session.busy;
  const routes = c.cameraRoutes;
  const label = (id: string) => c.cameras.find(x => x.id === id)?.name || id;
  const add = () => {
    const edges: CameraRoute[] = [{ from, to, kind, minSeconds: kind === 'overlap' ? 0 : min, maxSeconds: max }];
    if (both) edges.push({ ...edges[0], from: to, to: from });
    const next = [...(routes || []).filter(r => !edges.some(e => e.from === r.from && e.to === r.to)), ...edges];
    void session.action(async () => { await session.save({ ...c, cameraRoutes: next }); });
  };
  return <section className="aero-panel camera-routes">
    <div className="panel-heading"><div><h2>Continuidad entre cámaras</h2><p>Define por dónde puede pasar una persona. Estar cerca en el plano no basta.</p></div></div>
    {!c.clocksVerified && <p role="status" className="routes-warning">Falta sincronizar las cámaras en Homografía y cámaras relacionadas. Las rutas se guardan, pero no se unen IDs hasta verificar los tiempos.</p>}
    {routes === undefined && <p>Se están usando las relaciones existentes. Al guardar la primera ruta, esta lista pasa a definir las conexiones del proyecto.</p>}
    <fieldset disabled={disabled} className="routes-fields"><legend>Añadir o reemplazar conexión</legend>
      <label>Desde<select value={from} onChange={e => setFrom(e.target.value)}><option value="">Elegir cámara</option>{c.cameras.map(x => <option key={x.id} value={x.id}>{x.name || x.id}</option>)}</select></label>
      <label>Hacia<select value={to} onChange={e => setTo(e.target.value)}><option value="">Elegir cámara</option>{c.cameras.filter(x => x.id !== from).map(x => <option key={x.id} value={x.id}>{x.name || x.id}</option>)}</select></label>
      <label>Relación<select value={kind} onChange={e => setKind(e.target.value as CameraRoute['kind'])}><option value="overlap">Comparten parte de la vista</option><option value="transition">Se pasa de una vista a otra</option></select></label>
      {kind === 'transition' && <label>Tiempo mínimo (s)<input type="number" min={0} max={3600} value={min} onChange={e => setMin(+e.target.value)} /></label>}
      <label>Tiempo máximo (s)<input type="number" min={1} max={3600} value={max} onChange={e => setMax(+e.target.value)} /></label>
      <label className="routes-check"><input type="checkbox" checked={both} onChange={e => setBoth(e.target.checked)} />En ambos sentidos</label>
      <button className="primary" disabled={!from || !to || from === to || max <= 0 || max > 3600 || min < 0 || (kind === 'transition' && min > max)} onClick={add}>Guardar conexión</button>
    </fieldset>
    <ul className="routes-list">{routes?.map(r => <li key={`${r.from}-${r.to}`}><div><strong>{label(r.from)} → {label(r.to)}</strong><span>{r.kind === 'overlap' ? 'Vista compartida' : 'Tránsito'} · {r.minSeconds}–{r.maxSeconds} s</span></div><button disabled={disabled} onClick={() => void session.action(async () => { await session.save({ ...c, cameraRoutes: routes.filter(x => x !== r) }); })} aria-label={`Eliminar conexión ${label(r.from)} a ${label(r.to)}`}>Eliminar</button></li>)}</ul>
    {routes?.length === 0 && <p>Sin conexiones: cada cámara mantiene sus propios IDs.</p>}
    <details><summary>Procesamiento del equipo</summary><div className="routes-fields">
      <label>Modelo de apariencia<select disabled={disabled} value={c.reidModel || 'osnet.onnx'} onChange={e => void session.action(async () => { await session.save({ ...c, reidModel: e.target.value as 'osnet.onnx' | 'osnet_ain_msmt17.onnx' }); })}><option value="osnet.onnx">OSNet ligero · recomendado en CPU</option><option value="osnet_ain_msmt17.onnx">OSNet-AIN · evaluación experimental</option></select><small>AIN requiere pesos adicionales y consume más CPU. Sus coincidencias deben revisarse antes de adoptarlo.</small></label>
      <label>Detección<select disabled={disabled} value={c.hardware || 'auto'} onChange={e => void session.action(async () => { await session.save({ ...c, hardware: e.target.value as 'auto' | 'cpu' | 'gpu' }); })}><option value="auto">Automático (recomendado)</option><option value="cpu">CPU</option><option value="gpu">GPU NVIDIA si está disponible</option></select></label>
      <label>Apariencia de personas<select disabled={disabled} value={c.reidProvider || 'auto'} onChange={e => void session.action(async () => { await session.save({ ...c, reidProvider: e.target.value as 'auto' | 'cpu' | 'cuda' | 'openvino' | 'directml' }); })}><option value="auto">Automático</option><option value="cpu">CPU</option><option value="cuda">NVIDIA / CUDA</option><option value="openvino">Intel / OpenVINO</option><option value="directml">Windows / DirectML</option></select></label>
    </div><p>La aceleración requiere el controlador y el runtime compatibles. Si faltan, se utiliza CPU. Cambiar esta opción no instala controladores.</p></details>
    {session.saveError && <p role="alert">{session.saveError}</p>}
    <details><summary>Cámaras, zonas y accesos vinculados</summary><p>El grafo se construye con tu configuración. Las rutas limitan las cámaras candidatas; las puertas vinculan el conteo con un negocio. Compartir negocio no significa que dos cámaras vean a la misma persona.</p><button onClick={() => void checkGraph()}>Consultar relaciones guardadas</button>
      {graph && <><p>{graph.nodes.length} entidades · {graph.edges.length} relaciones</p><ul className="routes-list">{graph.edges.filter(e => e.kind === 'access_to').map(e => {
        const door = graph.nodes.find(n => n.id === e.source); const business = graph.nodes.find(n => n.id === e.target);
        return <li key={e.source + e.target}>{door?.name} → {business?.name}</li>;
      })}</ul>{graph.warnings.map(w => <p role="status" key={w}>{w}</p>)}</>}
    </details>
    <details><summary>Almacenamiento de resultados</summary><p>Las sesiones terminadas se archivan en PostgreSQL/PostGIS. Si la base no responde, el sistema conserva los archivos y reintenta enviarlos.</p><button disabled={checking} onClick={() => void checkStorage()}>{checking ? 'Comprobando…' : 'Comprobar almacenamiento'}</button><p role="status">{storage}</p></details>
  </section>;
}
