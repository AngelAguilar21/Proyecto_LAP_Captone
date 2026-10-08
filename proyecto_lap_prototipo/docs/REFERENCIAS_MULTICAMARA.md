# Referencias multicámara y decisiones para AeroTrack

## Qué resuelve realmente cada repositorio

### [tajwarchy/multi-camera-people-tracking](https://github.com/tajwarchy/multi-camera-people-tracking)

- Detecta con YOLOv8m y mantiene IDs locales con StrongSORT.
- Extrae embeddings OSNet de 512 dimensiones, normalizados L2.
- Asigna un ID global por similitud coseno y actualiza un prototipo con EMA.
- Proyecta el centro inferior de cada caja (los pies) con homografías de suelo ya incluidas en el dataset EPFL.
- Trabaja con cámaras sincronizadas y una escena pequeña de laboratorio. Su segunda pasada une prototipos parecidos, pero no aplica una compuerta física ni resuelve por sí sola una calibración incorrecta.

### [Jiahao-Ma/MvCHM](https://github.com/Jiahao-Ma/MvCHM)

- Es detección multivista, no un sistema completo de seguimiento y Re-ID.
- Usa matrices intrínsecas/extrínsecas, profundidad y nubes de puntos para llevar cada vista a coordenadas 3D del mundo.
- Modela el volumen aproximado de una persona para reducir el error que aparece al proyectar solo una imagen 2D sobre el suelo.
- Está pensado para datasets calibrados como Wildtrack/MultiviewX y requiere modelos entrenados y GPU. No generaliza a una cámara nueva con cuatro clics sin una fase de calibración.

### [hou-yz/MVDet](https://github.com/hou-yz/MVDet)

- También es detección multivista en una cuadrícula BEV común, no Re-ID temporal en producción.
- Construye la transformación imagen→mundo a partir de matrices intrínsecas, extrínsecas y la matriz mundo→cuadrícula.
- Proyecta características de todas las cámaras a la misma cuadrícula y las fusiona antes de detectar.
- Supone cámaras estáticas, sincronizadas, solapadas y calibradas con precisión. El costo y la necesidad de datos etiquetados son mayores que los de YOLO + tracker + Re-ID.

### [openvinotoolkit/open_model_zoo](https://github.com/openvinotoolkit/open_model_zoo), demo `multi_camera_multi_target_tracking_demo`

- Licencia Apache-2.0 (verificada en la API de GitHub el 2026-10-04); se puede usar y adaptar conservando el aviso.
- Detecta personas, extrae un vector Re-ID por recuadro y enlaza con apariencia y coherencia de velocidad del recuadro. No necesita calibrar las cámaras.
- Mantiene por pista un promedio y unos racimos de vectores; reenlaza fragmentos por cámara y une pistas entre cámaras de forma voraz cada cierto número de pasos.
- Está pensado para CPU. Se portó como motor `omz`, se midió que no mejora a `reid_v2` (ver `docs/EVALUACION_IDENTIDAD.md`) y se retiró.

### Licencias de los proyectos revisados (API de GitHub, 2026-10-04)

| Proyecto | Licencia |
|---|---|
| openvinotoolkit/open_model_zoo | Apache-2.0 |
| KaiyangZhou/deep-person-reid (Torchreid) | MIT |
| JDAI-CV/fast-reid | Apache-2.0 |
| NirAharon/BoT-SORT | MIT |
| tajwarchy/multi-camera-people-tracking | MIT |
| mikel-brostrom/boxmot | AGPL-3.0 (copyleft de red: revisar antes de integrarlo) |
| hou-yz/MVDet, ipl-uw/AIC23_Track1_UWIPL_ETRI, zhengthomastang/Cal_PnP | sin licencia declarada: no se copia código, solo se leen las ideas del artículo |

## Decisión para AeroTrack

No se copian MvCHM/MVDet porque el producto debe aceptar planos y cámaras diferentes en cada proyecto. Se sigue el esquema de
DeepCC (Ristani y Tomasi, 2018) y del primer lugar del AI City Challenge 2023 (Huang et al., 2023), descrito en
`docs/ARQUITECTURA.md`:

1. YOLO produce cajas y el punto de apoyo en los pies.
2. ByteTrack/Kalman mantiene la identidad local y conserva tracks durante oclusiones breves.
3. OSNet crea un vector multivista por tramo; no reemplaza la geometría.
4. La unión entre cámaras combina apariencia, tiempo y posición en un plano común, solo entre cámaras que el usuario
   relacionó marcando a la misma persona en ambas; al cerrar la sesión se reagrupa con la grabación completa.
5. La homografía usa puntos del suelo compartidos. Con cinco o más, RANSAC descarta clics inconsistentes.
6. Si dos homografías no concuerdan, el sistema lo mide y lo avisa; la solución es recalibrar, no una alineación estimada.

## Protocolo mínimo de calibración

- Marcar únicamente puntos del suelo, nunca cabeza, torso ni objetos elevados.
- Repartir 6–8 referencias por el área donde realmente caminan las personas; evitar puntos casi alineados o concentrados.
- Reutilizar exactamente los mismos hitos del plano en cámaras que se solapan.
- Reservar al menos dos referencias como comprobación visual y revisar la huella proyectada completa.
- Validar con una caminata conocida: la trayectoria debe seguir el pasillo y la misma persona debe quedar a una distancia pequeña entre cámaras simultáneas.
- Si el error cambia con la distancia o la persona parece desplazarse lateralmente, cuatro puntos no son suficientes: medir intrínsecos/extrínsecos o añadir referencias en esa región.

## Métricas de aceptación

- Homografía: error de reproyección y validación cruzada, porcentaje de inliers y cobertura de referencias en la imagen.
- Plano: distancia entre la misma persona proyectada simultáneamente desde dos cámaras.
- Tracking local: IDF1/HOTA, cambios de ID y fragmentaciones por persona.
- Re-ID multicámara: CMC@1, mAP, IDF1 global, IDs por persona y pureza de cada ID.
- Operación: latencia p50/p95, FPS efectivo, porcentaje de frames omitidos y tiempo de recuperación después de una oclusión.

Un resultado correcto en un video de cuatro personas no valida el producto. Los umbrales deben ajustarse con un conjunto distinto al usado para medir, idealmente por sitio y tipo de cámara.
