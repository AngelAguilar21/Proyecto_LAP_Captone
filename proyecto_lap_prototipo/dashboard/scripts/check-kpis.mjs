// El panel de monitoreo no puede mostrar cifras inventadas ni "0" cuando en
// realidad no se midio nada. Y el verde de la paleta esta permitido solo para
// indicadores de estado operativo, no como color de accion o decoracion.
import { readFileSync } from 'node:fs';

const fallos = [];
const ok = (cond, msg) => { if (!cond) fallos.push(msg); };
const leer = (p) => readFileSync(new URL(`../src/aero/${p}`, import.meta.url), 'utf8');

const panel = leer('MonitoringWorkspace.tsx');

// Las tarjetas KPI tienen que apagarse a "-" cuando no hay datos, no a 0.
ok(/label="Personas en el plano" value=\{hayDatos\?[^}]*:'—'\}/.test(panel),
   'Personas en el plano ya no distingue "sin datos" de "cero medido"');
ok(/hayDatos\?entries:'—'/.test(panel) && /hayDatos\?exits:'—'/.test(panel),
   'Entradas/Salidas ya no distinguen "sin datos" de "cero medido"');
ok(/pendientes\?\?'—'/.test(panel),
   'Alertas pendientes ya no distingue "no se pudo consultar" de "cero"');
ok(/api\/incidents\?estado=pendiente/.test(panel),
   'el conteo de alertas pendientes no viene de la bitacora persistida real');
// Nada de "hoy": ninguna de estas cifras se reinicia a medianoche, se
// reinician con cada sesion de analisis, asi que decir "hoy" seria falso.
ok(!/>Hoy</.test(panel) && !/'Hoy'/.test(panel),
   'una cifra de la sesion se etiqueta como "Hoy", que no es cierto: se reinicia con cada analisis, no a medianoche');

const refinamientos = leer('refinements.css');
// El verde queda en un solo token, documentado, y no se cuela un hex verde
// suelto en otra parte de la hoja (que fue exactamente el bug de antes:
// "Stray green #197958 en operations.css").
const tokenVerde = refinamientos.match(/--exito:\s*(#[0-9a-fA-F]{6})/);
ok(!!tokenVerde, 'no existe un token --exito definido para el verde de estado');
if (tokenVerde) {
  const otros = [...refinamientos.matchAll(/#[0-9a-fA-F]{6}/g)].map(m => m[0].toLowerCase());
  const propio = tokenVerde[1].toLowerCase();
  // Un color se cuenta como "verdoso" si verde domina claramente sobre rojo y azul.
  const esVerdoso = (hex) => {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return g > r + 25 && g > b + 25;
  };
  const sueltos = [...new Set(otros)].filter(h => h !== propio && esVerdoso(h));
  ok(sueltos.length === 0, `hex verde suelto fuera del token --exito: ${sueltos.join(', ')}`);
}
ok(/\.dot\.green\s*\{\s*background:\s*var\(--exito\)/.test(refinamientos),
   'el punto de estado verde ya no usa el token de verde dedicado');
ok(/\.text-green\s*\{\s*color:\s*var\(--exito\)/.test(refinamientos),
   'el texto verde ya no usa el token de verde dedicado');
// El verde no se convierte en color de boton: sigue sin existir una regla
// "button...--exito" en toda la hoja.
ok(!/button[^{]*\{[^}]*--exito/.test(refinamientos) && !/\.primary[^{]*\{[^}]*--exito/.test(refinamientos),
   'el verde se coló en un botón: debe quedar solo en indicadores de estado');

if (fallos.length) { console.log('FALLOS:'); fallos.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('TODO CORRECTO: los KPI son honestos y el verde queda acotado a estado');
