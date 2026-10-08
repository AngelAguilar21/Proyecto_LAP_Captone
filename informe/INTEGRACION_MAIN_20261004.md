# Integración de AeroTrack — 4 de octubre de 2026

Rama candidata: **`jose/automations-main-integration-v3`**. Corte en America/Lima.
**REQUIERE CORRECCIONES; candidata para revisión.** Este trabajo combina código
y documentación; no acredita una instalación limpia, LIVE Windows de la nueva
revisión, CUDA ni aprobación de producción.

## Revisiones combinadas

| Origen | Revisión fijada |
|---|---|
| Correcciones y automatizaciones, rama v2 | `90ba03d7d150d3db3b60b593dca18021ef6e03a0` |
| Novedades de `main` | `de44a7ec7dfbe68512b25cef707dc9f23c42d5bf` |
| Ancestro común | `e9790108dc4cf01f821c5261786a5b7955221be7` |

Antes de integrar, `main` contenía cinco commits exclusivos y v2 diez.
La integración conserva ambos historiales mediante un commit con dos padres.
El SHA de ese commit se comprueba al obtener la rama; ninguno de los hashes
de la tabla representa el nuevo commit. `main` y v2 se mantienen como orígenes.

## Cambios incorporados y conflictos resueltos

- Se mantienen las automatizaciones y correcciones AUD y REV-01/02/05 de v2.
- Se incorpora OSNet y su modelo ONNX, galerías de apariencia, estados de
  asociación, filtros de tamaño y objetos estáticos, perfiles de hardware y
  reintentos de frames del panel de cámara.
- Se incorporan los dos videos de ejemplo de `main`, su configuración y sus
  herramientas de prueba, además de la reorganización documental de ese origen.
- Cinco archivos habían cambiado en ambas ramas. `types.ts` y `live_core.py`
  admitieron combinación automática; `.gitignore`, `INSTALACION.md` y
  `live_server.py` requirieron resolución explícita.
- En `load_detector` se conserva el perfil nuevo de YOLO (pesos, dispositivo,
  tamaño y FP16) junto con el rechazo claro de modos inválidos de v2. Se evita
  recuperar el bloque duplicado e inalcanzable que subsistía en `main`.
- Las exclusiones de credenciales, automatizaciones y resultados locales se
  mantienen junto a las excepciones de los dos videos demo versionados.
- El test de degradación de OSNet ahora controla las tres rutas de modelos
  y exige ausencia real. Antes podía no ejecutar ninguna aserción cuando
  encontraba el modelo versionado por la ruta de respaldo.
- README, instalación y avance distinguen el estado actual de los informes
  históricos del 1 de octubre, que se conservan como antecedentes.

Los cinco archivos de REV distintos del servidor conservan sus bytes de
`90ba03d`: `replay.py`, ambas regresiones de auditoría, `SecurityAlerts.tsx` y
`audit-browser-regression.tsx`. En el servidor, `update_alert_rules` y
`do_POST` conservan su AST de esa revisión; las funciones cambiadas son
`load_detector` y `run`. Se ejecutan sus regresiones, no sólo una comparación.
El gitlink de P2PNet sigue en `5c91a81ca062b1c7fd3db3ad1c55b1c21f0a7455`.
Los parches locales del submódulo y los videos externos del usuario no se
transfieren ni modifican. Los archivos binarios versionados de los orígenes
se conservan por sus objetos Git existentes.

## Comprobaciones de esta integración

Resultados e IDs: [validacion/INTEGRACION_20261004.json](validacion/INTEGRACION_20261004.json).

| Comprobación | Alcance |
|---|---|
| Backend seleccionado | 557 tests descubiertos; 553/553 ejecutados OK en 18.782 s, 0 failures/errors/skipped; cuatro casos P2PNet excluidos expresamente por dependencias, pesos y fixture ausentes |
| Regresiones HTTP y recuperación | Incluidas en los 553; 10 + 10 casos, con control de proyecto y enteros históricos desbordados |
| Hardware, filtros y reidentificación | Incluidos en los 553; 12 + 9 casos, con fixtures sintéticos |
| Frontend | TypeScript, build Vite y scripts LOD/plano, aislamiento, seguimiento y KPI |
| Calibración, readiness y guardado | 20 checks del script existente; sin cámara ni red |
| OSNet nativo | ONNX Runtime 1.20.1, CPUExecutionProvider, dos recortes sintéticos, vectores de 512 valores finitos y norma L2 1 |
| Navegador React real | No ejecutado aquí; los seis casos históricos no se presentan como nuevos |
| Inferencia YOLO/P2PNet real, NMS y LIVE/CUDA | No ejecutados en esta integración |

La ejecución es Linux con Python 3.12.14, OpenCV 4.12.0.88, NumPy 2.2.6,
SciPy 1.17.0 y ONNX Runtime 1.20.1. No replica completamente las versiones
del entorno Windows. La comprobación de OSNet demuestra carga e inferencia
sobre entradas sintéticas; no evalúa precisión de asociación ni rendimiento
en multitudes. Las versiones completas y las exclusiones están en el JSON.

Se usó `unittest` con selección explícita de los IDs disponibles; los cuatro
casos excluidos siguen en el repositorio y no se marcaron como aprobados.
La primera ejecución se hizo sin el modelo local; se repitió al incorporar
el objeto ONNX y fijar ONNX Runtime, y de nuevo después de corregir el test
de modelo ausente. Las ejecuciones anteriores se identifican en el JSON y
no se suman como cobertura ni como una suite completa.

Para repetir en un entorno preparado, desde la raíz:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s proyecto_lap_prototipo/tests
cd proyecto_lap_prototipo/dashboard
npm ci
npx tsc --noEmit
npm run build
npm run check:lod
npm run check:aislamiento
npm run check:seguimiento
npm run check:kpis
node scripts/check-calibration.mjs
```

La suite completa requiere también el submódulo preparado, pesos y fixture
de P2PNet. Preparar dependencias no equivale a ejecutar la aplicación ni
a acreditar un primer arranque limpio.

## Antecedente LIVE comprobado, separado de esta candidata

El ZIP externo `piloto_live_cpu_20261004_171515_c5d3eb0b_RESULTADOS.zip`, SHA256
`a2055241caa25b086d8339a5df866774639c0c0f072d675022eeb82758eeb9c4`,
corresponde a `90ba03d`: captura DirectShow real, 300.188 s de ventana LIVE,
1392 inferencias YOLO, 40 P2PNet, 503 solicitudes HTTP de frames, salida 0 y
cierre cooperativo. Los modelos usaron CPU.

La confirmación visual del usuario sigue pendiente. Las solicitudes de frames
dejaron de avanzar aproximadamente en el segundo 234, mientras el backend
continuó; no se demostró la causa. El código anterior suspende solicitudes
cuando la página está oculta, pero no hay evidencia de que eso ocurriera en
ese intento. Los reintentos nuevos no prueban que ese problema esté resuelto.
Este ZIP, medios, credenciales, runtime y evidencias completas permanecen
fuera del repositorio. Estos resultados no se atribuyen al nuevo commit.

## Pendientes y alcance de CUDA

REV-03 (metadatos anidados inválidos durante exportación), REV-04 (contrato
legacy) y REV-06 (documentación de pertenencia de replays) siguen abiertos.
La causa original del fallo intermitente `torchvision::nms` tampoco se cierra
por una suite seleccionada ni por la inferencia de OSNet, que usa otro motor.

El Windows de referencia tiene PyTorch CPU-only. El perfil de hardware nuevo
detecta esa condición y utiliza CPU para YOLO; actualizar el driver no instala
PyTorch CUDA. La receta versionada de instalación continúa fijando paquetes
CPU. OSNet usa los providers disponibles; `onnxruntime` estándar no acredita
un provider CUDA. P2PNet conserva su selección de dispositivo original basada
en PyTorch: el perfil nuevo no representa por sí solo un control único de
todos los modelos. Cualquier entorno CUDA posterior debe comprobar por separado
los dispositivos reales de YOLO, P2PNet y OSNet.

El perfil puede elevar la resolución y cambiar el modelo utilizado respecto
al piloto anterior. Por ello se necesita una nueva validación Windows/LIVE de
esta revisión antes de atribuirle el resultado de v2. Los paquetes externos
del piloto anterior fijan hashes de código y frontend; no se deben modificar
sus comprobaciones de integridad para forzarlos a aceptar esta candidata.

## Obtener la candidata conservando la copia anterior

Usar una carpeta nueva y autenticación propia si GitHub la requiere:

```powershell
git clone --branch jose/automations-main-integration-v3 --recurse-submodules https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git AeroTrack-integracion-v3
git -C AeroTrack-integracion-v3 rev-parse HEAD
git -C AeroTrack-integracion-v3 status --short --branch
```

Después seguir [INSTALACION.md](../INSTALACION.md). Inicializar el submódulo
no aplica por sí solo sus parches de compatibilidad ni prepara los pesos.
La rama v2 sigue disponible para reproducir el antecedente CPU. El nuevo
commit no se integra automáticamente en `main`.
