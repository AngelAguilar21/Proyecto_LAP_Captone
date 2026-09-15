# Monitoreo, accesos y reportes

## Vista general y Videos y resultados

Vista general presenta un monitoreo seleccionado: mapa arriba, cámaras debajo y una reproducción sincronizada. Los indicadores siguen el instante seleccionado. Las observaciones de varias cámaras pueden incluir a la misma persona; no representan visitantes únicos.

Videos y resultados permite revisar el historial y comparar varios análisis. El selector «Capa sobre el video» distingue:

- Personas e IDs · YOLO + ByteTrack: cajas e identidades temporales del seguimiento.
- Presencia acumulada · seguimiento: dónde permanecieron las detecciones durante el intervalo.
- Conteo de multitudes · P2PNet: puntos estimados y conteo especializado, si ese análisis lo procesó. Activar el conteo especializado en la cámara y ejecutar un nuevo análisis si no hay estimaciones.

P2PNet localiza cabezas. Sus puntos no se proyectan mediante la calibración del suelo ni se suman al conteo de YOLO. El mapa de posiciones y recorridos corresponde al seguimiento calibrado.

## Presencia y alertas

La presencia acumulada se representa con celdas magenta: más intensidad indica mayor presencia relativa dentro del análisis. Integra observaciones y tiempo; no cuenta personas únicas ni implica por sí sola una aglomeración. Ámbar representa concentración en evaluación y rojo los umbrales de cantidad y duración de alerta alcanzados. La cobertura de cámara continúa siendo una capa independiente.

## Accesos opcionales por cámara

En Configuración, seleccionar cámara y abrir «Editar fuente, zona útil y accesos». Obtener la imagen inicial y desplegar «Accesos de locales · entradas y salidas (opcional)».

1. Escribir el nombre del local y acceso.
2. Añadir acceso y marcar dos extremos de la puerta sobre el suelo.
3. Ajustar los círculos de la línea y los cuatro cuadrados de las áreas Interior y Exterior. Mantener cada área a un lado de la línea.
4. Usar «Invertir entrada» si el interior está al lado contrario.
5. Guardar con «Guardar cámara, zona y líneas» y volver a procesar el video.

Se registra un paso cuando una trayectoria cruza la línea y se observa en ambas áreas. Aparecer dentro del local no basta. Se conservan entradas, salidas, acumulados por hora relativa y hasta los últimos 1000 eventos por acceso. Las horas de videos son relativas a su inicio; no se inventa una fecha de captura. Los análisis anteriores no incorporan retroactivamente una configuración nueva.

## Reportes localizables

«Sectores con mayor presencia» numera las celdas S1, S2, etc. y muestra la cámara más cercana como referencia. «Ubicar S1» centra y resalta la celda en el mapa. La referencia no equivale a identificar automáticamente una tienda. Los CSV incluyen sector, nivel, referencia y coordenadas.

«Eventos de accesos» muestra local, dirección y segundo del video. Si no hubo cruces confirmados, la tabla queda vacía; no se generan eventos de ejemplo. Ocupación, presencia por hora y trayectorias muestran sus propias fuentes de datos y explican cuando no están disponibles.

## Verificación de esta revisión

69 pruebas automatizadas superadas, comprobación TypeScript y compilación Vite correctas. Verificados en navegador el mapa sobre las cámaras, la ubicación de un sector y el guardado de áreas de confirmación en la cámara de tienda. Estas verificaciones comprueban funcionamiento; la precisión de detección y de los cruces requiere contrastar videos anotados manualmente.


## Actualización de cámaras y calibración

Vista general recalcula las posiciones y el calor del historial con las referencias del suelo actuales; el archivo original del análisis permanece intacto. Si cambias la zona útil, la fuente o los accesos, vuelve a procesar: las detecciones descartadas durante un análisis anterior no se pueden recuperar solo con reproyección. Las asociaciones antiguas entre cámaras vuelven a mostrarse como locales cuando cambia la calibración.

Al trasladar una cámara sobre el mapa también se trasladan sus referencias del suelo y su polígono de cobertura. Si cambia físicamente el encuadre, revisa las correspondencias: trasladar el icono no estima una perspectiva nueva. El recorte general del área de trabajo no excluye detecciones en la cartografía LAP; se usan la zona útil y, cuando está activado, el límite de cobertura de cada cámara.

Guardar configuración es independiente de Abrir monitoreo. En el editor de fuente el guardado está fijo en la cabecera. Obtener el primer fotograma no guarda otros cambios. Deshacer y Quitar punto están encima de la imagen.

La capa del mapa «Conteos y accesos por cámara» muestra P2PNet con el segundo de su muestra y las entradas/salidas, asociados al icono de cámara. No transforma cabezas en coordenadas del suelo. El detalle por acceso se consulta en los indicadores de cámara y reportes. Las estimaciones P2PNet se recuperan por tiempo de captura aunque la inferencia haya terminado después; no se muestran antes de ese instante.
