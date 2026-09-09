/** Mismos identificadores que usa el prototipo de vision real
 * (config/camaras.json, config/alcance.json, historial.sqlite): "A" y "B". */
export type CameraId = 'A' | 'B';

export type CameraStatus = 'online' | 'offline';

export type NormalizedPoint = [number, number];

export interface Camera {
  id: CameraId;
  label: string;
  status: CameraStatus;
  fps: number;
  resolution: string;
  /** Icono de la camara: el prototipo no calibra su posicion fisica (ver
   * proyecto_lap_prototipo/src/nodes.py), asi que este punto se deriva del
   * propio poligono real de `coverage` -- ver dashboard/src/data/realSession.ts. */
  anchor: NormalizedPoint;
  /** Poligono de alcance real, ya proyectado al plano compartido por la
   * homografia calculada en el prototipo (config/calibracion.json +
   * config/alcance.json) -- no es una forma dibujada a mano. */
  coverage: NormalizedPoint[];
  peopleCount: number;
}
