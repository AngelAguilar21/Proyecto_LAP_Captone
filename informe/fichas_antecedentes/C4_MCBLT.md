# Ficha C4 — MCBLT (ICCV Workshops 2025)

## 1. Referencia completa

```bibtex
@InProceedings{Wang_2025_ICCV,
author = {Wang, Yizhou and Meinhardt, Tim and Cetintas, Orcun and Yang, Cheng-Yen and Pusegaonkar, Sameer and Missaoui, Benjamin and Biswas, Sujit and Tang, Zheng and Leal-Taixe, Laura},
title = {MCBLT: Multi-Camera Multi-Object 3D Tracking in Long Videos},
booktitle = {Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV) Workshops},
month = {October},
year = {2025},
pages = {5304--5313}
}
```

## 2. Problema y propuesta

MCBLT aborda tracking multiobjeto multicámara en secuencias largas. Los métodos tradicionales suelen detectar y trackear en 2D por cámara y asociar después por ReID; eso desaprovecha parte de la información geométrica 3D y puede fallar con oclusiones prolongadas.

MCBLT fusiona información de varias cámaras en una representación Bird's-Eye View (BEV), genera detecciones 3D y realiza seguimiento de largo plazo con una jerarquía de Graph Neural Networks.

## 3. Datasets y licencias

**AICity'24**
- 6 entornos sintéticos.
- 90 escenas: 40 train, 20 val, 30 test.
- 953 cámaras.
- 2.491 personas.
- Más de 100 millones de bounding boxes.
- Secuencias de hasta 24.000 frames.
- Oclusiones de hasta ~2.000 frames.

**WildTrack**
- 7 cámaras sincronizadas.
- Área aproximada 36 x 12 m.
- Resolución 1920 x 1080.
- 400 frames anotados por cámara a 2 FPS.
- 313 identidades.
- 42.721 bounding boxes 2D.

**Licencias:** deben verificarse en las páginas oficiales de los datasets.

## 4. Técnicas

**Early Multi-View Aggregation.** Fusiona las cámaras antes del tracking.

**BEVFormer.** Proyecta las diferentes vistas hacia una representación BEV común usando calibración de cámaras.

**Detección 3D con Transformer/DETR.** Produce cajas tridimensionales en coordenadas globales.

**Asociación 3D-2D + ReID.** Reproyecta detecciones 3D a las vistas 2D para extraer características de apariencia.

**Multi-view ReID.** Combina información de apariencia entre cámaras.

**GNN jerárquica / SUSHI-3D.** Nodos y aristas representan detecciones/trayectorias y posibles asociaciones.

**Global Tracking Block.** Mantiene asociaciones durante videos muy largos y oclusiones prolongadas sin requerir entrenamiento adicional.

## 5. Figura del pipeline

Figura metodológica principal del framework MCBLT.

Nombre usado en LaTeX:

`mcblt_metodologia.png`

Flujo conceptual: `múltiples cámaras -> BEV -> detección 3D -> ReID -> GNN -> tracks globales`.

## 6. Limitaciones y resultados

El método requiere calibración y sincronización de cámaras y tiene una arquitectura mucho más compleja que tracking 2D. Los autores dejan como trabajo futuro estudiar modelos de movimiento 3D más sofisticados.

Resultados:
- AICity'24: 81,22 HOTA.
- WildTrack: 95,6 IDF1.
- Diseñado para secuencias de hasta 24.000 frames y oclusiones de hasta 2.000 frames.

## 7. RELEVANCIA PARA LAP

Es la referencia más avanzada para una fase futura multicámara. Su principal aporte conceptual es representar todas las cámaras en un mismo plano BEV y mantener tracks globales de larga duración. No se recomienda como punto de partida del MVP por sus requerimientos de calibración, sincronización, detección 3D, ReID y GNN.
