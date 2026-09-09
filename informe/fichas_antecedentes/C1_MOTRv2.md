# Ficha C1 — MOTRv2 (CVPR 2023)

## 1. Referencia completa

```bibtex
@InProceedings{Zhang_2023_CVPR,
author = {Zhang, Yuang and Wang, Tiancai and Zhang, Xiangyu},
title = {MOTRv2: Bootstrapping End-to-End Multi-Object Tracking by Pretrained Object Detectors},
booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
month = {June},
year = {2023},
pages = {22056--22065}
}
```

## 2. Problema y propuesta

MOTRv2 aborda una debilidad de los trackers end-to-end basados en Transformers: su detección puede ser inferior a la de métodos tracking-by-detection. Los autores atribuyen parte del problema al conflicto de aprender detección y asociación simultáneamente en el mismo decoder.

La propuesta incorpora un detector YOLOX preentrenado para generar propuestas de objetos. Esas detecciones se transforman en *proposal queries*, mientras que las *track queries* provenientes de cuadros anteriores representan los objetos ya seguidos. El Transformer MOTR combina ambas y actualiza cajas e identidades cuadro a cuadro.

## 3. Datasets y licencias

- DanceTrack: 100 videos (40 train, 25 val, 35 test), usado como benchmark principal de movimientos complejos.
- MOT17: 7 secuencias de entrenamiento y 7 de prueba.
- BDD100K: 1400 secuencias de entrenamiento y 200 de validación, con 8 clases.
- MOT20: usado en comparación adicional.
- CrowdHuman: usado para entrenamiento conjunto/pseudo-clips.

Métricas: HOTA, DetA, AssA, MOTA, IDF1, mMOTA y mIDF1.

**Licencias:** el paper no resume las licencias de todos los datasets; deben verificarse en sus fuentes oficiales.

## 4. Técnicas

**YOLOX.** Genera bounding boxes con posición, tamaño y score. Para maximizar recall, el paper conserva propuestas con score > 0,05.

**MOTR / Deformable DETR.** La parte de tracking usa MOTR con backbone ResNet-50.

**Proposal Queries.** Cada detección de YOLOX se convierte en una query anclada espacialmente. El número de queries depende del número de propuestas del detector.

**Track Queries.** Mantienen la representación de las instancias ya observadas y se propagan entre cuadros.

**Entrenamiento.** Se usan 8 GPU; en BDD100K YOLOX se entrena durante 16 épocas. Para DanceTrack se aplica aumentación HSV. Durante training se propagan track queries con confianza > 0,5 para introducir casos semejantes a falsos positivos y negativos de inferencia.

## 5. Figura del pipeline

**Figura 2 del paper:** *The overall architecture of MOTRv2*.

Nombre usado en LaTeX:

`motrv2_metodologia.png`

Flujo: `YOLOX -> proposal queries + track queries -> MOTR -> predicciones -> siguiente cuadro`.

## 6. Limitaciones y resultados

El paper no tiene una sección formal de limitaciones. La arquitectura depende de la calidad de YOLOX y es más costosa que trackers clásicos. Su mejor resultado en DanceTrack requiere asociación adicional, entrenamiento ampliado y ensemble de 4 modelos.

Resultados:
- DanceTrack: 69,9 HOTA en la configuración principal.
- DanceTrack: 73,4 HOTA con asociación extra + validation training + ensemble.
- Mejora de 14,8 puntos HOTA frente a OC-SORT.
- BDD100K: 43,6 mMOTA y 56,5 mIDF1.

## 7. RELEVANCIA PARA LAP

Es una referencia útil si el proyecto combina aglomeraciones con tracking temporal dentro de una cámara. Puede permitir trayectorias, cruces de línea, dirección y permanencia por zona. Su principal valor es comparar un enfoque Transformer avanzado frente a alternativas más simples como ByteTrack.
