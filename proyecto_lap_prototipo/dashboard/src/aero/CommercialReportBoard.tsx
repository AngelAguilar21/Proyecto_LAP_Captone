import type { Config, SessionState } from './types';
import { formatTime } from './types';
import Icon from './Icon';
import './commercial-report.css';

type Zone = SessionState['analytics']['zones'][number];
type Advisory = { tag: string; tone: 'amber' | 'red' | 'blue'; text: string };

function median(values: number[]) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function verdictFor(zone: Zone, medianSeconds: number, medianVisits: number) {
  if (zone.alert) return 'Aglomeración recurrente';
  const highTraffic = (zone.visits || 0) >= medianVisits;
  const highDwell = (zone.seconds || 0) >= medianSeconds;
  if (highTraffic && highDwell) return 'Tráfico y permanencia altos';
  if (highTraffic) return 'Zona de paso';
  if (highDwell) return 'Punto de permanencia';
  return 'Tráfico moderado';
}

function confidenceFor(visits: number | undefined, maxVisits: number) {
  const v = visits || 0;
  if (!maxVisits) return { label: 'Sin muestra', tone: 'low' as const };
  const ratio = v / maxVisits;
  if (v < 5) return { label: 'Muestra baja', tone: 'low' as const };
  if (ratio >= 0.5) return { label: 'Muestra sólida', tone: 'high' as const };
  return { label: 'Muestra parcial', tone: 'mid' as const };
}

export default function CommercialReportBoard({ config, state, demo }: { config: Config; state: SessionState; demo: boolean }) {
  const zones = state.analytics.zones || [];
  const medianSeconds = median(zones.map(z => z.seconds || 0));
  const medianVisits = median(zones.map(z => z.visits || 0));
  const ranking = [...zones].sort((a, b) => (b.seconds || 0) - (a.seconds || 0));
  const top = ranking[0];
  const maxSeconds = Math.max(1, ...ranking.map(z => z.seconds || 0));
  const maxVisits = Math.max(0, ...ranking.map(z => z.visits || 0));

  const series = state.series || [];
  const peakSample = series.reduce((a, b) => (b.count > (a?.count ?? -1) ? b : a), series[0]);
  const peakValue = peakSample?.count ?? 0;
  const maxSeries = Math.max(1, ...series.map(s => s.count));

  const activeCameras = ['running','paused'].includes(state.status)?state.cameras.filter(c => c.status === 'live').length:Object.keys(state.cameraAnalytics||{}).length;
  const totalCameras = config.cameras.length;

  const crossings = Object.entries(state.cameraAnalytics || {}).flatMap(([cid, a]: [string, any]) =>
    (a.crossings || []).map((l: any) => ({ camera: config.cameras.find(c => c.id === cid)?.name || cid, ...l }))
  );

  const hourly = (() => {
    const bins: Record<number, { sum: number; n: number; peak: number }> = {};
    for (const s of series) {
      const h = Math.floor(s.t / 3600);
      const b = bins[h] || (bins[h] = { sum: 0, n: 0, peak: 0 });
      b.sum += s.count; b.n += 1; b.peak = Math.max(b.peak, s.count);
    }
    return Object.entries(bins).map(([h, b]) => ({ hour: +h, avg: b.sum / b.n, peak: b.peak, n: b.n })).sort((a, b) => a.hour - b.hour);
  })();
  const busiest = hourly.reduce((a, b) => (b.avg > (a?.avg ?? -1) ? b : a), hourly[0]);

  const advisories: Advisory[] = [];
  if (top && (top.seconds || 0) > 0) {
    const share = Math.round((top.seconds || 0) / (ranking.reduce((n, z) => n + (z.seconds || 0), 0) || 1) * 100);
    advisories.push({ tag: 'Oportunidad', tone: 'amber', text: `${top.name} concentra ${share}% de la permanencia total observada (${formatTime(top.seconds || 0)} persona-segundo). Primera candidata para evaluar un nuevo punto comercial o ampliar el actual, contrastando con otras temporadas y horarios antes de decidir.` });
  }
  const alertZones = zones.filter(z => z.alert);
  if (alertZones.length) {
    advisories.push({ tag: 'Riesgo', tone: 'red', text: `${alertZones.map(z => z.name).join(', ')} registra${alertZones.length === 1 ? '' : 'n'} aglomeraciones recurrentes. Antes de invertir en espacio conviene revisar señalización o flujo: una zona congestionada no siempre es rentable.` });
  }
  const passZones = zones.filter(z => (z.visits || 0) >= medianVisits && (z.seconds || 0) < medianSeconds && z !== top);
  if (passZones.length) {
    advisories.push({ tag: 'Lectura', tone: 'blue', text: `${passZones.map(z => z.name).join(', ')} tiene${passZones.length === 1 ? '' : 'n'} tráfico alto pero poca permanencia. Encaja mejor con publicidad o señalización de paso que con retail que dependa de tiempo de exposición.` });
  }
  if (totalCameras > 0 && activeCameras < totalCameras) {
    advisories.push({ tag: 'Cobertura', tone: 'blue', text: `Solo ${activeCameras} de ${totalCameras} cámaras aportaron resultados en esta sesión. Antes de comparar zonas con confianza para una decisión comercial, conviene ampliar la cobertura o repetir la medición con todas las fuentes activas.` });
  }
  if (busiest) {
    advisories.push({ tag: 'Operación', tone: 'amber', text: `La franja ${busiest.hour}:00–${String((busiest.hour + 1) % 24).padStart(2, '0')}:00 concentra el mayor promedio de personas (${busiest.avg.toFixed(1)}). Úsala para planificar personal, reposición y activaciones comerciales.` });
  }
  if ((state.totals?.meanObservedSeconds || 0) > 0) {
    advisories.push({ tag: 'Conversión', tone: 'blue', text: `La permanencia media observada es ${(state.totals?.meanObservedSeconds || 0).toFixed(1)} s. Contrástala con ventas y transacciones del mismo intervalo para distinguir tráfico de paso, interés y conversión real.` });
  }
  if (crossings.length) {
    advisories.push({ tag: 'Medición', tone: 'blue', text: 'Las entradas se calculan con líneas virtuales y pueden incluir reingresos. Para visitantes únicos, mantén cámaras sincronizadas y revisa la asociación multicámara antes de comparar negocios.' });
  }

  const live = ['running', 'paused'].includes(state.status);

  return <div className="crb">
    <div className="crb-status">
      <span className={`crb-dot${live ? ' live' : ''}`} />
      <span className="crb-status-text">{live ? 'En vivo' : 'Sesión finalizada'}</span>
      <span className="crb-status-sep" />
      <span>{state.session ? `Sesión ${state.session}` : 'Sin sesión'}</span>
      <span className="crb-status-sep" />
      <span>{state.testRun ? 'Videos de prueba' : demo ? 'Datos sintéticos' : (config.airport || 'Aeropuerto')}</span>
      <span className="crb-status-sep" />
      <span>{formatTime(state.t)} de fuente</span>
    </div>

    <h1 className="crb-headline">Ocupación y flujo de la sesión</h1>

    <div className="crb-kpis">
      <div className="crb-kpi"><span>Ocupación pico</span><strong>{peakValue}</strong><small>{series.length ? `a las ${formatTime(peakSample.t)}` : 'sin muestras'}</small></div>
      <div className="crb-kpi"><span>Zona con más tráfico</span><strong className="crb-kpi-name">{top?.name || '—'}</strong><small>{top ? `${formatTime(top.seconds || 0)} persona-seg.` : 'define zonas'}</small></div>
      <div className="crb-kpi"><span>Permanencia media</span><strong>{(state.totals?.meanObservedSeconds || 0).toFixed(1)}<small className="crb-unit">s</small></strong><small>por persona</small></div>
      <div className="crb-kpi"><span>Aglomeraciones</span><strong className={state.totals?.alerts ? 'crb-red' : ''}>{state.totals?.alerts || 0}</strong><small>episodios</small></div>
    </div>

    <div className="crb-grid">
      <section className="crb-manifest">
        <h2>Zonas por oportunidad comercial</h2>
        {!ranking.length ? <p className="crb-empty">Define zonas en el plano para obtener este ranking.</p> : <div className="crb-rows">
          {ranking.map(z => {
            const avgDwell = z.visits ? (z.seconds || 0) / z.visits : 0;
            const conf = confidenceFor(z.visits, maxVisits);
            return <div className="crb-row" key={z.name}>
              <div className="crb-row-top"><span className="crb-row-name">{z.name}</span><span className={`crb-verdict ${z.alert ? 'red' : ''}`}>{verdictFor(z, medianSeconds, medianVisits)}</span></div>
              <div className="crb-bar"><i style={{ width: `${Math.max(2, (z.seconds || 0) / maxSeconds * 100)}%` }} /></div>
              <div className="crb-row-stats">
                <span><b>{z.visits ?? '—'}</b> visitas</span>
                <span><b>{z.visits ? `${avgDwell.toFixed(0)}s` : '—'}</b> permanencia media</span>
                <span><b>{z.peak ?? '—'}</b> pico simultáneo</span>
                <span className={`crb-confidence ${conf.tone}`}>{conf.label}</span>
              </div>
            </div>;
          })}
        </div>}
      </section>

      <aside className="crb-context">
        <h2>Contexto de la medición</h2>
        <div className="crb-context-row"><Icon name="camera" size={16} /><div><span>Cobertura de cámaras</span><strong>{activeCameras} / {totalCameras} analizadas</strong></div></div>
        <div className="crb-context-row"><Icon name={config.clocksVerified ? 'check' : 'alert'} size={16} /><div><span>Sincronización entre cámaras</span><strong>{config.cameras.length > 1 ? (config.clocksVerified ? 'Verificada' : 'Sin verificar') : 'No aplica (1 cámara)'}</strong></div></div>
        <div className="crb-context-row"><Icon name="clock" size={16} /><div><span>Ventana de mayor actividad</span><strong>{busiest ? `Hora ${busiest.hour} · prom. ${busiest.avg.toFixed(1)}` : 'sin datos aún'}</strong></div></div>
        <div className="crb-context-row"><Icon name="report" size={16} /><div><span>Unidad y procedencia</span><strong>{config.unit === 'meters' ? 'Metros' : 'Unidades relativas'} · {state.testRun ? 'Plano ilustrativo' : demo ? 'Simulación' : 'Fuente real'}</strong></div></div>
      </aside>
    </div>

    <section className="crb-trace">
      <h2>Traza de ocupación</h2>
      {series.length ? <svg viewBox="0 0 1000 220" role="img" aria-label="Personas observadas a lo largo del tiempo de fuente" preserveAspectRatio="none">
        <defs><linearGradient id="crbFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ffb020" stopOpacity=".35" /><stop offset="100%" stopColor="#ffb020" stopOpacity="0" /></linearGradient></defs>
        {[0, 1, 2, 3, 4].map(i => <path key={i} d={`M40 ${20 + i * 40}H970`} stroke="#1c2733" strokeWidth="1" />)}
        <path d={`M40 195 ${series.map((s, i) => `L${40 + i / Math.max(1, series.length - 1) * 930},${195 - s.count / maxSeries * 165}`).join(' ')} L970 195Z`} fill="url(#crbFade)" stroke="none" />
        <polyline points={series.map((s, i) => `${40 + i / Math.max(1, series.length - 1) * 930},${195 - s.count / maxSeries * 165}`).join(' ')} fill="none" stroke="#ffb020" strokeWidth="2.5" />
        {series.length && <circle cx={40 + series.indexOf(peakSample) / Math.max(1, series.length - 1) * 930} cy={195 - peakValue / maxSeries * 165} r="4" fill="#ffb020" />}
        <text x="40" y="212" fill="#7d93a4" fontSize="12">{formatTime(series[0].t)}</text>
        <text x="965" y="212" fill="#7d93a4" fontSize="12" textAnchor="end">{formatTime(state.t)}</text>
      </svg> : <p className="crb-empty">La traza aparecerá al iniciar una sesión.</p>}
    </section>

    {crossings.length > 0 && <section className="crb-access">
      <h2>Tráfico por acceso</h2>
      <div className="crb-access-rows">
        {crossings.map((l, i) => <div className="crb-access-row" key={i}><span>{l.camera} / {l.name}</span><span className="crb-access-nums"><b>{l.entries}</b> entradas<i /><b>{l.exits}</b> salidas</span></div>)}
      </div>
    </section>}

    <section className="crb-advisories">
      <h2>Recomendaciones comerciales y operativas</h2>
      {advisories.length ? <div className="crb-advisory-list">{advisories.map((a, i) => <div className={`crb-advisory ${a.tone}`} key={i}><span className="crb-advisory-tag">{a.tag}</span><p>{a.text}</p></div>)}</div>
        : <p className="crb-empty">Aún no hay suficientes datos en esta sesión para generar avisos. Aparecen a medida que se observan zonas y accesos.</p>}
      <p className="crb-footnote">Estimaciones de una sesión de tracking anónimo, sin identificación personal. No sustituyen un estudio de rentabilidad; son un punto de partida para decidir dónde mirar primero.</p>
    </section>
  </div>;
}
