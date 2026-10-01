# Negocios y análisis comercial

Contrato comercial conservado en la candidata
`jose/automations-main-integration-v2` (revisión Fase 8, base `0b611e0`).
Las sesiones y ventas de ejemplo documentadas aquí son antecedentes reportados
de `comercial-negocios-ventas`; no son fixtures garantizados de un clon ni permiso
para usar el Proyecto principal del operador. Nuevos ensayos requieren un
proyecto y datos de prueba aislados.

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

Referencia del entorno del ensayo original; no ejecutar sobre datos actuales
para reproducirla. La presencia de esos archivos/sesiones no se verificó en Fase 8.

1. Reinicia con `iniciar_sistema.cmd` desde la raíz, si el servidor estaba abierto antes de estos cambios.
2. Entra como operador y mantén **Proyecto principal**.
3. Abre **Ventas y análisis → Ver prueba guardada**. Selecciona las pestañas para ver ventas, proyección, incidente y señal experimental.
4. La simulación de accesos del 27/09/2026 está en **Videos y resultados**, sesión `e28d5219`. Registra 2 entradas y 2 salidas para El Bodegón. No contiene video real porque es una simulación.
5. En los datos de prueba de las 22:00 hay una venta de S/50 y proyección de S/42.50 con cuatro días históricos sintéticos. El incidente y las muestras de objetos son datos sintéticos explícitos; verifican persistencia y cálculo, no precisión del modelo.

CSV y resumen: `data/commercial-tests/ventas_prueba_comercial.csv` y `validacion.json`. Reproducciones: `data/replays/<sesión>/manifest.json` y `samples.jsonl`. Negocios, ventas, tráfico, incidentes y muestras comerciales: SQLite por proyecto, `config/projects/<id>.negocios.sqlite`. PostgreSQL/PostGIS pertenece a una etapa posterior.

## Verificación

El ensayo original reportó 131 pruebas aprobadas, TypeScript, build y revisión
comercial en navegador, además de un frame de cámara con YOLO. Es **RESULTADO
HISTÓRICO REPORTADO**, no ejecución LIVE de Fase 8 ni total actual de la suite.
La evidencia de la candidata está en [FASE8_VALIDACION.md](FASE8_VALIDACION.md).
Ejecutar un modelo no demuestra precisión de la señal comercial.

Desde CMD, para repetir las pruebas:

```cmd
cd proyecto_lap_prototipo
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
cd dashboard
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
```


## Pruebas con tus videos (27/09/2026)

El modo de videos de prueba permite geometría ilustrativa sin presentarla como
medición real del LAP; no aísla datos ni filesystem. Para asociar IDs entre vistas
se necesitan geometría coherente, desfases correctos y sincronización declarada.
En la candidata actual el monitoreo integrado solicita `hybrid`: YOLO principal
con `ByteTrackPuntos`, más P2PNet adaptativo para densidad. El backend también
admite P2PNet directo, que es un contrato distinto. La señal opcional de objetos
añade su propia inferencia YOLO. Véase [GUIA_SEGUIMIENTO.md](GUIA_SEGUIMIENTO.md).

Sesión guardada **6aa427dd**, dos videos originales CAM-1/CAM-2, P2PNet real, análisis de cruces y ocupación, sin error. Disponible en **Videos y resultados**. Resumen local en `data/commercial-tests/videos_actuales.json`. La reproducción de prueba dura aproximadamente 32 segundos de fuente analizada; no se validó manualmente la precisión de sus conteos ni la reidentificación.

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

Las grabaciones usan una rejilla de muestras de contenido cada 0.2 s independiente
del coste de inferencia; no procesan cada frame ni garantizan capturar todo cruce.
LIVE usa el reloj monotónico local del ciclo y frames recientes, con descarte
de anteriores; no demuestra sincronización de captura entre cámaras. Definiciones
y protocolo no ejecutado en [PRUEBA_LIVE.md](PRUEBA_LIVE.md).

Las observaciones y recorridos pueden quedar persistidos, además de agregados
comerciales. La retención parcial de replays/uploads no elimina todas las copias:
[INVENTARIO_PERSISTENCIA.md](INVENTARIO_PERSISTENCIA.md).

La cámara 1 tiene el acceso de Tanta To Go vinculado. La cámara 2 no tiene línea de conteo. La cámara 3 tiene una línea sin negocio asociado. No se inventa un vínculo comercial a partir de la imagen. Para vincularlo: Negocios y accesos → seleccionar tienda → Cámara del acceso → marcar su línea → Guardar negocio. También puede vincularse al editar la línea en la configuración de cámara.

CSV sintético de ventas e histórico para Tanta To Go: `data/commercial-tests/ventas_prueba_tres_camaras.csv`. Los resultados de videos se conservan en `data/replays`, y el resumen de la última prueba en `data/commercial-tests/videos_actuales.json`. Los escenarios de proyección sintéticos anteriores (18, 19 y 20 horas) siguen disponibles.

Prueba completa guardada: **e998c4da**, tres videos, 78.6 segundos de fuente. CAM-1: 1 entrada y 2 salidas en Tanta To Go. CAM-3: 0 entradas y 3 salidas en acceso sin negocio asociado. CAM-2 sin línea. Tanta To Go, origen Datos de prueba, 2026-09-27, 23:00: venta CSV sintética S/50 y proyección S/21.25 con cuatro días históricos sintéticos. La precisión de detección no fue anotada manualmente; estas verificaciones comprueban ejecución, persistencia y cálculo. Nueve exportaciones comprobadas vía HTTP: PDF, Excel y CSV de negocios, cámaras y accesos, en `data/commercial-tests/reportes/e998c4da-*`.
