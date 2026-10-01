# Monitoreo integrado sobre el mapa LAP

Contrato actualizado en Fase 8 para la candidata
`jose/automations-main-integration-v2`, base `0b611e0`. Los ejemplos de sesiones
al final son antecedentes reportados de otros ensayos; no son validaciones LIVE
de esta candidata ni recursos garantizados en una instalación nueva.

## Uso habitual

1. Abre **Configuración → Mapa y cámaras**. Selecciona el nivel que corresponde al proyecto; no hay un nivel operativo universal para todos los proyectos.
2. Añade una cámara en ese nivel y usa **Colocar cámara** para situarla. **Centrar cámara seleccionada** permite trabajar con detalle.
3. Arrastra el icono para trasladar su cobertura orientativa. El punto frontal gira y cambia el alcance; los cuadrados ajustan ancho y longitud. La rueda hace zoom dentro del mapa y desplaza la página fuera. La brújula alterna norte arriba y horizontal.
4. Abre **Editar fuente, zona útil y accesos**. Configura un archivo, USB o RTSP una sola vez. **Obtener imagen** permite ajustar el polígono. Los dos análisis comparten esta fuente y la zona útil. Puedes crear zonas interiores con nombre.
5. Si hay una puerta claramente visible, dibuja una línea sobre su umbral y orienta la flecha hacia el interior. Deja área útil a ambos lados para observar la trayectoria antes y después. No dibujes una línea transversal al pasillo y la llames entrada de tienda.
6. Guarda la cámara. Si necesitas posiciones sobre el plano, configura referencias reales del suelo. Abre Vista general e inicia el monitoreo. Se pueden procesar las cámaras activas de todos los niveles o las del nivel seleccionado; al elegir una cámara se procesa solamente esa.
7. En **Videos y resultados**, selecciona análisis y nivel. Reproduce, pausa, reinicia, adelanta o compara cámaras con un reloj compartido. Selecciona detecciones, presencia acumulada o la última estimación especializada. El CSV resume cada cámara por separado.

El editor conserva el borrador al cerrar su ventana. El indicador distingue cambios pendientes y guardados. Cambiar el archivo de una cámara invalida geometría de imagen y referencias anteriores. Durante el procesamiento no se permite cambiar la configuración que está produciendo resultados.

## Qué significa calibrar

La calibración relaciona el **mismo punto físico del suelo** en dos representaciones: el video y el plano. Por ejemplo, un cruce de baldosas visto en la imagen y su ubicación medida en el plano. Se necesitan al menos cuatro correspondencias repartidas, no alineadas. Con ellas se calcula una homografía.

No son cuatro esquinas arbitrarias del encuadre. No deben marcarse cabezas, mostradores, una planta superior o escalones como si pertenecieran al mismo suelo. La homografía es válida para una superficie aproximadamente plana. Verificar algebraicamente cuatro puntos no demuestra precisión: comprueba otros puntos y mide el error en el lugar real. Si cambia la posición, orientación o zoom físico de la cámara, hay que recalibrar.

La posición del icono y su rectángulo orientan al operador; moverlos no recalcula
automáticamente las correspondencias del suelo. En P2PNet directo, posición y
altura sí participan en la corrección de cabeza a suelo; no son sólo decoración.
El video puede ser horizontal, vertical o cuadrado: sigue siendo una matriz
rectangular de píxeles. Un cono dibujado representa cobertura, no el formato
del video ni una calibración automática de la cámara.

## Modelos y responsabilidades

| Componente | Función | Archivo |
|---|---|---|
| YOLO11n preentrenado | Detectar personas y cajas | `src/following/detector.py`, `models/yolo11n.pt` |
| ByteTrackPuntos | Tracker conectado por Engine para mantener trayectorias dentro de cada cámara | `src/tracking.py` |
| P2PNet preentrenado, adaptativo en hybrid | Estimar localizaciones de cabezas y conteo en multitudes cuando AVIE solicita densidad | `src/detection.py`, `src/following/adaptive.py` |
| Análisis integrado | Ocupación, zonas, episodios, calor y coordinación del conteo especializado | `src/following/combined.py` |
| Cruces de acceso | Contar cambios de lado que atraviesan el segmento, con tolerancia a oscilaciones y pérdidas | `src/following/line_counter.py` |
| Flujo del plano | Cruces de zonas y direcciones acumuladas de movimiento | `src/following/flow.py` |
| Asociación entre cámaras | Hipótesis conservadoras por suelo, tiempo, vecindad y apariencia de color | `src/live_core.py` |
| Persistencia y reproducción | Manifest de sesión, muestras temporales y lectura parcial del video original | `src/replay.py` |

El monitoreo integrado solicita `hybrid`: YOLO principal y P2PNet asíncrono bajo
demanda de AVIE. El detector no conserva por sí solo una identidad temporal;
Engine usa `ByteTrackPuntos`, no `YOLO.track()`. La densidad P2PNet no sustituye
IDs ni se suma a YOLO. En este modo el suelo se estima desde los pies de las
cajas. El backend también admite `p2pnet` directo, que sí proyecta cabezas con
corrección geométrica y altura válida; no confundirlo con la señal de densidad.
La prueba de cámara del asistente pide `yolo` a 640. Contratos completos en
[GUIA_SEGUIMIENTO.md](GUIA_SEGUIMIENTO.md).

La reconciliación tardía exige coincidencia mutua sostenida, apariencia compatible, nivel idéntico y tiempos verificados. Rechaza ambigüedad y fusiones que pondrían dos trayectorias de una cámara bajo el mismo ID. Sigue siendo una asociación estimada, no reconocimiento de identidad. No se añadió un modelo profundo de ReID ni caracterización demográfica. Vestimenta similar, oclusión y errores de calibración pueden producir cambios de ID.

Referencias: [ByteTrack, ECCV 2022](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136820001.pdf), [P2PNet, ICCV 2021](https://openaccess.thecvf.com/content/ICCV2021/papers/Song_Rethinking_Counting_and_Localization_in_Crowds_A_Purely_Point-Based_Framework_ICCV_2021_paper.pdf), [documentación oficial de tracking de Ultralytics](https://docs.ultralytics.com/modes/track/). El proyecto mantiene Ultralytics 8.3.203; no depende de que una versión nueva conserve la misma API.

## Métricas y límites de interpretación

- Personas en muestra: observaciones en ese instante, no visitantes únicos del video.
- Máximo y su instante: mayor ocupación observada en las muestras procesadas.
- Promedio: presencia media observada, no suma de todas las detecciones.
- Episodios: intervalos que superan el umbral durante el tiempo configurado.
- Calor: presencia acumulada en el espacio correspondiente. Calor de imagen y calor proyectado al suelo son representaciones distintas.
- Flechas de flujo: direcciones de desplazamiento acumuladas por celda. Las intensidades no son número de visitantes únicos.
- Entradas/salidas: cruces observados del segmento. Reingresar puede generar otro cruce. Perder el seguimiento puede omitir un cruce.

La Vista general conserva el último resultado de cada cámara y su fecha de análisis. El mapa indica la sesión a la que pertenece: resultados de periodos distintos no se presentan como ocupación simultánea. Elegir una cámara filtra sus resultados cartográficos cuando ese análisis los contiene. Los videos de prueba usan tiempo relativo; la fecha de ejecución no es la fecha original de grabación.

## Cartografía

Los cuatro niveles son datos vectoriales locales en `dashboard/public/maps/lap/1.json` hasta `4.json`. `VectorFloor.tsx` los dibuja como SVG y `MapCanvas.tsx` añade cámaras, geometría y resultados. No son una captura de pantalla ni una conexión permanente al mapa oficial. Puedes abrir, por ejemplo, `http://127.0.0.1:5173/maps/lap/3.json`.

La orientación horizontal es una transformación de visualización; no modifica los puntos almacenados ni las calibraciones. Etiquetas y símbolos permanecen legibles. Los embarques usan placas diferenciadas. Se conserva la atribución a Living Map/LAP. La copia local de referencia no otorga por sí misma permiso de redistribución comercial; para el producto con LAP corresponde obtener su cartografía autorizada y actualizada. Consulta también `dashboard/public/maps/lap/README.md`.

## Rendimiento y conexión en vivo

Durante procesamiento estable una captura alimenta cada cámara; reconexiones o
preview son etapas distintas. El seguimiento usa muestras de 0.2 s en archivos.
Frames con ancho mayor a 1280 se reducen antes del detector. El backend YOLO
acepta 320/480/640/960; la UI expone sus opciones. Menor resolución puede perder
personas pequeñas. Los requisitos fijan PyTorch CPU, pero no debe inferirse el
dispositivo sólo del nombre del modo: véase [PRUEBA_LIVE.md](PRUEBA_LIVE.md).

En hybrid, AVIE solicita P2PNet al detectar evidencia densa. El sampler conserva
una muestra pendiente por cámara, reemplazada por la más reciente, y un trabajo
en curso. No hay intervalo configurable efectivo mediante `denseInterval` ni
activación mediante `denseCounting`: ambos campos legacy se eliminan al validar.
Cada resultado especializado conserva su instante y puede ser anterior al frame
actual. No se cambia el detector principal mientras se calcula la densidad.

USB y RTSP conservan el fotograma reciente para evitar una cola creciente de retraso. Se omiten fotogramas cuando la inferencia tarda más que la llegada de video. El panel recibe actualizaciones mientras se procesa; no necesita esperar el final del archivo. La reproducción usa el video original y superpone muestras guardadas: no implica inferencia a los FPS originales.

El servidor actual escucha solo en el equipo local y admite hasta 32 cámaras configuradas. Eso no garantiza capacidad para procesarlas simultáneamente. Para LAP hacen falta fuentes RTSP/substreams o acceso al VMS autorizado, sincronización, calibración real y pruebas de carga. Una instalación aeroportuaria completa requiere dimensionar servidores y distribución del procesamiento. No se verificó una conexión a cámaras reales de LAP ni se promete 30 FPS multicámara en laptops sin GPU.

FPS fuente, procesamiento e inferencia tienen regiones de medición diferentes;
ninguno demuestra por sí solo latencia cámara-pantalla. El protocolo LIVE está
preparado para revalidar la candidata integrada, todavía no ejecutado en Legion;
se distingue del LIVE histórico MacBook reportado en [PRUEBA_LIVE.md](PRUEBA_LIVE.md). Al finalizar se limpia
estado activo, pero se conservan observaciones individuales en replays y
IdentityMemory: [INVENTARIO_PERSISTENCIA.md](INVENTARIO_PERSISTENCIA.md).

## Validación realizada y pendientes

**RESULTADOS HISTÓRICOS REPORTADOS**, no reproducidos por la revisión documental
Fase 8. Las rutas/sesiones dependen de aquel entorno; no cargar ni sustituir
datos del operador para hacerlas aparecer. Evidencia de la candidata actual:
[FASE8_VALIDACION.md](FASE8_VALIDACION.md).

La configuración anterior se respaldó en `config/backups/live-before-unified-20260914-125735.json`. Se reemplazó por CAM-1, CAM-2 y CAM-3 (tienda). Los originales no se eliminaron. Sus posiciones y referencias en LAP son **ilustrativas** y se indican en el panel; no permiten validar asociaciones reales entre cámaras.

- Videos CAM-1/CAM-2 completos: sesión `d0f9accc`, 200 y 182 muestras, hasta 39.8 y 36.2 s. Prueba de funcionamiento con entrada 480; no es evaluación de precisión.
- Ejecución conjunta YOLO y P2PNet: sesión parcial `765ca446`, con estimaciones especializadas de ambas cámaras. Se detuvo para ajustar rendimiento.
- Video de tienda completo: sesión `348683e3`, 394 muestras hasta 78.6 s, máximo observado 9, ningún cruce confirmado de la línea configurada. Se verificaron cruces positivos y negativos con trayectorias controladas en tests, sin inventar entradas en el video.
- Pruebas manuales: alternar orientación, arrastrar cámara sin mover las otras, redimensionar rectángulo, guardar, editar ROI, ajustar/invertir línea y verificar persistencia por API. Rueda dentro del mapa: cambió el viewBox y mantuvo `scrollTop=878.4` en la prueba.
- La suite verifica geometría, máscaras, identidades, pérdida/reaparición, cruces, cola especializada acotada, separación por niveles, persistencia y lectura HTTP Range.

Falta evaluar precisión con anotaciones humanas: conteo por instante, cruces reales, falsos positivos, cambios de ID y error espacial. QNRF puede servir para estudiar conteo de multitudes; no reemplaza videos anotados para evaluar seguimiento y accesos en el dominio del aeropuerto.

## Usabilidad aplicada

Se tomaron como referencia las [heurísticas de Nielsen](https://www.nngroup.com/articles/ten-usability-heuristics/): estado visible de guardado y procesamiento; lenguaje de cámara, puerta y suelo; cancelar dibujos y cerrar el editor sin perder el borrador; navegación común; validación de geometría y bloqueo de cambios durante un análisis; controles gráficos junto a sus instrucciones; zoom contextual; mapa de configuración sin calor; errores dentro del editor y guía de calibración. Esto es una revisión de implementación, no una certificación ni una prueba con usuarios finales.

### Cierre de verificación

La revisión final de tienda con zona «Frente a tienda» es `e7fef254`: 394 muestras, máximo general 9 y máximo del sector 5; cero cruces de puerta confirmados. La configuración deja esa cámara desactivada hasta elegir probarla, y CAM-1/CAM-2 activas. Los análisis siguen disponibles.

Se verificaron los cuatro niveles en la interfaz y el estado vacío de resultados para un nivel sin análisis. Ambos videos quedaron pausados en `currentTime=5` al reiniciar y adelantar cinco segundos; también se comprobó el final independiente del video más corto. El resumen integrado exportó CSV, XLSX y PDF con respuestas HTTP 200. Los cuatro análisis anteriores a la reorganización están conservados en `data/archived-before-map-unification/`.

La suite de aquel ensayo incluía 65 pruebas, además de TypeScript y compilación
de Vite. No es el total actual de la candidata. La prueba funcional no acredita
precisión de conteo, seguimiento ni calibración sobre LAP.

La cuadrícula cartográfica usa celdas de hasta 2 m en planos métricos; no depende de dividir todo el aeropuerto en 24 columnas. Los mapas derivados se recalcularon desde las observaciones guardadas con `tools/rebuild_replay_maps.py`, conservando los archivos previos en `data/replay-map-v1/`. Los conteos y cruces se mantuvieron. Al reiniciar se recuperan los agregados finalizados para reportes, sin encender cámaras ni restaurar personas como si estuvieran en vivo.
