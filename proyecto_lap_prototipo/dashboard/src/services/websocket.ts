import type { TrackingEvent } from '../types/event';

export type TrackingEventHandler = (event: TrackingEvent) => void;

/**
 * Stub tipado del canal en vivo. El backend real emitira exactamente los
 * `TrackingEventType` definidos en types/event.ts -- por ejemplo:
 *
 *   { "event": "person_camera_transition", "person_id": "01",
 *     "from_camera": "CAM_A", "to_camera": "CAM_B",
 *     "timestamp": "2026-09-08T22:10:15" }
 *
 * `connectTrackingSocket` traduce esos mensajes a `TrackingEvent` y los
 * entrega via `onEvent`. Sin backend disponible, conectar lanza un error
 * legible en vez de fingir una conexion que nunca llega.
 */
export function connectTrackingSocket(_url: string, _onEvent: TrackingEventHandler): { close: () => void } {
  throw new Error(
    'WebSocket real no conectado todavia. El modo LIVE queda deshabilitado en la UI ' +
      'hasta que proyecto_lap_prototipo exponga un canal de eventos.'
  );
}
