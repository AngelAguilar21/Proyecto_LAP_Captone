export type Point = [number, number];
export interface Zone { id: string; name: string; points: Point[]; threshold: number; dwell: number }
export interface Config { source: string; name: string; recordedAt?: string; confidence: number; interval: number; maxSide: number; zones: Zone[] }
export interface Episode { id: number; zone: string; zoneId?: string; start: number; confirmed: number; end: number | null; peak: number; duration: number; reason: string }
export interface Sample { t: number; count: number; zones: {id: string; name: string; count: number}[] }
export interface State {
  status: string; t: number; samples: number; error?: string; session?: string; name?: string; created?: string; timeOrigin?: string;
  count?: number; peakAt?: number; peak?: number; mean?: number; personSeconds?: number; observedSeconds?: number;
  inferenceMs?: number; elapsed?: number; duration?: number; live?: boolean; config?: Config;
  points: Point[]; series: Sample[]; episodes?: Episode[]; heat?: number[][]; instant?: number[][];
  zones?: { id: string; name: string; count: number; peak: number; peakAt?: number; personSeconds: number; alert: boolean }[];
}
export interface Ready { ready: boolean; missing: string[]; code: boolean; weights: boolean; model: string; device: string }
export const STATUS: Record<string, string> = { idle: 'Listo para preparar', starting: 'Preparando análisis', running: 'Analizando', paused: 'En pausa', stopping: 'Deteniendo', stopped: 'Análisis detenido', ended: 'Análisis completado', error: 'Análisis interrumpido' };
export const active = (s: string) => ['starting', 'running', 'paused', 'stopping'].includes(s);
export const timeLabel = (n = 0) => {const seconds=Math.max(0,Math.round(n));return `${Math.floor(seconds/60).toString().padStart(2,'0')}:${(seconds%60).toString().padStart(2,'0')}`;};
export const wholeZone = (): Zone => ({ id: 'full', name: 'Área completa', points: [[0,0],[1,0],[1,1],[0,1]], threshold: 10, dwell: 5 });
