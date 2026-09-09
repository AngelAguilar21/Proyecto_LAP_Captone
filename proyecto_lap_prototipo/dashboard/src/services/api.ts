import type { TrackingState } from '../types/tracking';

/**
 * Stub de integracion futura. Cuando el prototipo de vision (P2PNet +
 * ByteTrack + fusion cruzada, ver proyecto_lap_prototipo/) exponga un
 * endpoint HTTP con el snapshot inicial de camaras/personas, esta funcion
 * pasa a hacer un fetch real -- el resto de la app no cambia porque ya
 * consume `TrackingState` con esta misma forma.
 */
export async function fetchInitialState(): Promise<Pick<TrackingState, 'cameras' | 'persons'>> {
  throw new Error(
    'API real no conectada todavia. Usa el modo DEMO (ver src/state/TrackingContext.tsx) ' +
      'hasta que proyecto_lap_prototipo exponga un endpoint HTTP.'
  );
}
