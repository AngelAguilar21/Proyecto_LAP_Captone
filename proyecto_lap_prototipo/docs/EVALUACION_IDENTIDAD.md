# Evaluación de la identidad entre cámaras

> **Nota (2026-10-05).** Desde esta fecha el proyecto usa un solo motor de identidad (`reid_v2` con reagrupación al cerrar). Los motores `legacy` y `omz`, la alineación estimada (`identityAlign`) y la calibración con personas se retiraron; las cifras de este documento que los mencionan se conservan como registro de la evaluación. Arquitectura vigente: `docs/ARQUITECTURA.md`.

Estado: **fases 0 a 7 implementadas y medidas sobre una sola escena pequeña**. Este documento dice cómo se mide, cuánto
dio el motor actual (`legacy`) y el nuevo (`reid_v2`), qué aporta cada pieza y, sobre todo, **qué no se puede concluir
todavía**.

## Resumen honesto

- En las cámaras demo A y B (4 personas, 24 s), `reid_v2` cuenta 4 personas donde `legacy` cuenta 10, y el IDF1 pasa de
  0,48 a entre 0,73 y 1,00 según la configuración. **Esa mejora está medida sobre los mismos datos con los que se eligieron
  los umbrales y con etiquetas provisionales hechas por el asistente.** Es una demostración de que la idea funciona, no una
  medida de precisión general.
- La mayor ganancia viene de la **geometría**: las calibraciones de A y B del demo no concuerdan (la misma persona queda
  a 2,4 m entre cámaras mientras personas distintas quedan a 0,7 m). Con las calibraciones tal cual, la compuerta física
  rechaza uniones verdaderas. La alineación estimada lo corrige; con calibraciones coherentes el IDF1 llega a 1,00.
- Los umbrales de AeroVision no sirven tal cual con OSNet (IDF1 0,57 frente a 0,73 recalibrados).
- **Por decisión del usuario, las sesiones del monitoreo usan `reid_v2` con recorte en grupos por defecto** (los interruptores
  siguen en la interfaz y un proyecto con `identityEngine: "legacy"` lo conserva). El plan pedía cambiarlo solo con una mejora
  medible y sin empeorar el rendimiento; la mejora existe en el demo pero no está validada fuera de él. Conviene confirmarlo
  con tu propio conjunto etiquetado.
- **Punto ciego de las cifras anteriores:** medían solo los IDs confirmados. En vivo el mapa también dibuja los provisionales
  (`T…`), y ahí `reid_v2` se veía peor de lo que decían las tablas (ver «Segunda escena»). Se corrigió la vista, no la identidad.
- Rendimiento en CPU: el motor nuevo cuesta unos 2 a 5 ms por muestra (frente a menos de 1 ms) y pide hasta 1,5 veces más
  vectores OSNet; el ciclo completo por muestra no cambió de forma distinguible (1,6 s frente a 1,7 s, dominado por YOLO).

## Qué se mide

| Métrica | Qué dice |
|---|---|
| IDF1 | Fracción de detecciones con la identidad correcta tras la mejor asignación persona real a ID del sistema, entre cámaras. 1 es perfecto |
| IDs contados frente a personas reales | IDs que siguieron a alguien al menos 3 cuadros. Con `reid_v2` solo cuentan los IDs confirmados (los provisionales `T…` no cuentan, igual que en los conteos del sistema) |
| Cambios de ID | Veces que una persona real cambia de ID dentro de una cámara |
| IDs por persona | IDs distintos que recibió cada persona en todas las cámaras (1 es lo ideal) |
| Pureza | Fracción de cada ID que pertenece a su persona real dominante |
| Vectores OSNet y ms del motor | Costo: vectores calculados en la sesión y milisegundos del motor por muestra |

IDF1 está en `tools/evaluar_identidad.py` con la asignación húngara de scipy (sin `py-motmetrics`, para no añadir una
dependencia); está cubierto por `tests/test_evaluar_identidad.py`.

## Cómo reproducir (desde `proyecto_lap_prototipo`)

```powershell
# 1. Captura de observaciones (YOLO + ByteTrack + OSNet), un vector OSNet por track no tapado en cada muestra
python tools/capturar_observaciones.py config/ejemplos/demo_camaras_A_B.json --seconds 24 --out data/anotacion/obs_camera_AB.pkl
# 2. Plantilla de etiquetas y hojas de recortes por track; rellena id_real a mano
python tools/preparar_anotacion.py data/anotacion/obs_camera_AB.pkl
# 3. Un motor contra las etiquetas
python tools/evaluar_identidad.py --etiquetas data/anotacion/camera_AB/etiquetas.csv --salida-pkl data/anotacion/obs_camera_AB.pkl --solo-confirmados --cierre
# 4. Comparar encoders y recalibrar umbrales
python tools/barrido_umbrales.py data/anotacion/obs_camera_AB.pkl data/anotacion/camera_AB/etiquetas.csv
# 5. Tabla antes y después con ablaciones
python tools/ablaciones.py data/anotacion/obs_camera_AB.pkl data/anotacion/camera_AB/etiquetas.csv --oraculo B:2.39,0.09
# 6. Prueba de punta a punta en el servidor
..\.venv\Scripts\python.exe tools/prueba_completa.py
```

Para 6 usa el Python de `.venv`: `live_server.py` se relanza en ese entorno y, con rutas con espacios, un Python distinto
termina en una consola vacía. Los recortes de las hojas son personas reales y quedan solo en `data/anotacion/` (fuera de git).

## Línea base: motor `legacy` (Fase 0, antes de portar nada)

Equipo: i5-10210U (8 hilos), 20 GB de RAM, sin GPU NVIDIA. Motor `legacy` con OSNet x0.25 y respaldo de color.

| Comprobación | Resultado |
|---|---|
| `pytest tests` al inicio | 189 pasan |
| `npm run check:lod`, `check:aislamiento`, `check:kpis` | pasan |
| `npm run check:seguimiento` | **falla desde antes**: espera que la prueba del asistente fije P2PNet, pero desde `e979010` usa `detector:'yolo'`. Obsoleta; no se tocó |

Cámaras demo A y B, 24 s, 4 personas, etiquetas provisionales: 10 IDs, IDF1 0,477, 6 cambios de ID, 3,25 IDs por persona,
pureza 0,938. (La primera captura, con otra cadencia de vectores, dio 9 IDs y 0,451.)

## Fase 2: encoder Re-ID en CPU (OSNet frente a yolo26s-reid)

Mismas 91 vistas confiables de 8 tracks (4 personas), recortes del video, CPU de 8 hilos:

| | OSNet x0.25 | yolo26s-reid (AeroVision) |
|---|---|---|
| Entrada / vector | 128x256 / 512 | 448x448 / 512 |
| Coseno misma persona, otra cámara (media) | 0,653 | 0,455 |
| Coseno distinta persona, otra cámara (media) | 0,538 | 0,350 |
| AUC entre cámaras (vistas) · d' · EER | 0,872 · 1,57 · 0,21 | 0,807 · 1,23 · 0,26 |
| Emparejamiento de tracklets, acierto top-1 | 7 de 8 | 8 de 8 |
| Milisegundos por recorte en CPU | 17 a 20 | 130 |
| IDF1 de punta a punta (centro de la meseta de umbrales) | 0,729 | 0,690 |
| Licencia del modelo | la del proyecto | AGPL-3.0 (Ultralytics) |

**Decisión: se queda OSNet.** Separa igual o mejor en esta escena, es 6 a 7 veces más rápido y ya está en el repositorio.
yolo26s-reid acertó 8 de 8 en top-1 frente a 7 de 8, diferencia de un tracklet que con 4 personas es ruido. El encoder es
intercambiable (`reidModel: "yolo26s-reid"`, `src/identity/encoder.py`); la copia local `models/yolo26s-reid.onnx` está
**fuera de git** (`.gitignore`) hasta que decidas qué hacer con su licencia AGPL-3.0.

Hallazgo: con OSNet las parejas de la misma persona entre cámaras no se separan limpiamente de las de personas distintas
(centroides de tracklets 0,82 a 0,87 frente a un máximo de 0,83 en distintas). La apariencia sola no basta en esta escena;
por eso importa la geometría.

### Umbrales

`tools/barrido_umbrales.py` recorre `threshold` y `split_threshold`, mide IDF1 de punta a punta y elige el **centro de la
meseta** (mediana de las combinaciones a menos de 0,02 del máximo), no el máximo. Resultado para OSNet:
`threshold 0,75`, `average_threshold 0,55`, `same_camera_threshold 0,79`, `split_threshold 0,65` (los de AeroVision
eran 0,60 / 0,55 / 0,70 / 0,40, calibrados para otro encoder). Con `split_threshold` 0,40 el IDF1 baja a 0,60 a 0,64:
un corte más permisivo deja pasar mezclas dentro de un grupo. **Calibrados y medidos sobre las mismas 4 personas: la cifra es optimista.**

## Fase 3: geometría calibrada

El motor usa las homografías de AeroTrack (posición del pie de cada caja ya proyectada por el servidor), `links` y
`handoffSeconds` como transiciones, y la cobertura de las referencias del suelo para decidir qué cámaras se solapan. Sin
calibración en una cámara, decide por tiempo y apariencia y lo dice en la interfaz y los reportes.

**Hallazgo clave del demo.** El desfase de B respecto de A al proyectar a la misma persona es un vector casi constante,
(−2,39, −0,09) m con desviación (0,45, 0,11): las dos calibraciones del demo no concuerdan entre sí por unos 2,4 m
(personas distintas quedan a 0,66 m de mediana). La compuerta física rechaza entonces uniones verdaderas. El motor lo
detecta y avisa («parejas con apariencia parecida quedan a X en el plano»).

Tres escenarios, mismo motor y mismos umbrales:

| Geometría | IDs | IDF1 |
|---|---|---|
| Visual y temporal (sin homografías) | 5 de 4 | 0,759 |
| Calibraciones tal cual (no concuerdan) | 6 de 4 | 0,729 |
| Alineación estimada con las propias personas | 5 de 4 | 0,909 (1,000 con el cierre) |
| Oráculo: calibraciones coherentes (techo) | 4 de 4 | 1,000 |

Conclusión: **con calibraciones que no concuerdan, la geometría no mejora frente a visual y temporal (0,729 frente a
0,759); con calibraciones coherentes, sí (hasta 1,00).** El criterio de aceptación del plan («mejora medible frente a
visual_temporal») se cumple solo con la alineación estimada o con calibraciones buenas. La alineación estimada
(`identityAlign`) toma como parejas las uniones rechazadas por distancia que se parecían por apariencia y estima una
traslación (o semejanza acotada) con RANSAC: recuperó (2,44; 0,04) frente a (2,39; 0,09) del oráculo. Es una estimación,
no una medida; sobre 4 personas que caminan juntas puede no funcionar en otro lugar. La solución correcta es recalibrar
con referencias del suelo compartidas entre cámaras.

**Personas marcadas a mano en dos cámaras** (panel «Personas en dos cámaras», en Homografía): la misma idea, pero con parejas
que decide una persona en vez de inferirlas por apariencia. Con 12 parejas tomadas de las etiquetas del demo, la
comprobación estimó un desfase de (−2,43; −0,02) m frente a (−2,39; −0,09) del oráculo y marcó una pareja como sospechosa.
Aplicada en el servidor (vale para `legacy` y `reid_v2`), `legacy` bajó de 8 a 6 IDs en la sesión completa de 33,6 s y
`reid_v2` quedó en 5 identidades, 4 vistas en las dos cámaras, sin aviso de calibraciones que no concuerdan. Una corrida por
motor y sin etiquetas para esa duración: sirve para comprobar que el flujo funciona, no para medir IDF1.

## Fase 4: memoria de apariencia y reagrupación

- **Reagrupación al cerrar** (`src/identity/regroup.py`): primero la evidencia física (juntos en el plano o separados),
  después el Re-ID solo para lo que el asociador ya había unido, y renumeración 1..N por orden de aparición.
  Sin reagrupación, con alineación: 5 IDs, 2 cambios de ID, IDF1 0,909; con ella: 4 IDs, 0 cambios, 1,000. La primera versión
  unió personas distintas que caminaban muy juntas; se añadió una guarda de ambigüedad (la posición no distingue a una
  persona de su vecina en un grupo apretado).
- **Memoria de apariencia** (`src/identity/memory.py`): vectores comparados en RAM, escritura a SQLite en segundo plano,
  retención de 1 a 168 h, purga periódica, borrado inmediato (`POST /api/identity/purge`), nunca imágenes ni rostros, y un
  fallo del disco no detiene el monitoreo. **Solo está probada con personas sintéticas** (reconoce a quien vuelve tras
  minutos, no mezcla a una persona parecida, corrige un ID nuevo que era alguien ya visto, sobrevive a reiniciar, respeta
  la retención). No se midió con personas reales entre sesiones: no hay datos para eso.

## Ablaciones y «antes y después» (cámaras demo A y B)

Etiquetas provisionales, 4 personas, 121 muestras de 0,2 s. «IDs contados» son los confirmados.

| Configuración | IDs contados | IDF1 | Cambios de ID | IDs por persona | Pureza | Vectores OSNet | Motor (ms/muestra) |
|---|---|---|---|---|---|---|---|
| **legacy (antes)** | 10 de 4 | 0,477 | 6 | 3,25 | 0,938 | 189 | 0,85 |
| reid_v2, umbrales de AeroVision sin recalibrar | 6 de 4 | 0,571 | 0 | 2,0 | 0,903 | 282 | 4,0 |
| **reid_v2 por defecto** (umbrales de OSNet, calibraciones tal cual, con cierre) | 6 de 4 | 0,729 | 0 | 1,75 | 0,932 | 288 | 4,4 |
| **reid_v2 + alineación estimada + cierre** | 4 de 4 | 1,000 | 0 | 1,0 | 1,000 | 288 | 4,9 |
| &nbsp;&nbsp;sin compuerta física | 5 de 4 | 0,759 | 0 | 1,5 | 0,918 | 288 | 3,5 |
| &nbsp;&nbsp;sin coincidencia mutua | 4 de 4 | 1,000 | 0 | 1,0 | 1,000 | 288 | 4,1 |
| &nbsp;&nbsp;sin reagrupación al cerrar | 5 de 4 | 0,909 | 2 | 1,5 | 0,970 | 288 | 3,3 |
| &nbsp;&nbsp;sin alineación estimada | 6 de 4 | 0,729 | 0 | 1,75 | 0,932 | 288 | 2,5 |
| &nbsp;&nbsp;sin vistas confiables | 7 de 4 | 0,547 | 0 | 2,0 | 0,932 | 240 | 3,5 |
| &nbsp;&nbsp;sin corte de tracklet | 7 de 4 | 0,595 | 0 | 2,0 | 0,941 | 282 | 2,0 |
| ORÁCULO: legacy con calibraciones coherentes | 5 de 4 | 0,698 | 1 | 1,75 | 0,832 | 189 | 0,5 |
| ORÁCULO: reid_v2 con calibraciones coherentes | 4 de 4 | 1,000 | 0 | 1,0 | 1,000 | 288 | 2,4 |

Qué aporta cada pieza **en esta escena**: las vistas confiables y el corte de tracklet son las que más pesan (quitarlas
baja el IDF1 a 0,55 y 0,60); la compuerta física solo ayuda si las calibraciones concuerdan; el cierre quita dos cambios
de ID; la coincidencia mutua **no aportó nada medible aquí** (no hay dos candidatas en competencia suficiente). El oráculo
muestra que el motor `legacy` también mejora con calibraciones coherentes, pero mucho menos (0,70).

### Rendimiento en CPU (i5-10210U, sin GPU, sesión A+B completa de 33,6 s)

| | legacy | reid_v2 + alineación |
|---|---|---|
| Ciclo del servidor por muestra (mediana / p95) | 1594 / 3188 ms | 1656 / 2313 ms |
| Detección YOLO por cámara (mediana) | 606 ms | 516 ms |
| Motor de identidad por muestra | 0,9 ms | 4 a 5 ms |
| Vectores OSNet por sesión simulada | 189 | 288 (1,5 veces) |

El ciclo está dominado por YOLO a 1280 px: unas 8 veces más lento que el tiempo real en este equipo con ambos motores
(problema de siempre de la CPU, no de la identidad; además OneDrive sincronizaba la carpeta y consumía CPU durante las
mediciones). Las dos corridas no son estrictamente comparables: la de `reid_v2` ya limitaba OSNet a 2 hilos y la de
`legacy` no. La diferencia entre medianas (1594 y 1656 ms) está dentro del ruido de la máquina. Una sola corrida por motor.

### Rendimiento con 7 cámaras de 1920x1080 a 60 fps (mismo i5, `tools/medir_rendimiento.py`)

Un paso de análisis es una muestra de todas las cámaras. Se midió con la sesión completa del servidor sobre el proyecto de
7 cámaras, después de descartar los 2 primeros pasos:

| | un paso tarda | de video | veces más lento |
|---|---|---|---|
| Antes (7 cámaras, 960 px, decodificación por software, un OSNet por cámara) | 6,3 s | 0,2 s | 31 |
| Preciso (0,2 s, 960 px) | 5,1 s (otra corrida: 8,6 s) | 0,2 s | 25 a 43 |
| Equilibrado (0,4 s, 800 px) | 3,6 s | 0,4 s | 8,9 |
| Rápido (0,6 s, 640 px) | 3,4 s | 0,6 s | 5,7 |
| Preciso con 2 cámaras: antes y ahora | 1,52 y 1,11 s | 0,2 s | 7,6 y 5,6 |

Dónde se va el tiempo en Preciso con 7 cámaras: YOLO 3,5 s (68 %), decodificar 0,5 s, OSNet 0,5 s, seguimiento 0,26 s, dibujo y
resto 0,25 s, motor de identidad 0,05 s. Con Equilibrado y Rápido la decodificación crece (0,9 y 1,5 s) porque hay que decodificar
todos los cuadros intermedios. Qué se cambió: decodificación por hardware (D3D11; 10,8 ms por cuadro con software y 1,6 ms con
aceleración, aislado), un solo paso de OSNet para todas las cámaras (con el modelo de lote fijo de 16 cada llamada cuesta un bloque
entero aunque lleve un recorte, 200 a 460 ms según los hilos), tope de 16 recortes por paso, no pedir vectores que el motor
descartaría (solo usa una vista cada `sample_interval_s`; identidad medida igual antes y después) y refrescar a 1 s los tracks
ya establecidos (el intervalo de 8 cuadros del perfil estaba pensado para análisis cuadro a cuadro y con pasos de 12 cuadros todo
track estaba siempre pendiente).

Límites de esta medición: las corridas varían mucho (el mismo caso dio 5,1 y 8,6 s). **OneDrive consumía casi 2 núcleos en
reposo (185 % de un núcleo) y el CPU marcaba 100 %** porque el proyecto vive en su carpeta, con videos de varios GB, grabaciones
y archivos de captura. Las microprobas aisladas (YOLO 2,3 s para 7 cámaras) salen más rápidas que dentro del servidor (3,5 s).
Mover `data/` fuera de OneDrive o pausar la sincronización mientras se analiza es probablemente la mejora más grande y no se
midió. Con 7 cámaras 1080p a 60 fps este equipo no llega al tiempo real en ningún modo; sirve para analizar grabaciones, no
para verlas en vivo.

## Segunda escena: Proyecto01 (dos cámaras, 6 personas, 17 s)

Aparece al revisar capturas del mapa en vivo con `reid_v2`: 8 o 9 puntos para 5 personas. Se capturó el video del proyecto del
usuario (cámara A 1280x720, cámara B 832x464, con la calibración y las parejas marcadas del proyecto) y se etiquetaron 12
tracks en 6 personas **a partir de las hojas de recortes, hechas por el asistente y sin verificar**. Las dos parejas marcadas
por el operador (A1 con B1, A2 con B2) coinciden con esas etiquetas.

Qué se encontró:

- **No es el Re-ID.** Entre cámaras, las parejas verdaderas tienen parecido OSNet de 0,70 a 0,90 y las falsas de 0,43 a 0,64,
  salvo dos parejas falsas en 0,77 y 0,80 que la compuerta física descarta por distancia en el plano (5 m).
  La cámara B ve el pasillo en el borde derecho, con personas pequeñas y tapadas entre sí, lo que limita cualquier encoder.
- **Lo que se veía era la espera.** `reid_v2` no da ID público hasta reunir 5 vistas confiables en 2 s, y las personas que
  caminan juntas casi no dan vistas confiables. Mientras tanto el mapa dibujaba el provisional de cada cámara como un punto
  aparte. Los tracklets de las personas 5 y 6 se unieron entre 3 y 4 s después de aparecer.
- Una pareja verdadera (A3 con B4, parecido 0,70, a 0,33 m en el plano) queda bajo el umbral de OSNet (0,75) y no se une.

| Proyecto01, IDF1 contra etiquetas provisionales | solo IDs confirmados | con provisionales (lo que mostraba el mapa) |
|---|---|---|
| `legacy` | 0,84 | 0,84 |
| `reid_v2` | 0,92 (pureza 1,0) | 0,51 (19 IDs para 6 personas) |
| `reid_v2` con cierre y alineación | 0,99 | 0,99 |

Qué se cambió (solo la vista, no la identidad): un ID provisional que cae en el plano a menos de `geometry_close x
overlap_distance` de otra persona que **otra cámara solapada** ya dibuja se marca `duplicate` y no se dibuja ni se suma en
«Personas en el plano». El conteo, la ocupación y la memoria no cambian (el provisional nunca contaba). Medido como puntos de
más por muestra (ids distintos menos el máximo de tracks de una cámara, que es una cota inferior de personas; no llega a 0
porque hay gente vista por una sola cámara):

| | `legacy` | `reid_v2` antes | `reid_v2` ahora |
|---|---|---|---|
| Proyecto01 | 0,10 | 1,00 | 0,20 |
| Demo A y B | 0,42 | 0,51 | 0,21 |

El costo: personas aún sin confirmar no cuentan (0,5 a 0,9 personas por muestra faltan en ocupación mientras se confirman).
`legacy` no tiene esa espera pero cambia más de ID (pureza 0,82 frente a 1,0).

Lo que se probó y **no** se adoptó, porque el resultado es inestable entre las dos escenas:

| Final con cierre y alineación (IDF1) | Proyecto01 | Demo |
|---|---|---|
| Valores por defecto | 0,99 | 0,98 |
| `geometry_relief` 0,10 (rebaja el umbral si coinciden en el plano) | 0,92 | 0,57 |
| `geometry_relief` 0,10 y confirmación rápida (muestras cada 0,2 s, 3 vistas, 1 s) | 0,92 | 0,98 |

Un solo evento de unión cambia el IDF1 en decenas de puntos con tan pocas personas: es ruido, no una mejora. `geometry_relief`
queda disponible en `identityV2` (por defecto 0, apagado) y con pruebas, pero sin recomendación. La confirmación rápida sola mejora lo que se ve en vivo
en Proyecto01 (IDF1 con provisionales 0,51 a 0,67), no cambia el demo (0,44) y baja el IDF1 de los confirmados del demo (0,73 a 0,57); tampoco se activó.

Esta escena también se usó para ajustar, así que no es una validación independiente.

### Calibrar una cámara solo con personas (Proyecto01)

Con las etiquetas provisionales de Proyecto01 se tomaron los pies de la misma persona vistos a la vez por A y B (130 pares, 6
personas) y se ajustó la homografía de B contra las posiciones que da A (calibrada con puntos del suelo). Por la API nueva
(`/api/person-pairs/calibrate`), con una de cada tres parejas (44):

| | Resultado |
|---|---|
| Parejas que concuerdan | 36 de 44 |
| Error mediano / p90 | 0,14 / 0,26 (unidades del plano, `matchDistance` 1) |
| Dejando una pareja fuera cada vez | 0,16 |
| Con las referencias del suelo medidas de B, esas mismas personas quedan a | 0,45 de la posición según A |

Con personas, B concuerda mejor con A que con sus propias referencias medidas, lo que confirma que las dos calibraciones
medidas no son coherentes entre sí. Pero **no es una medición del suelo**: es coherencia con A, y A tiene su propio error. Y
solo vale donde caminó la gente: las personas ocuparon el 16 % derecho de la imagen de B, y en una referencia del suelo de B
lejos de esa zona la homografía hecha con personas se desvía 2,6 unidades. Las parejas salen de etiquetas del asistente, así
que el emparejamiento de la prueba es más limpio que el que habría con parejas marcadas a mano o por el motor.

### Recorte en grupos (`identityGroupCrops`)

Medido recapturando las dos escenas con el mismo flujo (con y sin relleno) y las mismas etiquetas provisionales. «Vivo» es
el IDF1 incluyendo provisionales, «conf» solo confirmados y «final» tras el cierre con alineación.

| | Proyecto01 vivo / conf / final | faltan | Demo A y B vivo / conf / final | faltan |
|---|---|---|---|---|
| Sin relleno (regla antigua) | 0,51 / 0,92 / 0,99 | 0,53 | 0,43 / 0,72 / 0,97 | 0,94 |
| Con relleno, `min_visible` 0,6 | 0,59 / 0,93 / 0,99 | 0,37 | 0,34 / 0,51 / 0,73 | 0,56 |

Ayuda en Proyecto01 (la cámara B pasa de tener la mitad de las muestras tapadas a aprovecharlas) y reduce las personas sin
confirmar en las dos escenas, pero **empeora el resultado final del demo**: aparecen 6 identidades para 4 personas. Una persona
cuyo tramo del medio solo tiene vistas con relleno no llega al umbral de unión (0,75), pensado para vistas limpias. Descartar
las vistas parciales que no encajan para no cortar tracklets (ya incluido) no lo resolvió. Por decisión del usuario queda activo por defecto en el monitoreo (se puede apagar con el interruptor), con este costo
conocido. Arreglarlo de verdad exige umbrales propios para vistas parciales, y con 4 y 6 personas no hay con qué calibrarlos
sin sobreajustar. Es una medición con dos escenas cortas y etiquetas del asistente.

## Motor `omz`: la gestión de identidades de Open Model Zoo (medido, no es el predeterminado)

Se portó la lógica de `multi_camera_multi_target_tracking_demo/python/mc_tracker/{sct,mct}.py` de Intel Open Model Zoo
(Apache-2.0, cita y licencia en el encabezado de `src/identity/omz.py`) como tercer motor, `identityEngine: "omz"`. Es un demo
que funciona sin calibrar las cámaras: promedio y racimos de apariencia por pista, reenlace de fragmentos y fusión periódica
dentro de cada cámara, y unión voraz uno a uno entre cámaras. Las pistas locales vienen de ByteTrack (el demo enlaza por IoU
a velocidad de video, y a 5 muestras por segundo eso no sirve). Los umbrales del demo son de su propio modelo Re-ID: con OSNet,
personas distintas dan coseno 0,6 a 0,8, así que se recalibraron (distancia 0,5 por (1 - coseno) entre 0,04 y 0,15).

Resultado con las mismas observaciones y etiquetas provisionales que el resto del documento (IDF1; más alto es mejor):

| Conjunto | `legacy` | `reid_v2` en vivo | `reid_v2` con cierre | `omz` (mejor umbral) |
|---|---|---|---|---|
| Demo A/B, 4 personas | 0,47 | 0,70 | 0,73 | 0,65 |
| Proyecto01, 6 personas | 0,84 | 0,59 | **0,99** | 0,45 |

En una captura larga y concurrida (2 cámaras, 175 s, sin etiquetas) `omz` crea 652 identidades, `reid_v2` en vivo 303 y
`reid_v2` con cierre 128 (31 personas). `omz` no mejora a `reid_v2` en ninguno de los tres casos, así que no se usa por defecto
y no está conectado a la interfaz; queda como opción experimental del archivo de configuración.

Lo que sí aparece en la medición: **la reagrupación al cerrar** (la misma que ya usa el servidor al terminar una sesión)
da IDF1 de 0,99 en Proyecto01 y deja 1 ID por persona, frente a 3 a 4 en vivo. Es la estrategia de los sistemas que ganan los
retos de seguimiento multicámara: agrupar los tramos con toda la grabación a la vista. Los ID de la vista en vivo son
provisionales por diseño; los que valen son los de la grabación cerrada. También se midió que, a nivel de pista completa, OSNet
separa bien a las personas en estos conjuntos (AUC de 0,96 a 1,00 entre pistas de la misma persona y de personas distintas),
así que el cuello de botella no está en el modelo sino en decidir con poca evidencia en vivo y en las pistas que el seguidor
parte en escenas concurridas. Con conjuntos de 4 a 6 personas y etiquetas provisionales, nada de esto es una prueba de campo.

## Decisión sobre el valor por defecto

Las sesiones del monitoreo arrancan con `reid_v2` y recorte en grupos **por decisión del usuario**, no porque la evidencia lo
exija: (1) la evidencia son dos escenas cortas (4 y 6 personas); (2) umbrales y reglas se ajustaron mirando esos mismos datos;
(3) las etiquetas son provisionales; (4) no se probó con cámaras reales; (5) el recorte en grupos empeoró el resultado final
del demo. El motor `legacy` sigue disponible con el interruptor «Identidad nueva» o con `identityEngine: "legacy"` en el
proyecto. Para decidir con rigor: etiqueta un conjunto propio
de al menos 10 personas y 2 o 3 cámaras solapadas, corre `barrido_umbrales.py` y `ablaciones.py`, y compara con `legacy`
sobre datos que no se usaron para calibrar.

## Pruebas automáticas

`unittest discover -s tests`: 352 pasan (189 al inicio) en el
`.venv` del proyecto (Python 3.12, numpy 2.0.2, scipy 1.13.1). Pruebas nuevas: núcleo de identidad (incluye la de vistas
confiables portada de AeroVision), memoria de apariencia (SQLite, retención, borrado, fallo del disco), motor y
configuración, alineación, reagrupación y cierre, insights espaciales (incluye los tests de AeroVision portados), servidor
(interruptor, borrado, insights, reportes) y el evaluador. `check:seguimiento` sigue fallando por el motivo de la línea base.

## Límites

- **Una sola escena, 4 personas, 24 s, un solo sitio**, etiquetas provisionales sin verificar por una persona.
  El plan pedía al menos 10 personas y 2 o 3 cámaras: no se cumplió.
- Las cifras con calibración y medición sobre los mismos datos son optimistas. Los umbrales de `reid_v2` no hay motivo
  para creer que sirvan en otro lugar.
- Ropa parecida y oclusiones: ningún método las elimina; en grupos apretados la posición tampoco distingue.
- La alineación estimada necesita personas distinguibles vistas a la vez por dos cámaras; en una prueba de candidatos
  por apariencia a cada instante solo 2 de 44 eran correctas, por eso se usa la pareja tracklet a tracklet.
- La memoria entre sesiones no se midió con personas reales.
- Recall y precisión de detección no son informativos con etiquetas por track (solo anotan lo que el sistema ya produjo).
- No se midió la variabilidad entre ejecuciones ni FPS de punta a punta en GPU.

## Trabajo futuro

- Conjunto etiquetado de verdad (10 o más personas, 2 o 3 cámaras, sitios distintos) y evaluación sin calibrar con los mismos datos.
- Comparar el seguidor local de AeroVision con ByteTrack (el plan lo deja como opción a medir; no se hizo).
- Recalibrar el demo con referencias compartidas entre A y B para quitar la necesidad de alineación.
- Medir la memoria entre sesiones y decidir con asesoría legal (Ley 29733) si se activa por defecto y con qué retención.
