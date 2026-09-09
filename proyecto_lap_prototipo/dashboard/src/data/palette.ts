/**
 * Paleta categorica validada (dataviz skill): orden fijo, nunca ciclado por
 * rango -- ver referencia del metodo. Validada contra superficie oscura
 * #12141a: CVD adyacente >= 8.4 dE, vision normal >= 19.3 dE, contraste >= 3:1
 * en las 8 posiciones. Cada ID de persona toma el siguiente slot disponible
 * y lo conserva para siempre, incluso si cambia de camara o de estado.
 */
export const CATEGORICAL_SLOTS = [
  '#3987e5', // 1 azul
  '#d95926', // 2 naranja
  '#199e70', // 3 verde-agua
  '#c98500', // 4 ambar
  '#d55181', // 5 magenta
  '#008300', // 6 verde
  '#9085e9', // 7 violeta
  '#e66767', // 8 rojo
] as const;

const assigned = new Map<string, string>();
let cursor = 0;

/** Asigna (o recupera) el color fijo de un ID de persona. Idempotente: la
 * primera vez que se ve un ID reserva el siguiente slot libre; despues
 * siempre devuelve el mismo color, sin importar cuantas veces cambie de
 * camara o se vuelva a construir el estado. */
export function colorForPersonId(id: string): string {
  const existing = assigned.get(id);
  if (existing) return existing;
  const color = CATEGORICAL_SLOTS[cursor % CATEGORICAL_SLOTS.length];
  cursor += 1;
  assigned.set(id, color);
  return color;
}

export const STATUS_COLOR = {
  good: '#0ca30c',
  warning: '#fab219',
  critical: '#d03b3b',
} as const;
