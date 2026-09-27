/** Zoom semántico del plano: qué se dibuja en cada nivel de acercamiento.
 *
 * El mapa ya escalaba cada elemento por `scale` (unidades del plano por píxel),
 * así que los puntos y textos ya conservaban su tamaño en pantalla. Lo que
 * faltaba es que el zoom decidiera *qué* mostrar: con el plano entero a la vista
 * todas las capas encima se pisan y no se lee nada.
 *
 * Dos mecanismos distintos, a propósito:
 *
 * - El **aumento** (cuántas veces cabe el plano en lo que se ve) decide qué
 *   capas aparecen. Es relativo al tamaño del plano, así que sirve igual para
 *   una sala, un campus o una ciudad sin cambiar ningún número.
 * - La **distancia en píxeles** decide cuándo dos personas se agrupan. Al
 *   acercarse, la misma distancia en pantalla equivale a menos metros, así que
 *   los grupos se abren solos sin umbrales por proyecto.
 *
 * Sobre agrupar en lugar de desplazar: cuando dos personas se superponen no se
 * mueve su punto, se muestran como un grupo con su cuenta. Correr un punto para
 * que "se vea mejor" sería afirmar que alguien está donde no está. Las
 * etiquetas sí se recolocan, porque una etiqueta es un rótulo y no una posición.
 */

export type DetailLevel = 'general' | 'zonas' | 'personas' | 'detalle';

/** Cuántas veces está ampliado el plano: 1 = se ve completo. */
export function magnification(planWidth: number, visibleWidth: number): number {
  if (!(planWidth > 0) || !(visibleWidth > 0)) return 1;
  return planWidth / visibleWidth;
}

/** Umbrales elegidos por legibilidad, no por precisión.
 *
 * Con el plano completo en una vista de ~900 px, un espacio de 100 m da unos
 * 9 px/m: dos personas a medio metro caen a 4 px y se pisan. A 4,5 aumentos son
 * unos 40 px/m, medio metro son 20 px y ya se distinguen de a una. De ahí el
 * salto a "personas". Los demás cortes reparten las capas que más saturan.
 */
export function detailLevel(mag: number): DetailLevel {
  if (mag < 1.8) return 'general';
  if (mag < 4.5) return 'zonas';
  if (mag < 11) return 'personas';
  return 'detalle';
}

export interface LodFlags {
  /** Personas de a una; si no, solo grupos. */
  individuals: boolean;
  trajectories: boolean;
  personLabels: boolean;
  zoneLabels: boolean;
  cameraLabels: boolean;
  metrics: boolean;
  prediction: boolean;
  flow: boolean;
  /** Radio de agrupamiento en píxeles de pantalla. */
  clusterPx: number;
}

export function lodFlags(level: DetailLevel): LodFlags {
  switch (level) {
    case 'general':
      return { individuals: false, trajectories: false, personLabels: false, zoneLabels: false,
               cameraLabels: false, metrics: false, prediction: false, flow: true, clusterPx: 34 };
    case 'zonas':
      return { individuals: false, trajectories: false, personLabels: false, zoneLabels: true,
               cameraLabels: true, metrics: false, prediction: false, flow: true, clusterPx: 30 };
    case 'personas':
      return { individuals: true, trajectories: true, personLabels: false, zoneLabels: true,
               cameraLabels: true, metrics: true, prediction: false, flow: true, clusterPx: 24 };
    default:
      return { individuals: true, trajectories: true, personLabels: true, zoneLabels: true,
               cameraLabels: true, metrics: true, prediction: true, flow: true, clusterPx: 18 };
  }
}

export interface Pin { id: string; point: [number, number]; uncertain?: boolean }

export interface Group<T extends Pin = Pin> {
  key: string;
  /** Centro del grupo: promedio de sus miembros. Con uno solo es su posición exacta. */
  point: [number, number];
  members: T[];
  count: number;
  /** Algún miembro con identidad dudosa: el grupo hereda la advertencia. */
  uncertain: boolean;
}

/**
 * Agrupa por cercanía **en pantalla**, no en metros.
 *
 * `scale` son unidades del plano por píxel, así que el radio en unidades es
 * `gapPx * scale`: al acercarse baja solo y los grupos se separan sin que nadie
 * ajuste nada. Recorre en orden de id para que el resultado no cambie entre
 * cuadros y los grupos no parpadeen.
 */
export function clusterPeople<T extends Pin>(people: T[], scale: number, gapPx: number): Group<T>[] {
  const radius = Math.max(0, gapPx) * Math.max(0, scale);
  const sorted = [...people].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  if (!(radius > 0)) return sorted.map(p => single(p));

  // Rejilla de celdas del tamaño del radio: solo se comparan celdas vecinas, de
  // modo que el costo no crece al cuadrado con la cantidad de personas.
  const cells = new Map<string, Group<T>[]>();
  const groups: Group<T>[] = [];
  const cellKey = (x: number, y: number) => `${Math.floor(x / radius)}:${Math.floor(y / radius)}`;

  for (const person of sorted) {
    const [px, py] = person.point;
    let best: Group<T> | null = null;
    let bestDistance = Infinity;
    const cx = Math.floor(px / radius), cy = Math.floor(py / radius);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      for (const group of cells.get(`${cx + dx}:${cy + dy}`) || []) {
        const distance = Math.hypot(group.point[0] - px, group.point[1] - py);
        if (distance <= radius && distance < bestDistance) { best = group; bestDistance = distance; }
      }
    }
    if (best) {
      // El centro se recalcula como promedio; el grupo puede cruzar de celda.
      const previous = cellKey(best.point[0], best.point[1]);
      best.members.push(person);
      best.count = best.members.length;
      best.point = [
        best.members.reduce((n, m) => n + m.point[0], 0) / best.count,
        best.members.reduce((n, m) => n + m.point[1], 0) / best.count,
      ];
      best.uncertain = best.uncertain || !!person.uncertain;
      const now = cellKey(best.point[0], best.point[1]);
      if (now !== previous) {
        const list = cells.get(previous);
        if (list) cells.set(previous, list.filter(g => g !== best));
        push(cells, now, best);
      }
    } else {
      const group = single(person);
      groups.push(group);
      push(cells, cellKey(px, py), group);
    }
  }
  return groups;
}

function single<T extends Pin>(person: T): Group<T> {
  return { key: person.id, point: [person.point[0], person.point[1]], members: [person], count: 1, uncertain: !!person.uncertain };
}

function push<T extends Pin>(cells: Map<string, Group<T>[]>, key: string, group: Group<T>) {
  const list = cells.get(key);
  if (list) list.push(group); else cells.set(key, [group]);
}

export interface LabelRequest {
  key: string;
  /** Ancla en unidades del plano. */
  point: [number, number];
  /** Tamaño del rótulo en píxeles de pantalla. */
  width: number; height: number;
  /** Mayor gana el sitio cuando dos rótulos se pisan. */
  priority: number;
}

export interface PlacedLabel { key: string; point: [number, number]; dx: number; dy: number }

/**
 * Coloca rótulos evitando que se pisen, en píxeles de pantalla.
 *
 * Prueba unas pocas posiciones alrededor del ancla y, si ninguna queda libre,
 * omite ese rótulo en vez de amontonarlo. Mover el rótulo no engaña a nadie
 * porque sigue junto a su ancla; lo que no se hace nunca es mover el punto.
 */
export function placeLabels(requests: LabelRequest[], scale: number, limit = 120): PlacedLabel[] {
  const px = Math.max(1e-9, scale);
  const candidates = [[10, -8], [-10, -8], [10, 12], [-10, 12], [0, -16], [0, 20]];
  const ordered = [...requests].sort((a, b) => b.priority - a.priority || (a.key < b.key ? -1 : 1));
  const taken: { x: number; y: number; w: number; h: number }[] = [];
  const placed: PlacedLabel[] = [];

  for (const request of ordered) {
    if (placed.length >= limit) break;
    // A píxeles de pantalla, donde el solape es lo que ve la persona.
    const ax = request.point[0] / px, ay = request.point[1] / px;
    for (const [dx, dy] of candidates) {
      const box = { x: dx >= 0 ? ax + dx : ax + dx - request.width, y: ay + dy - request.height, w: request.width, h: request.height };
      if (taken.some(other => box.x < other.x + other.w && other.x < box.x + box.w && box.y < other.y + other.h && other.y < box.y + box.h)) continue;
      taken.push(box);
      placed.push({ key: request.key, point: request.point, dx: dx * px, dy: dy * px });
      break;
    }
  }
  return placed;
}
