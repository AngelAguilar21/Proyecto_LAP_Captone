import type { NormalizedPoint } from '../types/camera';

/** Ray-casting point-in-polygon. Suficiente para poligonos simples
 * (triangulos/cuadrilateros) como los de cobertura de camara -- no hace
 * falta una libreria para esto. */
export function pointInPolygon(point: NormalizedPoint, polygon: NormalizedPoint[]): boolean {
  const [px, py] = point;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const intersects = yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

export interface PathSample {
  x: number;
  y: number;
  headingDeg: number;
}

/** Recorre `path` en vaiven (ida y vuelta) segun el tiempo transcurrido,
 * a una velocidad fija en segundos por tramo -- da un movimiento peatonal
 * continuo y predecible, sin depender de un backend real todavia. */
export function pingPongAlongPath(
  path: NormalizedPoint[],
  elapsedSec: number,
  secondsPerSegment: number
): PathSample {
  const segments = path.length - 1;
  if (segments <= 0) {
    const [x, y] = path[0];
    return { x, y, headingDeg: 0 };
  }
  const cycleLen = segments * secondsPerSegment * 2;
  const tt = ((elapsedSec % cycleLen) + cycleLen) % cycleLen;
  const forward = tt < segments * secondsPerSegment;
  const localT = forward ? tt : cycleLen - tt;
  const segFloat = Math.min(segments - 1e-6, localT / secondsPerSegment);
  const segIndex = Math.floor(segFloat);
  const frac = segFloat - segIndex;
  const [x0, y0] = path[segIndex];
  const [x1, y1] = path[Math.min(segIndex + 1, segments)];
  const x = x0 + (x1 - x0) * frac;
  const y = y0 + (y1 - y0) * frac;
  const dx = forward ? x1 - x0 : x0 - x1;
  const dy = forward ? y1 - y0 : y0 - y1;
  const headingDeg = (Math.atan2(-dy, dx) * 180) / Math.PI;
  return { x, y, headingDeg };
}
