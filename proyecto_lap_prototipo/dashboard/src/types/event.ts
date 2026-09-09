import type { CameraId } from './camera';

/** Nombres de evento alineados 1:1 con lo que emitira el backend real via
 * WebSocket (ver services/websocket.ts) -- el demo local dispara estos
 * mismos tipos para que el resto de la UI no distinga demo de real. */
export type TrackingEventType =
  | 'person_detected'
  | 'person_updated'
  | 'person_lost'
  | 'camera_connected'
  | 'camera_disconnected'
  | 'person_camera_transition';

export interface TrackingEvent {
  id: string;
  type: TrackingEventType;
  timestamp: string;
  personId?: string;
  camera?: CameraId;
  fromCamera?: CameraId;
  toCamera?: CameraId;
  label: string;
}
