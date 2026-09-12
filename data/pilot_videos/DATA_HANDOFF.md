# Entrega a Data Science — derivados de distribución LAP

## Procedencia y estado

Los nueve videos fueron capturados directamente por **José Ortega** durante la fase de adquisición de datos del Proyecto LAP. En todas las filas: `captured_by = José Ortega` y `source = Captura propia para Proyecto LAP`. VID_001–VID_008 corresponden a Universidad de Lima; VID_009 a Jockey Plaza. Las ubicaciones fueron confirmadas por el usuario.

Este directorio contiene **derivados de privacidad para distribución mediante Git LFS**. Los RAW canónicos permanecen intactos fuera del repositorio, en `data_collection/raw/`. Solo se eliminó metadata sensible explícita de geolocalización del contenedor; no hubo recodificación y los datos audiovisuales codificados permanecen idénticos byte por byte.

Los nueve derivados están verificados y fueron publicados mediante Git LFS. Están disponibles en la rama `pilot-video-lfs`; el [PR #2](https://github.com/AngelAguilar21/Proyecto_LAP_Captone/pull/2) está abierto hacia `main`. Consultar `DISTRIBUTION_REPORT.md` para resultados, hashes completos y límites de la inspección.

## Cómo usar el catálogo

- `video_id` identifica el archivo, nunca una persona.
- `original_filename` conserva exactamente el nombre original, incluyendo mayúsculas/minúsculas.
- `raw_sha256` corresponde al RAW canónico externo.
- `distribution_sha256` corresponde al derivado presente en el repositorio.
- `sha256` es un alias de `distribution_sha256` en este catálogo de distribución; el catálogo canónico externo mantiene su hash RAW.
- `repo_lfs_path` y `relative_path` son rutas relativas a la raíz del repositorio.
- `raw_source_relative_path` se interpreta respecto de la colección externa `data_collection/`; no es una ruta de archivo incluida en el repositorio.
- `privacy_transformation = location_metadata_removed` documenta la transformación aplicada.
- `geolocation_removed = true` se refiere a la metadata explícita de ubicación detectada, no a las referencias visuales ni a una anonimización integral.
- `encoded_media_identical = true` confirma identidad byte por byte del contenido multimedia codificado respecto del RAW.
- `filesystem_created` y `filesystem_modified` se conservan como datos de procedencia del RAW; no representan la creación del archivo derivado. `embedded_creation_date` se preserva en la copia. `original_unchanged = true` significa que el RAW fue verificado intacto.
- `status = distribution_published_lfs` indica que el derivado está publicado en GitHub mediante Git LFS en la rama `pilot-video-lfs`; su integración en `main` se gestiona mediante el PR #2, actualmente abierto.

## Semántica y limitaciones del piloto

Se preservaron las clasificaciones y valoraciones anteriores. `confirmed` significa al menos un evento claro en la revisión muestreada; `not_observed` no garantiza ausencia absoluta; `uncertain` indica evidencia insuficiente o ambigua. `not_annotated` significa que no hay anotación del concepto.

- `frame_entry` y `frame_exit` describen el cruce del borde de la imagen; no equivalen a entradas o salidas comerciales. `roi_entry_exit = not_annotated` en los nueve videos.
- `temporal_presence` describe presencia visible en una zona a través de muestras sucesivas. No equivale a permanencia comercial: `commercial_dwell = not_annotated` en los nueve.
- No se confirmó una cola clara: VID_006 y VID_009 mantienen `queue = uncertain`; los demás, `not_observed`.
- Ninguna cámara quedó completamente fija. Una ROI fija en píxeles puede desalinearse.
- No existe una escena de tracking controlado. VID_004 conserva `limited_candidate` por su duración de aproximadamente 5.5 s.
- Flujo y densidad son cualitativos; no son conteos ni métricas por área. Las valoraciones de tracking y ROI no son resultados de modelos.
- El material es un dataset piloto propio, no ground truth anotado completo. No contiene cajas, IDs de personas, trayectorias ni tiempos individuales de permanencia anotados.
- La revisión visual/temporal se basó en muestras y puede omitir eventos breves u ocultos. El QA técnico sí decodificó la pista completa de video.

## Pendientes para Data Science

Definir tareas y métricas, ROI/líneas y sus direcciones, manejo del movimiento de cámara y protocolo de anotación/evaluación antes de generar nuevos derivados o entrenar/evaluar modelos. `data_collection/processed/` permanece vacío. Las copias de distribución fueron autorizadas específicamente para este directorio del repositorio.

El audio sigue fuera del alcance: no decodificarlo, extraerlo, reproducirlo, transcribirlo ni analizarlo. No realizar reconocimiento facial, biometría, identificación de personas ni inferencias sobre intenciones o estados personales. Todo derivado futuro debe mantener trazabilidad al RAW y al archivo de distribución mediante sus hashes.
