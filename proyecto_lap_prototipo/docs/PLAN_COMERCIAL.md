# Negocios y análisis comercial

Rama: `comercial-negocios-ventas`. Todo se prueba en **Proyecto principal**.

## A. Negocios y accesos

Las tiendas y restaurantes del plano se registran automáticamente. Los servicios y salas no son tiendas. La lista se filtra por nivel y nombre, tiene desplazamiento propio y permite seleccionar otro negocio. Si hay cambios pendientes, ofrece guardarlos o descartarlos. Los iconos oficiales son seleccionables en esta pantalla; no se dibujan círculos adicionales.

Para cambiar un nombre, selecciona el negocio, edita su nombre y pulsa **Guardar negocio**. Para añadir un local que falta, usa **Añadir negocio**, escribe su nombre y marca su posición. El marcador propio se puede arrastrar. Su posición identifica al local: no representa una puerta ni un radio de conteo. Cerrar un negocio conserva su historial.

Para medir entradas, selecciona la cámara y sus líneas de acceso. Puedes crear y editar la línea sobre la primera imagen desde esta pantalla o desde **Configurar proyecto → cámara → Zona útil → Accesos de negocios**. Elige el negocio y el sentido de entrada. Una tienda puede tener varias puertas, incluso en distintas cámaras. Guarda antes de iniciar un nuevo monitoreo si cambiaste la geometría.

## B. Ventas CSV

En **Ventas y análisis → Ventas CSV**, descarga la plantilla, completa negocio_id, fecha (AAAA-MM-DD), hora (0 a 23) y monto en soles. negocio_nombre es una referencia legible; el vínculo usa negocio_id. Moneda y número de transacciones son opcionales. El sistema admite coma o punto y coma, valida todas las filas antes de importar y rechaza negocios desconocidos, importes inválidos y duplicados sin sobrescribir registros existentes. Solo el operador importa.

El selector **Origen** separa pruebas de datos reales. No mezcles registros sintéticos con ventas de una tienda.

## C. Proyección de ventas

Se relacionan entradas con ventas de al menos tres días anteriores del mismo día de semana y hora. Cada día necesita una franja de tráfico prácticamente completa (55 minutos como mínimo). La mediana de ingreso por entrada se multiplica por las entradas de la hora consultada. Se muestra el número de días y el rango histórico observado, que no es un intervalo estadístico de confianza. No se confunde ingreso por entrada con ticket por compra. Si falta historial, no se inventa una venta.

Los videos necesitan **Fecha de las grabaciones**, con zona horaria, para relacionarse con ventas civiles. Las fuentes en vivo usan el inicio de la sesión. Repetir el mismo análisis no suma sus entradas repetidas: se usa la sesión de mayor cobertura de la franja.

## D. Aglomeraciones y ventas

Los episodios guardados de ocupación se vinculan mediante la zona asociada al negocio; si no hay vínculo explícito y la cámara tiene un único negocio, se usa ese negocio. No se asigna un incidente arbitrariamente entre varios locales. Se compara la venta de la hora del incidente con horas y días de semana históricos equivalentes. Una venta horaria no permite medir la venta exacta de un incidente de segundos. Un incidente que cruza varias horas no produce un porcentaje engañoso. La pantalla advierte muestras pequeñas y ausencia de causalidad. **Exportar CSV** desde esta pestaña exporta los incidentes y su comparación.

## E. Señal de objeto nuevo — experimental

Activa **Evaluar objetos nuevos al salir (experimental)** en los accesos de la cámara. El modelo preentrenado YOLO11n detecta personas, mochilas, carteras y maletas; ByteTrack conserva identidades mientras siguen visibles. Se compara la apariencia de ropa de entrada y salida mediante histogramas y similitud coseno, con umbral conservador, rechazo de candidatos ambiguos, caducidad y asociación de una sola visita. No se entrenó un modelo ni se utiliza OSNet en esta implementación. Un bolso tipo cartera no demuestra que sea una bolsa de compras.

Se reportan salidas emparejadas, sin emparejar, cobertura y objetos nuevos. La galería de apariencia está en memoria y caduca; se guardan muestras agregadas, no fotografías de personas. La inferencia opcional tiene un intervalo mínimo de medio segundo y añade trabajo al equipo. Falta evaluar precisión con videos reales de entradas y salidas; una simulación no valida reidentificación ni compras. Esta fase ofrece una señal experimental utilizable, no un censo de compradores.

## Prueba guardada y cómo verla

1. Reinicia con `iniciar_sistema.cmd` desde la raíz, si el servidor estaba abierto antes de estos cambios.
2. Entra como operador y mantén **Proyecto principal**.
3. Abre **Ventas y análisis → Ver prueba guardada**. Selecciona las pestañas para ver ventas, proyección, incidente y señal experimental.
4. La simulación de accesos del 27/09/2026 está en **Videos y resultados**, sesión `e28d5219`. Registra 2 entradas y 2 salidas para El Bodegón. No contiene video real porque es una simulación.
5. En los datos de prueba de las 22:00 hay una venta de S/50 y proyección de S/42.50 con cuatro días históricos sintéticos. El incidente y las muestras de objetos son datos sintéticos explícitos; verifican persistencia y cálculo, no precisión del modelo.

CSV y resumen: `data/commercial-tests/ventas_prueba_comercial.csv` y `validacion.json`. Reproducciones: `data/replays/<sesión>/manifest.json` y `samples.jsonl`. Negocios, ventas, tráfico, incidentes y muestras comerciales: SQLite por proyecto, `config/projects/<id>.negocios.sqlite`. PostgreSQL/PostGIS pertenece a una etapa posterior.

## Verificación

131 pruebas automatizadas pasan, incluidos vínculos de negocios, importación atómica, duplicados, separación de orígenes, proyección con historial insuficiente, fechas de grabación, comparación horaria y emparejamientos ambiguos/caducados. TypeScript y compilación de producción pasan. Se comprobó la selección de negocios y las pestañas comerciales en navegador. YOLO11n cargó y procesó un primer frame real de una cámara; esto comprueba ejecución, no precisión de la señal de compra.

Desde CMD, para repetir las pruebas:

```cmd
cd proyecto_lap_prototipo
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
cd dashboard
npx tsc --noEmit
npm run build
```


## Pruebas con tus videos (27/09/2026)

En **Vista general**, activa **Prueba con videos** y pulsa **Analizar videos de prueba**. El selector Cámara permite analizar una sola; Todas las cámaras procesa las activas. Esta opción permite el plano ilustrativo sin presentarlo como medición real del LAP. Para asociar IDs entre vistas se necesitan geometría coherente, desfases correctos y sincronización declarada. El detector operativo de esta versión de main es P2PNet con tracking de puntos de cabeza; no es el antiguo seguimiento corporal YOLO. La señal opcional de objetos sí carga YOLO11n y ByteTrack.

Sesión guardada **6aa427dd**, dos videos originales CAM-1/CAM-2, análisis de cruces y ocupación, sin error (hecha cuando el sistema aún incluía P2PNet, retirado el 2026-10-05). Disponible en **Videos y resultados**. Resumen local en `data/commercial-tests/videos_actuales.json`. La reproducción de prueba dura aproximadamente 32 segundos de fuente analizada; no se validó manualmente la precisión de sus conteos ni la reidentificación.

Proyecciones sintéticas adicionales guardadas para El Bodegón, origen **Datos de prueba**, fecha **2026-09-27**:

| Hora | Entradas de prueba | Proyección PEN |
|---|---:|---:|
|18:00|10|212.50|
|19:00|25|531.25|
|20:00|40|850.00|

CSV importado: `data/commercial-tests/ventas_escenarios_prueba.csv`. Resumen: `pronosticos_prueba.json`. Estos escenarios ejercitan cálculos con entradas sintéticas; no provienen del video ni representan ventas reales. La prueba anterior de las 22:00 sigue disponible, con proyección S/42.50. Los historiales y pruebas se conservan al reiniciar.

## Videos públicos pequeños para próximas pruebas

Fuente: https://homepages.inf.ed.ac.uk/rbf/CAVIARDATA1/ — CAVIAR, dos vistas de un centro comercial en Portugal. Pareja **EnterExitCrossingPaths1**, aproximadamente 2 MB por archivo:

- https://homepages.inf.ed.ac.uk/rbf/CAVIARDATA2/EnterExitCrossingPaths1cor/EnterExitCrossingPaths1cor.mpg
- https://homepages.inf.ed.ac.uk/rbf/CAVIARDATA2/EnterExitCrossingPaths1front/EnterExitCrossingPaths1front.mpg

En ambas se observa la entrada de una tienda y personas cruzando. El reloj incrustado ayuda a establecer el desfase: no basta asumir que los primeros frames corresponden. Resolución 384×288; es una prueba rápida de correspondencias en áreas parcialmente compartidas, no un benchmark moderno de reidentificación entre cámaras sin solapamiento. No necesitas descargar todo el conjunto. Usa VLC si el navegador no reproduce MPEG2. La página identifica uso CC BY-SA y pide atribución CAVIAR/IST 2001 37540 al publicar resultados.


## Reportes de sesiones y prueba de tres cámaras

En **Reportes**, el selector **Monitoreo guardado** determina qué ejecución se consulta. El reporte abarca esa sesión, no todo el día. Conserva también las métricas de una cámara cuyo video terminó antes que los demás. PDF, Excel y CSV exportan la sesión seleccionada.

**Ventas y análisis** agrega tráfico por negocio, fecha y hora; las ventas vienen del CSV. El enlace del reporte abre la fecha y hora correspondientes. Para videos reales debe declararse la fecha de grabación; para videos de prueba se usa la fecha de ejecución y el origen Datos de prueba. Las ventas de prueba no se presentan como ventas reales.

Las grabaciones se procesan con tiempo de fuente independiente del coste de inferencia, a intervalos de 0.2 segundos. Esto conserva las muestras necesarias para cruces, promedios y alertas, aunque procesar en CPU tarde más que la duración del video. En vivo se mantiene el reloj real.

La cámara 1 tiene el acceso de Tanta To Go vinculado. La cámara 2 no tiene línea de conteo. La cámara 3 tiene una línea sin negocio asociado. No se inventa un vínculo comercial a partir de la imagen. Para vincularlo: Negocios y accesos → seleccionar tienda → Cámara del acceso → marcar su línea → Guardar negocio. También puede vincularse al editar la línea en la configuración de cámara.

CSV sintético de ventas e histórico para Tanta To Go: `data/commercial-tests/ventas_prueba_tres_camaras.csv`. Los resultados de videos se conservan en `data/replays`, y el resumen de la última prueba en `data/commercial-tests/videos_actuales.json`. Los escenarios de proyección sintéticos anteriores (18, 19 y 20 horas) siguen disponibles.

Prueba completa guardada: **e998c4da**, tres videos, 78.6 segundos de fuente. CAM-1: 1 entrada y 2 salidas en Tanta To Go. CAM-3: 0 entradas y 3 salidas en acceso sin negocio asociado. CAM-2 sin línea. Tanta To Go, origen Datos de prueba, 2026-09-27, 23:00: venta CSV sintética S/50 y proyección S/21.25 con cuatro días históricos sintéticos. La precisión de detección no fue anotada manualmente; estas verificaciones comprueban ejecución, persistencia y cálculo. Nueve exportaciones comprobadas vía HTTP: PDF, Excel y CSV de negocios, cámaras y accesos, en `data/commercial-tests/reportes/e998c4da-*`.
