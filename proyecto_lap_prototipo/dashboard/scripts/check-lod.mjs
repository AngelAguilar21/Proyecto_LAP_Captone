// Verificacion de lod.ts compilado: agrupamiento, niveles y rotulos.
import { magnification, detailLevel, lodFlags, clusterPeople, placeLabels } from '../.lodcheck/lod.js';

let fallos = [];
const ok = (cond, msg) => { if (!cond) fallos.push(msg); };
const casi = (a, b, t, msg) => ok(Math.abs(a - b) <= t, `${msg} (${a} vs ${b})`);

// ---------- aumento y niveles ----------
casi(magnification(100, 100), 1, 1e-9, 'plano completo = 1 aumento');
casi(magnification(100, 10), 10, 1e-9, 'una decima parte = 10 aumentos');
ok(magnification(0, 10) === 1 && magnification(100, 0) === 1, 'datos invalidos caen a 1');

ok(detailLevel(1) === 'general', 'plano completo -> general');
ok(detailLevel(3) === 'zonas', '3 aumentos -> zonas');
ok(detailLevel(6) === 'personas', '6 aumentos -> personas');
ok(detailLevel(40) === 'detalle', '40 aumentos -> detalle');

// el detalle solo puede crecer al acercarse: ninguna capa debe apagarse
const orden = ['general', 'zonas', 'personas', 'detalle'];
const claves = ['individuals', 'trajectories', 'personLabels', 'zoneLabels', 'cameraLabels', 'metrics', 'prediction'];
for (let i = 1; i < orden.length; i++) {
  const antes = lodFlags(orden[i - 1]), ahora = lodFlags(orden[i]);
  for (const k of claves) ok(!(antes[k] && !ahora[k]), `${k} se apaga al acercar entre ${orden[i - 1]} y ${orden[i]}`);
  ok(ahora.clusterPx <= antes.clusterPx, `el radio de agrupamiento crece al acercar en ${orden[i]}`);
}
// y el nivel mas lejano tiene que mostrar estrictamente menos
ok(claves.filter(k => lodFlags('general')[k]).length < claves.filter(k => lodFlags('detalle')[k]).length,
   'la vista general no reduce capas respecto al detalle');

// ---------- agrupamiento ----------
const persona = (id, x, y, uncertain = false) => ({ id, point: [x, y], uncertain });

// tres personas a 0.2 u en un plano con 0.1 u/px y radio 30 px = 3 u -> un grupo
let g = clusterPeople([persona('P3', 10.2, 10), persona('P1', 10, 10), persona('P2', 10.4, 10)], 0.1, 30);
ok(g.length === 1, `tres personas juntas deberian dar 1 grupo, dieron ${g.length}`);
ok(g[0].count === 3, 'el grupo no contó a los tres');
casi(g[0].point[0], 10.2, 1e-9, 'el centro del grupo no es el promedio');

// al acercarse (scale mas chico) el mismo caso se separa
g = clusterPeople([persona('P3', 10.2, 10), persona('P1', 10, 10), persona('P2', 10.4, 10)], 0.002, 30);
ok(g.length === 3, `al acercar deberian separarse en 3, dieron ${g.length}`);
ok(g.every(x => x.count === 1), 'al acercar quedan grupos con mas de uno');

// nadie se pierde ni se duplica, con muchas personas
const multitud = Array.from({ length: 400 }, (_, i) => persona(`P${String(i).padStart(3, '0')}`, (i % 20) * .3, Math.floor(i / 20) * .3));
for (const s of [0.5, 0.05, 0.005, 0.0005]) {
  const grupos = clusterPeople(multitud, s, 26);
  const total = grupos.reduce((n, x) => n + x.count, 0);
  const ids = new Set(grupos.flatMap(x => x.members.map(m => m.id)));
  ok(total === 400, `scale ${s}: la suma de los grupos es ${total}, no 400`);
  ok(ids.size === 400, `scale ${s}: hay personas repetidas o perdidas (${ids.size} ids)`);
}
// menos zoom debe dar menos o igual cantidad de grupos que mas zoom
const lejos = clusterPeople(multitud, 0.5, 26).length, cerca = clusterPeople(multitud, 0.001, 26).length;
ok(lejos < cerca, `agrupar de lejos (${lejos}) deberia dar menos grupos que de cerca (${cerca})`);
ok(cerca === 400, `muy de cerca deberian verse los 400 por separado, se ven ${cerca}`);

// determinismo: el mismo conjunto en otro orden da el mismo resultado
const a = clusterPeople(multitud, 0.05, 26).map(x => `${x.key}:${x.count}`).sort().join('|');
const b = clusterPeople([...multitud].reverse(), 0.05, 26).map(x => `${x.key}:${x.count}`).sort().join('|');
ok(a === b, 'el agrupamiento depende del orden de entrada (parpadearia entre cuadros)');

// la duda se hereda
g = clusterPeople([persona('P1', 0, 0), persona('P2', .1, 0, true)], .1, 30);
ok(g.length === 1 && g[0].uncertain, 'el grupo no heredo la identidad dudosa');

// scale 0 no debe romper ni agrupar
g = clusterPeople([persona('P1', 0, 0), persona('P2', 0, 0)], 0, 30);
ok(g.length === 2, 'con scale 0 no deberia agrupar');

// ---------- rotulos ----------
const pedido = (key, x, y, priority) => ({ key, point: [x, y], width: 60, height: 14, priority });
// dos anclas en el mismo punto: solo uno puede quedar en cada posicion candidata
let etiquetas = placeLabels([pedido('a', 0, 0, 5), pedido('b', 0, 0, 1)], 1);
ok(etiquetas.length === 2, 'dos rotulos en el mismo punto deberian reubicarse, no descartarse');
ok(etiquetas[0].key === 'a', 'la prioridad no se respeto');
ok(etiquetas[0].dx !== etiquetas[1].dx || etiquetas[0].dy !== etiquetas[1].dy, 'los dos rotulos quedaron en el mismo sitio');

// muchos rotulos en el mismo punto: se omiten los que no caben
etiquetas = placeLabels(Array.from({ length: 30 }, (_, i) => pedido('k' + i, 0, 0, 30 - i)), 1);
ok(etiquetas.length < 30, 'deberia omitir rotulos que no caben en vez de amontonarlos');
ok(etiquetas.length >= 1, 'no coloco ningun rotulo');
ok(etiquetas.every(e => e.point[0] === 0 && e.point[1] === 0), 'un rotulo perdio su ancla');

// anclas lejanas: todos caben sin desplazarse del primer candidato
etiquetas = placeLabels(Array.from({ length: 10 }, (_, i) => pedido('x' + i, i * 500, 0, 1)), 1);
ok(etiquetas.length === 10, `rotulos separados deberian caber todos, cupieron ${etiquetas.length}`);

// el limite se respeta
ok(placeLabels(Array.from({ length: 50 }, (_, i) => pedido('y' + i, i * 500, 0, 1)), 1, 7).length === 7, 'no se respeto el limite de rotulos');

if (fallos.length) { console.log('FALLOS:'); fallos.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('TODO CORRECTO');
console.log(`  agrupamiento de 400 personas: ${lejos} grupos de lejos, ${cerca} de cerca`);
console.log(`  niveles: ${orden.map(o => `${o}(${claves.filter(k => lodFlags(o)[k]).length} capas, ${lodFlags(o).clusterPx}px)`).join('  ')}`);
