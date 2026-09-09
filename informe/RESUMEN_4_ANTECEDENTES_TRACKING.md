# Resumen de los cuatro antecedentes de tracking

**Proyecto:** Estimación de aglomeraciones de personas mediante visión computacional en el Aeropuerto Internacional Jorge Chávez  
**Cliente:** Lima Airport Partners (LAP)  
**Capstone I — Universidad ESAN**

Los cuatro trabajos revisados forman una progresión desde tracking temporal dentro de una cámara hasta tracking multicámara 3D de larga duración.

## 1. MOTRv2 — CVPR 2023

Combina YOLOX con MOTR. YOLOX aporta detecciones robustas y las convierte en *proposal queries*, mientras las *track queries* mantienen las identidades entre cuadros. Es una referencia para tracking avanzado dentro de una sola cámara.

**Aporte para LAP:** trayectorias, cruces de línea, dirección y permanencia por zona.

## 2. GeneralTrack — CVPR 2024

Busca que el tracker generalice mejor entre escenarios distintos. Construye relaciones visuales desde puntos hasta instancias mediante volumen de correlación 4D, relaciones multiescala y agregación jerárquica.

**Aporte para LAP:** estudiar la transición desde datasets públicos hacia cámaras reales del aeropuerto y medir la brecha de dominio.

## 3. Huang et al. — CVPR Workshops 2023

Extiende el tracking a múltiples cámaras. Usa BoT-SORT, ReID, Anchor-Guided Clustering, algoritmo húngaro y consistencia espacio-temporal para mantener un ID global.

**Aporte para LAP:** reconstruir flujo entre diferentes zonas/cámaras del terminal.

## 4. MCBLT — ICCV Workshops 2025

Fusiona múltiples cámaras en Bird's-Eye View, genera detecciones 3D y realiza tracking con GNNs jerárquicas y un bloque global de largo plazo.

**Aporte para LAP:** referencia para una futura infraestructura multicámara 3D de gran escala.

## Cómo se articulan

`MOTRv2 -> GeneralTrack -> Huang MCPT -> MCBLT`

- **MOTRv2:** tracking single-camera con detector + Transformer.
- **GeneralTrack:** robustez/generalización a escenarios nuevos.
- **Huang:** continuidad de identidad entre cámaras.
- **MCBLT:** tracking multicámara en coordenadas 3D y videos muy largos.

En relación con el alcance actual, los dos primeros son más cercanos a una posible integración con el módulo de aglomeraciones. Los dos últimos representan extensiones futuras si LAP dispone de varias cámaras sincronizadas y se acuerda un alcance de tracking multicámara.

La combinación conceptual más viable para un prototipo sería mantener el conteo/localización de aglomeraciones como núcleo y añadir tracking temporal limitado dentro de una cámara. De ese modo el sistema podría responder tanto **cuántas personas hay y dónde se concentran** como **cómo se desplaza el flujo**, sin asumir desde el inicio la complejidad de una solución multicámara completa.
