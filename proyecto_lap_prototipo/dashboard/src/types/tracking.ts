import type { Camera, CameraId } from './camera';
import type { Person, PersonStatus } from './person';
import type { TrackingEvent } from './event';

export type DataSourceMode = 'demo' | 'live';

export interface LayerVisibility {
  persons: boolean;
  coverageA: boolean;
  coverageB: boolean;
  trajectories: boolean;
  connections: boolean;
  transitionZone: boolean;
}

export type CameraFilter = CameraId | 'all';
export type StatusFilter = PersonStatus | 'all';

export interface TrackingState {
  mode: DataSourceMode;
  /** Indice de frame actual dentro de la sesion real grabada (ver
   * data/realSession.ts) -- el reproductor avanza esto en un loop, no un
   * reloj de pared. */
  frameIndex: number;
  playing: boolean;
  /** Multiplicador de velocidad del replay (1 = tiempo real del video). */
  speed: number;
  cameras: Record<CameraId, Camera>;
  persons: Record<string, Person>;
  /** Vacio en el replay de la sesion grabada -- queda listo para cuando el
   * modo LIVE reciba estos eventos de un backend real (ver services/websocket.ts). */
  events: TrackingEvent[];
  selectedPersonId: string | null;
  highlightedCamera: CameraId | null;
  cameraFilter: CameraFilter;
  statusFilter: StatusFilter;
  layers: LayerVisibility;
}
