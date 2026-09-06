# Ficha B3 — ByteTrack (ECCV 2022)

Archivo fuente: `informe/papers/B3_ByteTrack_ECCV2022.pdf`, 14 páginas.

> **Nota sobre la versión del PDF.** El archivo corresponde a la **versión de arXiv**
> (`arXiv:2110.06864v3 [cs.CV]`, 7 de abril de 2022), tal como aparece impreso en el margen de la
> primera página. Se usa esta versión porque ECCV no publica en CVF Open Access —a diferencia de CVPR
> e ICCV, cuyos PDF de esta misma carpeta sí llevan la marca de agua de Open Access— y la versión
> editorial de Springer (LNCS) es de pago. Al citar y al referirse a números de página hay que tener
> presente que la paginación y la estructura de esta versión no coinciden necesariamente con las de la
> versión publicada por Springer: el PDF de arXiv incluye apéndices (secciones A–F) que la versión de
> actas puede presentar de otra forma.

## 1. Referencia completa

Copiada literalmente de `informe/papers/citas_oficiales.txt`:

```bibtex
@InProceedings{Zhang_2022_ECCV,
author = {Zhang, Yifu and Sun, Peize and Jiang, Yi and Yu, Dongdong and Weng, Fucheng and Yuan, Zehuan and Luo, Ping and Liu, Wenyu and Wang, Xinggang},
title = {ByteTrack: Multi-Object Tracking by Associating Every Detection Box},
booktitle = {Proceedings of the European Conference on Computer Vision (ECCV)},
year = {2022}
}
```

La cita apunta a las actas de ECCV, mientras que el PDF de trabajo de esta ficha es el preprint de
arXiv (ver la nota de versión al inicio). Es la combinación correcta —se cita la publicación y se
consulta el preprint accesible—, pero implica que los números de página que aparecen en los puntos 5
y 6 corresponden al PDF de arXiv y no a la paginación de las actas.

A diferencia de las otras cinco entradas del archivo de citas, esta no incluye campo `pages`. Se
copió tal cual, sin completarlo.

## 2. Problema y propuesta

El seguimiento multi-objeto estima cajas delimitadoras e identidades de objetos en video, y la
mayoría de los métodos obtiene las identidades asociando únicamente las cajas de detección cuyo score
supera un umbral. Los objetos con score bajo —por ejemplo los ocluidos— se descartan sin más, lo que
provoca una pérdida no despreciable de objetos reales y trayectorias fragmentadas. Los autores
sostienen que eliminar todas las cajas de score bajo es un error, porque a menudo esas cajas sí
indican la existencia de un objeto, y proponen BYTE: un método de asociación simple, efectivo y
genérico que asocia casi todas las cajas de detección en lugar de solo las de score alto. Para las
cajas de score bajo aprovechan su similitud con las tracklets existentes, lo que permite recuperar
objetos reales y filtrar las detecciones de fondo. Sobre BYTE construyen ByteTrack, un tracker que
combina el detector YOLOX con este esquema de asociación.

## 3. Datasets y licencias

Datasets de evaluación (sección 4.1):

- MOT17 y MOT20 — bajo el protocolo de "private detection". Ninguno tiene conjunto de validación, así
  que para los estudios de ablación usan la primera mitad de cada video del train set de MOT17 para
  entrenar y la segunda mitad para validar.
- HiEve — dataset humano a gran escala centrado en eventos concurridos y complejos.
- BDD100K — el mayor dataset de video de conducción; la partición de la tarea MOT es de 1400 videos
  de entrenamiento, 200 de validación y 400 de prueba, con 8 clases a seguir y casos de movimiento de
  cámara amplio.

Datos adicionales de entrenamiento:

- CrowdHuman, combinado con la mitad del train set de MOT17 para las ablaciones.
- Cityperson y ETHZ, añadidos para evaluar sobre el test set de MOT17.
- Para MOT20 y HiEve solo añaden CrowdHuman; para BDD100K no usan datos adicionales.
- COCO — el detector YOLOX-X se inicializa con pesos preentrenados en COCO.

Métricas: métricas CLEAR (MOTA, FP, FN, IDs), IDF1 y HOTA; para BDD100K, mMOTA y mIDF1.

**Restricciones de licencia: FALTA.** El artículo no menciona licencias, copyright ni condiciones de
uso de los datasets (búsqueda en el texto completo: 0 coincidencias). Conviene señalar, de cara al
informe, que varios de estos conjuntos son de conducción o de vigilancia y su licencia real habría
que verificarla fuera del artículo.

## 4. Técnicas

**Arquitectura.** ByteTrack no propone una red nueva: es la combinación de un detector de alto
rendimiento, YOLOX (variante YOLOX-X como backbone), con el método de asociación BYTE. El modelo de
movimiento es un filtro de Kalman, que predice la posición de cada tracklet en el fotograma nuevo. La
similitud entre la caja predicha y la detectada puede calcularse por IoU o por distancia de
características Re-ID. En los benchmarks de MOT17, MOT20 y HiEve usan solo IoU; en las ablaciones de
MOT17 extraen features Re-ID con FastReID, y en BDD100K usan UniTrack (un modelo ResNet-50 de
clasificación en ImageNet) como extractor Re-ID.

**Método principal: BYTE** (sección 3, pseudocódigo en Algorithm 1). Para cada fotograma se predicen
las cajas y sus scores, y se separan en dos grupos según un umbral de score `τ`: las de score alto
`D_high` y las de score bajo `D_low`. Después se procede en dos asociaciones:

1. *Primera asociación*: se emparejan las cajas de `D_high` con todas las tracklets, usando la
   similitud de movimiento (o de apariencia) respecto de las cajas predichas por el filtro de Kalman.
2. *Segunda asociación* —la aportación central del método—: se emparejan las tracklets que quedaron
   sin correspondencia con las cajas de `D_low`, usando la misma similitud de movimiento. Así la
   persona ocluida con score bajo se reasigna a su tracklet previa, mientras que las cajas de fondo,
   que no tienen tracklet que las reclame, se eliminan.

Detalles de implementación declarados: umbral de detección por defecto `τ = 0.6`; en el paso de
asignación lineal se rechaza el emparejamiento si el IoU entre la caja detectada y la de la tracklet
es menor que 0,2; las tracklets perdidas se conservan 30 fotogramas por si el objeto reaparece. El
algoritmo incorpora además "track rebirth", que los autores omiten del pseudocódigo por simplicidad.

**Función de pérdida: FALTA.** El artículo no formula ninguna función de pérdida propia: la palabra
"loss" no aparece en el texto fuera de una entrada de la bibliografía (la referencia a Focal Loss).
BYTE es un método de asociación en tiempo de inferencia, no un objetivo de entrenamiento, y el
entrenamiento del detector sigue el de YOLOX. Lo declarado sobre entrenamiento (sección 4.1): tamaño
de entrada 1440×800 con lado corto entre 576 y 1024 en entrenamiento multiescala; aumentación con
Mosaic y Mixup; 8 GPU NVIDIA Tesla V100 con batch size 48; optimizador SGD con weight decay 5e-4 y
momentum 0,9; learning rate inicial 1e-3 con 1 época de warm-up y planificación por cosine annealing;
80 épocas para MOT17 y 50 para BDD100K; tiempo total de entrenamiento de unas 12 horas.

## 5. Figura del pipeline

**El artículo no incluye una figura de arquitectura o pipeline; ese dato concreto es FALTA.** Lo que
hay, y es lo más cercano:

- **Figura 2, página 2 del PDF**: "Examples of our method which associates every detection box".
  Ilustra el método sobre tres fotogramas (t1, t2, t3), mostrando (a) todas las cajas con sus scores,
  (b) las tracklets que obtienen los métodos previos asociando solo las cajas por encima del umbral y
  (c) las tracklets que obtiene BYTE asociando todas las cajas. Es la figura que explica el mecanismo,
  aunque en forma de ejemplo y no de diagrama de bloques.
- **Algorithm 1, página 4 del PDF**: "Pseudo-code of BYTE". El procedimiento completo del método está
  ahí, en pseudocódigo, no en una figura.
- La **Figura 1, página 1 del PDF**, es una comparación de desempeño (MOTA-IDF1-FPS) entre trackers,
  no un pipeline.

## 6. Limitaciones reconocidas por los autores

El artículo no tiene una sección de limitaciones ni un párrafo dedicado a ellas. En prosa, sin
embargo, los autores sí reconocen los siguientes puntos:

- **El filtro de Kalman falla en escenas de conducción autónoma** (BDD100K), y lo señalan como la
  razón principal del bajo desempeño de SORT, DeepSORT y MOTDT en ese dataset. Por eso ellos mismos no
  usan filtro de Kalman en BDD100K y recurren a modelos Re-ID externos. La causa que dan es que
  BDD100K tiene movimiento de cámara amplio y anotaciones a baja tasa de fotogramas, lo que invalida
  las señales de movimiento.
- **El umbral de score de detección es un hiperparámetro sensible** que debe ajustarse con cuidado en
  la tarea de MOT. Los autores lo afirman como problema general y argumentan que BYTE es más robusto a
  él que SORT, pero no que el problema desaparezca.
- **Las características Re-ID de las cajas de score bajo no son fiables**, porque esas cajas suelen
  contener oclusión severa o desenfoque de movimiento; por eso en la segunda asociación es importante
  usar IoU y no Re-ID.
- Reconocen que las features Re-ID son vulnerables en casos de oclusión severa y pueden provocar
  cambios de identidad, frente a lo cual el modelo de movimiento se comporta de forma más fiable.
- Bajo el protocolo de detector público **no aplican la interpolación de tracklets**, es decir, esa
  mejora del método no está disponible en ese escenario.

Datos de desempeño confirmados en prosa (resumen y conclusión): aplicado a 9 trackers distintos del
estado del arte, el método mejora el IDF1 entre 1 y 10 puntos; ByteTrack alcanza 80,3 MOTA, 77,3 IDF1
y 63,1 HOTA en el test set de MOT17 con 30 FPS sobre una sola GPU V100.

## 7. RELEVANCIA PARA LAP

Evaluado y descartado en su configuración completa. Es el estándar de referencia en seguimiento multi-objeto y su mecanismo de asociación por cajas de detección de baja confianza resulta técnicamente sólido, pero produce identificadores persistentes entre fotogramas. Se documenta como referencia del estado del arte en seguimiento; el alcance acordado se limita a estimación de densidad y conteo direccional agregado.
