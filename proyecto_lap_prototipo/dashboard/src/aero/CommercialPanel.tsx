import { useEffect, useMemo, useState } from 'react';
import type { Session } from './useSession';
import './commercial-panel.css';

type Forecast = { estimate: number | null; days: number; reason: string; range?: number[]; confidence?: string; expectedEntries?: number | null; target?: string };
type HourRow = { hour: number; entries: number; exits: number; coverage: number; sales: number | null; transactions: number | null; estimate: number | null; confidence: string };
type Row = { id: string; name: string; empresa: string; accesses: number; entries: number | null; sales: number | null; transactions: number | null; conversion: number | null; forecast: Forecast; nextForecast: Forecast; hourly: HourRow[]; incidents: { id: string; start: string; duration: number; peak: number; sales: number | null; baseline: number | null; differencePercent: number | null; sampleDays: number; scope: string }[]; bags: { exits: number; matched: number; changed: number; unmatched: number; coverage: number | null } };
type Company = { name: string; businesses: number; entries: number; sales: number | null; estimate: number | null; transactions: number | null; conversion: number | null };
type Result = { date: string; hour: number; dataset: string; empresa: string | null; empresas: Company[]; businesses: Row[]; imports: { id: string; name: string; rows: number; created: string }[] };

const money = (value: number | null | undefined) => value == null ? 'Sin datos' : new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 }).format(value);
const hourLabel = (hour: number) => `${String(hour).padStart(2, '0')}:00–${String((hour + 1) % 24).padStart(2, '0')}:00`;
const confidenceLabel = (value?: string) => value === 'alta' ? 'Confianza alta' : value === 'media' ? 'Confianza media' : 'Muestra baja';

export default function CommercialPanel({ session }: { session: Session }) {
  const params = new URLSearchParams(window.location.search);
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const [tab, setTab] = useState<'sales' | 'forecast' | 'incidents' | 'bags'>('sales');
  const [dataset, setDataset] = useState(params.get('dataset') === 'demo' ? 'demo' : 'real');
  const [date, setDate] = useState(params.get('date') || today);
  const [hour, setHour] = useState(params.has('hour') ? Number(params.get('hour')) : Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Lima', hour: 'numeric', hourCycle: 'h23' }).format(new Date())));
  const [empresa, setEmpresa] = useState(params.get('empresa') || '');
  const [data, setData] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [csv, setCsv] = useState('');
  const [filename, setFilename] = useState('');
  const [validation, setValidation] = useState<{ rows: number; errors: string[]; imported: boolean } | null>(null);
  const [business, setBusiness] = useState('');
  const [recordingDate, setRecordingDate] = useState(session.config?.recordingStartedAt || '');
  const headers = { 'X-LAP-Session': localStorage.getItem('aero.session') || '' };

  useEffect(() => setRecordingDate(session.config?.recordingStartedAt || ''), [session.config?.recordingStartedAt, session.projects.active]);
  const query = `dataset=${encodeURIComponent(dataset)}&date=${encodeURIComponent(date)}&hour=${hour}${empresa ? `&empresa=${encodeURIComponent(empresa)}` : ''}`;
  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(`/api/commercial?${query}`, { headers, signal: controller.signal });
        const next = await response.json();
        if (!response.ok) throw Error(next.error);
        if (alive) { setData(next); setError(''); }
      } catch (cause) {
        if (alive) setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los datos comerciales.');
      }
    };
    void load();
    const timer = setInterval(() => void load(), 5000);
    return () => { alive = false; controller.abort(); clearInterval(timer); };
  }, [query, refresh, session.projects.active]);

  async function openSavedTest() {
    await session.action(async () => {
      const response = await fetch('/api/commercial/sample', { headers });
      const saved = await response.json();
      if (!response.ok) throw Error(saved.error);
      setDataset('demo'); setDate(saved.date); setHour(saved.hour); setEmpresa(saved.empresa || ''); setBusiness(saved.businessId || ''); setTab('forecast');
    });
  }
  async function download(path: string, name: string) {
    await session.action(async () => {
      const response = await fetch(path, { headers });
      if (!response.ok) throw Error('No se pudo descargar el archivo.');
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
    });
  }
  async function upload(preview: boolean) {
    await session.action(async () => {
      const result = await session.post('commercial/import', { csv, name: filename, dataset, preview, projectId: session.projects.active });
      setValidation(result);
      if (result.imported) { setRefresh(value => value + 1); setCsv(''); session.setNotice('Ventas importadas sin sobrescribir datos existentes.'); }
    });
  }

  async function generateDemo() {
    await session.action(async () => {
      const result = await session.post('commercial/simulate', { days: 28, projectId: session.projects.active });
      setDataset('demo');
      setDate(result.end);
      setHour(12);
      setEmpresa('');
      setBusiness('');
      setRefresh(value => value + 1);
      session.setNotice(`Datos sintéticos generados: ${result.businesses} negocios y ${result.days} días horarios.`);
    });
  }

  const companies = data?.empresas || [];
  const rows = (data?.businesses || []).filter(row => !business || row.id === business);
  const selectedCompany = companies.find(item => item.name === empresa);
  const totals = useMemo(() => ({
    entries: rows.reduce((total, row) => total + (row.entries || 0), 0),
    sales: rows.some(row => row.sales != null) ? rows.reduce((total, row) => total + (row.sales || 0), 0) : null,
    estimate: rows.some(row => row.forecast.estimate != null) ? rows.reduce((total, row) => total + (row.forecast.estimate || 0), 0) : null,
    transactions: rows.some(row => row.transactions != null) ? rows.reduce((total, row) => total + (row.transactions || 0), 0) : null,
  }), [rows]);
  const conversion = totals.transactions != null && totals.entries > 0 ? `${(totals.transactions / totals.entries * 100).toFixed(1)}%` : 'Sin POS';
  const hourly = useMemo(() => {
    const grouped = new Map<number, { hour: number; entries: number; sales: number; estimate: number; hasSales: boolean; hasEstimate: boolean }>();
    rows.forEach(row => row.hourly.forEach(item => {
      const current = grouped.get(item.hour) || { hour: item.hour, entries: 0, sales: 0, estimate: 0, hasSales: false, hasEstimate: false };
      current.entries += item.entries; if (item.sales != null) { current.sales += item.sales; current.hasSales = true; } if (item.estimate != null) { current.estimate += item.estimate; current.hasEstimate = true; } grouped.set(item.hour, current);
    }));
    return [...grouped.values()].sort((a, b) => a.hour - b.hour);
  }, [rows]);
  const recommendations = useMemo(() => {
    const messages: string[] = [];
    const busiest = [...rows].sort((a, b) => (b.entries || 0) - (a.entries || 0))[0];
    if (busiest && (busiest.entries || 0) > 0) messages.push(`${busiest.name} concentra el mayor aforo de la hora seleccionada (${busiest.entries} entradas). Prioriza personal, inventario y promociones en esta franja.`);
    const next = rows.find(row => row.nextForecast.estimate != null);
    if (next) messages.push(`El siguiente intervalo puede planificarse con el pronóstico de ${next.name}: ${money(next.nextForecast.estimate)} y ${next.nextForecast.expectedEntries ?? '—'} entradas esperadas. Úsalo como referencia, no como venta confirmada.`);
    const conversions = rows.filter(row => row.conversion != null);
    if (conversions.length) {
      const best = [...conversions].sort((a, b) => (b.conversion || 0) - (a.conversion || 0))[0];
      messages.push(`${best.name} tiene la mejor conversión observada (${best.conversion}%). Compara su propuesta, horario y acceso con los negocios de menor conversión.`);
    }
    if (rows.some(row => row.forecast.confidence === 'baja')) messages.push('Algunas estimaciones tienen muestra baja. Mantén la recomendación como hipótesis y acumula al menos tres días comparables antes de tomar decisiones comerciales.');
    if (hourly.length) {
      const peak = [...hourly].sort((a, b) => b.entries - a.entries)[0];
      messages.push(`La franja de mayor afluencia del periodo es ${hourLabel(peak.hour)}. Es una oportunidad para medir conversión, permanencia y capacidad operativa de forma conjunta.`);
    }
    return messages;
  }, [rows, hourly]);

  return <div className="commerce">
    <div className="page-heading commerce-heading"><div><span className="eyebrow">INTELIGENCIA COMERCIAL</span><h1>Ventas y análisis</h1><p>Entradas medidas por hora y ventas estimadas para cada empresa del aeropuerto.</p></div><div className="commerce-actions"><button onClick={() => void generateDemo()} disabled={session.busy}>Generar datos de prueba</button><button onClick={() => void openSavedTest()}>Ver prueba guardada</button><button onClick={() => void download(`/api/commercial/export?${query}&kind=${tab === 'incidents' ? 'incidents' : 'summary'}`, 'analisis-comercial.csv')}>Exportar CSV</button></div></div>
    <section className="aero-panel commerce-filters"><label>Empresa / operador<select value={empresa} onChange={event => { setEmpresa(event.target.value); setBusiness(''); }}><option value="">Todas las empresas</option>{companies.map(item => <option key={item.name} value={item.name}>{item.name} · {item.businesses} negocios</option>)}</select></label><label>Negocio<select value={business} onChange={event => setBusiness(event.target.value)}><option value="">Todos los negocios</option>{rows.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label>Fecha<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label><label>Hora cerrada<select value={hour} onChange={event => setHour(Number(event.target.value))}>{Array.from({ length: 24 }, (_, value) => <option key={value} value={value}>{hourLabel(value)}</option>)}</select></label><label>Origen<select value={dataset} onChange={event => { setDataset(event.target.value); setValidation(null); }}><option value="real">Datos reales</option><option value="demo">Datos de prueba</option></select></label></section>
    {selectedCompany && <section className="company-banner"><div><span>Empresa seleccionada</span><strong>{selectedCompany.name}</strong><small>{selectedCompany.businesses} negocios bajo este operador</small></div><div><span>Entradas</span><strong>{selectedCompany.entries}</strong></div><div><span>Ventas del periodo</span><strong>{money(selectedCompany.sales)}</strong></div><div><span>Conversión</span><strong>{selectedCompany.conversion == null ? 'Sin POS' : `${selectedCompany.conversion}%`}</strong></div></section>}
    {dataset === 'demo' && <p className="commerce-test" role="status">Datos de prueba separados de la operación real.</p>}
    {error && <p role="alert" className="notice warning">{error}</p>}
    <nav className="commerce-tabs" aria-label="Análisis comercial">{[['sales', 'Resumen horario'], ['forecast', 'Estimación y pronóstico'], ['incidents', 'Aglomeraciones y ventas'], ['bags', 'Señal de objeto nuevo']].map(([id, label]) => <button key={id} aria-pressed={tab === id} className={tab === id ? 'selected' : ''} onClick={() => setTab(id as typeof tab)}>{label}</button>)}</nav>
    <section className="commerce-recommendations"><div><h2>Recomendaciones comerciales</h2><p>Lecturas automáticas para aforo, ventas, conversión, operación y oportunidades de crecimiento.</p></div>{recommendations.length ? <ul>{recommendations.map((message, index) => <li key={index}>{message}</li>)}</ul> : <p className="empty-text">Genera datos de prueba o ejecuta un monitoreo con accesos vinculados para obtener recomendaciones.</p>}</section>
    {tab === 'sales' && <section className="aero-panel commerce-content"><div className="commerce-kpis"><article><span>Entradas {hourLabel(hour)}</span><strong>{totals.entries || 'Sin medición'}</strong><small>Conteo confirmado por las líneas de entrada</small></article><article><span>Venta registrada</span><strong>{money(totals.sales)}</strong><small>Dato cargado desde ventas o POS</small></article><article><span>Venta estimada</span><strong>{money(totals.estimate)}</strong><small>Basada en entradas y días comparables</small></article><article><span>Conversión</span><strong>{conversion}</strong><small>Transacciones / entradas, si existe POS</small></article></div><div className="commerce-section-heading"><div><h2>Conteo horario por empresa</h2><p>La hora seleccionada representa un intervalo cerrado. La estimación no reemplaza la venta confirmada.</p></div><button onClick={() => void download('/api/commercial/template', 'plantilla-ventas.csv')}>Descargar plantilla CSV</button></div>{!hourly.length ? <p className="empty-text">Todavía no hay horas guardadas. Ejecuta un monitoreo con fecha de grabación y accesos vinculados.</p> : <div className="commerce-hourly"><div className="hourly-chart">{hourly.map(item => <div className="hourly-bar" key={item.hour}><i style={{ height: `${Math.max(8, Math.min(100, item.entries / Math.max(1, ...hourly.map(value => value.entries)) * 100))}%` }} /><span>{item.entries}</span><small>{String(item.hour).padStart(2, '0')}h</small></div>)}</div><table><thead><tr><th>Hora</th><th>Entradas</th><th>Ventas</th><th>Estimación</th></tr></thead><tbody>{hourly.map(item => <tr key={item.hour}><td>{hourLabel(item.hour)}</td><td>{item.entries}</td><td>{item.hasSales ? money(item.sales) : 'Sin datos'}</td><td>{item.hasEstimate ? money(item.estimate) : 'Muestra insuficiente'}</td></tr>)}</tbody></table></div>}
    <h2>Importar ventas históricas</h2><p>Un registro por negocio, fecha y hora. Usa los identificadores de la plantilla y soles PEN; la carga es atómica y no sobrescribe datos existentes.</p>{session.auth.rol === 'operador' && <div className="commerce-import"><label>CSV de ventas<input type="file" accept=".csv,text/csv" onChange={event => { const file = event.target.files?.[0]; setValidation(null); setCsv(''); if (file) { setFilename(file.name); if (file.size > 2000000) { setValidation({ rows: 0, errors: ['El archivo supera 2 MB.'], imported: false }); return; } void file.text().then(setCsv); } }} /></label><button disabled={!csv || session.busy} onClick={() => void upload(true)}>Validar archivo</button><button className="primary" disabled={!csv || session.busy || !validation || !!validation.errors.length} onClick={() => void upload(false)}>Importar ventas</button></div>}{validation && <div role="status" className={validation.errors.length ? 'notice warning' : 'notice'}><strong>{validation.imported ? 'Importación guardada' : `${validation.rows} filas revisadas`}</strong>{validation.errors.length ? <ul>{validation.errors.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>Archivo válido. Se guardará en {dataset === 'demo' ? 'datos de prueba' : 'datos reales'}.</p>}</div>}<h3>Importaciones guardadas</h3>{!data?.imports.length ? <p>No hay importaciones para este origen.</p> : <ul>{data.imports.map(item => <li key={item.id}>{item.name} · {item.rows} filas · {new Date(item.created).toLocaleString('es-PE')}</li>)}</ul>}</section>}
    {tab === 'forecast' && <section className="aero-panel commerce-content"><div className="forecast-intro"><h2>Hora cerrada y siguiente hora</h2><p>A las 10:30 puedes revisar la estimación de 09:00–10:00 y el pronóstico de 10:00–11:00. Ambos son modelos, no ventas confirmadas.</p></div><div className="forecast-grid">{rows.map(row => <article key={row.id}><span>{row.empresa}</span><h3>{row.name}</h3><div><small>{hourLabel(hour)} · estimación</small><strong>{money(row.forecast.estimate)}</strong><em>{confidenceLabel(row.forecast.confidence)} · {row.forecast.days} días comparables</em></div><div><small>{row.nextForecast.target ? row.nextForecast.target.slice(11, 16) : 'Siguiente hora'} · pronóstico</small><strong>{money(row.nextForecast.estimate)}</strong><em>Entradas esperadas: {row.nextForecast.expectedEntries ?? 'sin historial'}</em></div></article>)}</div></section>}
    {tab === 'incidents' && <section className="aero-panel commerce-content"><h2>Aglomeraciones y ventas de su hora</h2><p>La comparación usa la hora que contiene el incidente. No atribuye ventas a minutos exactos ni implica causalidad.</p>{rows.map(row => row.incidents.length > 0 && <div className="commerce-incidents" key={row.id}><h3>{row.name}</h3>{row.incidents.map(incident => <article key={incident.id}><strong>{new Date(incident.start).toLocaleTimeString('es-PE', { timeZone: 'America/Lima' })} · {incident.duration.toFixed(0)} s · pico {incident.peak} personas</strong><p>Venta: {money(incident.sales)} · Referencia: {money(incident.baseline)} · {incident.sampleDays} días comparables</p><p>{incident.differencePercent == null ? 'Comparación insuficiente' : `Diferencia descriptiva: ${incident.differencePercent}%`}. {incident.scope}</p></article>)}</div>)}</section>}
    {tab === 'bags' && <section className="aero-panel commerce-content"><h2>Señal experimental de objeto nuevo</h2><p>Solo compara salidas con entradas emparejadas. Una mochila nueva no demuestra una compra; esta señal sirve para priorizar revisión, no para tomar decisiones automáticas.</p>{rows.map(row => <div className="commerce-bag-row" key={row.id}><strong>{row.name}</strong><span>{row.bags.exits} salidas · {row.bags.matched} emparejadas · {row.bags.changed} objetos nuevos · {row.bags.coverage == null ? 'sin muestra' : `${row.bags.coverage}% cobertura`}</span></div>)}</section>}
    {session.auth.rol === 'operador' && session.config?.sourceMode === 'recordings' && <section className="aero-panel commerce-content"><h2>Fecha de las grabaciones</h2><p>Indica cuándo comienza la línea de tiempo de los videos para cruzarla con las ventas.</p><label>Inicio con zona horaria<input placeholder="2026-09-27T09:00:00-05:00" value={recordingDate} onChange={event => setRecordingDate(event.target.value)} /></label><button disabled={session.busy} onClick={() => void session.action(async () => { const value = recordingDate; if (value && (!/(Z|[+-]\d\d:\d\d)$/.test(value) || Number.isNaN(Date.parse(value)))) throw Error('Usa una fecha válida con zona horaria.'); await session.save({ ...session.config!, recordingStartedAt: value }); session.setNotice('Fecha de grabación guardada.'); })}>Guardar fecha de grabación</button></section>}
  </div>;
}
