import type { CameraId } from './camera';

/** 'transitioning' = el punto cae dentro del alcance real de las dos
 * camaras a la vez (fusion cruzada); en cualquier otro caso, 'active'. No
 * existe un estado "inactive" fabricado: si la persona no aparece en el
 * frame actual, simplemente no esta en la lista -- eso ya lo dice la
 * ventana real [firstSeen, lastSeen] de esa persona. */
export type PersonStatus = 'active' | 'transitioning';

export interface TrajectoryPoint {
  x: number;
  y: number;
  /** segundos desde el inicio del video (tiempo real del recorrido). */
  t: number;
}

export interface Person {
  id: string;
  color: string;
  /** Camara(s) reales que ven a esta persona en el frame actual -- 1 en
   * condiciones normales, 2 mientras esta en la zona de solape. */
  cameras: CameraId[];
  x: number;
  y: number;
  heading: number;
  status: PersonStatus;
  /** segundos desde el inicio del video (no reloj de pared: esto es el
   * replay de una grabacion real, no un feed en vivo). */
  firstSeen: number;
  lastSeen: number;
  /** Camaras por las que paso, en el orden real en que la vieron. */
  route: CameraId[];
  trajectory: TrajectoryPoint[];
}
