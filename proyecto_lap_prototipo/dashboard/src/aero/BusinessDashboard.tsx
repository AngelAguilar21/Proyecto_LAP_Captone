import type { Config, SessionState } from './types';
import { formatTime } from './types';
import Icon from './Icon';

type Zone = SessionState['analytics']['zones'][number];
type Verdict = { label: string; tone: 'good' | 'warn' | 'muted' };

function verdictFor(zone: Zone, medianSeconds: number, medianVisits: number): Verdict {
  if (zone.alert) return { label: 'Aglomeración recurrente · revisar flujo', tone: 'warn' };
  const highTraffic = (zone.visits || 0) >= medianVisits;
  const highDwell = (zone.seconds || 0) >= medianSeconds;
  if (highTraffic && highDwell) return { label: 'Mayor tráfico y permanencia', tone: 'good' };
  if (highTraffic) return { label: 'Zona de paso · poca permanencia', tone: 'muted' };
  if (highDwell) return { label: 'Punto de permanencia · poco tráfico', tone: 'muted' };
  return { label: 'Tráfico moderado', tone: 'muted' };
}

function median(values: number[]) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export default function BusinessDashboard({ config, state, demo }: { config: Config; state: SessionState; demo: boolean }) {
  const zones = state.analytics.zones || [];
  const medianSeconds = median(zones.map(z => z.seconds || 0));
  const medianVisits = median(zones.map(z => z.visits || 0));
  const ranking = [...zones].sort((a, b) => (b.seconds || 0) - (a.seconds || 0));
  const top = ranking[0];

  const series = state.series || [];
  const peakSample = series.reduce((a, b) => (b.count > (a?.count ?? -1) ? b : a), series[0]);
  const peakValue = peakSample?.count ?? 0;
  const maxSeries = Math.max(1, ...series.map(s => s.count));

  const activeCameras = state.cameras.filter(c => c.status === 'live').length;
  const totalCameras = config.cameras.length;

  const crossings = Object.entries(state.cameraAnalytics || {}).flatMap(([cid, a]: [string, any]) =>
    (a.crossings || []).map((l: any) => ({ camera: config.cameras.find(c => c.id === cid)?.name || cid, ...l }))
  );
  const totalEntries = crossings.reduce((n, l) => n + (l.entries || 0), 0);

  const recommendations: string[] = [];
  if (top && (top.seconds || 0) > 0) {
    recommendations.push(`${top.name} concentra la mayor permanencia acumulada de la sesión (${formatTime(top.seconds || 0)} persona-segundo). Es la primera candidata para evaluar un nuevo punto comercial o ampliar el actual, siempre contrastando con temporadas y horarios distintos antes de decidir.`);
  }
  const alertZones = zones.filter(z => z.alert);
  if (alertZones.length) {
    recommendations.push(`${alertZones.map(z => z.name).join(', ')} registra${alertZones.length === 1 ? '' : 'n'} aglomeraciones recurrentes. Antes de invertir en espacio, conviene revisar señalización o flujo: una zona congestionada no siempre es una zona rentable.`);
  }
  const passZones = zones.filter(z => (z.visits || 0) >= medianVisits && (z.seconds || 0) < medianSeconds && z !== top);
  if (passZones.length) {
    recommendations.push(`${passZones.map(z => z.name).join(', ')} tiene${passZones.length === 1 ? '' : 'n'} tráfico alto pero poca permanencia. Encaja mejor con publicidad o señalización de paso que con retail que dependa de tiempo de exposición.`);
  }
  if (totalCameras > 0 && activeCameras < totalCameras) {
    recommendations.push(`Solo ${activeCameras} de ${totalCameras} cámaras están activas en esta sesión. Antes de comparar zonas con confianza para una decisión comercial, conviene ampliar la cobertura o repetir la medición con todas las fuentes activas.`);
  }

  return <div className="business-dashboard">
    <div className="page-heading">
      <div>
        <span className="eyebrow">INTELIGENCIA COMERCIAL · {demo ? 'DEMOSTRACIÓN' : (config.airport || 'AEROPUERTO').toUpperCase()}</span>
        <h1>Dónde está la gente, y qué hacer con eso</h1>
        <p>Lectura pensada para decisiones comerciales y operativas: qué zonas concentran tráfico y permanencia, dónde hay riesgo de aglomeración, y qué conviene revisar antes de actuar.</p>
      </div>
    </div>

    <div className="metrics-row">
      <article className="metric-card"><Icon name="people" size={25} /><div><span>Ocupación pico</span><strong className="text-blue">{peakValue}</strong><small>{series.length ? `a las ${formatTime(peakSample.t)}` : 'sin muestras aún'}</small></div></article>
      <article className="metric-card"><Icon name="pin" size={25} /><div><span>Zona con más tráfico</span><strong className="text-blue">{top?.name || '—'}</strong><small>{top ? `${formatTime(top.seconds || 0)} persona-seg. acumulados` : 'define zonas en el plano'}</small></div></article>
      <article className="metric-card"><Icon name="clock" size={25} /><div><span>Permanencia media</span><strong className="text-blue">{(state.totals?.meanObservedSeconds || 0).toFixed(1)} s</strong><small>por persona observada</small></div></article>
      <article className="metric-card"><Icon name="alert" size={25} /><div><span>Aglomeraciones</span><strong className={state.totals?.alerts ? 'text-red' : 'text-green'}>{state.totals?.alerts || 0}</strong><small>episodios en la sesión</small></div></article>
    </div>

    <section className="aero-panel">
      <div className="panel-heading"><div><h2>Zonas ordenadas por oportunidad comercial</h2><p className="subtle">Permanencia total = cuánta gente estuvo, por cuánto tiempo. No es lo mismo que tráfico de paso.</p></div></div>
      {!ranking.length ? <p className="empty-text">Define zonas en el plano para obtener este ranking. Las zonas se configuran en Zonas del plano.</p> :
        <table><thead><tr><th>Zona</th><th>Visitas</th><th>Permanencia media</th><th>Pico simultáneo</th><th>Lectura</th></tr></thead><tbody>
          {ranking.map(z => { const v = verdictFor(z, medianSeconds, medianVisits); const avgDwell = z.visits ? (z.seconds || 0) / z.visits : 0;
            return <tr key={z.name}><td>{z.name}</td><td>{z.visits ?? '—'}</td><td>{z.visits ? `${avgDwell.toFixed(0)} s` : '—'}</td><td>{z.peak ?? '—'}</td><td><span className={`pill ${v.tone === 'good' ? 'good' : v.tone === 'warn' ? 'warn' : 'muted'}`}>{v.label}</span></td></tr>; })}
        </tbody></table>}
    </section>

    <section className="aero-panel trend-panel">
      <div className="panel-heading"><div><h2>Evolución de la ocupación</h2><p className="subtle">Útil para dotación de personal por franja horaria y planificación estacional.</p></div></div>
      <div className="trend-chart">
        {series.length ? <svg viewBox="0 0 1000 180" role="img" aria-label="Personas observadas a lo largo del tiempo de fuente">
          <path d="M20 10V155H980" stroke="#e4e0d5" fill="none" />
          {[0, 1, 2, 3].map(i => <path key={i} d={`M20 ${20 + i * 40}H980`} stroke="#f0ede3" strokeDasharray="3 5" />)}
          <polyline points={series.map((s, i) => `${20 + i / Math.max(1, series.length - 1) * 950},${150 - s.count / maxSeries * 125}`).join(' ')} fill="none" stroke="#1f6fb2" strokeWidth="2.5" />
          <text x="20" y="174" fill="#6b6f74" fontSize="11">{formatTime(series[0].t)}</text>
          <text x="930" y="174" fill="#6b6f74" fontSize="11">{formatTime(state.t)}</text>
        </svg> : <div className="inline-empty"><Icon name="chart" size={28} /><p>El gráfico aparecerá al iniciar una sesión.</p></div>}
      </div>
    </section>

    {crossings.length > 0 && <section className="aero-panel">
      <div className="panel-heading"><div><h2>Tráfico por acceso</h2><p className="subtle">Cruces confirmados del exterior al interior. Útil para medir afluencia real por puerta o pasillo, no visitantes únicos.</p></div><span className="pill blue">{totalEntries} entradas totales</span></div>
      <table><thead><tr><th>Cámara / acceso</th><th>Entradas</th><th>Salidas</th><th>Último cruce</th></tr></thead><tbody>
        {crossings.map((l, i) => <tr key={i}><td>{l.camera} / {l.name}</td><td>{l.entries}</td><td>{l.exits}</td><td>{l.lastCrossing == null ? '—' : formatTime(l.lastCrossing)}</td></tr>)}
      </tbody></table>
    </section>}

    <aside className="business-note">
      <Icon name="shield" size={25} />
      <h3>Recomendaciones para LAP</h3>
      {recommendations.length ? <ul>{recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul> : <p>Aún no hay suficientes datos en esta sesión para generar recomendaciones. Estas aparecen a medida que se observan zonas y accesos.</p>}
      <p className="subtle">Estimaciones de una sesión de tracking anónimo, sin identificación personal. No sustituyen un estudio de rentabilidad; son un punto de partida para decidir dónde mirar primero.</p>
    </aside>
  </div>;
}
