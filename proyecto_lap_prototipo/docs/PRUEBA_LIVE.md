# Protocolo LIVE — Lenovo Legion

Estado: **PROPUESTA DE PRUEBA, NO EJECUTADA**. La evidencia sintética local de
Fase 8 se separa al final. No acredita latencia LIVE, precisión, capacidad de
cámaras ni aptitud para piloto. Base de inspección: `0b611e0`, rama candidata
`jose/automations-main-integration-v2`. Registrar el SHA final al ejecutar.

## Alcance y precondiciones humanas

La prueba futura admite una cámara USB o fuente IP/RTSP/VMS expresamente
autorizada, en una escena controlada. Dos fuentes requieren autorización para
ambas y verificación de sus relojes/contenido. Un video local autorizado sirve
como comparación offline, pero no demuestra transporte ni latencia LIVE.
No usar URLs públicas elegidas al azar, cámaras ajenas ni credenciales en informes.

Antes de arrancar: identificar responsable, fuentes y personas/escena permitidas;
acordar conservación y revisión de resultados; preparar workspace/configuración
aislados con automatizaciones y correo deshabilitados. Verificar rutas de
salida, configuración de proyectos y conteo, y que no apunten a datos operativos.
`testRun:true` no es una frontera de aislamiento: también persiste observaciones.

No iniciar esta prueba al ejecutar los tests de Fase 8. No ejecutar SMTP,
cleanup ni automatizaciones sobre datos reales para completar la tabla.
No instalar CUDA, MPS ni cambiar el venv existente durante una comparación.

## Ficha reproducible

Registrar sin secretos:

- SHA, rama, fecha/huso horario, comando de arranque y directorio de ejecución.
- Lenovo: modelo real, CPU, RAM, GPU, VRAM, driver, Windows, alimentación y
  perfil energético; no asumirlos por el nombre de la familia Legion.
- `sys.executable`, Python, torch, torchvision, Ultralytics, OpenCV, Node y npm.
- Dependencias declaradas, instaladas, aceleradores disponibles y dispositivo
  **efectivo por detector**, distinguiendo esos cuatro niveles.
- Hashes de los pesos y configuración solicitada: detector, tamaño de entrada,
  cámaras, resolución/FPS fuente, transporte, zonas, calibración y sincronización.
- Navegador, número de vistas abiertas, modo de visualización y otros procesos
  que compitan por CPU/GPU. No cambiar estas condiciones entre repeticiones.

El perfil declarado fija PyTorch CPU. El conteo independiente fuerza CPU;
P2PNet integrado selecciona CUDA si disponible, y YOLO integrado deja seleccionar
al backend. No existe selector UI de dispositivo. Un futuro perfil NVIDIA/CUDA
debe conservar un perfil CPU reproducible, validar ambos modelos y medir CUDA
con eventos o sincronización alrededor de la región de prueba; no añadir
sincronización global permanente al pipeline. MPS queda pendiente y no acredita
soporte Apple Silicon.

## Escenarios y duración propuesta

Estas duraciones son una propuesta de muestreo, **no requisitos operativos
aprobados**. Registrar cuánto se ejecutó realmente y cualquier interrupción.

| Escenario | Preparación | Duración estable propuesta | Comparación |
|---|---|---|---|
| Una fuente | Escena autorizada, cámara fija, área útil; calibración válida si se proyecta | 5 minutos | YOLO; después hybrid con misma escena/configuración |
| Dos simultáneas | Calibración y tiempos verificados; misma resolución/transporte documentados | 5 minutos | Muestras/cortes por cámara, asociación y consumo total |
| Escena densa | Escena controlada o material autorizado con referencia humana | 3 minutos | Estados AVIE, activaciones P2PNet, edad de sus resultados, ocupación |
| Sesión prolongada | Configuración estable y vigilancia del operador | 30 minutos | Tendencia de memoria, errores/reconexiones, continuidad y cierre |

Separar carga inicial/primera inferencia y al menos un minuto propuesto de
calentamiento; anotar el tiempo real de cada etapa. Repetir cada ensayo corto
tres veces si es viable. No mezclar el primer pase con estadísticas estables.
P2PNet directo, si se evalúa, lleva una fila separada: su geometría de cabeza
es distinta de YOLO y de la densidad adaptativa.

## Pasos de ejecución futura

1. Completar ficha, comprobar aislamiento y dejar constancia de automatizaciones
   y correo deshabilitados. Acordar criterios de aceptación antes de mirar resultados.
2. Guardar geometría válida mediante la validación backend; no interpretar
   «referencias suficientes» como calibración validada.
3. Abrir preview autorizado, comprobar orientación/resolución y luego iniciar
   una fuente. Anotar solicitud y modo efectivo. El asistente prueba YOLO 640;
   el monitoreo integrado solicita hybrid.
4. Medir carga, primer resultado y calentamiento por separado; iniciar registro
   estable sólo después. Comparar conteos/cruces/IDs con anotaciones humanas.
5. Repetir con segunda cámara, escena densa y sesión prolongada sin modificar
   silenciosamente resolución, detector ni entorno.
6. Con autorización de la prueba, interrumpir/restablecer una fuente y registrar
   comportamiento de reconexión. Comprobar que señal ausente no se interpreta
   como observación válida de cero personas.
7. Detener sesión desde UI; verificar estado final por cámara. Solicitar cierre
   del servidor y registrar tiempo hasta que terminen trabajadores/escritores.
   Si el cierre queda incompleto, conservar recursos y evidencia: no borrar ni
   reemplazar archivos todavía usados.
8. Revisar inventario de salidas del workspace de prueba, sin ejecutar limpieza
   real. Documentar errores, resultados y limitaciones; no declarar aprobado lo
   no medido.

AT-06 permanece **PARCIAL**: existe cancelación cooperativa y cierre
acotado, pero llamadas nativas de lectura/inferencia pueden continuar hasta
retornar. El timeout del coordinador no equivale a finalización de todos los
escritores. Si hay bloqueos persistentes, detener el ensayo y preservar evidencia
para revisión humana, sin forzar una supuesta recuperación exitosa.

## Qué mide realmente cada dato

| Métrica | Inicio/fin y método | Estado LIVE actual |
|---|---|---|
| FPS fuente | `CAP_PROP_FPS`, con fallback 25 en seguimiento; mostrado como FPS fuente | NO MEDIDA en Legion; no equivale a FPS procesados |
| Tasa efectiva por cámara | Contar actualizaciones nuevas, no polls repetidos, y dividir por tiempo de pared; conservar ventana y método | NO MEDIDA; hace falta registro de muestras/publicaciones por cámara |
| `processingMs` | Inicio de iteración hasta después del JPEG, antes de actualización final de ocupación/replay/alertas/tráfico | NO MEDIDA LIVE; no es ciclo completo |
| Inferencia YOLO integrada | Cronómetro alrededor de la detección del lote; API divide ese tiempo por cámaras pendientes | NO MEDIDA LIVE; media atribuida, no cronómetro individual |
| Inferencia P2PNet adaptativa | Tiempo de `detectar(frame)` en sampler; no incluye carga inicial ni espera de cola | NO MEDIDA LIVE |
| P2PNet conteo independiente | Campo `inferenceMs` incluye reducción, inferencia, analítica, replay y JPEG hasta actualizar estado | NO MEDIDA LIVE; no comparar como tiempo neuronal puro |
| AVIE | `state`, detecciones, tracks, proporción, solapamiento y `p2pRequested` por muestra | NO MEDIDA LIVE |
| Estado/cámaras | Estado por cámara y timestamp de publicación; guardar transiciones y errores | NO MEDIDA LIVE |
| Desfase de archivos | `sampleSkewSeconds` usa índices/FPS/offset; para LIVE el cálculo actual da cero | NO MEDIDA; ese cero no prueba sincronización LIVE |
| CPU/RAM | Monitor del sistema por PID, ventana/cadencia y unidad explícitas; CPU total vs normalizada por núcleo | NO MEDIDA; no inferir de duración neuronal |
| GPU/VRAM | Herramienta instalada fiable, identificar proceso/dispositivo y unidades; separar memoria total/ocupada | NO MEDIDA LIVE; inventario hardware no es utilización |
| Edad captura→pantalla | Reloj visible autorizado o marcas correlacionadas y observación externa; descontar precisión del método | NO MEDIDA; backend actual no preserva cadena completa de timestamps |
| Pérdida/descarte de frames | Contador fiable de recepción/procesamiento o referencia externa | NO MEDIDA; no hay contador de descartes expuesto |
| Cierre | Solicitud de stop hasta fin real de trabajadores/escritores, distinguido de respuesta HTTP | NO MEDIDA LIVE |

Puede calcularse p50/p95 de un conjunto de muestras obtenido con método y
ventana declarados; no hay percentiles incorporados ni se inventan valores.
El campo `updatedAt` es publicación del servidor, no hora de captura original.

## Contrato de muestreo y buffers comprobado estáticamente

`live_server.Engine.run` reduce frames de ancho mayor a 1280 antes del detector.
En archivos avanza el tiempo de contenido cada 0.2 s y descarta cuadros intermedios
con `grab`: conserva esa rejilla de muestras aunque procesar tarde más que el video.
LIVE usa tiempo monotónico local del ciclo.

`counting.source.VideoSource` consume la fuente en un hilo y conserva el frame
más reciente; solicita `CAP_PROP_BUFFERSIZE=1`, sin garantía sobre buffers del
dispositivo/red/backend. `NetworkCapture.read` descarta el timestamp de recepción.
Leer cada frame recibido y procesar cada frame son cosas distintas.

En hybrid, AVIE solicita P2PNet después de evidencia densa y el sampler conserva
una pendiente por cámara, reemplazándola con la última. La activación no usa los
antiguos `denseCounting/denseInterval`; la validación los elimina. P2PNet produce
densidad con timestamp propio, sin sustituir IDs ni sumarse al conteo YOLO.
No hay fallback automático a otro detector ante fallo de carga principal.

Evidencia: `live_server.py:Engine.start/run/load_detector`,
`src/following/adaptive.py`, `src/following/source.py`,
`src/counting/source.py:VideoSource`, `src/counting/engine.py:CountingEngine.run`.

## Evidencia local Fase 8: diagnóstico sintético, no LIVE

**OBSERVADO** por el diagnóstico de la revisión en Windows 11 build 26200 AMD64,
Python 3.12.10; intérprete
`D:\Projects\Proyecto_LAP_Captone-main\.venv\Scripts\python.exe`.
Versiones instaladas: torch 2.14.0+cpu, torchvision 0.29.0+cpu,
Ultralytics 8.3.203, OpenCV 4.12.0.88, Node 24.19.0, npm 11.17.0.

- `torch.version.cuda=None`; CUDA no disponible, cero dispositivos visibles
  para ese proceso. API MPS existente, disponibilidad falsa.
- `nvidia-smi` identificó NVIDIA GeForce RTX 4090 Laptop GPU, driver 566.26,
  memoria total 16376 MiB. Esto no demuestra utilización ni inferencia CUDA.
- Ruta de diagnóstico: `Engine.load_detector`, frame de ceros 480×640,
  conexión de sockets bloqueada y configuración YOLO temporal.
- YOLO: tamaño solicitado 640, sin dispositivo explícito; backend/predictor y
  parámetros observados en CPU.
- P2PNet: lado máximo solicitado 256, selección automática; parámetros y entrada
  observados en CPU. No se modificaron requisitos, modelos ni P2PNet.

El diagnóstico construyó `Engine` sin inicializar configuración personal
(`Engine.__new__`, caches y locks propios). Usó `time.perf_counter()` alrededor
de `Engine.load_detector` para carga y de `detector.detectar(frame)` para cada
inferencia; esta última delega en `detectar_lote` e incluye pre/postprocesamiento.
La sincronización CUDA condicional no se ejecutó porque el dispositivo fue CPU.
Cuatro llamadas por detector, primera más tres posteriores, **no constituyen
un benchmark estable**. Hashes y evidencia complementaria en
[FASE8_VALIDACION.md](FASE8_VALIDACION.md).

| Detector | Carga ms | Primera inferencia ms | Siguientes ms |
|---|---:|---:|---|
| YOLO 640 | 101.273 | 103.491 | 39.864 / 40.212 / 33.246 |
| P2PNet lado 256 | 1999.091 | 73.962 | 77.128 / 66.704 / 65.200 |

No se midieron CPU/RAM, GPUutil, VRAM ocupada, tráfico de red, precisión,
latencia extremo a extremo ni capacidad multicámara. No extrapolar estos
tiempos a la Lenovo Legion del usuario, a escenas con personas ni a LIVE.
No se afirma validación GPU ni MPS.

## Registro a completar y decisiones

| Campo | Una fuente | Dos fuentes | Densa | Prolongada |
|---|---|---|---|---|
| SHA / fecha / responsable | PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |
| Hardware / entorno / dispositivo por modelo | PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |
| Fuente autorizada / configuración / modo | PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |
| Duración propuesta / efectiva | 5 min / NO EJECUTADA | 5 min / NO EJECUTADA | 3 min / NO EJECUTADA | 30 min / NO EJECUTADA |
| Carga / calentamiento / ventana estable | NO MEDIDA | NO MEDIDA | NO MEDIDA | NO MEDIDA |
| FPS fuente / tasa efectiva por cámara | NO MEDIDA | NO MEDIDA | NO MEDIDA | NO MEDIDA |
| processingMs / inferencias / AVIE | NO MEDIDA | NO MEDIDA | NO MEDIDA | NO MEDIDA |
| CPU / RAM / GPU / VRAM / método | NO MEDIDA | NO MEDIDA | NO MEDIDA | NO MEDIDA |
| Latencia externa / errores / reconexiones | NO MEDIDA | NO MEDIDA | NO MEDIDA | NO MEDIDA |
| Referencia humana / precisión | PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |
| Tiempo de cierre / recursos restantes | NO MEDIDA | NO MEDIDA | NO MEDIDA | NO MEDIDA |
| Salidas generadas / resultado / limitaciones | PENDIENTE | PENDIENTE | PENDIENTE | PENDIENTE |

Pendientes del equipo: FPS/latencia objetivo, precisión mínima, hardware mínimo,
autorización y retención de fuentes/resultados; perfiles NVIDIA/CUDA y MPS.
Ninguna cifra de aceptación queda aprobada por este protocolo. Véase
[INVENTARIO_PERSISTENCIA.md](INVENTARIO_PERSISTENCIA.md) antes de recoger datos.
