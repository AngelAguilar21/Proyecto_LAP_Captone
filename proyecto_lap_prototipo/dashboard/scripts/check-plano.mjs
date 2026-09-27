// Que se dibuja del plano en cada situacion.
//
// Dos fallos reales que esto evita:
//   - imagen y lineas a la vez: el garabato extraido tapaba el plano real.
//   - ninguna de las dos: al importar, sin lineas todavia y con la plantilla
//     oculta, el lienzo quedaba negro y no se veia el plano.
import { planLayers, defaultPlanView } from '../.lodcheck/planLayers.js';

const fallos = [];
const ok = (cond, msg) => { if (!cond) fallos.push(msg); };

const caso = (o) => planLayers({ isSetup: false, template: false, planView: 'image',
  hasBackground: true, lineCount: 0, hasMapAsset: false, ...o });

// --- el fallo reportado: recien importado, sin lineas, en el editor ---
let r = caso({ isSetup: true, template: false, lineCount: 0 });
ok(r.image, 'al importar el plano no se muestra la imagen: el lienzo queda negro');
ok(r.imageOpacity === 1, `la imagen recien importada se dibuja atenuada (${r.imageOpacity})`);
ok(!r.lines, 'se dibujan lineas cuando no hay ninguna');

// --- nunca las dos a la vez ---
for (const isSetup of [true, false])
  for (const template of [true, false])
    for (const planView of ['image', 'lines'])
      for (const lineCount of [0, 300])
        for (const hasBackground of [true, false]) {
          const x = planLayers({ isSetup, template, planView, hasBackground, lineCount, hasMasterAsset: false, hasMapAsset: false });
          const etiqueta = `isSetup=${isSetup} template=${template} planView=${planView} lineas=${lineCount} imagen=${hasBackground}`;
          // si se ven las dos, la imagen tiene que ser una plantilla atenuada por detras
          if (x.image && x.lines) ok(x.imageOpacity < 1, `imagen y lineas a plena opacidad: ${etiqueta}`);
          // no puede quedar todo vacio habiendo algo que mostrar
          if (!x.image && !x.lines && (hasBackground || lineCount > 0))
            ok(false, `no se dibuja nada habiendo contenido: ${etiqueta}`);
          if (x.image) ok(hasBackground, `se dibuja una imagen que no existe: ${etiqueta}`);
          if (x.lines) ok(lineCount > 0, `se dibujan lineas que no existen: ${etiqueta}`);
        }

// --- fuera del editor manda la eleccion guardada ---
r = caso({ planView: 'image', lineCount: 300 });
ok(r.image && !r.lines, 'con "plano real" elegido no se muestra la imagen sola');
r = caso({ planView: 'lines', lineCount: 300 });
ok(!r.image && r.lines, 'con "esquema de lineas" elegido no se muestran las lineas solas');

// --- en el editor las lineas son la geometria de trabajo ---
r = caso({ isSetup: true, planView: 'image', lineCount: 300, template: false });
ok(r.lines, 'en el editor no se ven los trazos que se estan editando');
ok(!r.image, 'en el editor la imagen tapa los trazos sin pedirlo');
r = caso({ isSetup: true, planView: 'image', lineCount: 300, template: true });
ok(r.image && r.lines && r.imageOpacity < 1, 'con "Ver plantilla" la imagen no queda atenuada detras de los trazos');

// --- un mapa vectorial propio reemplaza a las dos ---
r = caso({ hasMapAsset: true, lineCount: 300 });
ok(!r.image && !r.lines, 'el mapa vectorial se mezcla con la imagen o los trazos');

// --- eleccion por defecto ---
ok(defaultPlanView(true, 0) === 'image', 'con solo imagen deberia elegirse la imagen');
ok(defaultPlanView(true, 300) === 'image', 'teniendo imagen deberia preferirse la imagen');
ok(defaultPlanView(false, 300) === 'lines', 'sin imagen deberian elegirse las lineas');

if (fallos.length) { console.log('FALLOS:'); fallos.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('TODO CORRECTO: nunca se dibujan las dos a plena opacidad ni se queda el plano vacio');
