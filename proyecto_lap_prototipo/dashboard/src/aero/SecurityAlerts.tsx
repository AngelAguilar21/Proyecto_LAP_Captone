import { useCallback, useEffect, useRef, useState } from 'react';
import type { Session } from './useSession';
import { formatTime, isActive } from './types';
import Icon from './Icon';
import MailSettings from './MailSettings';

type Incidente = {
  id: string; tipo: string; zona: string | null; camaraId: string | null;
  inicio: number; pico: number | null; duracion: number | null; estado: string;
  detalle: Record<string, unknown>; creado: number;
};
type Alert = {
  id: string; at: number; zone: string; camera: string; cameraId?: string;
  people: number; duration: number; threshold: number; dwell: number; open: boolean; origin: 'camera' | 'plan';
};

function beep() {
  try {
    const context = new AudioContext();
    const oscillator = context.createOscillator(), gain = context.createGain();
    oscillator.frequency.value = 880;
    oscillator.connect(gain); gain.connect(context.destination);
    gain.gain.setValueAtTime(.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(.18, context.currentTime + .02);
    gain.gain.exponentialRampToValueAtTime(.0001, context.currentTime + .45);
    oscillator.start(); oscillator.stop(context.currentTime + .5);
    setTimeout(() => void context.close(), 700);
  } catch { /* el navegador exige un clic previo para reproducir sonido */ }
}

export default function SecurityAlerts({ session, onOpenCamera }: { session: Session; onOpenCamera: (id: string) => void }) {
  const { state, config } = session;
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [sound, setSound] = useState(() => { try { return localStorage.getItem('aero.alerts.sound') !== 'off'; } catch { return true; } });
  const known = useRef(new Map<string, Alert>());
  const [log, setLog] = useState<Incidente[]>([]);
  const [logError, setLogError] = useState('');

  useEffect(() => { known.current.clear(); setAlerts([]); }, [state.session]);

  useEffect(() => {
    if (!config) return;
    let added = 0;
    for (const [cameraId, analytics] of Object.entries(state.cameraAnalytics || {})) {
      const camera = config.cameras.find(c => c.id === cameraId);
      for (const episode of (analytics as any).occupancy?.episodes || []) {
        const key = `cam:${cameraId}:${episode.id ?? episode.zone + episode.start}`;
        const zoneSetup = camera?.analysisZones?.find(z => z.id === episode.zoneId);
        const entry: Alert = {
          id: key, at: episode.start, zone: episode.zone, camera: camera?.name || cameraId, cameraId,
          people: episode.peak, duration: episode.duration || 0,
          threshold: zoneSetup?.threshold ?? camera?.crowdThreshold ?? 10,
          dwell: zoneSetup?.dwell ?? camera?.crowdDwell ?? 3,
          open: episode.end == null, origin: 'camera',
        };
        if (!known.current.has(key)) added++;
        known.current.set(key, entry);
      }
    }
    for (const zone of state.analytics.zones.filter(z => z.alert)) {
      const key = `plan:${zone.name}:${Math.round(state.t - (zone.duration || 0))}`;
      const rule = config.zones.find(z => z.name === zone.name)?.rule;
      const entry: Alert = {
        id: key, at: state.t - (zone.duration || 0), zone: zone.name, camera: 'Plano (varias cámaras)',
        people: zone.peak ?? zone.count, duration: zone.duration || 0,
        threshold: rule?.minPeople ?? config.minPeople, dwell: rule?.dwell ?? config.dwell,
        open: true, origin: 'plan',
      };
      if (!known.current.has(key)) added++;
      known.current.set(key, entry);
    }
    if (known.current.size !== alerts.length || added) {
      setAlerts([...known.current.values()].sort((a, b) => b.at - a.at));
      if (added && sound && isActive(state.status)) beep();
    }
  }, [state.cameraAnalytics, state.analytics.zones, state.t, state.status, config]);

  // Bitácora: los incidentes guardados sobreviven al cierre de la sesión, a
  // diferencia de las alertas de arriba, que solo existen mientras corre.
  const loadLog = useCallback(() => {
    void fetch('/api/incidents').then(r => r.json())
      .then(data => { setLog(data.incidentes || []); setLogError(data.error || ''); })
      .catch(() => setLogError('No se pudo leer la bitácora.'));
  }, []);
  useEffect(() => { loadLog(); }, [loadLog, state.session]);
  useEffect(() => { const id = setInterval(loadLog, 12000); return () => clearInterval(id); }, [loadLog]);

  function markIncident(id: string, estado: string) {
    void session.action(async () => {
      const data = await session.post('incidents', { id, estado });
      setLog(data.incidentes || []);
      session.setNotice('Incidente actualizado.');
    });
  }

  // Umbrales de alerta: el administrador puede cambiarlos sin entrar a
  // Configuración, porque definen cuándo le avisan a él.
  const [rules, setRules] = useState({ minPeople: 4, dwell: 3, radius: 1.5 });
  useEffect(() => {
    if (config) setRules({ minPeople: config.minPeople, dwell: config.dwell, radius: config.radius });
  }, [config?.minPeople, config?.dwell, config?.radius]);
  const rulesDirty = !!config && (rules.minPeople !== config.minPeople || rules.dwell !== config.dwell || rules.radius !== config.radius);
  function saveRules() {
    void session.action(async () => {
      await session.post('alert-rules', rules);
      session.setNotice('Umbrales de alerta actualizados.');
    });
  }

  function toggleSound() {
    setSound(value => { const next = !value; try { localStorage.setItem('aero.alerts.sound', next ? 'on' : 'off'); } catch { /* modo privado */ } if (next) beep(); return next; });
  }

  const luggage = Object.entries(state.cameraAnalytics || {}).flatMap(([cameraId, analytics]) => {
    const watch = (analytics as any).luggage;
    if (!watch) return [];
    const camera = config?.cameras.find(c => c.id === cameraId);
    return (watch.items || []).filter((item: any) => item.alert).map((item: any) => ({
      ...item, cameraId, camera: camera?.name || cameraId, dwell: watch.dwell,
    }));
  });

  const open = alerts.filter(a => a.open).length;
  const pendingLog = log.filter(i => i.estado === 'pendiente').length;
  return <div className="security-alerts">
    <div className="page-heading">
      <div>
        <h1>Alertas para seguridad</h1>
        <p>Cada aviso indica dónde se formó la aglomeración y por qué se disparó, para que el personal pueda ir a revisarla.</p>
      </div>
      <button onClick={toggleSound}><Icon name={sound ? 'alert' : 'shield'} size={15} /> {sound ? 'Sonido activado' : 'Sonido apagado'}</button>
    </div>

    <section className="aero-panel">
      <div className="panel-heading">
        <div><h2>Cuándo avisar</h2><p className="subtle">Define cuánta gente junta y por cuánto tiempo cuenta como aglomeración. No hace falta entrar a Configuración para cambiarlo.</p></div>
        <button className="primary" disabled={session.busy || !rulesDirty} onClick={saveRules}>Guardar umbrales</button>
      </div>
      <div className="rules-form">
        <label>Personas mínimas<input type="number" min={2} max={1000} value={rules.minPeople} onChange={e => setRules({ ...rules, minPeople: +e.target.value })} /></label>
        <label>Permanencia (segundos)<input type="number" min={0} max={3600} value={rules.dwell} onChange={e => setRules({ ...rules, dwell: +e.target.value })} /></label>
        <label>Radio ({config?.unit === 'meters' ? 'metros' : 'unidades relativas'})<input type="number" min={0.01} step={0.1} value={rules.radius} onChange={e => setRules({ ...rules, radius: +e.target.value })} /></label>
      </div>
    </section>

    <MailSettings session={session}/>

    <div className="metrics-row">
      <article className="metric-card"><Icon name="alert" size={25} /><div><span>Alertas activas</span><strong className={open ? 'text-red' : 'text-blue'}>{open}</strong><small>ahora mismo</small></div></article>
      <article className="metric-card"><Icon name="report" size={25} /><div><span>Total en la sesión</span><strong className="text-blue">{alerts.length}</strong><small>incluye las ya despejadas</small></div></article>
      <article className="metric-card"><Icon name="clock" size={25} /><div><span>Sin revisar</span><strong className={pendingLog ? 'text-red' : 'text-blue'}>{pendingLog}</strong><small>en la bitácora</small></div></article>
    </div>

    <section className="aero-panel">
      <div className="panel-heading">
        <div><h2>Bitácora de incidentes</h2><p className="subtle">Queda guardada aunque termine la sesión. Marca cada caso cuando alguien lo haya ido a revisar.</p></div>
        <span className="pill muted">{log.length} registrados</span>
      </div>
      {logError && <p className="empty-text">{logError}</p>}
      {!log.length && !logError
        ? <p className="empty-text">Todavía no hay incidentes guardados en este proyecto.</p>
        : <div className="alert-log">
          {log.map(item => <article className={item.estado === 'pendiente' ? 'alert-row open' : 'alert-row'} key={item.id}>
            <div className="alert-when">
              <strong>{new Date(item.creado * 1000).toLocaleString('es-PE', { timeZone: 'America/Lima', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</strong>
              <span className={`pill ${item.estado === 'pendiente' ? 'warn' : item.estado === 'falsa_alarma' ? 'muted' : 'good'}`}>
                {{ pendiente: 'Sin revisar', revisado: 'Revisado', falsa_alarma: 'Falsa alarma', resuelto: 'Resuelto' }[item.estado] || item.estado}
              </span>
            </div>
            <div className="alert-what">
              <strong>{item.tipo === 'equipaje' ? 'Equipaje sin custodia' : `Aglomeración en ${item.zona || 'zona sin nombre'}`}</strong>
              <small>{String(item.detalle?.camara || item.camaraId || 'Plano')}</small>
              <p>
                {item.pico != null && <>Máximo de <b>{Math.round(item.pico)} personas</b>. </>}
                {item.duracion != null && <>Duró <b>{Math.round(item.duracion)} s</b>.</>}
              </p>
            </div>
            <div className="alert-actions">
              {item.estado === 'pendiente'
                ? <>
                  <button disabled={session.busy} onClick={() => markIncident(item.id, 'revisado')}>Revisado</button>
                  <button disabled={session.busy} onClick={() => markIncident(item.id, 'falsa_alarma')}>Falsa alarma</button>
                  <button disabled={session.busy} onClick={() => markIncident(item.id, 'resuelto')}>Resuelto</button>
                </>
                : <button disabled={session.busy} onClick={() => markIncident(item.id, 'pendiente')}>Reabrir</button>}
            </div>
          </article>)}
        </div>}
    </section>

    {luggage.length > 0 && <section className="aero-panel">
      <div className="panel-heading"><div><h2>Equipaje sin custodia</h2><p className="subtle">Bultos que llevan quietos más del tiempo configurado. Requiere revisión de una persona: el sistema no distingue una maleta olvidada de una que alguien dejó a su lado mientras espera.</p></div><span className="pill warn">{luggage.length}</span></div>
      <div className="alert-log">
        {luggage.map((item: any) => <article className="alert-row open" key={item.cameraId + item.id}>
          <div className="alert-when"><strong>{formatTime(item.since)}</strong><span className="pill warn">Sin custodia</span></div>
          <div className="alert-what">
            <strong>{item.kind ? item.kind[0].toUpperCase() + item.kind.slice(1) : 'Bulto'} {item.id}</strong>
            <small>{item.camera}</small>
            <p>Lleva <b>{Math.round(item.duration)} s</b> sin moverse. El aviso salta a partir de {Math.round(item.dwell)} s.</p>
          </div>
          <div className="alert-actions"><button onClick={() => onOpenCamera(item.cameraId)}><Icon name="camera" size={14} /> Ver cámara</button></div>
        </article>)}
      </div>
    </section>}

    {!alerts.length
      ? <p className="empty-text">Sin alertas de aglomeración en esta sesión. Aparecen cuando una zona supera su umbral de personas durante el tiempo configurado.</p>
      : <div className="alert-log">
        {alerts.map(alert => <article className={alert.open ? 'alert-row open' : 'alert-row'} key={alert.id}>
          <div className="alert-when">
            <strong>{formatTime(alert.at)}</strong>
            <span className={`pill ${alert.open ? 'warn' : 'muted'}`}>{alert.open ? 'Activa' : 'Despejada'}</span>
          </div>
          <div className="alert-what">
            <strong>{alert.zone}</strong>
            <small>{alert.camera}</small>
            <p>Se juntaron <b>{alert.people} personas</b> y se mantuvieron <b>{Math.round(alert.duration)} s</b>. El aviso salta al superar {alert.threshold} personas durante {alert.dwell} s.</p>
          </div>
          <div className="alert-actions">
            {alert.cameraId && <button onClick={() => onOpenCamera(alert.cameraId!)}><Icon name="camera" size={14} /> Ver cámara</button>}
          </div>
        </article>)}
      </div>}
  </div>;
}
