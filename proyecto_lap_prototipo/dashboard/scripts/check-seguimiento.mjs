// "Iniciar prueba de seguimiento" no puede volver a estar conectado a un
// no-op. Ese fue exactamente el bug reportado: el boton de Zona util tenia
// onStart={()=>{}}, asi que al pulsarlo no pasaba
// nada perceptible, y el operador no tenia forma de saber si el sistema
// estaba haciendo algo o si el boton simplemente no funcionaba.
import { readFileSync } from 'node:fs';

const fallos = [];
const ok = (cond, msg) => { if (!cond) fallos.push(msg); };
const leer = (p) => readFileSync(new URL(`../src/aero/${p}`, import.meta.url), 'utf8');

const asistente = leer('SetupFlow.tsx');

ok(!/onStart=\{(\(\)=>\{\}|\(\)\s*=>\s*\{\})\}/.test(asistente),
   'CameraPanel vuelve a recibir onStart como una funcion vacia');
ok(/onStart=\{startCameraTest\}/.test(asistente),
   'el boton de prueba de seguimiento del asistente no llama a una funcion real');
ok(/function startCameraTest/.test(asistente),
   'no existe la funcion que inicia la prueba de seguimiento');
ok(/session\.post\(['"]start['"]/.test(asistente),
   'startCameraTest no llama al endpoint que inicia el analisis');
ok(/detector:['"]p2pnet['"]/.test(asistente),
   'la prueba del asistente ya no fija P2PNet');
ok(/PROJECT_STEPS[^\n]*\['project','plan','source','test','calibrate','zones','review'\]/.test(asistente),
   'el asistente no respeta el flujo simplificado proyecto-plano-camara-zona-homografia-zonas-revision');
ok(/inferenceSize:256/.test(asistente),
   'la prueba de camara ya no usa el perfil P2PNet de baja latencia');
ok(!/equipaje|luggage/i.test(asistente),
   'el asistente todavia expone el modulo de equipaje retirado');

const panel = leer('CameraPanel.tsx');
ok(/const starting *= *session\.connected *&& *session\.state\.status *=== *['"]starting['"]/.test(panel),
   'CameraPanel ya no distingue el estado "iniciando" para avisar al operador');
ok(/video-starting/.test(panel),
   'no hay ningun aviso visible mientras la sesion esta iniciando');
ok(!/YOLO|HOG|onDetector|denseCounting|denseInterval/.test(panel),
   'la camara todavia ofrece detectores o una segunda inferencia fuera del flujo P2PNet');
ok(!/Orientación|Cobertura orientativa|Accesos de un local/.test(panel),
   'la configuracion basica de camara volvio a exponer opciones avanzadas');

const monitoreo = leer('MonitoringWorkspace.tsx');
ok(/<section className="monitor-results-disclosure"/.test(monitoreo)
   && !/<details className="monitor-results-disclosure"/.test(monitoreo),
   'el ultimo analisis guardado vuelve a poder minimizarse');

const oportunidades = leer('ZoneWorkspace.tsx');
ok(/commercialContext/.test(oportunidades) && /source:'system'/.test(oportunidades),
   'las oportunidades ya no distinguen negocios declarados de zonas sugeridas por el sistema');

if (fallos.length) { console.log('FALLOS:'); fallos.forEach(f => console.log('  ' + f)); process.exit(1); }
console.log('TODO CORRECTO: el boton de prueba de seguimiento del asistente hace algo real');
