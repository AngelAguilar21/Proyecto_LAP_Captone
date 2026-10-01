# Fase 8: evidencia de integración y validación de candidata

Fechas de ejecución y cierre: 2026-09-30 a 2026-10-01. No es la auditoría final ni autorización de piloto.
Rama: `jose/automations-main-integration-v2`.
SHA obligatorio de entrada verificado:
`0b611e0c23f485103b7e51866f77967d06292d41`.
El commit que contiene el cierre de este documento identifica la candidata
resultante; consultar `git log` y el informe de entrega para su SHA completo.

## Entrada y método

**HECHO VERIFICADO.** Raíz de trabajo:
`D:\Projects\Proyecto_LAP_Captone-main`. No se trabajó en la otra copia
`D:\Projects\Proyecto_LAP_Captone`. Tras `git fetch origin`, rama/SHA coincidían
y `git rev-list --left-right --count HEAD...origin/jose/automations-main-integration-v2`
devolvió `0 0`. No había staging. Único cambio previo: submódulo P2PNet.
No se encontraron AGENTS.md aplicables.

Se registraron diffs y hashes SHA-256 de los dos parches locales del instalador
(`models/backbone.py`, `util/misc.py`) y siete pyc no versionados de P2PNet.
Se usa Python `-B` para evitar generar o reemplazar bytecode al validar.
No se ejecutó instalación ni se modificaron venv, dependencias, lockfiles o perfiles.

La [matriz de integración](INTEGRACION_AUTOMATIZACIONES.md) se construyó antes de
corregir: se comprobó configuración → consumidor/registro → persistencia → cierre.
Los nuevos tests usan temporales y dobles de SMTP/captura; las inferencias reales
descritas abajo sólo reciben matrices sintéticas, excepto el fixture oficial que
ya utilizaban los tests P2PNet. No hay cámaras/RTSP, correo real ni tareas sobre
almacenamiento del usuario.

## Entorno realmente usado

| Dato | HECHO VERIFICADO |
| --- | --- |
| OS | Windows 11, build 26200, AMD64 |
| Intérprete | `D:\Projects\Proyecto_LAP_Captone-main\.venv\Scripts\python.exe`, Python 3.12.10 AMD64 |
| PyTorch / torchvision | `2.14.0+cpu` / `0.29.0+cpu` |
| Ultralytics / OpenCV / NumPy | `8.3.203` / `4.12.0.88` / `2.0.2` |
| pip check | No broken requirements found |
| Node / npm | `24.19.0` / `11.17.0` |
| Frontend instalado | React/react-dom 18.3.1, TypeScript 5.9.3, Vite 5.4.21, plugin-react 4.7.0 |
| CUDA build / proceso | `torch.version.cuda=None`, `is_available=False`, 0 dispositivos Torch |
| MPS | API presente, disponible False; pipeline MPS no probado |
| Hardware expuesto por nvidia-smi | RTX 4090 Laptop GPU; driver 566.26; memoria total 16376 MiB |

Los manifiestos fijan Torch/torchvision `+cpu`. La GPU visible al driver no
convierte ese wheel en CUDA. No se extrapolan estas observaciones a otra máquina
ni se declara soporte macOS/Apple Silicon.

## Baseline antes de editar

Python desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s proyecto_lap_prototipo\tests
```

**HECHO VERIFICADO:** 500 tests, 498 aprobados, 1 failure, 1 error, 0 skipped;
48.805 s. Coincide con el número y fallos reportados al entrar, sin asumir su causa.

Frontend desde `proyecto_lap_prototipo/dashboard`, comandos reales del package:

```powershell
npm run check:lod
npm run check:aislamiento
npm run check:seguimiento
npm run check:kpis
node scripts/check-zone-alerts.mjs
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
```

Todos pasaron salvo `check:seguimiento`: dos aserciones de fuente todavía exigían
P2PNet/256 mientras `SetupFlow.startCameraTest()` enviaba YOLO/640. TypeScript pasó;
build Vite pasó (81 módulos, 1.27 s). No se omitió el check fallido para declarar
el baseline verde. Dist y `.lodcheck` son artefactos ignorados, no versionados.

## Fixture P2PNet: causa demostrada y corrección

Los dos tests fallaban en `cv2.imread('external/P2PNet/vis/demo1.jpg')`:
desde la raíz esa ruta no existe; uno recibe None y el otro lo pasa al detector.
El archivo correcto existe en `proyecto_lap_prototipo/external/P2PNet/vis/demo1.jpg`.
`git ls-files --stage` del submódulo y `git hash-object` del archivo coinciden:
blob `304e24f698f1b4969d8d8abed0ffaf7d33fedf38`.
Pertenece al submódulo fijado en `5c91a81ca062b1c7fd3db3ad1c55b1c21f0a7455`;
no es un archivo suelto de los parches locales.

Antes de editar, ejecutar los mismos cinco tests desde `proyecto_lap_prototipo`
pasó en 6.069 s. Se cambiaron sólo raíces/imports/rutas en `test_detector_cache.py`
para derivarlas de `__file__`. Mismas entradas y aserciones funcionales, sin skip
ni sustitución del fixture. Desde raíz los cinco pasaron en 6.032 s después.

## Inferencia controlada por detector

Se usó `Engine.__new__` con los campos de caché/lock, sin construir servicios ni
leer configuración de usuario, y `Engine.load_detector(mode, {inferenceSize})`.
Entrada `numpy.zeros((480,640,3), uint8)`, una llamada inicial y tres sucesivas por
detector; `YOLO_CONFIG_DIR` apuntó a TemporaryDirectory antes de importar
Ultralytics y `socket.socket.connect` estuvo bloqueado. Pesos locales existentes.
`perf_counter` rodeó carga e inferencia; el script contempló sincronización
CUDA si estuviera disponible, pero las ejecuciones observadas fueron CPU.

| Detector | Solicitud / dispositivo observado | Carga ms | Primera inferencia ms | Tres sucesivas ms |
| --- | --- | --- | --- | --- |
| YOLO | imgsz 640, device None delegado; parámetro y predictor backend `cpu` | 101.273 | 103.491 | 39.864 / 40.212 / 33.246 |
| P2PNet | lado máximo 256, automático; setting/parámetro/tensor `cpu` | 1999.091 | 73.962 | 77.128 / 66.704 / 65.200 |

Las ocho salidas tuvieron cero detecciones. Son muestras pequeñas del costo de
una entrada vacía; **no** miden FPS operativo, capacidad de cámaras, exactitud,
latencia cámara-pantalla o estabilidad prolongada. CPU/RAM/utilización GPU/VRAM
en ejecución: **NO MEDIDAS**. La memoria total reportada por el driver no es uso
del proceso. Véanse métodos pendientes en [PRUEBA_LIVE.md](PRUEBA_LIVE.md).

Hashes SHA-256 de activos utilizados (no se modificaron):

- YOLO11n: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
- SHTechA: `506047732b128ff09efef18e94bfacbe35fcfef300e5e9eeeece259b0488c63f`.
- demo1.jpg: `608edfa5ec044ec577cdf6cc844dcbe6c29c1c5648d76a7de3c8b435b4852feb`.

## Correcciones demostradas

| Problema | Corrección acotada | Evidencia |
| --- | --- | --- |
| Readiness aceptaba sólo contar pares, incluso cruzados | Resultado del endpoint existente `calibration-check`, asociado a proyecto/servidor/cámara/plano/pares; cambios invalidan la respuesta anterior; no se replica geometría en TS | `calibration.ts`, `setupReadiness.ts`, `useSession.ts`; 19 checks dinámicos de calibración/guardado y HTTP con datos válidos/cruzados |
| Save manual rechazado podía mantener etiqueta Guardado | Feedback compartido manual/autosave; conserva causa backend, borrador pendiente y rechazo de la promesa; aviso enlaza también proyección cruzada con calibración | `sessionSave.ts`, `SetupFlow.tsx`, `AeroTrack.tsx`; checks de éxito/error diferidos |
| Guardados simultáneos podían persistir el borrador anterior después del nuevo | Cola compartida por guardado manual/autosave; congela cada payload y descarta solicitudes pendientes cuyo proyecto/generación ya cambió | Cuatro checks dinámicos adicionales de serialización, recuperación tras rechazo, payload congelado y cambio de propietario |
| Check de fuente y mensajes exigían/describían P2PNet fijo | Se alinean con YOLO640 para prueba y hybrid para monitoreo; se corrigen mensajes inválidos y etiqueta warmup; se retira bloque YOLO inalcanzable posterior a raise | `check-seguimiento`, tests de cache, inspección del flujo; detector/algoritmo/umbrales intactos |
| Dos tests dependían del cwd | Raíz derivada de `__file__`, mismo fixture oficial y aserciones | Cinco DetectorCacheTests pasan; causa y hashes arriba |
| Reinicio perdía series/totals y causaba no_data aunque había sesión válida | Recupera evidencia del replay con lectura estricta y conserva configuración de esa sesión para reportes; no reactiva cámaras ni personas | Reproducción antes del fix: 1 failure en 0.136 s; tests de integración y regresiones reportes/snapshot |
| La lectura estricta inicial aún admitía miembros de people que no eran objetos | Rechaza esos registros como evidencia para reportes recuperados | Subcasos people=[null] y people=[3] del test de muestras malformadas |

La calibración distingue referencias suficientes, geometría inválida, geometría
verificada y validación no disponible. Fallos de conexión/autorización no se
presentan como geometría inválida ni como éxito. Un resultado geométrico válido
no acredita precisión física independiente; conserva advertencia del backend.
No se cambiaron homografía, umbrales, rechazos ni políticas de negocio.

## Validación final ejecutada

| Control | Resultado observado | Duración |
| --- | --- | --- |
| Regresiones pertinentes F1–7 + integración/calibración/reporte/cache | 364 tests, 0 failures, 0 errors, 0 skipped | 32.196 s |
| Suite Python completa, mismo intérprete/cwd/comando del baseline | **508 tests, 508 OK, 0 failures, 0 errors, 0 skipped** | **56.937 s** |
| `check:lod`, `check:aislamiento`, `check:seguimiento`, `check:kpis` | Todos OK | Lote frontend total 8.737 s, incluidos los checks siguientes y build |
| `node scripts/check-zone-alerts.mjs` | 10 aserciones alertas + 7 resumen OK | Incluido en lote |
| `node scripts/check-calibration.mjs` | 19 checks dinámicos OK | Incluido en lote |
| `.\node_modules\.bin\tsc.cmd --noEmit` | OK | Incluido en lote |
| `npm run build` | OK, 84 módulos; dist ignorado sin artefactos versionados | Vite 1.19 s |
| Smoke HTTP con copia temporal del build final | 1 test, 0 failures/errors/skipped | 0.563 s |

La primera validación completa pasó 508 tests en 53.095 s. La revisión cruzada
posterior identificó la concurrencia de guardados y el caso people con miembros
no objeto; se corrigieron y justificaron repetir los controles afectados. Las
regresiones de 364 tests son anteriores a ese último endurecimiento de lectura;
después pasaron los ocho tests de integración en 1.924 s y la suite completa
final de 508 de la tabla, que vuelve a incluir esas regresiones.

Las ocho pruebas nuevas de Python están en `tests/test_integration_candidate.py`:

- `test_restart_restores_report_evidence_with_its_historical_configuration`: reinicio,
  privacidad del snapshot, PDF real verificado y deduplicación.
- `test_restored_configuration_is_not_reused_for_a_new_session`: descarta binding anterior.
- `test_missing_totals_do_not_invent_reportable_evidence`: no_data sin inventar KPI.
- `test_malformed_saved_samples_leave_summary_without_reportable_evidence`: JSON
  parcial, estructura/timestamp inválidos, vacío/ausencia no habilitan publicación.
- `test_public_report_snapshot_keeps_historical_configuration`: GET de reporte
  corresponde a la sesión, sin sobrescribir configuración editable.
- `test_legacy_unscoped_replay_is_not_adopted_as_project_report_evidence`: no infiere pertenencia legacy.
- `test_project_change_clears_restored_report_configuration`: aislamiento entre proyectos.
- `test_main_http_auth_projects_calibration_preview_and_shutdown_are_isolated`:
  lifecycle integrado, registro de tareas, auth, config, preview y cierre.

El smoke ejecuta `main` con ROOT/CONFIG_PATH temporales y puerto loopback efímero;
copia HTML/JS del build, verifica GET principal/asset, crea usuario/clave
sintéticos, login y proyecto, guarda configuración válida, comprueba rechazo
de homografía cruzada sin alterar el archivo previo, produce JPEG desde una
matriz con VideoCapture sustituido y espera cierre de workers/recursos.
Las cuatro tareas quedan registradas, disabled y protegidas por mocks que
fallan si se invocan. SMTP e inferencia también están bloqueados.

En la suite Python normal ese test sirve HTML/JS sintéticos, para que un checkout
sin dist compilado no pierda reproducibilidad. La ejecución explícita posterior
al build usó:

```powershell
@'
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path('proyecto_lap_prototipo/tests').resolve()))
from test_integration_candidate import CandidateIntegrationTests, ROOT
CandidateIntegrationTests.frontend_root = ROOT / 'dashboard/dist'
suite = unittest.TestSuite([CandidateIntegrationTests(
    'test_main_http_auth_projects_calibration_preview_and_shutdown_are_isolated')])
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'@ | .\.venv\Scripts\python.exe -B -
```

Los checks TS ejecutan helpers reales consumidos por la interfaz, incluyendo
promesas desordenadas, invalidación y guardado. No montan hooks en navegador.
El smoke sirve el build pero no ejecuta una sesión interactiva de React: **no es
E2E de navegador ni validación live**. La cola serializa los guardados iniciados
por una misma instancia de la interfaz; no coordina pestañas o procesos distintos
ni garantiza orden tras un timeout de transporte si el servidor sigue escribiendo.

Las regresiones específicas se ejecutaron con `unittest.TestLoader.discover`
combinando patrones `test_automation*.py`, `test_incident*.py`, `test_notifier.py`,
`test_zone_episodes.py`, `test_upload_cleanup.py`, `test_resource_control.py`,
`test_task_control.py`, `test_integration_candidate.py`, `test_calibration_quality.py`,
`test_session_reports.py` y `test_detector_cache.py`, desde la misma raíz y con
el mismo intérprete `-B`. No se instaló ni cambió el entorno entre baseline/final.

## Cierre funcional y limitaciones

Archivos revisados para esta entrega (25; P2PNet excluido):

| Grupo | Archivos |
| --- | --- |
| Backend | `proyecto_lap_prototipo/live_server.py`, `src/automation_snapshot.py`, `src/replay.py` |
| Tests Python | `tests/test_detector_cache.py`, `tests/test_integration_candidate.py` |
| Frontend | `dashboard/src/aero/AeroTrack.tsx`, `PlanWorkspace.tsx`, `SetupFlow.tsx`, `useSession.ts`, `calibration.ts`, `sessionSave.ts`, `setupReadiness.ts` |
| Checks frontend | `dashboard/scripts/check-seguimiento.mjs`, `check-calibration.mjs` |
| Documentación | `INSTALACION.md` en raíz; `docs/ESCALAMIENTO_INCIDENTES.md`, `GUIA_SEGUIMIENTO.md`, `MONITOREO_INTEGRADO.md`, `PLAN_COMERCIAL.md`, `REPORTES_PROGRAMADOS.md`, `UPLOADS_CLEANUP.md`, `FASE8_VALIDACION.md`, `INTEGRACION_AUTOMATIZACIONES.md`, `INVENTARIO_PERSISTENCIA.md`, `PRUEBA_LIVE.md` |

Salvo la instalación raíz, las rutas abreviadas pertenecen a
`proyecto_lap_prototipo/` y los nombres consecutivos a su mismo directorio.

Los controles funcionales pasan. El cierre funcional queda **completado con
limitaciones de entorno declaradas**. La comparación posterior a las pruebas
confirmó P2PNet idéntico al registro inicial: mismo HEAD, diff, lista de archivos
no versionados y hashes de los parches/pyc. `git diff --check` pasó; no hay cambios
en requirements, package/lockfiles, drivers o venv. El informe de entrega y la
rama remota identifican el commit publicado, sin incluir P2PNet. Las decisiones de producto y propuestas se
mantienen separadas en [INTEGRACION_AUTOMATIZACIONES.md](INTEGRACION_AUTOMATIZACIONES.md).

AT-06 sigue PARCIAL; AT-11 sigue PARCIALMENTE MITIGADO. El protocolo de cámaras
físicas/Lenovo Legion no se ejecutó. Esta fase no instala CUDA/MPS, no implementa
selector, calibración asistida o restore, no abre PR y no integra main.
