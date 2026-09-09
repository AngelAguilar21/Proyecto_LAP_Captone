import { REAL_SESSION } from '../data/realSession';
import { colorForPersonId } from '../data/palette';
import type { Camera, CameraId } from '../types/camera';
import type { Person } from '../types/person';

interface DenseSample {
  x: number;
  y: number;
  cameras: CameraId[];
}

/** Por persona, un slot por bin de tiempo (ya viene denso/relleno-hacia-
 * adelante desde el script de export -- ver realSession.ts) o null fuera de
 * su ventana real [firstSeen, lastSeen]. Precalculado una sola vez. */
const denseByPerson: Record<string, (DenseSample | null)[]> = {};
for (const id of Object.keys(REAL_SESSION.personas)) {
  denseByPerson[id] = new Array(REAL_SESSION.meta.totalBins).fill(null);
}
REAL_SESSION.frames.forEach((frame, binIndex) => {
  frame.forEach((entry) => {
    denseByPerson[entry.id][binIndex] = { x: entry.x, y: entry.y, cameras: entry.camaras };
  });
});

function headingBetween(a: DenseSample, b: DenseSample): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) return 0;
  return (Math.atan2(-dy, dx) * 180) / Math.PI;
}

/** Estado de todas las personas reales en el bin `frameIndex` del replay.
 * Puramente derivado de la sesion real -- no muta nada entre llamadas. */
export function personsAtFrame(frameIndex: number): Record<string, Person> {
  const result: Record<string, Person> = {};
  const paso = REAL_SESSION.meta.paso;

  for (const [id, meta] of Object.entries(REAL_SESSION.personas)) {
    const sample = denseByPerson[id][frameIndex];
    if (!sample) continue;

    let prevSample: DenseSample | null = null;
    for (let i = frameIndex - 1; i >= 0; i -= 1) {
      const candidate = denseByPerson[id][i];
      if (candidate) {
        prevSample = candidate;
        break;
      }
    }

    const trajectory = [];
    for (let i = 0; i <= frameIndex; i += 1) {
      const s = denseByPerson[id][i];
      if (s) trajectory.push({ x: s.x, y: s.y, t: i * paso });
    }

    result[id] = {
      id,
      color: colorForPersonId(id),
      cameras: sample.cameras,
      x: sample.x,
      y: sample.y,
      heading: prevSample ? headingBetween(prevSample, sample) : 0,
      status: sample.cameras.length >= 2 ? 'transitioning' : 'active',
      firstSeen: meta.primero,
      lastSeen: meta.ultimo,
      route: meta.ruta,
      trajectory: trajectory.slice(-80),
    };
  }
  return result;
}

export function camerasAtFrame(persons: Record<string, Person>): Record<CameraId, Camera> {
  const ids: CameraId[] = ['A', 'B'];
  const result = {} as Record<CameraId, Camera>;
  ids.forEach((id) => {
    const base = REAL_SESSION.camaras[id];
    const peopleCount = Object.values(persons).filter((p) => p.cameras.includes(id)).length;
    result[id] = {
      id,
      label: `Cámara ${id}`,
      status: 'online',
      fps: base.fps,
      resolution: base.resolucion,
      anchor: base.ancla,
      coverage: base.alcance,
      peopleCount,
    };
  });
  return result;
}
