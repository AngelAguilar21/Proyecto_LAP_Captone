import { useEffect, useMemo, useState } from 'react';
import type { Session } from './useSession';
import './insights-panel.css';

type Local = { local_id: string; nombre: string; negocio_id: string | null; categoria: string; exposicion: number; visitas: number; captados: number; tasa_captacion: number | null; permanencia_media_s: number | null; retornos: number };
type ZonaMetrica = { zone_id: number; nombre: string; tipo: string; visitantes: number; visitas: number; exposicion: number; colas: number; permanencia_media_s: number | null; ocupacion_max: number; densidad_max: number | null; segundos_congestion: number | null };
type Ruta = { secuencia: string[]; frecuencia: number; porcentaje: number };
type Arista = { desde_nombre: string; hacia_nombre: string; personas: number };
type Congestion = { nombre: string; inicio_s: number; fin_s: number; personas_max: number; densidad_max: number | null; velocidad_media: number | null };
type Relacion = { n: number; motivo: string | null; limite: string; captacion_mediana?: number | null; correlaciones: { exposicion_ventas: number | null; visitas_ventas: number | null } | null; horas: { fecha: string; hora: number; exposicion: number; visitas: number; captacion: number | null; conversion: number | null; ventas: number }[] };
type Insights = {
  sesion: string; unidad: string; aviso: string[]; limites: string[]; dataset: string; identidad: { engine?: string; finalizada?: boolean; geometria?: string };
  plano: { ancho: number; alto: number };
  resumen: { personas: number; posiciones: number; zonas: number; locales: number; ajustadas_al_piso: number; eventos: Record<string, number>; con_fecha: boolean };
  kde: { celda: number; columnas: number; filas: number; ocupacion: number[]; visitantes: number[] };
  zonas_definidas: { id: number; nombre: string; tipo: string; vertices: number[][] }[];
  locales: Local[]; zonas: ZonaMetrica[]; rutas: Ruta[]; origen_destino: Arista[]; congestion: Congestion[];
  ventas?: Record<string, Relacion>;
};
type Run = { session: string; created: string; end: number; status: string; module: string; cameras: { id: string }[]; identity?: { engine?: string; personas?: number } };

const pct = (v: number | null | undefined) => v == null ? 'No disponible' : `${v.toFixed(1)} %`;
const seg = (v: number | null | undefined) => v == null ? '—' : `${v.toFixed(1)} s`;
const TIPOS: Record<string, string> = { INTERIOR: 'Interior de local', FRONTAGE: 'Frente de local', COLA: 'Cola', ZONA: 'Zona' };

function Calor({ data, modo }: { data: Insights; modo: 'ocupacion' | 'visitantes' }) {
  const { kde, plano } = data;
  const valores = modo === 'ocupacion' ? kde.ocupacion : kde.visitantes;
  const maximo = Math.max(...valores, 1e-9);
  if (!kde.columnas || !valores.length) return <p className="subtle">No hay posiciones suficientes para el mapa de calor.</p>;
  return <svg className="insights-heat" viewBox={`0 0 ${plano.ancho} ${plano.alto}`} role="img" aria-label="Mapa de calor del plano">
    <rect x="0" y="0" width={plano.ancho} height={plano.alto} className="heat-floor" />
    {valores.map((v, i) => v > maximo * 0.04 && <rect key={i} x={(i % kde.columnas) * kde.celda} y={Math.floor(i / kde.columnas) * kde.celda} width={kde.celda} height={kde.celda} fill="#ff6a1a" opacity={Math.min(0.85, (v / maximo) * 0.85)} />)}
    {data.zonas_definidas.map(z => <polygon key={z.id} points={z.vertices.map(p => p.join(',')).join(' ')} className={`heat-zone zone-${z.tipo.toLowerCase()}`}><title>{z.nombre} · {TIPOS[z.tipo] || z.tipo}</title></polygon>)}
  </svg>;
}

export default function InsightsPanel({ session }: { session: Session }) {
  const headers = { 'X-LAP-Session': localStorage.getItem('aero.session') || '' };
  const [runs, setRuns] = useState<Run[]>([]);
  const [sid, setSid] = useState('');
  const [data, setData] = useState<Insights | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'negocios' | 'calor' | 'rutas' | 'congestion'>('negocios');
  const [modo, setModo] = useState<'ocupacion' | 'visitantes'>('ocupacion');

  useEffect(() => {
    let alive = true;
    void fetch('/api/replay/history', { headers }).then(r => r.ok ? r.json() : []).then((rows: Run[]) => {
      if (!alive) return;
      const done = rows.filter(r => r.end > 0 && r.status !== 'running');
      setRuns(done);
      setSid(current => current || done[0]?.session || '');
    }).catch(() => undefined);
    return () => { alive = false; };
  }, [session.projects.active, session.state.status]);

  async function load(id: string) {
    if (!id) return;
    setLoading(true); setError('');
    try {
      const response = await fetch(`/api/insights?session=${encodeURIComponent(id)}`, { headers });
      const body = await response.json();
      if (response.status === 404) { setData(null); setError(body.error); return; }
      if (!response.ok) throw Error(body.error);
      setData(body);
    } catch (cause) { setData(null); setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los insights.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(sid); }, [sid]);

  async function compute() {
    await session.action(async () => { await session.post('insights/compute', { session: sid }); await load(sid); session.setNotice('Insights calculados con las zonas y los negocios actuales.'); });
  }

  const totales = useMemo(() => {
    const l = data?.locales || [];
    const exp = l.reduce((n, x) => n + x.exposicion, 0), cap = l.reduce((n, x) => n + x.captados, 0);
    return { exposicion: exp, visitas: l.reduce((n, x) => n + x.visitas, 0), captacion: exp ? 100 * cap / exp : null };
  }, [data]);
  const maxOD = Math.max(...(data?.origen_destino || []).map(a => a.personas), 1);

  return <section className="insights-panel">
    <div className="page-heading">
      <div><span className="eyebrow">INSIGHTS ESPACIALES</span><h1>Exposición y captación por negocio</h1>
        <p>Calculados sobre una grabación ya procesada: quién pasó por el frente de cada local, quién entró, cuánto se quedó y por dónde se mueve la gente. IDs anónimos de sesión, sin identificar a nadie.</p></div>
      <div className="insights-actions">
        <label>Sesión<select value={sid} onChange={e => setSid(e.target.value)}>{runs.map(r => <option key={r.session} value={r.session}>{new Date(r.created).toLocaleString('es-PE')} · {r.cameras.length} cám. · {r.identity?.engine === 'reid_v2' ? 'identidad nueva' : 'identidad estable'}</option>)}{!runs.length && <option value="">Sin sesiones guardadas</option>}</select></label>
        <button disabled={!sid || session.busy} onClick={() => void compute()}>{data ? 'Recalcular' : 'Calcular insights'}</button>
      </div>
    </div>
    {error && <div className="notice" role="status">{error}</div>}
    {loading && <p className="subtle">Cargando…</p>}
    {data && <>
      {data.aviso.map(a => <div key={a} className="notice error" role="alert">{a}</div>)}
      <div className="insights-kpis">
        <article><span>Personas con trayectoria</span><strong>{data.resumen.personas}</strong></article>
        <article><span>Expuestos a un local</span><strong>{totales.exposicion}</strong></article>
        <article><span>Entraron a un local</span><strong>{totales.visitas}</strong></article>
        <article><span>Captación global</span><strong>{pct(totales.captacion)}</strong></article>
        <article><span>Identidad</span><strong>{data.identidad?.engine === 'reid_v2' ? 'Nueva' : 'Estable'}</strong></article>
      </div>
      <nav className="insights-tabs" aria-label="Vistas de insights">{([['negocios', 'Negocios'], ['calor', 'Mapa de calor'], ['rutas', 'Rutas y flujos'], ['congestion', 'Congestión y colas']] as const).map(([id, label]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>)}</nav>

      {tab === 'negocios' && <>
        <section className="aero-panel"><div className="panel-heading"><h2>Locales del plano</h2><span className="pill blue">{data.resumen.locales} locales</span></div>
          {!data.locales.length ? <p className="subtle">No hay locales dibujados en el plano. Dibuja zonas de tipo comercial para medir exposición y captación.</p> :
            <div className="table-scroll"><table><thead><tr><th>Local</th><th>Exposición</th><th>Visitas</th><th>Captación</th><th>Permanencia media</th><th>Retornos</th><th>Vinculado a negocio</th></tr></thead>
              <tbody>{data.locales.map(l => <tr key={l.local_id}><td>{l.nombre}</td><td>{l.exposicion}</td><td>{l.visitas}</td><td>{pct(l.tasa_captacion)}</td><td>{seg(l.permanencia_media_s)}</td><td>{l.retornos}</td><td>{l.negocio_id ? 'Sí' : 'No (solo plano)'}</td></tr>)}</tbody></table></div>}
          <p className="subtle">Exposición: personas que cruzaron la franja de frente del local. Captación: de ellas, las que luego entraron. Sin expuestos la tasa no está disponible.</p>
        </section>
        <section className="aero-panel"><div className="panel-heading"><h2>Relación con las ventas por hora</h2></div>
          {!Object.keys(data.ventas || {}).length ? <p className="subtle">Ningún local está vinculado a un negocio con ventas. Vincula el local a un negocio (su ubicación debe quedar dentro del local o llevar el mismo nombre).</p> :
            Object.entries(data.ventas || {}).map(([id, r]) => <article key={id} className="insights-sales"><h3>{data.locales.find(l => l.negocio_id === id)?.nombre || id}</h3>
              {r.correlaciones ? <p>{r.n} horas completas · captación mediana {pct(r.captacion_mediana)} · correlación de rangos exposición-ventas <b>{r.correlaciones.exposicion_ventas ?? 'n/d'}</b>, visitas-ventas <b>{r.correlaciones.visitas_ventas ?? 'n/d'}</b></p> : <p>{r.motivo}</p>}
              <small>{r.limite}</small></article>)}
        </section></>}

      {tab === 'calor' && <section className="aero-panel"><div className="panel-heading"><h2>Dónde se concentra la gente</h2>
        <div className="segmented">{(['ocupacion', 'visitantes'] as const).map(m => <button key={m} className={modo === m ? 'active' : ''} onClick={() => setModo(m)}>{m === 'ocupacion' ? 'Tiempo acumulado' : 'Personas distintas'}</button>)}</div></div>
        <Calor data={data} modo={modo} />
        <p className="subtle">Estimación de densidad por kernel gaussiano sobre las posiciones consolidadas ({data.kde.columnas}×{data.kde.filas} celdas de {data.kde.celda} {data.unidad === 'meters' ? 'm' : 'u'}). Los contornos son las zonas del plano.</p></section>}

      {tab === 'rutas' && <div className="insights-two">
        <section className="aero-panel"><div className="panel-heading"><h2>Rutas frecuentes</h2></div>
          {!data.rutas.length ? <p className="subtle">Ninguna secuencia de zonas se repite en suficientes personas.</p> :
            <ol className="insights-routes">{data.rutas.map((r, i) => <li key={i}><span>{r.secuencia.join(' → ')}</span><b>{r.frecuencia} personas · {r.porcentaje} %</b></li>)}</ol>}</section>
        <section className="aero-panel"><div className="panel-heading"><h2>Flujos entre zonas</h2></div>
          {!data.origen_destino.length ? <p className="subtle">No hay pasos directos entre zonas.</p> :
            <ul className="insights-od">{data.origen_destino.slice(0, 20).map((a, i) => <li key={i}><span>{a.desde_nombre} → {a.hacia_nombre}</span><i style={{ width: `${(a.personas / maxOD) * 100}%` }} /><b>{a.personas}</b></li>)}</ul>}</section>
      </div>}

      {tab === 'congestion' && <section className="aero-panel"><div className="panel-heading"><h2>Congestión y colas</h2></div>
        {!data.congestion.length ? <p className="subtle">No hubo episodios de congestión sostenida (varias personas, densidad alta y movimiento lento).</p> :
          <div className="table-scroll"><table><thead><tr><th>Zona</th><th>Desde</th><th>Hasta</th><th>Personas máx.</th><th>Densidad máx.</th><th>Velocidad media</th></tr></thead><tbody>{data.congestion.map((c, i) => <tr key={i}><td>{c.nombre}</td><td>{c.inicio_s.toFixed(0)} s</td><td>{c.fin_s.toFixed(0)} s</td><td>{c.personas_max}</td><td>{c.densidad_max ?? '—'}</td><td>{c.velocidad_media ?? '—'}</td></tr>)}</tbody></table></div>}
        <div className="table-scroll"><table><thead><tr><th>Zona</th><th>Tipo</th><th>Visitantes</th><th>Permanencia media</th><th>Ocupación máx.</th><th>Colas</th></tr></thead><tbody>{data.zonas.map(z => <tr key={z.zone_id}><td>{z.nombre}</td><td>{TIPOS[z.tipo] || z.tipo}</td><td>{z.visitantes}</td><td>{seg(z.permanencia_media_s)}</td><td>{z.ocupacion_max}</td><td>{z.colas}</td></tr>)}</tbody></table></div>
      </section>}

      <section className="aero-panel insights-limits"><div className="panel-heading"><h2>Cómo leer estos resultados</h2></div>
        <ul>{data.limites.map(l => <li key={l}>{l}</li>)}<li>Eventos detectados: {Object.entries(data.resumen.eventos).map(([k, v]) => `${k} ${v}`).join(' · ') || 'ninguno'}.</li>{!data.resumen.con_fecha && <li>La grabación no declara fecha de inicio: no se relaciona con las ventas por hora.</li>}</ul>
      </section>
    </>}
  </section>;
}
