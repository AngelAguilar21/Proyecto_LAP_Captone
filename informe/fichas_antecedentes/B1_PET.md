# Ficha B1 — PET, Point quEry Transformer (ICCV 2023)

Archivo fuente: `informe/papers/B1_PET_ICCV2023.pdf` (versión CVF Open Access, 10 páginas).

## 1. Referencia completa

Copiada literalmente de `informe/papers/citas_oficiales.txt`:

```bibtex
@InProceedings{Liu_2023_ICCV,
author = {Liu, Chengxin and Lu, Hao and Cao, Zhiguo and Liu, Tongliang},
title = {Point-Query Quadtree for Crowd Counting, Localization, and More},
booktitle = {Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)},
month = {October},
year = {2023},
pages = {1676--1685}
}
```

## 2. Problema y propuesta

El conteo de multitudes se aborda habitualmente aprendiendo objetivos sustitutos como los mapas de
densidad, que no aportan información a nivel de instancia; las alternativas por detección o por punto
dependen de cajas pseudo-generadas o de post-procesamiento heurístico, y cada método suele resolver
una sola tarea o un solo paradigma de aprendizaje. Los autores reformulan el conteo como un proceso
de consulta por puntos descomponible: el modelo recibe puntos arbitrarios de entrada y razona, para
cada uno, si es una persona y dónde se ubica. El problema que abre esa formulación es cuántos puntos
de consulta usar —pocos subestiman, muchos disparan el costo—, y lo resuelven con una estructura
descomponible, el quadtree de consulta por puntos, en la que un punto se divide en cuatro cuando la
región lo requiere. Sobre esa estructura instancian PET (Point quEry Transformer), con atención
progresiva en ventana rectangular, y muestran que un mismo modelo cubre conteo y localización
totalmente supervisados, aprendizaje con anotación parcial y refinamiento de anotaciones de punto.

## 3. Datasets y licencias

Datasets usados (sección 4.1), con las particiones que declara el artículo:

- ShanghaiTech — PartA (300 imágenes de entrenamiento / 182 de prueba) y PartB (400 / 316)
- UCF-QNRF — 1535 imágenes de densidad diversa (1201 / 334)
- JHU-Crowd++ — 4372 imágenes (2272 entrenamiento / 500 validación / 1600 prueba)
- NWPU-Crowd — 3109 entrenamiento / 500 validación / 1500 prueba

Métricas: MAE y MSE. Para los datasets de alta resolución limitan el lado mayor de cada imagen a
1536 px (UCF-QNRF), 2048 px (JHU-Crowd++) y 2048 px (NWPU-Crowd).

**Restricciones de licencia: FALTA.** El artículo no menciona licencias, copyright ni condiciones de
uso de los datasets (búsqueda en el texto completo: 0 coincidencias).

## 4. Técnicas

**Arquitectura** (sección 3.2). Cuatro componentes: un backbone CNN, un transformer encoder-decoder
eficiente, el quadtree de consulta por puntos y una cabeza de predicción. El backbone (VGG16) extrae
la representación `F ∈ R^{h×w×c}`; cada elemento espacial de `F` se trata como un token. Los tokens
pasan por un encoder transformer implementado con atención progresiva en ventana rectangular. El
quadtree splitter recibe los puntos de consulta dispersos y las características codificadas y produce
el quadtree; el decoder decodifica las consultas en paralelo, calculando atención dentro de una
ventana local; la cabeza de predicción son capas MLP con activación ReLU y emite, por consulta, una
probabilidad de clasificación y una localización normalizada. El encoder tiene 4 capas y el decoder
2; el quadtree comparte el mismo decoder.

**Quadtree de consulta por puntos** (sección 3.3). Se siembran puntos dispersos sobre la imagen con
stride `K = 8` (nivel 0). Un quadtree splitter —average pooling, convolución 1×1 y sigmoide, de costo
computacional despreciable— produce un split map `Ms` donde cada elemento es la probabilidad de que
una región sea densa; se binariza con umbral 0,5 y las regiones densas se subdividen, formando el
nivel 1. El proceso se repite hasta L divisiones; en la práctica los autores encuentran que dividir
una sola vez (L = 1) basta. La profundidad máxima del quadtree es 2. Cada consulta se representa
sumando la característica CNN interpolada `Fx,y` y un positional embedding espacial fijo.

**Atención progresiva en ventana rectangular** (sección 3.4). El encoder atiende primero dentro de
una ventana rectangular grande de tamaño `se × re·se` en las primeras capas y luego dentro de una
ventana la mitad de grande en las siguientes. La ventana es horizontal porque, por el efecto de
perspectiva, un parche horizontal suele contener más personas que uno vertical (Figura 5). En el
decoder la atención de las consultas dispersas se calcula en una ventana de `½se × ½re·se` y la de
las consultas densas en una de `¼se × ¼re·se`. Parámetros: `se = 16`, `re = 2`. Los autores destacan
que este diseño da complejidad lineal, útil en imágenes de alta resolución.

**Función de pérdida** (sección 3.5, Ecs. 3–5):

- `ℓ_pq` (Ec. 3): entropía cruzada para la clasificación más `λ1` por una pérdida smooth-L1 de
  localización, con la correspondencia entre predicciones y puntos de verdad-terreno obtenida por
  emparejamiento bipartito. La etiqueta de clasificación vale 1 solo si la consulta quedó emparejada.
- `ℓ_split` (Ec. 4): `1(dense)·(1 − max(Ms)) + min(Ms)`, supervisión mínima para que el splitter
  distinga regiones densas de dispersas.
- Pérdida total (Ec. 5): `ℓ_total = ℓ_pq + λ2·ℓ_split`, con `λ1 = 5.0` y `λ2 = 0.1`.

Adicionalmente aplican "dual supervision": dividen cada mini-batch en paquetes disperso y denso según
densidad, calculan `ℓ_total` por separado en cada uno y suman las pérdidas, para evitar que las
muestras con pocas personas diluyan la señal.

Optimización: Adam, weight decay 5e-4, learning rate inicial 1e-5 para el backbone CNN y 1e-4 para el
transformer. Aumentación: recortes aleatorios de 256×256, escalado y volteo aleatorios.

## 5. Figura del pipeline

**Figura 2, página 3 del PDF (p. 1678 de las actas).** Título: "Overall architecture of PET".

## 6. Limitaciones reconocidas por los autores

Reconocidas explícitamente al cierre de la sección 4 (página 8 del PDF, p. 1683 de las actas), bajo
la fórmula "Albeit effective, PET still has limitations":

- PET puede sufrir detecciones perdidas ante cabezas grandes, debido al tamaño limitado de la ventana
  rectangular.
- La representación de la consulta por punto (point query) es mejorable.
- Como trabajo futuro plantean extender la formulación a otras tareas de predicción densa.

En la sección 4.2, al discutir el refinamiento de anotaciones, matizan también que la mejora obtenida
al reentrenar con anotaciones refinadas es marginal porque la mayoría de las anotaciones del dataset
ya son razonables.

Dato de desempeño confirmado en prosa (introducción): MAE de 49,34 en ShanghaiTech PartA.

## 7. RELEVANCIA PARA LAP

Su quadtree adaptativo procesa dinámicamente regiones densas y dispersas dentro de una misma imagen, lo cual es directamente aplicable al terminal, donde una sola cámara observa simultáneamente colas congestionadas y pasillos vacíos. El aprendizaje con anotación parcial reduce el costo de etiquetado sobre el video que proporcione la empresa. Al igual que P2PNet, opera sobre imágenes individuales sin asociación temporal.
