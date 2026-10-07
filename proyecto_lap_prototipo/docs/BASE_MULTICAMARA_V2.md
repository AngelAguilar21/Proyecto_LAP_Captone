# Base multicámara: implementación y siguiente validación

> Esta nota conserva la primera etapa. Para el estado actualizado, Docker activo, OSNet-AIN y las pruebas de cámaras 4/5, consultar [Validación del 7 de octubre](VALIDACION_BASE_2026-10-07.md).

Fecha de revisión: 2026-10-07. Rama: `codex/base-multicamara-postgis`, desde main `f0f2a5e`.

## Objetivo y criterio de aceptación

Conservar la identidad de una persona entre cámaras sin aumentar fusiones de personas distintas. Un ID igual en dos pantallas no demuestra que sea correcto. Compararemos IDF1, cambios de ID, precisión de asociaciones y latencia p50/p95 usando personas etiquetadas a mano; los videos de calibración no deben ser los mismos que los de evaluación.

## Entregado en esta primera base

- Rutas dirigidas `cameraRoutes`: origen, destino, vista compartida o tránsito, tiempo mínimo y máximo (hasta 3600 s). Lista vacía desactiva los enlaces; campo ausente conserva las relaciones anteriores. No inferimos puertas o pasillos por cercanía de iconos.
- Configuración visible en **Configurar proyecto → Continuidad entre cámaras**, con guardar/eliminar y ejecución CPU/GPU. Los relojes siguen requiriendo verificación; una ruta no demuestra sincronización.
- Índice de candidatas por cámara antes de comparar apariencia en el asociador de sesión.
- La memoria ya no recupera identidades de componentes desconectados. En la sesión respeta la compatibilidad física; entre sesiones solo puede comprobar conectividad y retención, porque la memoria antigua no guarda el tiempo de contenido por cámara. Esa limitación exige una siguiente migración de visitas.
- La reagrupación al cerrar también respeta rutas y ventanas; ya no puede unir cámaras desconectadas solo por ropa parecida.
- Corrección del top-k de memoria: excluir candidatas antes de elegir las mejores para no ocultar coincidencias válidas.
- Diagnóstico agregado en `manifest.json`: comparaciones, descartes, ambigüedades, fusiones y proveedor de ejecución. Los contadores son intentos de comparación, no personas ni probabilidades.
- Memorias separadas por huella SHA-256 del archivo del modelo, preservando archivos anteriores. Cambiar pesos inicia una galería distinta aunque el archivo tenga el mismo nombre.
- Selección opcional de proveedores ONNX CPU/CUDA/OpenVINO/DirectML. CPU es el respaldo cuando el runtime requerido falta. DirectML usa ejecución secuencial y desactiva memory patterns. Tener una GPU integrada no implica que PyTorch/YOLO la usen.
- Archivo PostGIS transaccional de sesiones cerradas, observaciones, rutas e insights; importación repetible, consulta espacial GiST y por persona/tiempo. No incluye videos, credenciales ni embeddings.

## Base de datos: qué está y qué falta

Esto es una **migración gradual**, no la sustitución completa de SQLite/JSON. Los usuarios, negocios, ventas y memoria de apariencia continúan en sus almacenes actuales. Los reportes existentes aún leen esos almacenes. PostGIS recibe una copia analítica al terminar si se configura `AEROTRACK_DATABASE_URL`.

La primera versión guarda puntos en coordenadas locales, SRID 0, separados por piso y proyecto. No declarar EPSG:4326 para un dibujo. Para georreferenciar LAP hace falta una transformación validada del plano local al sistema geográfico; el esquema conserva la unidad del plano en los metadatos. Las cámaras sin homografía guardan posición nula.

Próxima migración: repositorios únicos para proyectos, pisos, cámaras, calibraciones versionadas, negocios/puertas, usuarios/roles, sesiones y ventas. Luego lecturas SQL de reportes y política de retención. `pgvector` solo cuando haya una galería grande y un benchmark que justifique búsqueda aproximada; para pocas personas la comparación exacta evita pérdida de recall. No hace falta una segunda base de grafos: relaciones dirigidas en PostgreSQL y listas de adyacencia en memoria son suficientes.

### Activación local (desde la raíz del repositorio, PowerShell)

1. Abrir Docker Desktop y esperar a que el motor Linux esté listo.
2. Crear `.env` local con `AEROTRACK_DB_PASSWORD` y una contraseña propia. Nunca versionar ese archivo.
3. Ejecutar `docker compose -f compose.postgis.yml up -d`.
4. Ejecutar `.\.venv\Scripts\python.exe -m pip install -r proyecto_lap_prototipo/requirements-storage.txt`.
5. Definir en la terminal `$env:AEROTRACK_DATABASE_URL='postgresql://aerotrack:CONTRASENA_CODIFICADA@127.0.0.1:5433/aerotrack'` (codificar caracteres especiales de la contraseña como URL).
6. Ejecutar `powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar_sistema.ps1` desde esa terminal.

Para archivar una grabación existente: `.\.venv\Scripts\python.exe proyecto_lap_prototipo/tools/archivar_postgis.py proyecto_lap_prototipo/data/replays/ID_SESION`.

El volumen Docker mantiene la base entre reinicios. La importación usa transacción y bloqueo por sesión; si falla, el JSONL sigue disponible. No es todavía una cola de reintentos: el reintento es por herramienta. Durante esta ejecución Docker no ofreció su motor Linux; no se verificó la integración con una base real.

## Modelos y fuentes consultadas

| Alternativa | Decisión para este equipo |
|---|---|
| [YOLO26, documentación oficial](https://docs.ultralytics.com/models/yolo26/) | Candidato a comparar contra YOLO11n con las mismas imágenes y resolución. No reemplazado por defecto sin medición propia. Detector mejor no garantiza asociación mejor. |
| [OSNet / deep-person-reid](https://github.com/KaiyangZhou/deep-person-reid) | Mantener línea base CPU y vectores multivista. No entrenamos desde cero. |
| [KPR, ECCV 2024](https://github.com/VlSomers/keypoint_promptable_reidentification) | Candidato prioritario para oclusiones: partes visibles y puntos corporales. Requiere integración propia de preprocesamiento, pesos, visibilidad y métricas; no basta sustituir osnet.onnx. |
| [BPBreID, WACV 2023](https://github.com/VlSomers/bpbreid) | Comparación por partes; alternativa para investigar costo y precisión. |
| [CLIP-ReID, AAAI 2023](https://github.com/Syliz517/CLIP-ReID) | Baseline adicional con pesos adecuados. No confundir CLIP genérico con un modelo preparado para ReID. |
| [TransReID, ICCV 2021](https://github.com/damo-cv/TransReID) | Transformer; probar en GPU antes de recomendarlo para esta laptop. |
| [COPE, repositorio CVPR 2026](https://github.com/Cecoming/COPE) | Investigación reciente sobre oclusiones; revisión pendiente de pesos, licencia, dependencias y reproducibilidad. No incorporado. |

No afirmamos que el modelo más reciente sea mejor para estas cámaras. Separar cabeza/tronco/piernas recortando arbitrariamente y pasando todo por OSNet no equivale a un modelo entrenado por partes: puede empeorar la métrica.

## Ejecución local y nube

Equipo observado: 8 hilos, 7.7 GiB RAM, sin CUDA disponible, ONNX en CPU. OSNet carga y devuelve vectores normalizados de 512 valores.

- Laptop: YOLO ligero, lotes de recortes ReID compartidos y muestreo de vistas útiles. Medir antes de instalar OpenVINO/DirectML en un entorno separado. [Proveedores ONNX](https://onnxruntime.ai/docs/execution-providers/).
- NVIDIA: PyTorch CUDA y ONNX Runtime GPU compatibles con CUDA/cuDNN. No instalar indiscriminadamente CPU/GPU/DirectML en el mismo entorno. [Requisitos CUDA](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).
- Nube: un trabajador de inferencia con NVIDIA L4 es un primer candidato razonable, sujeto a benchmark, coste, región y cuota. [AWS G6](https://aws.amazon.com/ec2/instance-types/g6/) y [GCP G2](https://docs.cloud.google.com/compute/docs/gpus). No se han creado recursos ni contratado servicios.
- Grabaciones: cola persistente de trabajos, reanudación, progreso, almacenamiento de objetos y prioridad baja frente a cámaras en vivo. No saltar cuadros por falta de CPU como se hace en vivo.
- Vivo: mantener el cuadro más reciente por cámara, contabilizar cuadros descartados y desfase; evitar que una cola creciente convierta la imagen en histórico. Los lectores actuales ya tienen un buffer del último cuadro. Aún falta medir jitter extremo y sincronización efectiva entre fuentes HLS independientes.
- La nube acelera inferencia si hay GPU suficiente; no corrige homografías, relojes ni recortes pobres. En vivo la subida de video y la latencia de red pueden dominar. Empezar con captura local y trabajador GPU remoto solo tras medir ancho de banda.

## Referencia del otro grupo

Clonado localmente en `referencias-locales/Aeropuerto`, excluido por `.gitignore`; no se copió su implementación en esta entrega. Su README describe API Go, Vue, PostgreSQL/PostGIS y un subsistema vivo con pgvector. La separación de módulos es una referencia arquitectónica, no evidencia de precisión.

La ventaja que buscaremos demostrar: evaluación reproducible, rutas explícitas, decisiones diagnosticables, continuidad consistente entre análisis vivo y cierre, trazabilidad de modelo/calibración y métricas comerciales con cobertura temporal declarada.

## Orden de trabajo

1. **Base entregada aquí:** grafo, coherencia de memoria/cierre, configuración, archivo PostGIS y ejecución por proveedor.
2. **Validación ReID:** sincronizar y calibrar dos cámaras; etiquetar al menos 10–20 transiciones reales y negativos difíciles. Separar conjunto de ajuste/evaluación. Comparar OSNet, detector alternativo y KPR; medir falsos enlaces, no solo IDs compartidos.
3. **Migración completa:** repositorios PostgreSQL, roles, migración de datos con conteos de verificación, visitas por cámara y luego embeddings versionados.
4. **Procesamiento escalable:** trabajadores CPU/GPU, cola, backpressure y recuperación de streams; benchmark local frente a L4 si se dispone de cuenta y presupuesto.
5. **Presentación:** diagnóstico visual de pares, errores de calibración, resultados antes/después y reportes explicables. Ninguna promesa de reconocer a todas las personas.

## Pruebas realizadas

- 337 pruebas Python pasaron en la última suite completa; después se verificaron las 8 pruebas del módulo de base (incluida una regresión adicional contra el respaldo silencioso). Build Vite y TypeScript también pasaron.
- Regresiones nuevas: rutas inválidas, ventanas, desconexión explícita, memoria sin enlace, reagrupación final y filas espaciales sin homografía.
- Pruebas `fc2aab82` y `8c3583a6`: se detectó que el cargador había rechazado las rutas al validar pisos y usado videos demo de respaldo. No validan los videos del usuario. Se conservan con `validationNote` explícita y se corrigió la causa; ahora iniciar una sesión con `config_error` falla de forma visible en lugar de procesar fuentes demo por error.
- La configuración guardada de Cámara 1 no supera la consistencia geométrica: referencias separadas 7.56 unidades en un plano de 2026.02. No se falsificaron ni movieron sus puntos para eludirlo. Para probar solo apariencia se utiliza una copia sin homografías, conservando el proyecto original.
- Prueba válida de los archivos `sincronizado1_cam1.mp4` y `sincronizado1_cam2.mp4`: sesión **97e3ae0b**, 40.4 s y 102 muestras, sin errores del motor. OSNet calculó 299 vistas. El motor en vivo registró 7 fusiones y 2 identidades multicámara; tras el cierre hubo cinco IDs compartidos (`P00003`, `P00004`, `P00005`, `P00006`, `P00010`) en 35 muestras. Son asociaciones estimadas, NO cinco aciertos verificados. Prueba visual-temporal con el indicador de sincronización que ya tenía el proyecto; no se midió de nuevo el desfase ni se validó precisión con anotaciones.
- Tokio: `DjdUEyjx8GM` y `gFRtAAmiFbE` respondieron como transmisiones en vivo disponibles a 720p. Se verificó resolución/acceso, no sincronización, lectura continua ni precisión del seguimiento.

Para ver la prueba válida: abrir **proyecto 3** (ID `p-493a0866`, nombre que ya estaba guardado) → Videos y resultados → sesión **97e3ae0b**. No se creó otro proyecto. Las reglas nuevas se aplican a análisis nuevos; no cambian automáticamente IDs de grabaciones antiguas.
