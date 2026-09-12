import { useId, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import type { Config, Person, Point, SessionState, Zone } from './types';
import { COLORS } from './types';
import Icon from './Icon';

export type MapTool = 'select' | 'camera' | 'polygon' | 'rectangle' | 'circle' | 'move' | 'calibrate';
interface Props {
  config: Config; state: SessionState; connected: boolean; editable?: boolean; compact?: boolean;
  selectedCamera: string; onCamera: (id: string) => void; selectedPerson?: string; onPerson?: (p: Person) => void;
  onChange?: (config: Config) => void; tool?: MapTool; onTool?: (tool: MapTool) => void;
  onCalibrationPoint?: (point: Point) => void;
}
const kinds: Record<string, string> = { roi: '#0789e9', queue: '#e2a037', restricted: '#d65d63', room: '#839cac', wall: '#c1ced6', door: '#6fc8ab', corridor: '#5c8096', commercial: '#29b48c' };

export default function MapCanvas({ config, state, connected, editable, compact, selectedCamera, onCamera, selectedPerson, onPerson, onChange, tool = 'select', onTool, onCalibrationPoint }: Props) {
  const svg = useRef<SVGSVGElement>(null);
  const pattern = useId().replace(/:/g, '');
  const [draft, setDraft] = useState<Point[]>([]);
  const [name, setName] = useState('Nueva zona ROI');
  const [kind, setKind] = useState<NonNullable<Zone['kind']>>('roi');
  const [layers, setLayers] = useState({ cameras: true, coverage: true, labels: true, trajectories: true, heat: true, prediction: false, zones: true });
  const [showLayers, setShowLayers] = useState(false);
  const drag = useRef<{ type: 'camera' | 'zone' | 'aim'; id: string | number; origin: Point; snapshot: Config } | null>(null);
  const moved = useRef(false);
  const active = connected && ['running', 'paused'].includes(state.status);
  const people = active ? Array.from(new Map(state.people.filter(p => p.point).map(p => [p.id, p] as const)).values()) : [];
  const scale = config.width / (compact ? 560 : 900);
  function point(e: PointerEvent): Point {
    const matrix = svg.current?.getScreenCTM();
    if (!matrix) return [0, 0];
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse());
    return [Math.max(0, Math.min(config.width, p.x)), Math.max(0, Math.min(config.height, p.y))];
  }
  function finish(points: Point[], shape: Zone['shape']) {
    if (!onChange || points.length < 3 || !name.trim()) return;
    onChange({ ...config, zones: [...config.zones, { id: crypto.randomUUID(), name: name.trim(), kind, shape, points }] });
    setDraft([]); onTool?.('select');
  }
  function click(e: PointerEvent<SVGSVGElement>) {
    if (!editable || moved.current) { moved.current = false; return; }
    const p = point(e);
    if (tool === 'camera') onChange?.({ ...config, cameras: config.cameras.map(c => c.id === selectedCamera ? { ...c, x: p[0], y: p[1] } : c) });
    else if (tool === 'calibrate') onCalibrationPoint?.(p);
    else if (tool === 'polygon') setDraft(v => [...v, p]);
    else if (tool === 'rectangle' || tool === 'circle') {
      if (!draft.length) setDraft([p]);
      else if (tool === 'rectangle') finish([draft[0], [p[0], draft[0][1]], p, [draft[0][0], p[1]]], 'rectangle');
      else {
        const center = draft[0];
        const radius = Math.min(Math.hypot(p[0]-center[0], p[1]-center[1]), center[0], center[1], config.width-center[0], config.height-center[1]);
        if (radius > .001) finish(Array.from({ length: 36 }, (_, i) => [center[0] + Math.cos(i * Math.PI / 18) * radius, center[1] + Math.sin(i * Math.PI / 18) * radius]), 'circle');
      }
    }
  }
  function beginDrag(e: PointerEvent, type: 'camera' | 'zone' | 'aim', id: string | number) {
    if (!editable || (type !== 'aim' && tool !== 'move')) return;
    e.stopPropagation(); moved.current = false;
    drag.current = { type, id, origin: point(e), snapshot: config };
    svg.current?.setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (!drag.current || !onChange) return;
    const p = point(e), d = drag.current;
    const dx = p[0]-d.origin[0], dy = p[1]-d.origin[1];
    if (Math.abs(dx)+Math.abs(dy) < config.width / 1000) return;
    moved.current = true;
    if (d.type === 'camera') onChange({ ...config, cameras: d.snapshot.cameras.map(c => c.id === d.id ? { ...c, x: Math.max(0, Math.min(config.width, c.x+dx)), y: Math.max(0, Math.min(config.height, c.y+dy)) } : c) });
    else if (d.type === 'aim') {
      const cam = d.snapshot.cameras.find(c => c.id === d.id);
      if (!cam) return;
      const heading = (Math.atan2(p[1]-cam.y, p[0]-cam.x) * 180 / Math.PI + 360) % 360;
      const range = Math.max(0.2, Math.hypot(p[0]-cam.x, p[1]-cam.y));
      onChange({ ...config, cameras: d.snapshot.cameras.map(c => c.id === d.id ? { ...c, heading, range } : c) });
    } else {
      const zone = d.snapshot.zones[d.id as number];
      const tx = Math.max(-Math.min(...zone.points.map(v => v[0])), Math.min(dx, config.width-Math.max(...zone.points.map(v => v[0]))));
      const ty = Math.max(-Math.min(...zone.points.map(v => v[1])), Math.min(dy, config.height-Math.max(...zone.points.map(v => v[1]))));
      onChange({ ...config, zones: d.snapshot.zones.map((z, i) => i === d.id ? { ...z, points: z.points.map(v => [v[0]+tx, v[1]+ty] as Point) } : z) });
    }
  }
  function coverageShape(c: Config['cameras'][number]) {
    const angle = (c.heading ?? 90) * Math.PI / 180, radius = c.range ?? config.width * .25;
    if (c.coverageShape === 'rectangle') {
      const half = (c.coverageWidth ?? 2) / 2;
      const nx = -Math.sin(angle), ny = Math.cos(angle);
      const near: Point = [c.x + nx * half, c.y + ny * half];
      const far: Point = [c.x + Math.cos(angle) * radius, c.y + Math.sin(angle) * radius];
      const points: Point[] = [[c.x - nx * half, c.y - ny * half], near, [far[0] + nx * half, far[1] + ny * half], [far[0] - nx * half, far[1] - ny * half]];
      return { d: `M${points.map(p => p.join(',')).join('L')}Z`, tip: far };
    }
    const half = (c.fov ?? 60) * Math.PI / 360;
    const p1: Point = [c.x + Math.cos(angle-half) * radius, c.y + Math.sin(angle-half) * radius];
    const p2: Point = [c.x + Math.cos(angle+half) * radius, c.y + Math.sin(angle+half) * radius];
    const tip: Point = [c.x + Math.cos(angle) * radius, c.y + Math.sin(angle) * radius];
    return { d: `M${c.x},${c.y} L${p1.join(',')} A${radius},${radius} 0 0 1 ${p2.join(',')} Z`, tip };
  }
  const chooseTool = (next: MapTool) => { setDraft([]); onTool?.(next); };
  const selected = config.cameras.find(c => c.id === selectedCamera);
  return <div className={`aero-map ${compact ? 'compact' : ''}`}>
    <div className="map-toolbar"><div className="inline"><Icon name="map" size={15}/><span>{config.floor || 'Plano principal'}</span><span className="subtle">{config.width} × {config.height} {config.unit === 'meters' ? 'm' : 'u'}</span></div><div className="inline">{editable && <><button title="Colocar cámara seleccionada" className={tool === 'camera' ? 'on' : ''} onClick={() => chooseTool('camera')}><Icon name="camera" size={14}/><span>Cámara</span></button><button className={tool === 'polygon' ? 'on' : ''} onClick={() => chooseTool('polygon')}>Polígono</button><button className={tool === 'rectangle' ? 'on' : ''} onClick={() => chooseTool('rectangle')}>Rectángulo</button><button className={tool === 'circle' ? 'on' : ''} onClick={() => chooseTool('circle')}>Círculo</button><button className={tool === 'move' ? 'on' : ''} onClick={() => chooseTool('move')}>Mover</button></>}<button title="Mostrar capas del plano" onClick={() => setShowLayers(!showLayers)}><Icon name="layers" size={15}/></button></div></div>
    {editable && ['polygon', 'rectangle', 'circle'].includes(tool) && <div className="drawing-options"><input aria-label="Nombre del área" value={name} onChange={e => setName(e.target.value)} maxLength={80}/><select aria-label="Tipo de área" value={kind} onChange={e => setKind(e.target.value as NonNullable<Zone['kind']>)}>{Object.entries({ roi: 'Zona ROI', queue: 'Cola', restricted: 'Restringida', room: 'Sala', wall: 'Muro', door: 'Puerta', corridor: 'Pasillo', commercial: 'Comercio' }).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select><span>{tool === 'polygon' ? `${draft.length} vértices` : draft.length ? 'Marca el segundo punto' : tool === 'circle' ? 'Marca el centro y el radio' : 'Marca dos esquinas'}</span>{tool === 'polygon' && <button disabled={draft.length < 3} onClick={() => finish(draft, 'polygon')}>Cerrar área</button>}<button onClick={() => setDraft(p => p.slice(0, -1))}>Deshacer</button><button onClick={() => chooseTool('select')}>Cancelar</button></div>}
    {editable && tool === 'calibrate' && <div className="map-hint">Calibración: marca la correspondencia del punto del video sobre este plano.</div>}
    <div className="map-stage"><svg ref={svg} viewBox={`0 0 ${config.width} ${config.height}`} onPointerUp={e => { const wasDrag = !!drag.current; drag.current = null; if (!wasDrag) click(e); }} onPointerMove={move} onPointerCancel={() => { drag.current = null; }} aria-label={editable ? 'Editor interactivo del plano' : 'Plano vivo de personas'} role="img"><defs><pattern id={pattern} width={config.width / 30} height={config.height / 20} patternUnits="userSpaceOnUse"><path d={`M ${config.width/30} 0 H0 V${config.height/20}`} fill="none" stroke="#527488" strokeWidth={scale*.6}/></pattern><radialGradient id={`${pattern}-heat`}><stop offset="0" stopColor="#f64545" stopOpacity=".85"/><stop offset=".3" stopColor="#ffa632" stopOpacity=".65"/><stop offset=".6" stopColor="#f6df49" stopOpacity=".4"/><stop offset="1" stopColor="#59d680" stopOpacity="0"/></radialGradient></defs><rect width={config.width} height={config.height} fill={config.background ? '#ced8db' : '#10212d'}/>{config.background && <image href={config.background} width={config.width} height={config.height} preserveAspectRatio="none" opacity=".86"/>}<rect width={config.width} height={config.height} fill={`url(#${pattern})`} opacity={config.background ? '.22' : '.3'}/>
      {state.mode === 'demo' && !config.background && !config.zones.length && <g opacity=".6">{[[.06,.08,.26,.26,'Accesos'],[.38,.08,.23,.26,'Check-in'],[.69,.08,.25,.26,'Seguridad'],[.06,.67,.25,.25,'Sala de espera'],[.39,.67,.22,.25,'Servicios'],[.69,.67,.25,.25,'Comercios']].map((r, i) => <g key={i}><rect x={Number(r[0])*config.width} y={Number(r[1])*config.height} width={Number(r[2])*config.width} height={Number(r[3])*config.height} fill="#536a7944" stroke="#92aab7" strokeWidth={scale*2}/><text x={(Number(r[0])+Number(r[2])/2)*config.width} y={(Number(r[1])+Number(r[3])/2)*config.height} fill="#bdd3e1" fontSize={scale*12} textAnchor="middle">{r[4]}</text></g>)}</g>}
      {layers.zones && config.zones.map((z, i) => <g key={z.id || i} onPointerDown={e => beginDrag(e, 'zone', i)} className={tool === 'move' ? 'move-target' : ''}><polygon points={z.points.map(p => p.join(',')).join(' ')} fill={z.color || kinds[z.kind || 'roi']} fillOpacity={z.kind === 'wall' ? .6 : .13} stroke={z.color || kinds[z.kind || 'roi']} strokeWidth={scale*1.7} strokeDasharray={z.kind === 'roi' ? `${scale*5} ${scale*4}` : undefined}/>{layers.labels && <text x={z.points.reduce((n,p)=>n+p[0],0)/z.points.length} y={z.points.reduce((n,p)=>n+p[1],0)/z.points.length} textAnchor="middle" fill={config.background ? '#073043' : '#cbe3ee'} fontSize={scale*12}>{z.name}</text>}</g>)}
      {layers.coverage && config.cameras.map(c => { const cov = coverageShape(c); return <path key={c.id} d={cov.d} fill="#179bea" opacity={c.id === selectedCamera ? '.2' : '.1'} stroke="#19a5ff" strokeWidth={scale}/>; })}
      {editable && layers.coverage && tool !== 'move' && (() => { const cam = config.cameras.find(c => c.id === selectedCamera); if (!cam) return null; const cov = coverageShape(cam); return <g className="aim-handle" onPointerDown={e => beginDrag(e, 'aim', cam.id)}><line x1={cam.x} y1={cam.y} x2={cov.tip[0]} y2={cov.tip[1]} stroke="#ffce81" strokeDasharray={`${scale*3} ${scale*3}`} strokeWidth={scale}/><circle cx={cov.tip[0]} cy={cov.tip[1]} r={scale*7} fill="#ffce81" stroke="#4a2f00" strokeWidth={scale}/></g>; })()}
      {layers.heat && state.analytics.heat.map((cell, i) => <circle key={i} cx={cell.x+cell.size/2} cy={cell.y+cell.size/2} r={cell.size*2.4} fill={`url(#${pattern}-heat)`} opacity={Math.min(.85,cell.seconds/Math.max(1,state.analytics.heat[0]?.seconds||1))}/>)}
      {layers.trajectories && people.map(p => <polyline key={p.id} points={p.history.map(h => `${h[0]},${h[1]}`).join(' ')} fill="none" stroke={p.association === 'uncertain' ? '#ffae42' : '#21aaff'} opacity={selectedPerson === p.id ? 1 : .45} strokeWidth={scale*(selectedPerson === p.id ? 2.4 : 1.1)}/>)}
      {active && state.analytics.clusters.map((c,i) => <g key={i}><circle cx={c.center[0]} cy={c.center[1]} r={c.radius} fill={c.alert ? '#ef444420' : '#fda84a13'} stroke={c.alert ? '#ff5e66' : '#f2c268'} strokeWidth={scale*1.7} strokeDasharray={`${scale*5} ${scale*4}`}/><text x={c.center[0]} y={c.center[1]-c.radius+scale*15} textAnchor="middle" fill={c.alert ? '#ffbdba' : '#ffe2a8'} fontSize={scale*12}>{c.count} personas · {c.duration.toFixed(0)}s</text></g>)}
      {layers.cameras && config.cameras.map((c, i) => <g key={c.id} transform={`translate(${c.x},${c.y})`} className="map-camera" onPointerDown={e => beginDrag(e,'camera',c.id)} onPointerUp={e => { if (tool !== 'move') {e.stopPropagation(); onCamera(c.id);} }}><circle r={scale*14} fill={selectedCamera===c.id ? '#096cbd' : '#132b3e'} stroke={COLORS[i%COLORS.length]} strokeWidth={scale*1.7}/><path d={`M${-scale*7},${-scale*4} h${scale*8} v${scale*8} h${-scale*8}z M${scale*2},0 l${scale*5},${-scale*4}v${scale*8}z`} fill="#c2e5f8"/>{layers.labels && <text y={scale*29} fill={config.background ? '#092232' : '#bfe4fa'} fontSize={scale*11} textAnchor="middle" fontWeight="600">{c.id}</text>}</g>)}
      {editable && selected?.pairs.map((p,i) => <g key={i}><circle cx={p[2]} cy={p[3]} r={scale*5} fill="#ffca65"/><text x={p[2]+scale*8} y={p[3]-scale*3} fontSize={scale*12} fill="#ffdb99">{i+1}</text></g>)}
      {draft.length > 0 && <g><polyline points={draft.map(p=>p.join(',')).join(' ')} fill="#ffb34022" stroke="#ffce81" strokeWidth={scale*2}/>{draft.map((p,i)=><circle key={i} cx={p[0]} cy={p[1]} r={scale*4} fill="#ffce81"/>)}</g>}
      {people.map(p => <g key={p.id} transform={`translate(${p.point![0]},${p.point![1]})`} className="map-person" onPointerUp={e => {e.stopPropagation(); onPerson?.(p);}}><circle r={scale*(selectedPerson===p.id ? 7.5 : 4.8)} fill={p.association==='uncertain' ? '#ffb340' : '#21a8ff'} stroke="#061c31" strokeWidth={scale*1.3}/>{layers.labels && <text x={scale*9} y={-scale*7} fontSize={scale*10} fill={config.background ? '#06263c' : '#d4eeff'}>{p.id}{p.association==='uncertain' ? ' ?' : p.association==='estimated' ? ' ~' : ''}</text>}{layers.prediction && p.velocity && <path d={`M0,0 L${p.velocity[0]*2},${p.velocity[1]*2}`} stroke="#ffc777" strokeDasharray={`${scale*4} ${scale*3}`} strokeWidth={scale*1.4}/>}</g>)}
    </svg>{showLayers && <div className="layer-menu"><strong>Capas del plano</strong>{Object.entries({ cameras: 'Cámaras', coverage: 'Alcance orientativo', labels: 'Etiquetas e IDs', trajectories: 'Trayectorias recientes', heat: 'Calor de ocupación', prediction: 'Dirección estimada', zones: 'Zonas dibujadas' }).map(([key,label])=><label key={key}><input type="checkbox" checked={layers[key as keyof typeof layers]} onChange={()=>setLayers({...layers,[key]:!layers[key as keyof typeof layers]})}/>{label}</label>)}</div>}
      {!config.mapConfigured && !config.background && !config.zones.length && state.mode !== 'demo' && <div className="map-empty"><Icon name="map" size={30}/><strong>Plano no configurado</strong><span>Importa tu plano o define un espacio en blanco.<br/>Después coloca y calibra tus cámaras.</span></div>}
      <div className="scale-indicator"><span>{(config.width/5).toFixed(1)} {config.unit==='meters' ? 'm' : 'unidades relativas'}</span><i/></div>
    </div><div className="map-caption"><span><i className="dot blue"/> ID local</span><span><i className="dot amber"/> Asociación incierta</span><span>~ Asociación estimada</span><span>Alcance orientativo · requiere calibración</span></div>
  </div>;
}
