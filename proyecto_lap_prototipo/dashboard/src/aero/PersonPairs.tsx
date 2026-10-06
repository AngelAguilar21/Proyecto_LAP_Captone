import { useEffect, useMemo, useRef, useState } from 'react';
import type { Config, Point } from './types';
import { MIN_PAREJAS_RELACION } from './types';
import type { Session } from './useSession';
import './person-pairs.css';

/** La misma persona marcada en dos cámaras.
 *
 * Es lo que relaciona las cámaras para la identidad entre cámaras: con MIN_PAREJAS_RELACION parejas o más, el servidor
 * las trata como vecinas (live_core.related_cameras). Las mismas parejas miden el desfase de tiempo entre los dos videos
 * y, si las dos cámaras tienen puntos del suelo, cuánto concuerdan sus homografías. No se calibra nada con personas:
 * la posición en el plano sale solo de los puntos del suelo.
 */

type Box = [number, number, number, number];
type Side = { camera: string; point: Point; bbox?: Box };
type Pair = { id: string; t?: number; ta?: number; tb?: number; pa?: number; pb?: number; a: Side; b: Side };   // pa/pb: instante en el archivo de video
type Report = {
  n: number; suficiente: boolean;
  pares: { id: string; ta: number; tb: number; dt: number; fueraDeTiempo: boolean; distancia: number | null }[];
  avisos: { nivel: 'error' | 'aviso' | 'info'; texto: string }[];
  espacial: { mediana: number; max: number; n: number; concuerdan: boolean } | null;
  temporal: { offset: number; muestras: number; dispersion: number | null; necesita: boolean; verificada: boolean; syncBase: number; syncDestino: number };
};
type Info = { duration: number };

function validPair(value: unknown): value is Pair {
  const pair = value as Partial<Pair> | null;
  return !!pair && typeof pair === 'object'
    && !!pair.a && typeof pair.a.camera === 'string' && Array.isArray(pair.a.point) && pair.a.point.length === 2
    && !!pair.b && typeof pair.b.camera === 'string' && Array.isArray(pair.b.point) && pair.b.point.length === 2;
}

export function useFrame(camera: string, t: number, headers: Record<string, string>) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!camera) { setUrl(''); setLoading(false); return; }
    let alive = true;
    const controller = new AbortController();
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/camera-frame?camera=${encodeURIComponent(camera)}&t=${t}`, { headers, signal: controller.signal });
        if (!response.ok) throw Error((await response.json()).error);
        const blob = URL.createObjectURL(await response.blob());
        if (alive) { setUrl(old => { if (old) URL.revokeObjectURL(old); return blob; }); setError(''); setLoading(false); } else URL.revokeObjectURL(blob);
      } catch (cause) { if (alive && !(cause instanceof DOMException)) { setError(cause instanceof Error ? cause.message : 'No se pudo cargar el video.'); setLoading(false); } }
    }, 150);
    return () => { alive = false; clearTimeout(timer); controller.abort(); };
  }, [camera, t]);
  return { url, error, loading };
}

function Frame({ camera, label, t, headers, markers, boxes, onPoint, onBox }: {
  camera: string; label: string; t: number; headers: Record<string, string>; markers: { point: Point; label: string; tone: string }[]; boxes: { box: Box; tone: string }[]; onPoint: (p: Point) => void; onBox: (box: Box, point: Point) => void;
}) {
  const { url, error, loading } = useFrame(camera, t, headers);
  const [drag, setDrag] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Box | null>(null);
  const norm = (event: React.PointerEvent<HTMLImageElement>): Point => { const r = event.currentTarget.getBoundingClientRect(); return [Math.min(1, Math.max(0, (event.clientX-r.left)/r.width)), Math.min(1, Math.max(0, (event.clientY-r.top)/r.height))]; };
  return <figure className="pp-frame">
    <figcaption>{label}</figcaption>
    <div className="pp-stage">
      {url ? <img src={url} alt={`Cámara ${camera} en ${t.toFixed(1)} s`} draggable={false}
        onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); setDrag(norm(event)); setDraft(null); }}
        onPointerMove={event => { if (!drag) return; const p=norm(event); setDraft([Math.min(drag[0],p[0]),Math.min(drag[1],p[1]),Math.max(drag[0],p[0]),Math.max(drag[1],p[1])]); }}
        onPointerUp={event => { if (!drag) return; const p=norm(event); const box: Box=[Math.min(drag[0],p[0]),Math.min(drag[1],p[1]),Math.max(drag[0],p[0]),Math.max(drag[1],p[1])]; setDrag(null); setDraft(null); if (box[2]-box[0] >= .02 && box[3]-box[1] >= .02) onBox(box, [(box[0]+box[2])/2,box[3]]); else onPoint(p); }} /> : <div className={`pp-empty ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{loading ? 'Cargando fotograma…' : error || 'No hay imagen disponible para este instante.'}</div>}
      {url && boxes.map((b, i) => <span key={`box-${i}`} className={`pp-box ${b.tone}`} style={{ left: `${b.box[0]*100}%`, top: `${b.box[1]*100}%`, width: `${(b.box[2]-b.box[0])*100}%`, height: `${(b.box[3]-b.box[1])*100}%` }} />)}
      {draft && <span className="pp-box pending" style={{ left: `${draft[0]*100}%`, top: `${draft[1]*100}%`, width: `${(draft[2]-draft[0])*100}%`, height: `${(draft[3]-draft[1])*100}%` }} />}
      {url && markers.map((m, i) => <span key={i} className={`pp-marker ${m.tone}`} style={{ left: `${m.point[0] * 100}%`, top: `${m.point[1] * 100}%` }}>{m.label}</span>)}
    </div>
  </figure>;
}

/** Pares de cámaras relacionados hoy por personas marcadas (mismo criterio que el servidor). */
export function relatedPairs(config: Config) {
  const conteo: Record<string, number> = {};
  for (const p of (config.personPairs || []).filter(validPair)) {
    if (p.a.camera === p.b.camera) continue;
    const clave = [p.a.camera, p.b.camera].sort().join('|');
    conteo[clave] = (conteo[clave] || 0) + 1;
  }
  return Object.entries(conteo).map(([clave, n]) => ({ a: clave.split('|')[0], b: clave.split('|')[1], n, relacionadas: n >= MIN_PAREJAS_RELACION }));
}

export default function PersonPairs({ session, config, selected, disabled }: { session: Session; config: Config; selected: string; disabled: boolean }) {
  const configRef = useRef(config);
  configRef.current = config;
  // Desfase de lectura de una cámara: el que usa el monitoreo y también la vista previa de esta pantalla.
  const lectura = (id: string) => { const c = configRef.current.cameras.find(x => x.id === id); return c ? (c.offset || 0) + (c.syncOffset || 0) : 0; };
  const headers = useMemo(() => ({ 'X-LAP-Session': localStorage.getItem('aero.session') || '' }), []);
  const cameras = config.cameras.filter(c => (c.planId || 'custom') === (config.planId || 'custom') && typeof c.source === 'string' && c.source && !String(c.source).includes('://'));
  const ids = cameras.map(c => c.id);
  const [base, setBase] = useState(() => ids.includes(selected) ? selected : ids[0] || '');
  const [target, setTarget] = useState(() => ids.find(id => id !== (ids.includes(selected) ? selected : ids[0])) || '');
  const [ta, setTa] = useState(0);
  const [tb, setTb] = useState(0);
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [pending, setPending] = useState<{ a?: { point: Point; bbox?: Box }; b?: { point: Point; bbox?: Box } }>({});
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const [calculando, setCalculando] = useState(false);
  const corriendo = useRef(false);

  // Si una cámara se quita del plano, la selección pasa a otra válida.
  useEffect(() => {
    if (!ids.includes(base)) setBase(ids[0] || '');
    if (!ids.includes(target) || target === base) setTarget(ids.find(id => id !== base) || '');
  }, [ids.join(','), base, target]);
  useEffect(() => { setError(''); setPending({}); setReport(null); }, [base, target]);

  // La duración útil de cada video depende de su desfase de lectura, así que se vuelve a pedir cuando cambia.
  const lecturaBase = lectura(base), lecturaTarget = lectura(target);
  useEffect(() => {
    let alive = true;
    if (!base || !target || base === target) return;
    void Promise.all([base, target].map(id => fetch(`/api/camera-frame-info?camera=${encodeURIComponent(id)}`, { headers }).then(async r => { const body = await r.json(); if (!r.ok) throw Error(body.error); return body as Info; })))
      .then(infos => { if (alive) { setDurations({ [base]: infos[0].duration, [target]: infos[1].duration }); setTa(v => Math.min(v, Math.max(0, infos[0].duration - 0.2))); setTb(v => Math.min(v, Math.max(0, infos[1].duration - 0.2))); } })
      .catch(cause => { if (alive) setError(cause instanceof Error ? cause.message : 'No se pudo leer el video.'); });
    return () => { alive = false; };
  }, [base, target, lecturaBase, lecturaTarget]);

  // Si cambia el desfase, el cuadro que se estaba viendo no debe saltar: el instante común se corre lo mismo que el desfase.
  const lecturaPrevia = useRef<Record<string, number>>({});
  useEffect(() => {
    const antes = lecturaPrevia.current;
    if (antes[base] !== undefined && antes[base] !== lecturaBase) setTa(v => Math.max(0, Math.round((v - (lecturaBase - antes[base])) * 100) / 100));
    if (antes[target] !== undefined && antes[target] !== lecturaTarget) setTb(v => Math.max(0, Math.round((v - (lecturaTarget - antes[target])) * 100) / 100));
    lecturaPrevia.current = { [base]: lecturaBase, [target]: lecturaTarget };
  }, [base, target, lecturaBase, lecturaTarget]);

  const between = (config.personPairs || []).filter(validPair).filter(p => [p.a.camera, p.b.camera].sort().join() === [base, target].sort().join());
  const side = (pair: Pair, id: string) => pair.a.camera === id ? pair.a : pair.b;
  // Instante común de una pareja con el desfase de ahora (las antiguas, sin pa/pb, conservan el tiempo con que se marcaron).
  const pairTime = (p: Pair, camera: string) => {
    const enArchivo = p.a.camera === camera ? p.pa : p.pb;
    return enArchivo !== undefined ? Math.max(0, enArchivo - lectura(camera)) : p.a.camera === camera ? (p.ta ?? p.t ?? 0) : (p.tb ?? p.t ?? 0);
  };
  const here = between.filter(p => Math.abs(pairTime(p, base) - ta) < 0.05 && Math.abs(pairTime(p, target) - tb) < 0.05);
  const update = (patch: Partial<Config>) => session.setConfig({ ...configRef.current, ...patch });
  const unit = config.unit === 'meters' ? 'm' : 'u';
  const nombre = (id: string) => cameras.find(c => c.id === id)?.name || id;
  const relacionadas = relatedPairs(config);

  // Avanza o retrocede el video de una cámara (o de las dos a la vez) en pasos de 0,5 s sin salirse del video.
  const PASO = 0.5;
  const limite = (id: string) => Math.max((durations[id] || 0) - 0.2, 0);
  const acotar = (id: string, valor: number) => Math.round(Math.min(limite(id), Math.max(0, valor)) * 100) / 100;
  function mover(cual: 'a' | 'b' | 'ambas', delta: number) {
    if (cual !== 'b') setTa(v => acotar(base, v + delta));
    if (cual !== 'a') setTb(v => acotar(target, v + delta));
    setPending({});
  }
  const pasos = (cual: 'a' | 'b' | 'ambas', etiqueta: string) => <span className="pp-step" role="group" aria-label={`Mover ${etiqueta}`}>
    <button type="button" disabled={disabled || !durations[base]} title={`${etiqueta}: retroceder ${PASO} s`} onClick={() => mover(cual, -PASO)}>− {PASO} s</button>
    <button type="button" disabled={disabled || !durations[base]} title={`${etiqueta}: avanzar ${PASO} s`} onClick={() => mover(cual, PASO)}>+ {PASO} s</button>
  </span>;

  function mark(which: 'a' | 'b', point: Point, bbox?: Box) {
    const next = { ...pending, [which]: { point, bbox } };
    if (next.a && next.b) {
      const redondo = (v: number) => Math.round(v * 100) / 100;
      const pair: Pair = { id: crypto.randomUUID().slice(0, 8), t: redondo(ta), ta: redondo(ta), tb: redondo(tb), pa: redondo(ta + lectura(base)), pb: redondo(tb + lectura(target)),
        a: { camera: base, point: next.a.point, bbox: next.a.bbox }, b: { camera: target, point: next.b.point, bbox: next.b.bbox } };
      update({ personPairs: [...(configRef.current.personPairs || []), pair] });
      setPending({});
    } else setPending(next);
  }

  // Con 4 o más parejas el servidor calcula el desfase de tiempo; si es fiable se guarda y las cámaras quedan sincronizadas.
  async function comprobar() {
    if (corriendo.current || !base || !target || base === target) return;
    corriendo.current = true; setCalculando(true); setError('');
    try {
      await session.save();
      const parejas = (configRef.current.personPairs || []).filter(p => [p.a.camera, p.b.camera].sort().join() === [base, target].sort().join());
      const r = await session.post('person-pairs/check', { base, target, pairs: parejas }) as Report;
      if (!r.temporal || !Array.isArray(r.pares) || (r.avisos || []).some(a => typeof a !== 'object') || (r.espacial != null && typeof r.espacial !== 'object')) {
        throw Error('El servidor está ejecutando una versión anterior del programa. Ciérralo con Ctrl+C y vuelve a abrir iniciar_sistema.cmd.');
      }
      setReport(r);
      const cfg = configRef.current;
      if (r.temporal.verificada) {
        const sync = (id: string) => !r.temporal.necesita ? undefined : id === target ? r.temporal.syncDestino : id === base ? r.temporal.syncBase : undefined;
        const next = { ...cfg, clocksVerified: true, cameras: cfg.cameras.map(c => { const valor = sync(c.id); return valor === undefined ? c : { ...c, syncOffset: valor }; }) };
        if (JSON.stringify(next) !== JSON.stringify(cfg)) { await session.save(next); session.setConfig(next); }
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo comprobar con estas personas.'); }
    finally { corriendo.current = false; setCalculando(false); }
  }
  const clave = between.map(p => `${p.id}:${p.pa ?? p.ta}:${p.pb ?? p.tb}`).join('|');
  useEffect(() => {
    if (disabled || between.length < MIN_PAREJAS_RELACION) return;
    const timer = setTimeout(() => { void comprobar(); }, 700);
    return () => clearTimeout(timer);
  }, [clave, base, target, disabled]);

  if (cameras.length < 2) return <section className="aero-panel person-pairs"><div className="panel-heading"><h2>La misma persona en dos cámaras</h2></div><p className="subtle">Necesitas al menos dos cámaras del plano con videos grabados para marcar a la misma persona en ambas.</p></section>;

  const fila = (id: string) => report?.pares.find(r => r.id === id);
  const estado = (id: string) => {
    const r = fila(id);
    if (!r) return '—';
    if (r.fueraDeTiempo) return `otro desfase de tiempo (${r.dt >= 0 ? '+' : ''}${r.dt.toFixed(2)} s): revisar`;
    return r.distancia == null ? 'bien' : `bien · en el plano a ${r.distancia.toFixed(2)} ${unit}`;
  };
  const rotulo = { error: 'Error: ', aviso: 'Revisa: ', info: '' };

  return <section className="aero-panel person-pairs">
    <div className="panel-heading"><h2>La misma persona en dos cámaras</h2><span className={`pill ${between.length >= MIN_PAREJAS_RELACION ? 'good' : 'blue'}`}>{between.length} de {MIN_PAREJAS_RELACION} parejas</span></div>
    <p>Arrastra un <b>rectángulo alrededor de la misma persona</b> en las dos cámaras (primero en una, luego en la otra). El sistema usa automáticamente el centro inferior del rectángulo como punto de los pies. Con {MIN_PAREJAS_RELACION} o más parejas las dos cámaras quedan <b>relacionadas</b>: el monitoreo podrá reconocer a una persona cuando pase de una a otra y medirá el desfase entre sus videos. Si necesitas marcar solo un punto, haz un clic corto.</p>
    <div className="pp-controls">
      <label>Primera cámara<select value={base} disabled={disabled} onChange={e => setBase(e.target.value)}>{cameras.map(c => <option key={c.id} value={c.id}>{c.name || c.id}</option>)}</select></label>
      <label>Segunda cámara<select value={target} disabled={disabled} onChange={e => setTarget(e.target.value)}>{cameras.filter(c => c.id !== base).map(c => <option key={c.id} value={c.id}>{c.name || c.id}</option>)}</select></label>
      <label className="pp-time">Tiempo {nombre(base)}: <b>{ta.toFixed(2)} s</b> de {(durations[base] || 0).toFixed(1)} s
        <input type="range" min={0} max={limite(base)} step={0.1} value={ta} disabled={disabled || !durations[base]} onChange={e => { setTa(+e.target.value); setPending({}); }} />
        {pasos('a', base)}</label>
      <label className="pp-time">Tiempo {nombre(target)}: <b>{tb.toFixed(2)} s</b> de {(durations[target] || 0).toFixed(1)} s
        <input type="range" min={0} max={limite(target)} step={0.1} value={tb} disabled={disabled || !durations[target]} onChange={e => { setTb(+e.target.value); setPending({}); }} />
        {pasos('b', target)}</label>
      <div className="pp-both"><span>Las dos cámaras a la vez</span>{pasos('ambas', 'las dos cámaras')}</div>
    </div>
    {error && <div className="notice error" role="alert">{error}</div>}
    {base && target && base !== target && <div className="pp-frames">
      <Frame camera={base} label={`${nombre(base)}: marca los pies`} t={ta} headers={headers}
        markers={[...here.map(p => ({ point: side(p, base).point, label: String(between.indexOf(p) + 1), tone: 'done' })), ...(pending.a ? [{ point: pending.a.point, label: '?', tone: 'pending' }] : [])]} boxes={here.flatMap(p => side(p, base).bbox ? [{ box: side(p, base).bbox!, tone: 'done' }] : [])} onPoint={p => !disabled && mark('a', p)} onBox={(box,p) => !disabled && mark('a', p, box)} />
      <Frame camera={target} label={`${nombre(target)}: los pies de la misma persona`} t={tb} headers={headers}
        markers={[...here.map(p => ({ point: side(p, target).point, label: String(between.indexOf(p) + 1), tone: 'done' })), ...(pending.b ? [{ point: pending.b.point, label: '?', tone: 'pending' }] : [])]} boxes={here.flatMap(p => side(p, target).bbox ? [{ box: side(p, target).bbox!, tone: 'done' }] : [])} onPoint={p => !disabled && mark('b', p)} onBox={(box,p) => !disabled && mark('b', p, box)} />
    </div>}
    {(pending.a || pending.b) && <p className="subtle">Falta marcar a la misma persona en {pending.a ? nombre(target) : nombre(base)}. <button onClick={() => setPending({})}>Cancelar</button></p>}

    <div className="pp-list">
      {between.length === 0 ? <p className="subtle">Todavía no hay parejas entre estas dos cámaras.</p> :
        <table><thead><tr><th>#</th><th>Instantes</th><th>Estado</th><th /></tr></thead>
          <tbody>{between.map((p, i) => <tr key={p.id} className={fila(p.id)?.fueraDeTiempo ? 'pp-bad' : ''}>
            <td>{i + 1}</td><td><button className="link" onClick={() => { setTa(pairTime(p, base)); setTb(pairTime(p, target)); }}>{pairTime(p, base).toFixed(1)} / {pairTime(p, target).toFixed(1)} s</button></td>
            <td>{estado(p.id)}</td>
            <td><button disabled={disabled} title="Quitar pareja" onClick={() => update({ personPairs: (configRef.current.personPairs || []).filter(x => x.id !== p.id) })}>×</button></td></tr>)}</tbody></table>}
    </div>

    {between.length > 0 && between.length < MIN_PAREJAS_RELACION && <p className="subtle">Faltan {MIN_PAREJAS_RELACION - between.length} parejas para relacionar estas cámaras.</p>}
    {calculando && <p className="subtle" role="status">Comprobando con estas personas…</p>}
    {report && !calculando && <div className={`notice ${report.avisos.some(a => a.nivel !== 'info') ? 'warning' : ''}`} role="status">
      <strong>{report.temporal.verificada ? `${nombre(base)} y ${nombre(target)} relacionadas y sincronizadas` : 'Todavía no se puede fijar el desfase de tiempo'}</strong>
      {report.temporal.verificada && <span>{Math.abs(report.temporal.offset) < 0.15 ? 'Los dos videos ya coinciden en el tiempo.' : `${nombre(target)} va ${Math.abs(report.temporal.offset).toFixed(2)} s ${report.temporal.offset > 0 ? 'adelantada' : 'atrasada'} respecto de ${nombre(base)}${report.temporal.necesita ? ': se corrige al leer los videos.' : ' (ya corregido).'}`}</span>}
      {report.espacial && <span>En el plano, la misma persona queda a {report.espacial.mediana.toFixed(2)} {unit} entre las dos cámaras (mediana de {report.espacial.n} parejas){report.espacial.concuerdan ? ': sus puntos del suelo concuerdan.' : '.'}</span>}
      <ul className="pp-problemas">{report.avisos.map((a, i) => <li key={i} className={`pp-${a.nivel}`}><b>{rotulo[a.nivel]}</b>{a.texto}</li>)}</ul>
    </div>}
    {between.length >= MIN_PAREJAS_RELACION && <div className="pp-actions"><button disabled={disabled || session.busy || calculando} onClick={() => void comprobar()}>Volver a comprobar</button></div>}

    <div className="pp-related">
      <h3>Cámaras relacionadas en este proyecto</h3>
      {!relacionadas.length ? <p className="subtle">Ninguna todavía. Sin relaciones, cada cámara conserva sus propios IDs.</p> :
        <ul>{relacionadas.map(r => <li key={r.a + r.b}><b>{nombre(r.a)} ↔ {nombre(r.b)}</b> · {r.n} {r.n === 1 ? 'pareja' : 'parejas'} · {r.relacionadas ? 'relacionadas' : `faltan ${MIN_PAREJAS_RELACION - r.n}`}</li>)}</ul>}
    </div>
  </section>;
}
