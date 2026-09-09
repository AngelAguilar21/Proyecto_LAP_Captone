import { useTracking } from '../../hooks/useTracking';
import { useCameras } from '../../hooks/useCameras';
import { usePersons } from '../../hooks/usePersons';
import { CameraStatusDot, PERSON_STATUS_COLOR, PERSON_STATUS_LABEL } from '../StatusDot';
import { cameraLabel, formatDurationSeconds } from '../../utils/format';
import { REAL_SESSION } from '../../data/realSession';
import type { Camera, CameraId, NormalizedPoint } from '../../types/camera';

const CAM_ACCENT: Record<CameraId, string> = { A: '#5b7a99', B: '#a67c52' };

function polyPoints(pts: NormalizedPoint[]): string {
  return pts.map(([x, y]) => `${x},${y}`).join(' ');
}

function centroid(pts: NormalizedPoint[]): NormalizedPoint {
  const n = pts.length || 1;
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
}

/** Encuadre del plano: la union real de las posiciones observadas
 * (meta.rangoX/rangoY, calculadas del historial real) y de las anclas de
 * camara derivadas de sus propios poligonos de alcance -- nunca un
 * rectangulo de losa fijo, porque el prototipo no calibro uno en estas
 * mismas unidades (ver config/camaras.json: metros_por_unidad = null). */
function computeViewBox(cameras: Record<CameraId, Camera>) {
  const [rx0, rx1] = REAL_SESSION.meta.rangoX;
  const [ry0, ry1] = REAL_SESSION.meta.rangoY;
  const anchors = (['A', 'B'] as CameraId[]).map((id) => cameras[id].anchor);
  const xs = [rx0, rx1, ...anchors.map((a) => a[0])];
  const ys = [ry0, ry1, ...anchors.map((a) => a[1])];
  const pad = 0.3;
  const x0 = Math.min(...xs) - pad;
  const x1 = Math.max(...xs) + pad;
  const y0 = Math.min(...ys) - pad;
  const y1 = Math.max(...ys) + pad;
  return { x0, y0, w: x1 - x0, h: y1 - y0 };
}

function PersonCard({
  x,
  y,
  viewW,
  flip,
  id,
  color,
  status,
  cameras,
  route,
  firstSeen,
  lastSeen,
}: {
  x: number;
  y: number;
  viewW: number;
  flip: boolean;
  id: string;
  color: string;
  status: 'active' | 'transitioning';
  cameras: CameraId[];
  route: CameraId[];
  firstSeen: number;
  lastSeen: number;
}) {
  const cardW = viewW * 0.22;
  const cardH = viewW * 0.12;
  const gap = viewW * 0.02;
  const cx = flip ? x - cardW - gap : x + gap;
  const cy = y - cardH / 2;
  const line = (i: number) => cy + cardH * (0.24 + i * 0.19);

  return (
    <g pointerEvents="none">
      <rect x={cx} y={cy} width={cardW} height={cardH} rx={cardW * 0.03} fill="#0a0b0fe6" stroke={color} strokeWidth={viewW * 0.0015} />
      <circle cx={cx + cardW * 0.07} cy={line(0)} r={cardW * 0.028} fill={color} />
      <text x={cx + cardW * 0.14} y={line(0) + cardW * 0.012} fontSize={cardW * 0.09} fontWeight={800} fill="#ffffff" fontFamily="JetBrains Mono, monospace">
        ID {id}
      </text>
      <circle cx={cx + cardW * 0.07} cy={line(1)} r={cardW * 0.02} fill={PERSON_STATUS_COLOR[status]} />
      <text x={cx + cardW * 0.12} y={line(1) + cardW * 0.01} fontSize={cardW * 0.065} fill="#c3c2b7" fontFamily="JetBrains Mono, monospace">
        {PERSON_STATUS_LABEL[status]} · {cameraLabel(cameras)}
      </text>
      <text x={cx + cardW * 0.07} y={line(2) + cardW * 0.01} fontSize={cardW * 0.065} fill="#7d818c" fontFamily="JetBrains Mono, monospace">
        Ruta real: {route.join(' → ')}
      </text>
      <text x={cx + cardW * 0.07} y={line(3) + cardW * 0.01} fontSize={cardW * 0.065} fill="#7d818c" fontFamily="JetBrains Mono, monospace">
        Video {formatDurationSeconds(firstSeen)}–{formatDurationSeconds(lastSeen)} ({formatDurationSeconds(lastSeen - firstSeen)})
      </text>
    </g>
  );
}

export function MapView() {
  const { state, selectPerson, setHighlightedCamera } = useTracking();
  const cameras = useCameras();
  const persons = usePersons();
  const { layers, selectedPersonId, highlightedCamera } = state;
  const selectedPerson = selectedPersonId ? state.persons[selectedPersonId] : null;

  const view = computeViewBox(cameras);
  const midpoint: NormalizedPoint = [
    (centroid(cameras.A.coverage)[0] + centroid(cameras.B.coverage)[0]) / 2,
    (centroid(cameras.A.coverage)[1] + centroid(cameras.B.coverage)[1]) / 2,
  ];

  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-md border border-hairline bg-surface">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <span className="text-sm font-semibold uppercase tracking-wide text-ink-primary">Plano de la losa</span>
        <span className="text-[10px] text-ink-muted">datos reales · proyecto_lap_prototipo/data/historial.sqlite</span>
      </div>

      <svg
        viewBox={`${view.x0} ${view.y0} ${view.w} ${view.h}`}
        className="flex-1"
        preserveAspectRatio="xMidYMid meet"
        onClick={() => {
          setHighlightedCamera(null);
          selectPerson(null);
        }}
      >
        {Array.from({ length: 12 }).map((_, i) => {
          const gx = view.x0 + (view.w * (i + 1)) / 13;
          return <line key={`v${i}`} x1={gx} y1={view.y0} x2={gx} y2={view.y0 + view.h} stroke="#ffffff09" strokeWidth={view.w * 0.0012} />;
        })}
        {Array.from({ length: 8 }).map((_, i) => {
          const gy = view.y0 + (view.h * (i + 1)) / 9;
          return <line key={`h${i}`} x1={view.x0} y1={gy} x2={view.x0 + view.w} y2={gy} stroke="#ffffff09" strokeWidth={view.w * 0.0012} />;
        })}

        {/* alcance real de cada camara: solo contorno punteado, sin relleno */}
        {layers.coverageA && (
          <polygon points={polyPoints(cameras.A.coverage)} fill="none" stroke={CAM_ACCENT.A} strokeWidth={view.w * 0.0035} strokeDasharray={`${view.w * 0.012} ${view.w * 0.009}`} />
        )}
        {layers.coverageB && (
          <polygon points={polyPoints(cameras.B.coverage)} fill="none" stroke={CAM_ACCENT.B} strokeWidth={view.w * 0.0035} strokeDasharray={`${view.w * 0.012} ${view.w * 0.009}`} />
        )}
        {layers.transitionZone && layers.coverageA && layers.coverageB && (
          <text x={midpoint[0]} y={midpoint[1]} textAnchor="middle" fontSize={view.w * 0.022} fill="#ffffff80" fontFamily="JetBrains Mono, monospace" letterSpacing={0.01}>
            ZONA DE TRANSICIÓN
          </text>
        )}

        {layers.connections && (
          <line
            x1={cameras.A.anchor[0]}
            y1={cameras.A.anchor[1]}
            x2={cameras.B.anchor[0]}
            y2={cameras.B.anchor[1]}
            stroke="#ffffff1a"
            strokeDasharray={`${view.w * 0.01} ${view.w * 0.008}`}
            strokeWidth={view.w * 0.0025}
          />
        )}

        {/* trayectorias reales recorridas hasta el frame actual */}
        {layers.trajectories &&
          persons.map((p) => {
            if (p.trajectory.length < 2) return null;
            const points = p.trajectory.map((t) => `${t.x},${t.y}`).join(' ');
            return (
              <polyline
                key={p.id}
                points={points}
                fill="none"
                stroke={p.color}
                strokeOpacity={p.id === selectedPersonId ? 0.6 : 0.28}
                strokeWidth={view.w * 0.0032}
              />
            );
          })}

        {/* camaras: icono derivado de su propio alcance real (esquinas opuestas) */}
        {(['A', 'B'] as CameraId[]).map((id) => {
          const cam = cameras[id];
          const dimmed = highlightedCamera !== null && highlightedCamera !== id;
          return (
            <g
              key={id}
              opacity={dimmed ? 0.35 : 1}
              className="cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                setHighlightedCamera(highlightedCamera === id ? null : id);
              }}
            >
              <circle cx={cam.anchor[0]} cy={cam.anchor[1]} r={view.w * 0.017} fill={CAM_ACCENT[id]} />
              <circle cx={cam.anchor[0]} cy={cam.anchor[1]} r={view.w * 0.026} fill="none" stroke={CAM_ACCENT[id]} strokeWidth={view.w * 0.0025} />
              <text
                x={cam.anchor[0]}
                y={cam.anchor[1] - view.w * 0.035}
                textAnchor="middle"
                fontSize={view.w * 0.02}
                fontWeight={700}
                fill="#e8e6df"
                fontFamily="JetBrains Mono, monospace"
              >
                CÁMARA {id}
              </text>
            </g>
          );
        })}

        {/* personas reales: nodo + ID en su color, con placa de fondo para legibilidad */}
        {layers.persons &&
          persons.map((p) => {
            const selected = p.id === selectedPersonId;
            const r = selected ? view.w * 0.017 : view.w * 0.013;
            const labelW = view.w * 0.014 + p.id.length * view.w * 0.012;
            return (
              <g
                key={p.id}
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  selectPerson(selected ? null : p.id);
                }}
              >
                {p.status === 'transitioning' && (
                  <circle cx={p.x} cy={p.y} r={r + view.w * 0.011} fill="none" stroke="#fab219" strokeWidth={view.w * 0.0025} strokeDasharray={`${view.w * 0.005} ${view.w * 0.004}`} />
                )}
                <line
                  x1={p.x}
                  y1={p.y}
                  x2={p.x + Math.cos((-p.heading * Math.PI) / 180) * view.w * 0.028}
                  y2={p.y + Math.sin((-p.heading * Math.PI) / 180) * view.w * 0.028}
                  stroke={p.color}
                  strokeWidth={view.w * 0.002}
                  opacity={0.7}
                />
                <circle cx={p.x} cy={p.y} r={r} fill={p.color} stroke={selected ? '#ffffff' : 'none'} strokeWidth={view.w * 0.0035} />
                <rect x={p.x + r + view.w * 0.004} y={p.y - view.w * 0.012} width={labelW} height={view.w * 0.021} rx={view.w * 0.004} fill="#0a0b0fcc" />
                <text
                  x={p.x + r + view.w * 0.004 + labelW / 2}
                  y={p.y + view.w * 0.004}
                  textAnchor="middle"
                  fontSize={view.w * 0.017}
                  fill={p.color}
                  fontWeight={800}
                  fontFamily="JetBrains Mono, monospace"
                >
                  {p.id}
                </text>
              </g>
            );
          })}

        {selectedPerson && (
          <PersonCard
            x={selectedPerson.x}
            y={selectedPerson.y}
            viewW={view.w}
            flip={selectedPerson.x > view.x0 + view.w * 0.6}
            id={selectedPerson.id}
            color={selectedPerson.color}
            status={selectedPerson.status}
            cameras={selectedPerson.cameras}
            route={selectedPerson.route}
            firstSeen={selectedPerson.firstSeen}
            lastSeen={selectedPerson.lastSeen}
          />
        )}
      </svg>
      <div className="flex items-center gap-4 border-t border-hairline px-4 py-2 text-[11px] text-ink-muted">
        <span className="flex items-center gap-1.5">
          <CameraStatusDot status={cameras.A.status} /> Cámara A · {cameras.A.fps} fps
        </span>
        <span className="flex items-center gap-1.5">
          <CameraStatusDot status={cameras.B.status} /> Cámara B · {cameras.B.fps} fps
        </span>
        <span className="ml-auto">click en una cámara resalta su alcance · click en una persona muestra su ficha</span>
      </div>
    </div>
  );
}
