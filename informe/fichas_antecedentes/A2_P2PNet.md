# Ficha A2 — P2PNet (ICCV 2021)

Archivo fuente: `informe/papers/A2_P2PNet_ICCV2021.pdf` (versión CVF Open Access, 10 páginas).

## 1. Referencia completa

Copiada literalmente de `informe/papers/citas_oficiales.txt`:

```bibtex
@InProceedings{Song_2021_ICCV,
author = {Song, Qingyu and Wang, Changan and Jiang, Zhengkai and Wang, Yabiao and Tai, Ying and Wang, Chengjie and Li, Jilin and Huang, Feiyue and Wu, Yang},
title = {Rethinking Counting and Localization in Crowds: A Purely Point-Based Framework},
booktitle = {Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)},
month = {October},
year = {2021},
pages = {3365--3374}
}
```

## 2. Problema y propuesta

Localizar individuos dentro de una multitud responde mejor a las necesidades de las tareas de
análisis posteriores que limitarse a contar, pero los métodos de localización existentes dependen
de representaciones intermedias —mapas de densidad o cajas delimitadoras pseudo-generadas— que los
autores califican de contraintuitivas y propensas a error. El artículo propone un marco puramente
basado en puntos: usa las anotaciones de punto directamente como objetivo de aprendizaje y produce
puntos como salida. Introduce además una métrica nueva, density Normalized Average Precision (nAP),
que evalúa conjuntamente el error de conteo y el de localización. Como instancia concreta del marco
presentan P2PNet, que predice un conjunto de propuestas de punto con sus confianzas; el paso clave
identificado es asignar objetivos óptimos a esas propuestas mediante un emparejamiento uno a uno
resuelto con el algoritmo húngaro.

## 3. Datasets y licencias

Datasets usados (sección 4.1, "Dataset"), descritos por los autores como "existing publicly
available datasets":

- ShanghaiTech PartA y PartB
- UCF_CC_50 — con validación cruzada de cinco pliegues
- UCF-QNRF
- NWPU-Crowd

Para QNRF y NWPU-Crowd, por su resolución elevada, limitan el lado mayor de la imagen a 1408 y 1920
píxeles respectivamente, conservando la relación de aspecto original.

**Restricciones de licencia: FALTA.** El artículo no menciona licencias, copyright ni condiciones de
uso de ninguno de los datasets (búsqueda en el texto completo: 0 coincidencias).

## 4. Técnicas

**Arquitectura** (sección 3.4, "Network Design"). Las primeras 13 capas convolucionales de VGG-16_bn
como extractor de características. Sobre el mapa resultante se aplica una ruta de upsampling: se
duplica la resolución espacial por interpolación de vecino más cercano y se fusiona, mediante suma
elemento a elemento, con el mapa que llega por una conexión lateral desde el cuarto bloque
convolucional (la conexión lateral reduce la dimensión de canales). El mapa fusionado pasa por una
convolución 3×3 —que reduce el aliasing del upsampling— y produce el mapa de características `Fs`.
La cabeza de predicción tiene dos ramas de idéntica estructura, alimentadas ambas con `Fs`: una de
regresión de coordenadas y una de clasificación. Cada rama son tres convoluciones apiladas
intercaladas con activaciones ReLU; la de clasificación normaliza con softmax.

**Método principal.** Cada píxel de `Fs` corresponde a un parche de s×s en la imagen de entrada. En
ese parche se fijan K puntos de referencia con posiciones predefinidas, en dos disposiciones posibles
(Center Layout y Grid Layout, Figura 4). La rama de regresión predice offsets respecto a esos puntos
de referencia, de modo que se generan H×W×K propuestas de punto en total. La asignación de objetivos
se resuelve como un emparejamiento uno a uno con el algoritmo húngaro sobre una matriz de costo
`D` de tamaño N×M que combina la distancia euclidiana entre puntos con la confianza de la propuesta
(Ec. 3), no solo la distancia en píxeles. Las propuestas emparejadas son positivas; las restantes
quedan automáticamente como negativas, sin necesidad de introducir un umbral adicional. Los autores
razonan explícitamente (Figura 3) por qué las alternativas 1-a-N y N-a-1 fallan: producen conteos
subestimados y sobreestimados respectivamente.

**Función de pérdida** (Ecs. 4–6). `L = Lcls + λ2·Lloc`, donde:

- `Lcls` es una pérdida de entropía cruzada sobre la clasificación de las propuestas, con un factor
  de re-peso `λ1` aplicado a las propuestas negativas.
- `Lloc` es una pérdida euclidiana (distancia l2) que supervisa la regresión de los puntos positivos.
- `λ2` es el término que balancea la contribución de la regresión.

Hiperparámetros declarados en prosa: stride `s = 8`, `K = 4` (8 para QNRF), término de normalización
de offsets 100, peso de la confianza en el matching 5e-2, `λ1 = 0.5`, `λ2 = 2e-4`, optimizador Adam
con learning rate fijo 1e-4 (1e-5 para el backbone preentrenado en ImageNet), batch size 8.

## 5. Figura del pipeline

**Figura 5, página 6 del PDF (p. 3370 de las actas).** Título: "The overall architecture of the
proposed P2PNet".

Como referencia adicional, la Figura 1 (página 1 del PDF, p. 3365) ilustra el pipeline a nivel
conceptual, comparándolo con el de los métodos basados en mapas de densidad y en detección.

## 6. Limitaciones reconocidas por los autores

El artículo no tiene una sección de limitaciones. En prosa los autores sí reconocen lo siguiente:

- Las predicciones se basan en un único mapa de características de una sola escala "for simplicity";
  por eso, en NWPU-Crowd, el resultado en la métrica MAE[S] queda algo por debajo de los mejores,
  aunque el MAE global sea el mejor.
- Descartan deliberadamente las técnicas de fusión de características multiescala (citan Feature
  Pyramid Networks) por simplicidad, y señalan que sería interesante incorporarlas al método base.
- Observan que un mapa de características más fino mejora la precisión de localización (nAP), lo que
  implica que la resolución elegida acota el desempeño alcanzable.
- Sobre la tarea en general, reconocen que es difícil de abordar por las oclusiones severas, la
  variación de densidad y los errores de anotación; citan trabajos que la consideran ideal pero
  inviable.

Dato de desempeño confirmado en prosa: en NWPU-Crowd, P2PNet obtiene el mejor MAE global, con una
reducción del 12,4 % respecto al segundo mejor método, DM-Count.

## 7. RELEVANCIA PARA LAP

Entrega conteo y localización simultáneos mediante predicción de puntos, sin detección de rostros ni identificadores persistentes. La salida en coordenadas permite construir mapas de calor por zona comercial del terminal, que es el nivel de granularidad que requiere el área usuaria de LAP. Cada fotograma se procesa de forma independiente, por lo que no se generan trayectorias individuales.
