# Ficha C3 — Multi-Camera People Tracking con Anchor-Guided Clustering (CVPR Workshops 2023)

## 1. Referencia completa

```bibtex
@InProceedings{Huang_2023_CVPR,
author = {Huang, Hsiang-Wei and Yang, Cheng-Yen and Jiang, Zhongyu and Kim, Pyong-Kun and Lee, Kyoungoh and Kim, Kwangju and Ramkumar, Samartha and Mullapudi, Chaitanya and Jang, In-Su and Huang, Chung-I and Hwang, Jenq-Neng},
title = {Enhancing Multi-Camera People Tracking With Anchor-Guided Clustering and Spatio-Temporal Consistency ID Re-Assignment},
booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops},
month = {June},
year = {2023},
pages = {5239--5249}
}
```

## 2. Problema y propuesta

El trabajo aborda el seguimiento de una misma persona entre diferentes cámaras. Cambios de perspectiva, iluminación, oclusiones y personas con apariencia similar pueden provocar cambios o duplicaciones de identidad.

La propuesta tiene tres etapas:
1. Tracking dentro de cada cámara.
2. Anchor-Guided Clustering para asignar un ID global.
3. Reasignación de IDs usando consistencia espacio-temporal y geometría.

## 3. Dataset y licencias

Evaluación principal: **AI City Challenge 2023 — Track 1**, con datos multicámara reales y sintéticos.

Métrica principal: IDF1.

**Licencias:** el paper no sustituye la revisión de las condiciones oficiales del AI City Challenge.

## 4. Técnicas

**BoT-SORT + ReID.** Genera trayectorias preliminares por cámara combinando movimiento y apariencia.

**Anchor-Guided Clustering.** Se muestrean features de apariencia y se aplica clustering jerárquico para construir anchors/bancos de características.

**Algoritmo húngaro.** Asigna detecciones/trayectorias a anchors globales.

**Sliding Window Majority Vote.** Estabiliza las decisiones de identidad a lo largo del tiempo.

**Spatio-Temporal Consistency ID Re-Assignment.** Usa pose humana 2D y auto-calibración para reproyectar posiciones a un mapa común y corregir asociaciones incompatibles geométricamente.

## 5. Figura del pipeline

**Figura 2 del paper:** pipeline general del framework multicámara.

Nombre usado en LaTeX:

`huang_mcpt_metodologia.png`

Flujo: `Single-Camera Tracking -> Anchor-Guided Clustering -> Spatio-Temporal Consistency ID Reassignment`.

La Figura 3 es útil como complemento para explicar Anchor-Guided Clustering.

## 6. Limitaciones y resultados

Los autores señalan que los datos sintéticos pueden no capturar completamente la complejidad del mundo real. También persisten dificultades de ReID ante apariencias similares, razón por la cual incorporan restricciones espacio-temporales.

Resultado principal:
- IDF1 = 95,36 %.
- Primer lugar en AI City Challenge 2023 Track 1.

## 7. RELEVANCIA PARA LAP

Es una referencia directa para una futura extensión multicámara: mantener una identidad cuando una persona sale de una cámara y aparece en otra. Podría permitir análisis de flujos entre zonas del terminal, pero exige mayor cuidado en privacidad, persistencia de IDs, sincronización y geometría.
