/** Dibujo del plano a mano: con puntos (trazo continuo) o con líneas sueltas.
 *
 * Las líneas se guardan como [x1, y1, x2, y2] en fracciones del ancho y el alto del plano (igual que las que se extraen de
 * un PDF o un DXF). Aquí vive la parte que se puede comprobar sin abrir el navegador: imán a los extremos ya dibujados,
 * ángulo recto con Shift, deshacer y el fondo con que se dibuja.
 */
export type Punto = [number, number];
export type LineaPlano = number[];

export const HERRAMIENTAS_DE_TRAZO = ['line', 'trace', 'erase'] as const;
export const MAX_LINEAS = 6000;   // el mismo límite que valida el servidor

export const esHerramientaDeTrazo = (tool?: string) => (HERRAMIENTAS_DE_TRAZO as readonly string[]).includes(tool || '');

/** Dibujar el plano, o verlo en modo líneas, se hace siempre sobre fondo oscuro con líneas blancas. */
export function planoOscuro(preferenciaOscura: boolean, tool: string | undefined, planView: string | undefined, lineCount: number): boolean {
  return preferenciaOscura || esHerramientaDeTrazo(tool) || (planView === 'lines' && lineCount > 0);
}

/** Punto donde cae el clic: imán al extremo ya dibujado más cercano (dentro de `radio`) y, con Shift, ángulo recto respecto a `previo`. */
export function ajustarPunto(p: Punto, previo: Punto | null, lineas: LineaPlano[], ancho: number, alto: number, radio: number, ortogonal = false): Punto {
  let q: Punto = [p[0], p[1]];
  if (previo && ortogonal) q = Math.abs(p[0] - previo[0]) >= Math.abs(p[1] - previo[1]) ? [p[0], previo[1]] : [previo[0], p[1]];
  let mejor: Punto | null = null, distancia = radio;
  for (const l of lineas) {
    for (const e of [[l[0] * ancho, l[1] * alto], [l[2] * ancho, l[3] * alto]] as Punto[]) {
      const d = Math.hypot(e[0] - q[0], e[1] - q[1]);
      if (d <= distancia) { distancia = d; mejor = e; }
    }
  }
  return mejor ?? q;
}

/** Segmento listo para guardar (fracciones 0..1), o null si es demasiado corto o hay demasiadas líneas. */
export function segmentoNormalizado(a: Punto, b: Punto, ancho: number, alto: number, existentes = 0): LineaPlano | null {
  if (existentes >= MAX_LINEAS || Math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6 * Math.max(ancho, alto)) return null;
  const f = (v: number, total: number) => Math.min(1, Math.max(0, v / total));
  return [f(a[0], ancho), f(a[1], alto), f(b[0], ancho), f(b[1], alto)];
}

/** Quita la última línea. Con un trazo continuo, el siguiente punto sale de donde empezaba esa línea. */
export function deshacerTrazo(lineas: LineaPlano[], ancho: number, alto: number): { lineas: LineaPlano[]; inicio: Punto | null } {
  if (!lineas.length) return { lineas, inicio: null };
  const ultima = lineas[lineas.length - 1];
  return { lineas: lineas.slice(0, -1), inicio: [ultima[0] * ancho, ultima[1] * alto] };
}
