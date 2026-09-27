/** Qué capa del plano se dibuja: la imagen importada o los trazos extraídos.
 *
 * La imagen y las líneas son dos versiones del mismo plano, no dos capas que se
 * superponen. Dibujarlas juntas tapa el plano real con un garabato; ocultar las
 * dos deja el lienzo en negro. Las dos cosas han pasado, así que la decisión
 * vive aquí, en una función que se puede comprobar sin abrir el navegador.
 *
 * En el editor manda lo que se está trabajando: si hay trazos, son la geometría
 * y la imagen pasa a ser una plantilla tenue que se enseña con «Ver plantilla».
 * Si no hay trazos no hay nada que tapar, así que se muestra la imagen entera.
 * Fuera del editor manda la elección guardada del proyecto.
 */
export interface PlanLayerInput {
  /** Editor de plano o de zonas (configuration || editable). */
  isSetup: boolean;
  /** Casilla «Ver plantilla» del editor. */
  template: boolean;
  /** Elección guardada del proyecto. */
  planView: 'image' | 'lines';
  hasBackground: boolean;
  lineCount: number;
  /** Mapa vectorial propio (LAP): reemplaza a las dos. */
  hasMapAsset: boolean;
}

export interface PlanLayers {
  image: boolean;
  /** Atenuada solo cuando hace de plantilla por detrás de los trazos. */
  imageOpacity: number;
  lines: boolean;
}

export function planLayers(input: PlanLayerInput): PlanLayers {
  const { isSetup, template, planView, hasBackground, lineCount, hasMapAsset } = input;
  if (hasMapAsset) return { image: false, imageOpacity: 1, lines: false };

  // La elección guardada puede sobrevivir a su contenido: un proyecto marcado
  // como «líneas» al que luego se le quitaron los trazos, o al revés. Manda solo
  // cuando existen las dos; si no, se muestra lo que haya antes que nada.
  const elegido: 'image' | 'lines' =
    planView === 'lines' && lineCount === 0 ? 'image'
    : planView === 'image' && !hasBackground && lineCount > 0 ? 'lines'
    : planView;

  const deFondo = isSetup && template && lineCount > 0;
  const image = hasBackground && (isSetup ? (template || lineCount === 0) : elegido === 'image');
  const lines = lineCount > 0 && (isSetup || elegido === 'lines');
  return { image, imageOpacity: deFondo ? .55 : 1, lines };
}

/** Elección efectiva cuando el proyecto todavía no guardó ninguna. */
export function defaultPlanView(hasBackground: boolean, lineCount: number): 'image' | 'lines' {
  return !hasBackground && lineCount > 0 ? 'lines' : 'image';
}
