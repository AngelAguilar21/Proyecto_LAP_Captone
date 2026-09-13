export type Point = [number, number];
export type SourceMode = 'recordings' | 'live' | 'demo';
export type View = 'overview' | 'setup' | 'map' | 'cameras' | 'lab' | 'dashboard' | 'zones' | 'rules' | 'reports' | 'audit';
export interface Camera {
  color?: string; active?: boolean; restrictCoverage?: boolean;
  id: string; name?: string; location?: string; type?: 'fixed' | 'overhead' | 'tilted';
  source: string | number; x: number; y: number; offset: number; links: string[]; pairs: number[][];
  heading?: number; fov?: number; range?: number; height?: number; tilt?: number; coverageShape?: 'cone' | 'rectangle' | 'free'; coverageWidth?: number; coveragePolygon?: Point[]; detectionZone?: Point[];
}
export interface Zone {
  id?: string; name: string; points: Point[]; kind?: 'roi' | 'queue' | 'restricted' | 'room' | 'wall' | 'door' | 'corridor' | 'commercial';
  shape?: 'polygon' | 'circle' | 'rectangle'; color?: string;
  rule?: { enabled: boolean; minPeople: number; dwell: number };
}
export interface Config {
  workArea?: Point[]; planLines?: number[][];
  width: number; height: number; unit: 'relative' | 'meters'; background: string; radius: number;
  minPeople: number; dwell: number; handoffSeconds: number; matchDistance: number; clocksVerified: boolean;
  cameras: Camera[]; zones: Zone[]; airport?: string; floor?: string; sourceMode?: SourceMode;
  mapConfigured?: boolean; setupComplete?: boolean; planName?: string; importWarnings?: string[];
}
export interface Person {
  id: string; camera: string; point: Point | null; history: number[][]; association: string;
  predicted: boolean; score?: number; pixel?: Point; velocity?: Point; nextCamera?: string | null;
}
export interface CameraStatus {
  id: string; status: string; count?: number; calibrated?: boolean; error?: string; timestamp?: number;
  width?: number; height?: number; fps?: number; processingMs?: number; sourceKey?: string; calibrationError?: number | null;
}
export interface HeatCell { x: number; y: number; size: number; seconds: number; peak: number; visits?: number }
export interface SessionState {
  status: string; mode?: string; session?: string; configRevision?: number; t: number; processingMs?: number;
  updatedAt?: number; serverTime?: number; error?: string; people: Person[]; cameras: CameraStatus[];
  events: { id: string; from: string; to: string; t: number }[];
  analytics: {
    clusters: { center: Point; radius: number; count: number; duration: number; alert: boolean }[];
    zones: { name: string; count: number; seconds?: number; peak?: number; visits?: number; alert?: boolean; duration?: number }[];
    heat: HeatCell[]; mappedCount: number;
  };
  totals?: { observed: number; identities: number; personSeconds: number; meanObservedSeconds: number; alerts: number };
  series?: { t: number; count: number; mapped: number; alerts: number }[];
  audit?: { at: string; action: string; detail: string }[];
  identityDeleted?: boolean;
  sourceChecks?: Record<string,{source:string|number;valid:boolean;width:number;height:number;fps:number;checkedAt:number}>;
}
export const STATUS: Record<string, string> = { idle: 'Sin sesión', starting: 'Conectando', running: 'Procesamiento activo', paused: 'Pausado', stopping: 'Finalizando', stopped: 'Sesión finalizada', ended: 'Grabación finalizada', error: 'Error', live: 'Fuente válida', ready: 'Preparada' };
export const COLORS = ['#19a5ff', '#6c7fe0', '#b59aff', '#ffbb55', '#ef7aa0', '#53c9e8'];
export const EMPTY_STATE: SessionState = { status: 'idle', t: 0, people: [], cameras: [], events: [], analytics: { clusters: [], zones: [], heat: [], mappedCount: 0 } };
export const isActive = (s: string) => ['starting', 'running', 'paused', 'stopping'].includes(s);
export const isStream = (source: string | number) => typeof source === 'number' || /^(rtsp|https?|rtmp):\/\//i.test(source);
export const formatTime = (value: number) => `${Math.floor(value / 60).toString().padStart(2, '0')}:${Math.floor(value % 60).toString().padStart(2, '0')}`;
export const labelAssociation = (p: Person) => p.association === 'estimated' ? 'Asociación estimada' : p.association === 'uncertain' ? 'Confianza insuficiente para asociación' : p.association === 'synthetic' ? 'Simulación' : 'ID local confirmado';
export const freshCamera = (): Camera => ({ id: `C-${crypto.randomUUID().slice(0, 5).toUpperCase()}`, name: 'Nueva cámara', location: '', type: 'tilted', source: '', x: 0, y: 0, offset: 0, links: [], pairs: [], heading: 90, fov: 60, range: 3, height: 3, tilt: 45, coverageShape: 'cone', coverageWidth: 2 });
