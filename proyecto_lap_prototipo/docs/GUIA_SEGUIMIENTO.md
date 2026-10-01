# Seguimiento de personas: contrato de la candidata

Revisión Fase 8 sobre `jose/automations-main-integration-v2`, base `0b611e0`.
La implementación es la fuente para describir los modos; los resultados de
precisión requieren mediciones independientes.

## Uso y modelos

Configura fuentes autorizadas, guarda el proyecto y delimita zona útil. Para
medir sobre el plano, coloca al menos cuatro correspondencias válidas del mismo
suelo, comprueba geometría y define vecindad/desfases. Tener suficientes puntos
no demuestra que la calibración sea válida. La asociación entre cámaras necesita
calibración y sincronización fiables.

| Ruta | Solicitud y comportamiento efectivo |
|---|---|
| Obtener imagen / preview | Lee la fuente para mostrar imagen; no es una medición de precisión del detector |
| Prueba de cámara del asistente | `SetupFlow.startCameraTest()` solicita `yolo`, `inferenceSize:640`, `testRun:true` |
| Monitoreo integrado | `MonitoringWorkspace` solicita `hybrid`, `combined:true` y tamaño seleccionado; YOLO es primario |
| `yolo` explícito backend | Detector primario YOLO para seguimiento; sin sampler adaptativo P2PNet |
| `hybrid` | YOLO más densidad P2PNet asíncrona cuando AVIE la solicita; no suma conteos ni reemplaza IDs |
| `p2pnet` explícito backend | Seguimiento de puntos de cabeza con corrección geométrica para suelo; requiere altura válida al proyectar |
| `demo` | Simulación; no prueba ejecución ni precisión de un modelo |

La pantalla principal remapea una solicitud `p2pnet` a `hybrid`; no existe un
selector global de modelos que exponga necesariamente todos los modos backend.
No hay fallback de YOLO faltante a P2PNet. Un fallo de carga debe conservarse
como error; un fallo de densidad puede aparecer como `dense.status=error` mientras
el seguimiento primario continúa. `testRun` flexibiliza ciertas precondiciones
de geometría; no aísla filesystem, datos ni persistencia.

## Componentes actuales

| Código | Responsabilidad |
|---|---|
| `src/following/detector.py` | YOLO11n COCO, personas, cajas y centro inferior como punto de apoyo |
| `src/tracking.py:ByteTrackPuntos` | Tracker empleado por `Engine.run()` para YOLO y P2PNet; instancia por cámara |
| `src/following/appearance.py` | Firma de color HSV y Lab en dos franjas del cuerpo |
| `src/live_core.py:IdentityStore` | Asociación global estimada por posición, tiempo, vecindad, apariencia y rechazo de ambigüedad |
| `src/following/adaptive.py` | AVIE y sampler asíncrono de densidad P2PNet |
| `src/following/source.py`, `src/counting/source.py` | Recepción de frame reciente y reconexión de fuentes LIVE |
| `src/following/combined.py`, `line_counter.py`, `flow.py` | Ocupación, episodios, cruces y flujo |
| `src/counting/` | Módulo independiente de conteo P2PNet, sin IDs de personas |
| `src/identity_memory.py`, `src/replay.py` | Persistencia de observaciones y reproducción |
| `src/live_metrics.py`, `src/live_reports.py` | Agregados y exportación |

El tracker web actual no es `src/following/tracker.py` ni una llamada a
`YOLO.track()`. Engine construye `ByteTrackPuntos` con umbral alto `.6` y
`max_frames_perdido=45`; el umbral bajo de su constructor es `.1`. El detector
YOLO filtra a `.25` por defecto, de modo que no entrega detecciones de `.1` a
`.25` al tracker. Los 45 corresponden a actualizaciones perdidas, no a una
garantía fija de 1.8 segundos: el muestreo efectivo importa.

## Muestreo, dispositivo y límites

Archivos: muestras de contenido cada `.2` segundos, independientemente de lo
que tarde procesarlas; no se infiere cada frame. LIVE: recepción continua del
frame reciente, con descarte de anteriores. El tiempo de seguimiento es el
reloj monotónico local del ciclo, no timestamp autenticado de captura.

Los requisitos fijan wheels PyTorch CPU. La revisión sintética observó CPU en
ambos detectores. Una NVIDIA instalada no demuestra uso GPU; CUDA y la
revalidación integrada MPS quedan pendientes. Sí hubo un LIVE histórico MacBook
con MPS reportado por el usuario. Véanse [INSTALACION.md](../../INSTALACION.md)
y [PRUEBA_LIVE.md](PRUEBA_LIVE.md) para entorno y significado de métricas.

AVIE entra en estado denso tras tres actualizaciones con evidencia de densidad
según cantidad, solapamiento, proporción de tracks o presupuesto de inferencia.
El sampler conserva a lo sumo una pendiente por cámara y reemplaza anteriores.
No hay intervalo `denseInterval` efectivo: la validación elimina ese campo
legacy y `denseCounting`. Cada resultado especializado conserva su propio
instante y puede estar retrasado respecto al frame actual.

El módulo de conteo independiente y el tracking no se inician simultáneamente;
el modo híbrido sí puede ejecutar su densidad P2PNet mientras sigue YOLO. La
capacidad y precisión multicámara no se deducen del límite de cámaras configurables.

La apariencia es un histograma, no Re-ID neuronal ni reconocimiento facial.
Los IDs se reinician por sesión; ropa similar, oclusión, cámara móvil o mala
calibración pueden fragmentar o confundir trayectorias. Se requieren anotaciones
para medir detecciones, cambios de ID, cruces y error espacial.

## Persistencia

Finalizar limpia el estado activo, pero **no elimina todos los IDs/recorridos
persistidos**. IdentityMemory conserva muestras individuales en SQLite; replays
conservan posiciones, IDs, historia y agregados incluso de fuentes LIVE. El video
remoto no se graba automáticamente; los uploads sí conservan videos originales.
La imagen del operador no está difuminada. No se declara anonimización ni
cumplimiento de privacidad: véase [INVENTARIO_PERSISTENCIA.md](INVENTARIO_PERSISTENCIA.md).

## Referencias de los algoritmos

- [YOLO11](https://docs.ultralytics.com/models/yolo11/).
- [ByteTrack, ECCV 2022](https://arxiv.org/abs/2110.06864).

Estas referencias no sustituyen la descripción del tracker realmente conectado
en esta versión ni una evaluación propia con el dominio aeroportuario.
