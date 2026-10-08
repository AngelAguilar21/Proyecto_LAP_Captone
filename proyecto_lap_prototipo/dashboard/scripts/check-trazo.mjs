// Dibujo del plano con puntos o lineas: iman, angulo recto, deshacer y fondo oscuro.
import { ajustarPunto, segmentoNormalizado, deshacerTrazo, planoOscuro, esHerramientaDeTrazo, MAX_LINEAS } from '../.lodcheck/trazo.js';

const fallos = [];
const ok = (cond, msg) => { if (!cond) fallos.push(msg); };
const cerca = (a, b) => Math.abs(a - b) < 1e-9;

// fondo: dibujando o en vista de lineas siempre oscuro; si no, manda la preferencia
ok(planoOscuro(false, 'line', 'image', 0), 'dibujar con lineas debe ser sobre fondo oscuro');
ok(planoOscuro(false, 'trace', undefined, 0), 'dibujar con puntos debe ser sobre fondo oscuro');
ok(planoOscuro(false, 'select', 'lines', 12), 'la vista de lineas debe ser oscura');
ok(!planoOscuro(false, 'select', 'lines', 0), 'sin lineas la vista de lineas no fuerza el fondo');
ok(!planoOscuro(false, 'select', 'image', 40), 'con imagen manda la preferencia del operador');
ok(planoOscuro(true, 'select', 'image', 0), 'la preferencia oscura se respeta');
ok(esHerramientaDeTrazo('erase') && !esHerramientaDeTrazo('polygon'), 'herramientas de trazo mal reconocidas');

// iman al extremo mas cercano dentro del radio
const lineas = [[0.1, 0.1, 0.5, 0.1]];           // plano de 100 x 50: extremos (10,5) y (50,5)
let p = ajustarPunto([11, 6], null, lineas, 100, 50, 3);
ok(cerca(p[0], 10) && cerca(p[1], 5), `iman al extremo: ${p}`);
p = ajustarPunto([30, 20], null, lineas, 100, 50, 3);
ok(cerca(p[0], 30) && cerca(p[1], 20), 'fuera del radio no se mueve');
p = ajustarPunto([49, 7], null, lineas, 100, 50, 3);
ok(cerca(p[0], 50) && cerca(p[1], 5), 'iman al otro extremo');

// angulo recto con Shift
p = ajustarPunto([40, 12], [10, 10], [], 100, 50, 3, true);
ok(cerca(p[0], 40) && cerca(p[1], 10), `angulo recto horizontal: ${p}`);
p = ajustarPunto([12, 40], [10, 10], [], 100, 50, 3, true);
ok(cerca(p[0], 10) && cerca(p[1], 40), `angulo recto vertical: ${p}`);

// segmento normalizado y limites
let s = segmentoNormalizado([10, 5], [50, 25], 100, 50);
ok(s && cerca(s[0], .1) && cerca(s[1], .1) && cerca(s[2], .5) && cerca(s[3], .5), `segmento normalizado: ${s}`);
ok(segmentoNormalizado([10, 5], [10, 5], 100, 50) === null, 'un segmento de largo cero se guarda');
ok(segmentoNormalizado([0, 0], [1, 1], 100, 50, MAX_LINEAS) === null, 'se pasa del limite de lineas');
s = segmentoNormalizado([-20, 5], [500, 90], 100, 50);
ok(s && s.every(v => v >= 0 && v <= 1), 'las coordenadas deben quedar entre 0 y 1');

// deshacer devuelve el inicio de la ultima linea
let d = deshacerTrazo([[0, 0, .5, .5], [.5, .5, 1, .5]], 100, 50);
ok(d.lineas.length === 1 && cerca(d.inicio[0], 50) && cerca(d.inicio[1], 25), `deshacer: ${JSON.stringify(d)}`);
d = deshacerTrazo([], 100, 50);
ok(d.lineas.length === 0 && d.inicio === null, 'deshacer sin lineas');

if (fallos.length) { console.error('FALLOS:\n- ' + fallos.join('\n- ')); process.exit(1); }
console.log('check-trazo: OK');
