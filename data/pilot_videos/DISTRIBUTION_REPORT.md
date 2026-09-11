# Privacidad y distribución del dataset piloto LAP

Estado: **9/9 derivados de distribución verificados**, creados en sus rutas definitivas. Los nueve videos están añadidos al índice como punteros Git LFS junto al catálogo, documentación y reglas del milestone. No se ejecutaron commit ni push.

Los nueve RAW canónicos de `data_collection/raw/` permanecen absolutamente intactos. Cada `raw_sha256` coincide con el catálogo canónico antes y después del proceso. El catálogo canónico tampoco fue modificado. Los archivos de este directorio son **derivados de distribución para Git/LFS**, no sustitutos de los RAW originales.

Procedencia de todos los videos: `captured_by = José Ortega`; `source = Captura propia para Proyecto LAP`. Fueron capturados directamente por José Ortega durante la fase de adquisición de datos del proyecto.

## Transformación aplicada

Se repitió el procedimiento aprobado con VID_009 en cada copia. Solo se eliminaron las claves y valores sensibles de ubicación explícita encontrados:

- `com.apple.quicktime.location.ISO6709`: latitud, longitud y altitud.
- `com.apple.quicktime.location.accuracy.horizontal`: precisión horizontal.

No se encontraron otros campos explícitos equivalentes de geolocalización en las estructuras inspeccionadas. Se reconstruyó únicamente el átomo `moov/meta`, remapeando los índices de las claves retenidas y rellenando con un átomo `free` de ceros el espacio liberado. Las restantes claves y valores legibles se conservaron.

**No hubo recodificación de video ni audio ni remultiplexado de pistas.** Los bytes externos al átomo editado permanecen idénticos, incluidos los datos multimedia `mdat`, tablas de muestras, tiempos y descripciones de pistas. Las comparaciones byte por byte y los hashes de los bloques multimedia coinciden para las nueve parejas RAW/derivado. El SHA-256 del archivo completo cambia, como corresponde a la edición de metadatos.

## Verificaciones

Cada copia se verificó primero en una carpeta temporal; solo después se colocó en su destino. Las nueve abrieron correctamente y completaron la decodificación de video sin errores. Resolución, FPS nominal y medido, duración, frames, codec y orientación coinciden con el QA canónico. La decodificación de control fue exclusivamente de video: el audio no se decodificó, extrajo, reprodujo ni analizó; sus bytes codificados se conservaron.

Después de colocar las nueve copias se repitió la inspección de metadatos: no aparecen etiquetas explícitas de ubicación/GPS, coordenadas ISO6709, latitud, longitud, altitud o geolocalización en las comprobaciones realizadas. Las claves declaradas por las pistas de metadatos tampoco indican geolocalización. Las demás etiquetas legibles y los tipos de pistas coinciden con sus RAW.

Se comprobó `filter=lfs`, `diff=lfs`, `merge=lfs` y `text=unset` para las nueve rutas, incluyendo comprobación sensible a mayúsculas/minúsculas. Ninguna ruta está excluida por .gitignore. El índice contiene exactamente nueve punteros LFS: sus oid SHA-256 y tamaños coinciden con los derivados de distribución, no con los RAW canónicos. La caché LFS local y los archivos de trabajo se verificaron contra esos mismos hashes.

## Tabla consolidada

| video_id | original_filename | raw_sha256 | distribution_sha256 | resolution | fps | duration_seconds | frames | codec | geolocation_removed | encoded_media_identical | repo_lfs_path | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VID_001 | IMG_1556.MOV | c977e41abe2ff9f34aa28de523512db09eca2b7b7aec1bd6b3615291e0676d7d | a72986309adcd20c2ceb74d2bf0ec15be706d09563236e3a25b7b7c6f135fafa | 3840x2160 | 29.999193136 | 185.938333333 | 5578 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1556.MOV | distribution_verified_staged |
| VID_002 | IMG_1558.MOV | 10d9befb9ef122c10071e321e961f3af25b4b2d2187cdd65535527c0e1eca5cc | 633b51f56e1524ccfd0292b6cd93690f73bf89a341db2f1f2885ebd3ba5b10ba | 3840x2160 | 29.999204265 | 125.703333333 | 3771 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1558.MOV | distribution_verified_staged |
| VID_003 | IMG_1559.MOV | 690819e6c18a04e20f7b6af5e302528457fb5bbf68027e2de13dc59ec967a670 | c023720bed761600dd8ba0f8b8f8feeef34094e4d0f384b285120c824346c6ba | 3840x2160 | 29.999265564 | 204.271666667 | 6128 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1559.MOV | distribution_verified_staged |
| VID_004 | IMG_1565.MOV | b654543c913e48d241f08bec7cb80b09d9934bcd376e543e2ae16f27e611d067 | 9168593a89a88e2d97a42f6b64c60628ef17c837d1f92e02ef8e8d465b878d1a | 3840x2160 | 30 | 5.5 | 165 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1565.MOV | distribution_verified_staged |
| VID_005 | IMG_1566.MOV | 933a5ec5e70682391037753fb7df0336a0d633fbe5320f30611a05ee6e175b5c | e85a91e909ea472611a19427e32b78a73aceea89fe9a759b1751da003e3e335e | 3840x2160 | 29.999302828 | 143.47 | 4304 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1566.MOV | distribution_verified_staged |
| VID_006 | IMG_1567.MOV | ebb28127ceb8ffebdcf4134bdd7895612135dc0c1681ef0e2bd8a40894d3cff1 | 47b8415502d49d9ff6ecf6f2363ea6e39b87379a5c688cbd80ee61857f7f06ae | 3840x2160 | 29.999174183 | 181.67 | 5450 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1567.MOV | distribution_verified_staged |
| VID_007 | IMG_1568.MOV | f4c2865d722c3fc493d52c29d46a174a87dd56e1c1d9ca62debf0a7906886351 | d7216d300efd2112860ce9b8405b9714a9af2a1a456738f90c61fc3ae4daa2b0 | 3840x2160 | 29.999177804 | 182.47 | 5474 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1568.MOV | distribution_verified_staged |
| VID_008 | IMG_1555.MOV | 7725526ca384b7433b9e58e349f310254d8dd9654e4c8358cc3e12f6a24c861d | c14f5a72691a40d6b260a3d3d0e057cc6337a89159f2b8b6ef30489965bed2d3 | 3840x2160 | 29.999206090170514 | 188.97 | 5669 | HEVC/H.265 | true | true | data/pilot_videos/universidad_lima/IMG_1555.MOV | distribution_verified_staged |
| VID_009 | IMG_1569.mov | cff652159f28a8c3072efb2b9b06791bcaf606e39d8d45c10b8a43e3e9f071d8 | 5c5b61402208242affda7838b6c386d0f36a0e2d76be0b03d29e98fda4dd97a8 | 3840x2160 | 29.99910236079112 | 55.735 | 1672 | HEVC/H.265 | true | true | data/pilot_videos/jockey_plaza/IMG_1569.mov | distribution_verified_staged |

Tamaño total de derivados: **4098895779 bytes (4.098895779 GB)**. Duración total: **1273.728333333 segundos**. Los tamaños se mantienen iguales a los RAW debido al espacio libre rellenado con ceros; no se comprimió ningún video. Universidad de Lima: 8 derivados. Jockey Plaza: 1 derivado.

## Alcance de privacidad y trazabilidad

La transformación elimina la geolocalización explícita detectada. Se conservan otros campos y pistas propietarias de Apple: no se interpretó el contenido de todas sus muestras opacas ni se certifica una anonimización integral. El contenido visual y sus referencias de lugar no se alteraron. No se analizan rostros, identidades ni intenciones.

La prueba aprobada de VID_009 y el derivado definitivo de ese mismo archivo producen el mismo distribution_sha256. Los demás ocho pasaron las mismas verificaciones. Los nueve pares de hashes completos están en esta tabla y en `videos_metadata.csv`.

La evidencia local detallada se conserva en `data_collection/reports/privacy_distribution_batch/`: verificaciones estructurales por archivo, hashes de bloques multimedia, QA, metadatos legibles posteriores y revisión final del lote. Se omitieron las coordenadas originales en la documentación de distribución.

## Referencias de formato

- [Apple: correspondencia entre claves y elementos de metadatos](https://developer.apple.com/documentation/quicktime-file-format/metadata_item_atom).
- [Apple: estructura de metadatos y uso de espacio libre tras eliminar elementos](https://developer.apple.com/documentation/quicktime-file-format/metadata_atoms_and_types).
- [Apple: metadatos de ubicación](https://developer.apple.com/documentation/quicktime-file-format/location_metadata).
