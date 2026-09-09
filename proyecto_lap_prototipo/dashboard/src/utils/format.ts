import type { CameraId } from '../types/camera';

/** mm:ss.s relativo al inicio del video -- esto es el replay de una
 * grabacion real, no un feed en vivo, asi que no se muestra un reloj de
 * pared inventado. */
export function formatVideoTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(1).padStart(4, '0')}`;
}

export function formatDurationSeconds(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds - m * 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function cameraLabel(ids: CameraId[] | CameraId | null | undefined): string {
  const arr = ids == null ? [] : Array.isArray(ids) ? ids : [ids];
  if (arr.length === 0) return '—';
  return arr.map((id) => `Cámara ${id}`).join(' + ');
}
