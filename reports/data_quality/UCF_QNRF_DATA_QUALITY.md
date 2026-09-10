# UCF-QNRF — Data Quality Report
## 1. Objetivo

Este documento registra el proceso de auditoría, limpieza y validación aplicado al dataset UCF-QNRF antes de utilizarlo en experimentos de crowd counting.

El objetivo es garantizar la calidad de las anotaciones utilizadas por los modelos, identificar muestras problemáticas y mantener trazabilidad entre el dataset original (RAW) y el dataset procesado.

## 2. Descripción del dataset

**Dataset:** UCF-QNRF
**Tarea principal:** Crowd Counting
**Tipo de anotación:** Point annotations `(x, y)`

El dataset original contiene:

- **Train:** 1,201 imágenes
- **Test:** 334 imágenes
- **Total:** 1,535 imágenes
- **Total de personas anotadas:** 1,251,642

Cada imagen `.jpg` posee un archivo de anotaciones MATLAB `.mat` asociado.

Las coordenadas de las personas se encuentran almacenadas en la variable `annPoints`, cuya estructura es:

`N x 2`

donde cada fila representa las coordenadas:

`[x, y]`

de una persona anotada en la imagen.

## 3. Validación inicial

Antes de utilizar UCF-QNRF en experimentos de modelado, se ejecutó una auditoría inicial sobre imágenes y anotaciones.

Las validaciones incluyeron:

- conteo de imágenes por split;
- conteo de archivos de anotación;
- correspondencia 1:1 entre cada imagen `.jpg` y su archivo `_ann.mat`;
- verificación del formato de `annPoints`;
- lectura de dimensiones de cada imagen;
- detección de imágenes corruptas;
- validación espacial de cada coordenada `(x, y)`;
- identificación de puntos Out-of-Bounds (OOB).

Los conteos obtenidos fueron:

- **Train:** 1,201 imágenes y 1,201 archivos de anotación;
- **Test:** 334 imágenes y 334 archivos de anotación;
- **Total:** 1,535 imágenes;
- **Total de anotaciones:** 1,251,642.

La correspondencia entre nombres de imágenes y archivos de anotación fue verificada sin encontrar muestras faltantes.

### 3.1 Detección de anotaciones fuera de rango

Un punto se considera fuera de rango cuando no cumple:

`0 <= x < image_width`

o:

`0 <= y < image_height`

La auditoría inicial detectó:

- **256 imágenes** con al menos una anotación fuera de los límites;
- **4,256 puntos OOB** en total.

Los puntos fueron clasificados según la magnitud de su desviación respecto al borde de la imagen:

| Severidad | Cantidad de puntos |
|---|---:|
| <= 5 px | 212 |
| > 5 px y <= 50 px | 79 |
| > 50 px | 3,965 |

## 4. Análisis de outliers y cuarentena

Después de detectar las anotaciones fuera de rango, se analizó la distribución de los casos más severos para determinar si se trataba de errores puntuales o de problemas estructurales entre imagen y anotación.

Las imágenes con mayor cantidad de puntos OOB fueron:

| Imagen | Puntos OOB |
|---|---:|
| Train/img_1070.jpg | 2,343 |
| Train/img_1066.jpg | 1,164 |
| Train/img_0191.jpg | 347 |

La inspección visual mostró que, en estos casos, las anotaciones mantenían una estructura coherente de multitud, pero se extendían ampliamente fuera de las dimensiones disponibles de la imagen.

Esto sugiere una desalineación entre la imagen disponible y el sistema de coordenadas utilizado por sus anotaciones, posiblemente asociada a una versión redimensionada, recortada o diferente de la imagen original.

### 4.1 Criterio de cuarentena

No se intentó corregir automáticamente estas muestras, ya que no existe evidencia suficiente para reconstruir con certeza las coordenadas correctas.

Por este motivo, se decidió excluirlas del dataset procesado y mantenerlas intactas en el dataset RAW.

Las muestras puestas en cuarentena fueron:

| Split | Imagen | Motivo |
|---|---|---|
| Train | img_1070.jpg | image_annotation_misalignment |
| Train | img_1066.jpg | image_annotation_misalignment |
| Train | img_0191.jpg | image_annotation_misalignment |

La decisión se registra explícitamente en:

`configs/ucf_qnrf_quarantine.csv`

Las tres muestras representan la mayor concentración de anotaciones severamente fuera de rango detectadas durante la auditoría.

## 5. Estrategia de limpieza

Después de excluir las tres muestras en cuarentena, se volvió a evaluar el conjunto restante.

Los resultados fueron:

- **253 imágenes** con al menos un punto OOB;
- **402 puntos OOB** en total.

Estos casos ya no mostraban una desalineación global entre imagen y anotaciones. En la mayoría de las imágenes, las anotaciones estaban correctamente alineadas y solo existían uno o pocos puntos fuera de los límites.

Por este motivo, se decidió conservar las imágenes y eliminar únicamente las anotaciones espacialmente inválidas.

### 5.1 Regla de validez espacial

Una anotación se considera válida si cumple simultáneamente:

`0 <= x < image_width`

y:

`0 <= y < image_height`

Los puntos que no cumplen estas condiciones son descartados únicamente en el dataset procesado.

### 5.2 Principios aplicados durante la limpieza

La estrategia de limpieza siguió los siguientes criterios:

- el dataset RAW permanece inmutable;
- las muestras en cuarentena no son modificadas ni eliminadas físicamente;
- los puntos OOB no son desplazados hacia el borde de la imagen;
- no se generan coordenadas artificiales;
- solo se eliminan anotaciones que no pueden representar una posición válida dentro de la imagen;
- cada transformación queda registrada en el `manifest.csv`.

## 6. Implementación del preprocessing

La limpieza del dataset fue implementada en:

`src/preprocessing/clean_ucf_qnrf.py`

El script procesa las anotaciones sin modificar el dataset RAW.

El flujo aplicado es:

1. cargar la imagen RAW;
2. obtener sus dimensiones `width` y `height`;
3. cargar `annPoints` desde el archivo `.mat`;
4. evaluar cada punto según los límites espaciales de la imagen;
5. eliminar únicamente los puntos OOB;
6. excluir las muestras registradas en cuarentena;
7. guardar nuevas anotaciones procesadas;
8. registrar el resultado de cada muestra en `manifest.csv`.

### 6.1 Dataset RAW y dataset procesado

El dataset original se conserva sin modificaciones.

Las anotaciones limpias se escriben en un directorio separado de datos procesados.

Esto permite mantener una separación clara entre:

- **RAW:** fuente original e inmutable;
- **PROCESSED:** versión preparada para uso experimental.

Esta separación permite repetir el proceso de limpieza desde cero si cambian las reglas de validación o preprocessing.

### 6.2 Manifest de procesamiento

Durante el preprocessing se genera un archivo:

`manifest.csv`

Este archivo mantiene trazabilidad a nivel de muestra.

Para cada imagen se registran campos como:

- `split`;
- `image`;
- `original_points`;
- `removed_points`;
- `clean_points`;
- `status`.

Los posibles estados son:

- `valid`: la muestra no requirió cambios;
- `cleaned`: se conservaron la imagen y las anotaciones válidas, eliminando únicamente puntos OOB;
- `quarantined`: la muestra fue excluida del dataset procesado por una inconsistencia grave.

## 7. Resultados del preprocessing

Después de aplicar la cuarentena y la limpieza de anotaciones OOB, se obtuvieron los siguientes resultados:

| Métrica | Resultado |
|---|---:|
| Imágenes RAW | 1,535 |
| Imágenes en cuarentena | 3 |
| Muestras utilizables | 1,532 |
| Anotaciones RAW | 1,251,642 |
| Puntos procesados después de cuarentena | 1,244,517 |
| Puntos OOB eliminados | 402 |
| Puntos finales válidos | 1,244,115 |

### 7.1 Interpretación

La diferencia entre las anotaciones RAW y las anotaciones procesadas no corresponde únicamente a los 402 puntos OOB eliminados.

Las tres muestras puestas en cuarentena también dejan de formar parte del conjunto procesado.

Por este motivo:

`1,251,642`

anotaciones RAW

no se convierten directamente en:

`1,251,642 - 402`.

Primero se excluyen las muestras en cuarentena y después se eliminan los puntos OOB restantes.

## 8. Auditoría final del dataset procesado

Después de generar las anotaciones procesadas, se ejecutó una segunda auditoría utilizando:

`src/data_quality/audit_processed_ucf_qnrf.py`

El objetivo de esta validación fue comprobar que las anotaciones del dataset procesado respetaran los límites espaciales de las imágenes RAW correspondientes.

Los resultados obtenidos fueron:

| Métrica | Resultado |
|---|---:|
| Archivos de anotaciones procesados | 1,532 |
| Total de puntos procesados | 1,244,115 |
| Imágenes con puntos OOB | 0 |
| Puntos OOB | 0 |

La auditoría final confirmó que no quedaron anotaciones fuera de los límites de imagen en el dataset procesado.

### 8.1 Estado de validación

El resultado final de la validación espacial es:

**PASS**

Esto indica que, bajo las reglas de calidad definidas para este pipeline, las anotaciones procesadas cumplen las condiciones espaciales esperadas.

## 9. Trazabilidad del pipeline

El procesamiento de UCF-QNRF mantiene una separación explícita entre datos originales y datos procesados.

El flujo implementado es:

RAW Dataset
→ Data Quality Audit
→ Quarantine Rules
→ Preprocessing
→ Processed Annotations
→ Processed Data Quality Audit

La trazabilidad se mantiene mediante:

- `configs/ucf_qnrf_quarantine.csv`
- `manifest.csv`
- `reports/data_quality/ucf_qnrf_summary.json`
- `reports/data_quality/ucf_qnrf_issues.csv`

El dataset RAW permanece sin modificaciones durante todo el proceso.

## 10. Artefactos generados

### Código

- `src/data_quality/audit_ucf_qnrf.py`
- `src/data_quality/audit_processed_ucf_qnrf.py`
- `src/preprocessing/clean_ucf_qnrf.py`

### Configuración

- `configs/ucf_qnrf_quarantine.csv`

### Reportes

- `reports/data_quality/ucf_qnrf_summary.json`
- `reports/data_quality/ucf_qnrf_issues.csv`
- `reports/data_quality/UCF_QNRF_DATA_QUALITY.md`

### Datos procesados

El dataset procesado se mantiene fuera del repositorio Git debido a su tamaño.

El repositorio contiene únicamente el código, configuraciones y reportes necesarios para reproducir el proceso de validación y limpieza.

## 11. Estado final

El pipeline de Data Engineering aplicado a UCF-QNRF completó las siguientes etapas:

- Raw dataset validation: **PASS**
- Image/annotation correspondence: **PASS**
- Annotation format validation: **PASS**
- Quarantine identification: **PASS**
- Annotation preprocessing: **PASS**
- Processed dataset audit: **PASS**
- Out-of-Bounds annotations after preprocessing: **0**

### Resultado

**READY FOR BASELINE MODEL EXPERIMENTS**

El dataset procesado puede utilizarse como entrada para los primeros experimentos de crowd counting, manteniendo trazabilidad respecto al dataset original y a las decisiones de limpieza aplicadas.
