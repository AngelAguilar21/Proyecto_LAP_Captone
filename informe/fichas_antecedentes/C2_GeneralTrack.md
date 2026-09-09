# Ficha C2 — GeneralTrack (CVPR 2024)

## 1. Referencia completa

```bibtex
@InProceedings{Qin_2024_CVPR,
author = {Qin, Zheng and Wang, Le and Zhou, Sanping and Fu, Panpan and Hua, Gang and Tang, Wei},
title = {Towards Generalizable Multi-Object Tracking},
booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
month = {June},
year = {2024},
pages = {18995--19004}
}
```

## 2. Problema y propuesta

GeneralTrack aborda la baja generalización de trackers entre escenarios diferentes. Los autores identifican atributos que cambian fuertemente entre datasets: complejidad de movimiento, variación de posición y forma, densidad, tamaño de objetivos y frame rate.

Los métodos basados en movimiento o apariencia suelen necesitar ajustes por escenario. GeneralTrack evita esa dependencia construyendo relaciones visuales desde puntos finos hasta asociaciones completas de instancia.

## 3. Datasets y licencias

Benchmarks:
- BDD100K
- SportsMOT
- DanceTrack
- MOT17
- MOT20

Incluye pruebas de *domain generalization* sin fine-tuning, por ejemplo BDD100K -> SportsMOT y BDD100K -> DanceTrack.

Métricas: HOTA, MOTA, IDF1, AssA, DetA y mTETA.

**Licencias:** no se detallan de forma consolidada en el paper.

## 4. Técnicas

**Tracking-by-detection con YOLOX.** YOLOX produce las detecciones del cuadro actual.

**Feature Relation Extractor.** Extrae relaciones visuales densas entre dos cuadros.

**4D Correlation Volume.** Compara puntos entre el frame t-1 y el frame t.

**Multi-scale Point-Region Relations.** Convierte relaciones globales en relaciones punto-región a múltiples escalas, permitiendo manejar desplazamientos distintos y varios frame rates.

**Hierarchical Relation Aggregation.** Agrega la información siguiendo la jerarquía `punto -> parte -> instancia`.

El resultado final es una afinidad entre tracklets existentes y detecciones nuevas.

## 5. Figura del pipeline

**Figura 3 del paper:** *Overview of our GeneralTrack*.

Nombre usado en LaTeX:

`generaltrack_metodologia.png`

Muestra: `4D Correlation Volume -> Multi-scale Point-region Relations -> Hierarchical Relation Aggregation`.

## 6. Limitaciones y resultados

Limitación declarada por los autores: el modelo se concentra en relaciones entre dos cuadros consecutivos y no extiende la relación a múltiples cuadros/clips; esto queda como trabajo futuro.

Resultados:
- BDD100K: 57,87 mTETA.
- BDD100K -> SportsMOT sin fine-tuning: 73,8 HOTA frente a 75,0 in-domain.
- BDD100K -> DanceTrack sin fine-tuning: 54,9 HOTA frente a 56,9 in-domain.

## 7. RELEVANCIA PARA LAP

Es uno de los antecedentes más importantes para la transición `dataset público -> cámaras LAP`. Su aporte principal es la generalización de la asociación entre dominios. Puede servir como alternativa avanzada a ByteTrack si se quiere evaluar qué tan robusto es el tracking al cambiar perspectiva, iluminación, densidad y resolución.
