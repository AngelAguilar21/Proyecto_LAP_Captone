# Ficha B2 — MeMOTR (ICCV 2023)

Archivo fuente: `informe/papers/B2_MeMOTR_ICCV2023.pdf` (versión CVF Open Access, 10 páginas).

## 1. Referencia completa

Copiada literalmente de `informe/papers/citas_oficiales.txt`:

```bibtex
@InProceedings{Gao_2023_ICCV,
author = {Gao, Ruopeng and Wang, Limin},
title = {MeMOTR: Long-Term Memory-Augmented Transformer for Multi-Object Tracking},
booktitle = {Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)},
month = {October},
year = {2023},
pages = {9901--9910}
}
```

## 2. Problema y propuesta

El seguimiento multi-objeto (MOT) es una tarea de video y debería capturar información temporal, pero
la mayoría de los métodos explota únicamente las características de los objetos entre fotogramas
adyacentes, sin capacidad de modelar información temporal de largo plazo; eso los hace fallar ante
apariencias similares, movimientos irregulares y oclusiones prolongadas. MeMOTR propone un
Transformer aumentado con memoria de largo plazo: mantiene, para cada objeto rastreado, una memoria
actualizada por recursión exponencial e inyecta esa memoria en el track embedding, de modo que este
evita cambios abruptos y se vuelve más estable y distinguible. Una capa de memory-attention hace
interactuar las distintas trayectorias entre sí para obtener representaciones más discriminativas, y
una agregación adaptativa fusiona la salida de dos fotogramas contiguos para ganar robustez. Los
autores añaden un decoder de detección separado para cerrar la brecha semántica entre las consultas
de detección aprendibles y las de seguimiento.

## 3. Datasets y licencias

Datasets de evaluación (sección 4.1):

- DanceTrack — el principal, elegido por presentar desafíos de asociación más severos que los
  datasets clásicos de peatones
- MOT17
- BDD100K — seguimiento multi-categoría

Datos adicionales de entrenamiento e inicialización (sección 4.2):

- CrowdHuman, conjunto de validación (~4000 imágenes estáticas), añadido al entrenamiento de MOT17
  para mitigar el sobreajuste por el tamaño reducido de su train set (~5000 fotogramas); se le aplican
  desplazamientos aleatorios al estilo de CenterTrack para generar trayectorias pseudo.
- COCO — el modelo se inicializa con los pesos oficiales de DAB-Deformable-DETR preentrenados en COCO.

Métricas: HOTA (con análisis específico sobre AssA), además de MOTA e IDF1.

**Restricciones de licencia: FALTA.** El artículo no menciona licencias, copyright ni condiciones de
uso de los datasets (búsqueda en el texto completo: 0 coincidencias).

## 4. Técnicas

**Arquitectura** (sección 3.1). Backbone ResNet-50 y un Transformer Encoder producen la
característica de imagen del fotograma de entrada. El modelo se construye sobre DAB-Deformable-DETR
—los autores señalan que el prior de posición basado en anclas de esa variante resulta eficaz por la
suavidad temporal de las cajas rastreadas— y también reportan una variante sobre Deformable-DETR
estándar para comparación justa.

**Decoder dividido** (sección 3.2). En lugar de introducir juntas desde cero la detect query
aprendible y las track queries previas, dividen el Transformer Decoder en dos partes: la primera capa
actúa como Detection Decoder `D_det` y produce el detect embedding con semántica específica; las
cinco capas restantes forman el Joint Decoder `D_joint`, que recibe conjuntamente los detect y track
embeddings. Ambos decoders tienen la misma estructura pero entradas distintas. La motivación es que
la object query aprendible de DETR funciona como un ancla sin apenas semántica, mientras que la track
query sí porta conocimiento semántico del objeto, y esa brecha degrada el desempeño.

**Memoria de largo plazo** (sección 3.3). Para cada objeto rastreado se mantiene una memoria `M`
inicializada con la salida del fotograma en que nace, y actualizada con una media móvil de pesos
exponencialmente decrecientes (Ec. 1): `M_{t+1} = (1 − λ)·M_t + λ·O_t`. La tasa de actualización se
fija experimentalmente en `λ = 0.01`, bajo el supuesto de que la memoria cambia de forma suave y
consistente entre fotogramas consecutivos.

**Temporal Interaction Module** (sección 3.4). Tres piezas encadenadas:

1. *Agregación adaptativa*: se genera un peso por canal `W = Sigmoid(MLP(O))` para cada instancia
   rastreada (Ec. 2), se multiplica por la salida actual, se concatena con la salida del fotograma
   anterior y un MLP de dos capas produce la fusión. Al output previo no se le aplica el peso
   adaptativo, porque en inferencia ya se garantiza su fiabilidad mediante un umbral de score.
2. *Capa de memory-attention*: una estructura de Multi-Head Attention donde la memoria de largo plazo
   actúa como `K`, la agregación temporal como `Q` y el output embedding como `V`, estableciendo
   interacción entre trayectorias distintas.
3. Se suma la memoria de largo plazo al resultado de la atención y se pasa por una red FFN para
   predecir el track embedding del fotograma siguiente.

**Inferencia** (sección 3.5). Una detección con confianza superior a `τ_det` se convierte en objeto
recién nacido. Si un objeto rastreado se pierde (confianza ≤ `τ_tck`) no se elimina su track
embedding: se marca como trayectoria inactiva y se descarta por completo tras `T_miss` fotogramas.
El track embedding y la memoria no se actualizan en cada paso para todos los objetos, sino solo para
aquellos cuya confianza supera `τ_next` (Ec. 3). Valores: `τ_det = τ_tck = τ_next = 0.5`;
`T_miss` = 30 en DanceTrack, 15 en MOT17 y 10 en BDD100K.

**Función de pérdida: FALTA.** El artículo no describe ninguna función de pérdida. La palabra "loss"
no aparece en el texto completo del PDF (0 coincidencias, incluidas las referencias), y no hay
ecuación ni párrafo dedicados a la supervisión del entrenamiento. Lo único declarado sobre
optimización es el uso de AdamW con learning rate inicial 2,0e-4, umbrales de filtrado durante el
entrenamiento `τ_update = 0.5` e `IoU = 0.5`, entrenamiento sobre clips de video con intervalos
muestreados aleatoriamente entre 1 y 10 fotogramas, batch size 1 por GPU sobre 8 NVIDIA Tesla V100, y
los calendarios de épocas por dataset (18 en DanceTrack, 130 en MOT17, 14 en BDD100K). Si se necesita
la formulación de la pérdida habrá que buscarla en MOTR, cuyos ajustes los autores declaran seguir.

## 5. Figura del pipeline

**Figura 1, página 3 del PDF (p. 9903 de las actas).** Título: "Overview of MeMOTR".

Complementariamente, la **Figura 2, página 4 del PDF (p. 9904)** detalla el Temporal Interaction
Module, que es el componente central del método.

## 6. Limitaciones reconocidas por los autores

El artículo sí tiene una sección propia: **4.7. Limitations** (página 8 del PDF, p. 9908 de las
actas). Lo que reconocen:

- Aunque MeMOTR mejora notablemente la asociación, el desempeño de **detección sigue siendo un punto
  débil**, especialmente en escenarios concurridos como MOT17.
- Durante los experimentos observaron que **a veces los objetos recién nacidos quedan suprimidos por
  los objetivos ya rastreados** dentro de la estructura de self-attention, lo que reduce el desempeño
  de detección. Resolver ese conflicto lo señalan como un desafío crucial del paradigma de tracking
  conjunto, y apuntan que mejorarlo elevaría el desempeño global del modelo.
- En seguimiento de peatones, **los datasets existentes siguen siendo limitados en tamaño y
  diversidad**; sugieren que entrenar con datasets de simulación (mencionan MOTSynth) podría aliviar
  el problema de sobreajuste de su modelo.

Además, en la sección 4.6 reconocen que la tasa de actualización de la memoria `λ` es un
hiperparámetro que debe elegirse según el dataset: escenarios con abundante deformación no rígida de
los objetivos podrían necesitar una tasa más alta para adaptarse a características que cambian rápido.

Datos de desempeño confirmados en prosa (resumen): MeMOTR supera al método del estado del arte en
DanceTrack en 7,9 % en HOTA y 13,0 % en AssA.

## 7. RELEVANCIA PARA LAP

Evaluado y descartado. Su contribución central es una memoria de largo plazo que mantiene la identidad de cada objeto a lo largo del tiempo, lo cual constituye seguimiento individual persistente. Bajo el alcance acordado para el proyecto, ese tipo de tratamiento excede el principio de proporcionalidad y aproxima la solución al régimen de datos sensibles del D.S. 016-2024-JUS. Se documenta como alternativa considerada dentro del estado del arte, no como componente de la arquitectura propuesta.
