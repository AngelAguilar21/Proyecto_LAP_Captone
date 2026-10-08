# Arquitectura de AeroTrack

AeroTrack analiza video de cámaras fijas para medir afluencia y aglomeraciones, seguir a las personas en cada cámara y
reconocer a la misma persona cuando pasa de una cámara a otra. Asigna IDs anónimos: no identifica a nadie, no usa rostros y
no guarda imágenes de personas.

## El flujo, de la imagen al plano

| Etapa | Qué hace | Código |
|---|---|---|
| 1. Detección | YOLO11n (preentrenado en COCO) encuentra a las personas y su caja en cada muestra de video | `src/following/detector.py`, `models/yolo11n.pt` |
| 2. Zona útil | Se descartan detecciones fuera del suelo útil de la imagen (espejos, pantallas, otros pisos) | `src/spatial_scope.py` |
| 3. Seguimiento por cámara | BoT-SORT sobre puntos de pies, con Kalman, posición, solapamiento de caja y apariencia, une las detecciones de una cámara en trayectorias con ID local | `src/tracking.py` |
| 4. Posición en el plano | El centro inferior de la caja (los pies) se proyecta con la homografía de puntos del suelo | `src/live_core.py` (`calibration`, `ground_point`) |
| 5. Apariencia | OSNet calcula un vector de 512 valores por vista confiable de cada persona | `src/following/reid.py`, `models/osnet.onnx` |
| 6. Identidad entre cámaras | Tramos (tracklets) por cámara, unidos por apariencia y por coherencia de tiempo y posición, solo entre cámaras relacionadas | `src/identity/` |
| 7. Cierre de sesión | Con la grabación completa a la vista se reagrupan los tramos y la grabación queda con IDs finales 1..N | `src/identity/regroup.py`, `src/identity/closing.py` |
| 8. Analítica | Ocupación y aglomeraciones, presencia acumulada, flujos, cruces de líneas de acceso, insights comerciales | `src/live_core.py` (`Occupancy`), `src/following/`, `src/insights/` |

`live_server.py` orquesta las fuentes (archivos, USB, RTSP), las etapas y la API que usa la interfaz (`dashboard/`).

## En qué se apoya

El diseño sigue el esquema que comparten los sistemas de referencia de seguimiento multicámara de personas:

- **Seguimiento por detección en cada cámara** con BoT-SORT: asociar también las detecciones de baja confianza conserva el
  ID en oclusiones breves ([Zhang et al., ECCV 2022](https://arxiv.org/abs/2110.06864)).
- **Re-identificación con OSNet**, un modelo ligero pensado para Re-ID de personas
  ([Zhou et al., ICCV 2019](https://arxiv.org/abs/1905.00953)), con un vector por tramo formado por varias vistas.
- **Unir tramos con apariencia y restricciones de espacio y tiempo, y refinar con la secuencia completa.** Es el esquema de
  DeepCC ([Ristani y Tomasi, CVPR 2018](https://arxiv.org/abs/1803.10859)) y del primer lugar del AI City Challenge 2023 en
  seguimiento multicámara de personas (IDF1 95 %): tracker por cámara, OSNet, agrupamiento de tramos, homografía hecha con
  6 a 12 puntos marcados a mano y reasignación por coherencia espacio-temporal ([Huang et al., 2023](https://arxiv.org/abs/2304.09471)).
- **El punto del suelo es el centro inferior de la caja**, proyectado con una homografía del plano del suelo; es lo que usan
  esos mismos trabajos cuando no hay detección de tobillos.

Lo que **no** se adoptó, y por qué:

- **Modelos de enlace entre cámaras aprendidos** (zonas de entrada y salida y tiempos de tránsito,
  [Hsu et al., 2020](https://arxiv.org/abs/2008.09785)): están pensados para redes de cámaras sin solape y necesitan muchas
  trayectorias para aprenderse. Con escenas de pocas personas no se aprenden de forma fiable. Aquí basta con saber qué
  cámaras están relacionadas y el tiempo máximo de paso (`handoffSeconds`).
- **Detección multivista con calibración completa** (MVDet, MvCHM): exige cámaras sincronizadas y calibradas con
  intrínsecos y extrínsecos, y datos etiquetados para entrenar. Ver `docs/REFERENCIAS_MULTICAMARA.md`.

## Cómo se relacionan las cámaras

Dos cámaras quedan **relacionadas** cuando el usuario marca a la misma persona en ambas (sus pies, en el instante de cada
video) al menos 4 veces (`live_core.related_cameras`). Nada se deduce de la posición de las cámaras en el plano. Esas mismas
parejas sirven para dos cosas más:

1. **Desfase de tiempo** entre los dos videos: mediana robusta de las diferencias de instante. Si es consistente se guarda en
   `syncOffset` y se aplica al leer los videos; las cámaras quedan sincronizadas (`clocksVerified`).
2. **Concordancia de las homografías**: si las dos cámaras tienen puntos del suelo, se mide a qué distancia queda en el plano
   la misma persona vista a la vez. Es un diagnóstico; si no concuerdan hay que recalibrar con puntos del plano compartidos.
   No se corrige con una alineación estimada.

Sin relación, cada cámara conserva sus propios IDs. Los `links` de un proyecto importado también cuentan como relación.

## Identidad entre cámaras (`src/identity/`)

1. Cada ID local de ByteTrack forma **tramos**: segmentos continuos (hueco máximo de 2 s). Si el Re-ID ve a otra persona dentro
   del mismo ID local, el tramo se parte.
2. Solo las **vistas confiables** calculan vector: buena confianza, altura suficiente, lejos del borde y sin otra persona tapando.
   Con «Recorte en grupos» se tapa la zona cubierta por otra persona en vez de descartar la vista.
3. Dos tramos solo se unen si es **físicamente posible**: cámaras relacionadas, dentro de `handoffSeconds` y, con homografía,
   posición, dirección y velocidad coherentes en el plano. Sin posición se decide por tiempo y apariencia y la interfaz lo dice.
4. La unión exige **coincidencia mutua** y rechaza la ambigüedad (dos candidatas casi igual de parecidas).
5. Una persona recién vista lleva un ID **provisional** `T…` hasta reunir 5 vistas durante 2 s; los provisionales no cuentan en
   ocupación ni métricas.
6. Al cerrar la sesión se **reagrupa con la sesión completa a la vista** y la grabación queda con `P00001`..`P0000N`. Las pasadas
   breves quedan sin número. Primero se juntan los tramos que coinciden en el plano y se respeta lo decidido en vivo; después un
   **agrupamiento jerárquico por apariencia OSNet** (enlace promedio, umbral `closing_threshold`) junta los grupos más parecidos,
   con una sola restricción dura: nunca juntar dos que choquen (la misma cámara a la vez, o dos cámaras a la vez en lugares muy
   distintos del plano). Es el esquema de DeepCC y del AI City Challenge 2023; aquí la apariencia manda y el plano solo veta.

Los umbrales de OSNet están en `src/identity/engine.py` (`UMBRALES_OSNET`). Se eligieron con dos escenas pequeñas
(`docs/EVALUACION_IDENTIDAD.md`); `tools/barrido_umbrales.py` los recalcula con etiquetas propias.

## Videos en el navegador

Chrome no reproduce AVI ni MKV. Los análisis leen siempre el archivo original; para «Videos y resultados» se crea una copia VP8
`.webm` junto al original (`<carpeta>/web/<nombre>.webm`) con el encoder que ya trae OpenCV (`src/video_web.py`). La conversión
corre en segundo plano al cargar el video y al terminar un análisis (así no le quita CPU al análisis); si todavía no está lista, la reproducción avisa y reintenta.
Cada copia pesa varias veces el AVI original (unos 77 MB para 2 minutos a 360x288).

## Calibración

La homografía relaciona el **mismo punto físico del suelo** en el video y en el plano: al menos 4 correspondencias, mejor 6 a 8
repartidas por donde camina la gente. Con 5 o más, RANSAC descarta clics inconsistentes y se informa el error dejando una
referencia fuera cada vez. La homografía solo se usa dentro de la región que cubren sus referencias (ampliada un 50 %): fuera
de ella la persona sigue en el video pero sin punto en el plano. Si cambia el zoom o la orientación de la cámara, hay que
recalibrar. Los puntos del suelo son opcionales: sin ellos la cámara cuenta en la imagen y asocia por tiempo y apariencia.

## Qué se guarda y privacidad

- **Memoria de apariencia** (`data/identidad/<proyecto>_apariencia.sqlite`): por persona anónima, la suma de sus vectores
  OSNet, el prototipo de cada tramo, en qué cámaras y cuándo. Retención de 1 a 168 h (`identityRetentionHours`, 24 por
  defecto), purga periódica y borrado inmediato (`POST /api/identity/purge`). Se desactiva con `appearanceMemory: false`.
- **Grabaciones** (`data/replays/<sesión>/`): posiciones por ID de sesión, el resumen de la reagrupación y los insights.
- **No se guardan** rostros, imágenes, recortes, nombres, género ni edad. AeroTrack no infiere características demográficas.
- Un ID anónimo y un vector de apariencia pueden ser datos personales (Ley 29733 en Perú): el uso con cámaras reales de LAP
  requiere revisión legal y autorización de LAP.

## Qué se retiró el 2026-10-05 y por qué

| Retirado | Motivo |
|---|---|
| P2PNet (conteo de cabezas en multitudes), su submódulo, AVIE y la capa de densidad | Fuera del alcance acordado. La ocupación y las aglomeraciones salen del seguimiento con YOLO |
| Motores de identidad `legacy` y `omz` | Un solo motor. `omz` medía peor que `reid_v2` y `legacy` era la línea base anterior |
| Alineación estimada entre cámaras, calibración con personas y plano relativo | Parches para homografías que no concuerdan; lo correcto es recalibrar con puntos del suelo compartidos |
| Zonas de conexión automáticas, relaciones numeradas y límites aprendidos | Las cámaras se relacionan solo por una acción explícita del usuario: marcar a la misma persona |
| Alcance o cono de cobertura de cada cámara | Descartaba detecciones válidas; la zona útil de la imagen y el límite del plano bastan |
| Memoria temporal duplicada (`identity_memory.py`) | Guardaba ropa y medidas por ID; la memoria de apariencia ya cubre el reconocimiento |
| Encoder alternativo `yolo26s-reid` | Más lento en CPU, sin mejora medida y con licencia AGPL |
| Prototipo histórico (`main.py`, `nodes.py`, `cross_camera.py`, …) y dashboard antiguo | La aplicación no los usaba |

Los proyectos guardados con esos campos se abren igual: al validar la configuración se eliminan. Una cámara calibrada con
personas vuelve a sus puntos del suelo medidos.

## Límites conocidos

- Ropa parecida, grupos apretados y oclusiones largas siguen produciendo cambios de ID; ningún método los elimina.
- Los umbrales se ajustaron con escenas de 4 y 6 personas y etiquetas provisionales: hace falta un conjunto propio etiquetado
  (10 o más personas, 2 o 3 cámaras) para medir IDF1 con datos que no se usaron para ajustar.
- En CPU, YOLO domina el tiempo: con varias cámaras 1080p el análisis va más lento que el video. Sirve para grabaciones; el
  tiempo real con muchas cámaras exige GPU o dimensionar servidores.
- La ocupación sin P2PNet depende de que YOLO vea a las personas: en multitudes muy densas subestima.
