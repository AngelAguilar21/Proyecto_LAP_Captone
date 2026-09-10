# Antecedentes del proyecto

Este documento reúne antecedentes académicos relevantes para el desarrollo del proyecto de Computer Vision y crowd counting aplicado al contexto de Lima Airport Partners (LAP).

La selección incluye trabajos sobre:

- crowd counting;
- estimación mediante mapas de densidad;
- localización basada en puntos;
- datasets de multitudes densas;
- metodologías relevantes para la selección y preparación de datos.

## Resumen de antecedentes

| Antecedente | Venue | Año | Aporte principal |
|---|---|---:|---|
| CSRNet | CVPR | 2018 | Crowd counting mediante mapas de densidad y convoluciones dilatadas |
| Composition Loss / UCF-QNRF | ECCV | 2018 | Introduce UCF-QNRF y aborda conteo, mapas de densidad y localización |
| P2PNet | ICCV | 2021 | Crowd counting y localización mediante predicción directa de puntos |
| Trabajo CVPR 2025 | CVPR | 2025 | Pendiente de identificar y documentar formalmente |

---

## 1. CSRNet

**Título:** CSRNet: Dilated Convolutional Neural Networks for Understanding the Highly Congested Scenes
**Autores:** Yuhong Li, Xiaofan Zhang, Deming Chen
**Venue:** IEEE Conference on Computer Vision and Pattern Recognition (CVPR)
**Año:** 2018

### Problema

CSRNet aborda el conteo de personas en escenas altamente congestionadas, donde la detección individual puede ser difícil debido a oclusiones, variación de escala y alta densidad.

### Método

La arquitectura utiliza:

- una CNN frontal para extracción de características;
- una CNN posterior basada en convoluciones dilatadas;
- generación de mapas de densidad para estimar el número de personas.

Las convoluciones dilatadas permiten aumentar el campo receptivo sin recurrir a operaciones adicionales de pooling.

### Relación con el proyecto

CSRNet representa un antecedente relevante porque permite estudiar el enfoque clásico de crowd counting basado en mapas de densidad.

También sirve como referencia para comparar este paradigma con métodos posteriores basados directamente en anotaciones de puntos.

---

## 2. Composition Loss y UCF-QNRF

**Título:** Composition Loss for Counting, Density Map Estimation and Localization in Dense Crowds
**Autores:** Haroon Idrees, Muhmmad Tayyab, Kishan Athrey, Dong Zhang, Somaya Al-Maadeed, Nasir Rajpoot, Mubarak Shah
**Venue:** European Conference on Computer Vision (ECCV)
**Año:** 2018

### Problema

El trabajo estudia conjuntamente tres tareas relacionadas:

- crowd counting;
- estimación de mapas de densidad;
- localización de personas en multitudes densas.

### Dataset UCF-QNRF

El paper introduce el dataset **UCF-QNRF**, utilizado actualmente en el pipeline de Data Engineering del proyecto.

El dataset contiene:

- 1,535 imágenes;
- 1,251,642 personas anotadas;
- anotaciones mediante puntos;
- escenas con fuertes variaciones de densidad y resolución.

### Relación con el proyecto

UCF-QNRF constituye un antecedente central para la etapa de Data Engineering debido a que:

- proporciona anotaciones puntuales compatibles con tareas de crowd counting;
- permite estudiar escenas con alta densidad y oclusión;
- puede utilizarse para evaluar métodos de conteo y localización;
- sirve como uno de los primeros datasets públicos utilizados antes de validar posteriormente con datos proporcionados por LAP.

El proceso de auditoría, limpieza y validación desarrollado en este repositorio sobre UCF-QNRF corresponde a trabajo propio del proyecto y se documenta por separado en:

`reports/data_quality/UCF_QNRF_DATA_QUALITY.md`

---

## 3. P2PNet

**Título:** Rethinking Counting and Localization in Crowds: A Purely Point-Based Framework
**Autores:** Qingyu Song, Changan Wang, Zhengkai Jiang, Yabiao Wang, Ying Tai, Chengjie Wang, Jilin Li, Feiyue Huang, Yang Wu
**Venue:** IEEE/CVF International Conference on Computer Vision (ICCV)
**Año:** 2021

### Problema

P2PNet plantea que la localización individual mediante puntos puede ser más directa que utilizar representaciones intermedias como mapas de densidad o pseudo bounding boxes.

### Método

El modelo:

- predice directamente un conjunto de puntos asociados a personas;
- realiza conjuntamente conteo y localización;
- utiliza matching uno a uno mediante el algoritmo húngaro para asociar predicciones y anotaciones.

### Relación con el proyecto

P2PNet es particularmente relevante porque UCF-QNRF ya proporciona anotaciones en forma de puntos `(x, y)`.

Esto permite evaluar un enfoque que trabaja más directamente con el tipo de anotación disponible, evitando la necesidad de transformar obligatoriamente los puntos en bounding boxes.

También resulta conceptualmente compatible con un escenario donde se busca estimar presencia y afluencia por regiones de interés sin necesidad de realizar tracking persistente.

---

## 4. Antecedente CVPR 2025

El equipo ha identificado un trabajo de CVPR 2025 como posible antecedente reciente.

La referencia exacta todavía debe confirmarse antes de documentar:

- título;
- autores;
- arquitectura;
- datasets;
- métricas;
- resultados;
- ventajas y limitaciones;
- relación con el escenario LAP.

No se incluirá información adicional hasta identificar formalmente el paper utilizado por el equipo.
