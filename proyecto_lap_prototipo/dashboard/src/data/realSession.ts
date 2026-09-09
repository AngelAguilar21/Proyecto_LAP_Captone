import raw from './realSession.json';
import type { CameraId, NormalizedPoint } from '../types/camera';

/**
 * Sesion real, generada por
 * proyecto_lap_prototipo/dashboard (script de export en el historial de
 * conversacion) a partir de:
 *   - proyecto_lap_prototipo/data/historial.sqlite (salida real de
 *     P2PNet + ByteTrack + fusion cruzada de camaras)
 *   - proyecto_lap_prototipo/config/alcance.json + calibracion.json
 *     (poligonos de alcance reales, ya proyectados al plano compartido)
 *   - proyecto_lap_prototipo/data/camera_A.mp4 / camera_B.mp4 (fps y
 *     resolucion reales, leidos con cv2)
 *
 * Nada de esto es inventado: para regenerarlo tras una nueva corrida del
 * pipeline, se vuelve a correr ese mismo script contra el historial.sqlite
 * actualizado.
 */

export interface RealCameraData {
  alcance: NormalizedPoint[];
  ancla: NormalizedPoint;
  fps: number;
  resolucion: string;
}

export interface RealPersonMeta {
  primero: number;
  ultimo: number;
  duracion: number;
  detecciones: number;
  ruta: CameraId[];
}

export interface RealFrameEntry {
  id: string;
  x: number;
  y: number;
  camaras: CameraId[];
}

export interface RealSession {
  meta: {
    duracionTotal: number;
    paso: number;
    totalBins: number;
    rangoX: [number, number];
    rangoY: [number, number];
    totalPersonas: number;
  };
  camaras: Record<CameraId, RealCameraData>;
  personas: Record<string, RealPersonMeta>;
  frames: RealFrameEntry[][];
}

export const REAL_SESSION = raw as unknown as RealSession;
