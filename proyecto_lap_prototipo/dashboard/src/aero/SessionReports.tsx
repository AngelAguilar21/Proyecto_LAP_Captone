import {Component, type ReactNode, useEffect, useState} from 'react';
import type {Session} from './useSession';
import CommercialReportBoard from './CommercialReportBoard';
import {formatTime} from './types';

type ReportProps = {session: Session};

class ReportErrorBoundary extends Component<{children: ReactNode}, {hasError: boolean}> {
  state = {hasError: false};

  static getDerivedStateFromError() {
    return {hasError: true};
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <section className="aero-panel report-runtime-error" role="alert">
        <h2>No se pudo mostrar este reporte</h2>
        <p>La sesión guardada tiene datos incompletos o cambió mientras se cargaba. Puedes volver a intentar la vista sin perder el monitoreo.</p>
        <button type="button" onClick={() => window.location.reload()}>Reintentar vista</button>
      </section>
    );
  }
}

async function readJson(response: Response) {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error || `La solicitud falló (${response.status})`);
  }
  return payload;
}

function SessionReportsContent({session}: ReportProps) {
  const [history, setHistory] = useState<any[]>([]);
  const [selected, setSelected] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [historyLoading, setHistoryLoading] = useState(true);
  const headers = {'X-LAP-Session': localStorage.getItem('aero.session') || ''};

  useEffect(() => {
    let alive = true;
    setHistoryLoading(true);
    setError('');

    void fetch('/api/replay/history', {headers})
      .then(readJson)
      .then((rows) => {
        if (!alive) return;
        if (!Array.isArray(rows)) throw new Error('El historial no tiene un formato válido.');
        const completed = rows.filter((row: any) => ['ended', 'stopped'].includes(row?.status));
        setHistory(completed);
        setSelected((current) => completed.some((row: any) => row?.session === current) ? current : (completed[0]?.session || ''));
      })
      .catch((reason: unknown) => {
        if (alive) setError(reason instanceof Error ? reason.message : 'No se pudo cargar el historial.');
      })
      .finally(() => {
        if (alive) setHistoryLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [session.projects.active, session.state.status]);

  useEffect(() => {
    let alive = true;
    setData(null);
    if (!selected) return () => { alive = false; };

    void fetch(`/api/report/session?session=${encodeURIComponent(selected)}`, {headers})
      .then(readJson)
      .then((payload) => {
        if (!alive) return;
        if (!payload?.config || !payload?.state) throw new Error('El reporte no contiene configuración o resultados.');
        setData(payload);
        setError('');
      })
      .catch((reason: unknown) => {
        if (alive) setError(reason instanceof Error ? reason.message : 'No se pudo cargar el reporte.');
      });

    return () => {
      alive = false;
    };
  }, [selected]);

  async function download(format: string, kind = 'business') {
    await session.action(async () => {
      const response = await fetch(`/api/report?session=${encodeURIComponent(selected)}&format=${format}&kind=${kind}`, {headers});
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.error || `No se pudo descargar el archivo (${response.status})`);
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `monitoreo-${selected}-${kind}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  const reportConfig = data ? {
    ...data.config,
    cameras: Array.isArray(data.config?.cameras) ? data.config.cameras : [],
  } : {cameras: []};
  const rawState = data?.state || {};
  const reportState = data ? {
    ...rawState,
    cameraAnalytics: rawState.cameraAnalytics || {},
    analytics: {
      clusters: [],
      zones: [],
      heat: [],
      mappedCount: 0,
      ...(rawState.analytics || {}),
    },
  } : null;
  const cameraAnalytics = reportState?.cameraAnalytics || {};
  const cameras = Array.isArray(reportConfig.cameras) ? reportConfig.cameras : [];
  const sourceDate = rawState.testRun || rawState.mode === 'demo' || reportConfig.sourceMode === 'live'
    ? data?.created
    : reportConfig.recordingStartedAt;
  const parsedDate = sourceDate ? new Date(sourceDate) : new Date();
  const dateValue = Number.isNaN(parsedDate.getTime()) ? new Date() : parsedDate;
  const date = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit'}).format(dateValue);
  const hour = new Intl.DateTimeFormat('en-GB', {timeZone: 'America/Lima', hour: 'numeric', hourCycle: 'h23'}).format(dateValue);
  const salesLink = `?view=commercial&dataset=${rawState.testRun || rawState.mode === 'demo' ? 'demo' : 'real'}&date=${date}&hour=${hour}`;

  return (
    <div className="commerce reports-page">
      <div className="page-heading commerce-heading">
        <div>
          <h1>Reportes de monitoreo</h1>
          <p>Un reporte corresponde a una sesión procesada, desde su inicio hasta su fin. No suma automáticamente todo el día.</p>
        </div>
      </div>

      <section className="aero-panel commerce-content reports-selector">
        <label>
          Monitoreo guardado
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            <option value="">Seleccionar monitoreo…</option>
            {history.map((row: any) => (
              <option key={row.session} value={row.session}>
                {row.created ? new Date(row.created).toLocaleString('es-PE') : 'Fecha no disponible'} · {Array.isArray(row.cameras) ? row.cameras.length : 0} cámaras · {formatTime(Number(row.end) || 0)} · {row.session}
              </option>
            ))}
          </select>
        </label>

        {data && (
          <>
            <p><strong>Sesión {selected}</strong> · {cameras.length} cámaras · {formatTime(Number(rawState.t) || 0)} de fuente · {rawState.testRun || rawState.mode === 'demo' ? 'Datos de prueba' : 'Fuente configurada'}</p>
            <div className="inline">
              <button disabled={session.busy} onClick={() => void download('pdf')}>Descargar PDF</button>
              <button disabled={session.busy} onClick={() => void download('xlsx')}>Descargar Excel</button>
              <button disabled={session.busy} onClick={() => void download('csv', 'cameras')}>CSV por cámara</button>
              <button disabled={session.busy} onClick={() => void download('csv', 'crossings')}>CSV de accesos</button>
            </div>
          </>
        )}

        {error && <p className="report-error" role="alert">{error}</p>}
        {historyLoading && <p role="status">Cargando monitoreos guardados…</p>}
        {selected && !data && !error && <p role="status">Cargando el reporte seleccionado…</p>}
        {!historyLoading && !selected && !error && <p>Finaliza un monitoreo para generar su reporte. Los resultados guardados se conservan al reiniciar.</p>}
      </section>

      {data && (
        <>
          <section className="aero-panel commerce-content">
            <h2>Resultados de las cámaras de esta sesión</h2>
            <div className="commerce-table">
              <table>
                <thead><tr><th>Cámara</th><th>Personas: última muestra</th><th>Máximo</th><th>Promedio</th><th>Entradas</th><th>Salidas</th><th>Configuración de accesos</th></tr></thead>
                <tbody>
                  {cameras.map((camera: any) => {
                    const analytics = cameraAnalytics[camera.id] || {};
                    const occupancy = analytics.occupancy;
                    const lines = Array.isArray(analytics.crossings) ? analytics.crossings : [];
                    return (
                      <tr key={camera.id}>
                        <td>{camera.name || camera.id}</td>
                        <td>{occupancy?.count ?? 'Sin muestra'}</td>
                        <td>{occupancy?.peak ?? '—'}</td>
                        <td>{typeof occupancy?.mean === 'number' ? occupancy.mean.toFixed(1) : '—'}</td>
                        <td>{lines.length ? lines.reduce((total: number, line: any) => total + (Number(line.entries) || 0), 0) : '—'}</td>
                        <td>{lines.length ? lines.reduce((total: number, line: any) => total + (Number(line.exits) || 0), 0) : '—'}</td>
                        <td>{!lines.length ? 'Sin línea de conteo' : lines.some((line: any) => !line.place) ? 'Hay accesos sin negocio vinculado' : `${lines.length} acceso(s) vinculado(s)`}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <h3>Accesos y negocios medidos</h3>
            {cameras.flatMap((camera: any) => (cameraAnalytics[camera.id]?.crossings || []).map((line: any) => (
              <p key={`${camera.id}-${line.id}`}><strong>{line.place?.name || 'Acceso sin negocio vinculado'} · {line.name}</strong>: {Number(line.entries) || 0} entradas, {Number(line.exits) || 0} salidas · {camera.name || camera.id}</p>
            )))}
            <p>Las entradas y salidas requieren una línea de acceso. Tener video de una tienda no identifica automáticamente su puerta.</p>
          </section>
          <CommercialReportBoard config={reportConfig} state={reportState} demo={rawState.mode === 'demo' || Boolean(rawState.testRun)} />
        </>
      )}

      <section className="aero-panel commerce-content">
        <h2>Ventas del día y proyecciones</h2>
        <p>Se consultan por negocio, fecha y hora en Ventas y análisis. Para grabaciones reales se necesita la fecha de grabación; las pruebas usan su fecha de ejecución y están separadas de los datos reales.</p>
        {sourceDate ? <a href={salesLink}>Ver ventas de la fecha y hora del monitoreo</a> : <p>Define la fecha de grabación antes de vincular este video con ventas. <a href="?view=commercial">Consultar ventas por fecha</a></p>}
      </section>
    </div>
  );
}

export default function SessionReports(props: ReportProps) {
  return <ReportErrorBoundary><SessionReportsContent {...props} /></ReportErrorBoundary>;
}
