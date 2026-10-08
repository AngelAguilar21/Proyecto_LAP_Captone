// La Vista general no puede mostrar el espacio de otro proyecto.
//
// El fallo real estuvo aqui: MonitoringWorkspace arrancaba fijo en el nivel
// 'lap-3' y, si el proyecto no tenia ese nivel, descargaba /maps/lap/3.json.
// Un proyecto recien creado abria mostrando el plano del aeropuerto LAP. No era
// un rotulo heredado: se cargaba el mapa de otro espacio.
//
// Se revisa el fuente, porque el fallo es exactamente "que valor arranca" y
// "cuando se descarga un plano ajeno".
import { readFileSync } from 'node:fs';

const fallos = [];
const ok = (cond, msg) => { if (!cond) fallos.push(msg); };
const leer = (p) => readFileSync(new URL(`../src/aero/${p}`, import.meta.url), 'utf8');

const monitoreo = leer('MonitoringWorkspace.tsx');

ok(!/useState\(['"]lap-\d/.test(monitoreo),
   'la Vista general vuelve a arrancar en un nivel del LAP fijo');
ok(/const propio\s*=\s*config\.planId/.test(monitoreo),
   'el nivel inicial ya no sale del propio proyecto');
ok(/if\(!level\.startsWith\('lap-'\)\)/.test(monitoreo),
   'se descarga /maps/lap sin comprobar que el nivel sea de esa demostracion');
ok(!/\[1,2,3,4\]\.map/.test(monitoreo),
   'el selector de nivel vuelve a listar los 4 niveles del LAP en todo proyecto');
ok(/niveles\.map/.test(monitoreo),
   'el selector de nivel no lista los niveles del proyecto');
ok(!/Ocupacion y flujo del aeropuerto|Ocupación y flujo del aeropuerto/.test(monitoreo),
   'el titulo vuelve a dar por hecho que el espacio es un aeropuerto');
ok(/sinCamaras/.test(monitoreo),
   'no hay estado vacio para un proyecto sin camaras');

const selector = leer('PlanSelector.tsx');
ok(/usaLap/.test(selector),
   'el selector de plano vuelve a ofrecer los niveles del LAP sin comprobar si el proyecto los usa');

// El administrador no debe ver Configuracion. Al mover la navegacion de una
// barra horizontal a la lateral, este filtro tenia que viajar con ella.
const app = leer('AeroTrack.tsx');
const menu = app.match(/session\.auth\.rol==='administrador'\?\[([^\]]*)\]:\[([^\]]*)\]/);
ok(!!menu, 'la navegacion ya no filtra las secciones por rol');
if (menu) {
  const [, admin, operador] = menu;
  ok(!admin.includes("'setup'"), 'el administrador vuelve a ver Configuracion en el menu');
  ok(operador.includes("'setup'"), 'el operador perdio el acceso a Configuracion');
  for (const comun of ["'overview'", "'alerts'", "'projects'"]) {
    ok(admin.includes(comun) && operador.includes(comun), `${comun} deberia estar en el menu de ambos roles`);
  }
}
ok(/aria-label="Navegación principal"/.test(app), 'la navegacion principal perdio su etiqueta accesible');
ok(/sidebar-nav/.test(app) && /sidebar-collapsed/.test(app),
   'la barra lateral plegable desaparecio del shell');

// Ningun texto de cliente debe estar fijo en una pantalla de uso general.
for (const archivo of ['MonitoringWorkspace.tsx', 'AeroTrack.tsx']) {
  const fuente = leer(archivo);
  for (const marca of ['Aeropuerto LAP', 'Terminal A']) {
    ok(!fuente.includes(marca), `${archivo} contiene el texto fijo "${marca}"`);
  }
}

if (fallos.length) { console.log('FALLOS:'); fallos.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('TODO CORRECTO: la Vista general arranca en el plano del propio proyecto');
