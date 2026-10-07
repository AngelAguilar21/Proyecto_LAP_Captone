# Guion para exponer: relación entre afluencia y actividad comercial

## Qué presentar como tu aporte

«Mi parte relaciona lo que observamos en las cámaras con los negocios del aeropuerto. Una línea de conteo representa un acceso y se vincula a una tienda. A partir de los cruces obtenemos entradas y salidas por periodo. Después combinamos ese tráfico con un histórico comercial para estimar un valor asociado al tráfico observado y un pronóstico para la siguiente hora».

La cadena es: **cámara → línea de acceso → tienda → entradas por periodo → histórico de ventas → indicadores comerciales**. Un negocio puede tener varios accesos; una cámara sin acceso vinculado puede servir para monitoreo de personas, pero no aporta automáticamente entradas de una tienda.

## Demostración en pantalla: aproximadamente tres minutos

1. Abre **proyecto 3 → Ventas y análisis → Prueba con Excel**.
2. En el monitoreo, elige el análisis de **Cámara 2, Cámara 3 y Cámara 4, del 7 de octubre a las 06:04:30**, de aproximadamente un minuto. El código técnico de ese registro es 4feb3f3e, pero ya no necesitas reconocerlo para seleccionarlo.
3. Señala las tiendas disponibles y elige **Puku Puku**, la de tu captura. La aplicación muestra **2 entradas y 3 salidas en 59,6 segundos**, dentro de la franja asignada 06:00–07:00. Las 06:04:30 indican cuándo se ejecutó el análisis; la franja de ventas procede de la fecha y hora asignada a la grabación. No son el mismo dato.
4. Carga **Puku_Puku_SINTETICO.xlsx**, ubicado en `outputs/comercial-20261007/por-tienda` desde la raíz del proyecto. No necesitas modificarlo. Pulsa **Calcular y guardar ensayo**.
5. Explica los tres resultados usando el guion de abajo. Abre la explicación de conversión y la de utilidad para LAP.
6. Abre **Ensayos guardados**. Muestra que el resultado se conserva y que, al seleccionar otro ensayo, cambian también la tienda y el monitoreo correspondiente. No se sobrescriben los cálculos anteriores.

Para exponer sin recalcular: abre directamente el ensayo guardado de Puku Puku. Para otra prueba con videos: termina un monitoreo con líneas vinculadas a tiendas, actualiza la lista y selecciona ese monitoreo. El botón de descarga crea un CSV de ejemplo compatible con la tienda y la fecha seleccionadas. Ese CSV usa otros valores ficticios; no tiene por qué producir exactamente los importes de los Excel de esta entrega.

## Qué explicar de los datos de entrada

«No deducimos las ventas a partir de la imagen. El video aporta entradas y salidas; el sistema de ventas de la tienda tendría que aportar ventas y transacciones. Como no tenemos ese histórico real, preparé un Excel ficticio por tienda para probar la integración».

Cada fila del Excel corresponde a **una tienda, una fecha y una hora**:

| Campo | Explicación para el profesor |
|---|---|
| negocio_id | Clave para relacionar el histórico con la tienda y sus accesos. No es un importe ni un resultado. |
| fecha y hora | Permiten comparar periodos equivalentes. Hora 6 significa 06:00–07:00, en Lima. |
| ventas_pen | Importe total vendido en soles en esa franja. En operación vendría del registro comercial. |
| transacciones | Número de boletas o transacciones. No es cantidad de productos ni compradores únicos. |
| entradas | Cruces de entrada registrados en esa franja histórica. |
| cobertura_min | Minutos durante los que se pudo observar el acceso. Evita comparar un minuto de cámara contra una hora de ventas. |

Los libros de esta prueba tienen ocho miércoles anteriores para la hora 6 y ocho para la hora 7. Tanto las ventas como el tráfico **histórico** de esos libros son ficticios. Los cruces del video actual proceden del análisis de las cámaras.

## Cómo se obtiene cada indicador

### Entradas y salidas

El seguimiento registra el cruce de una línea configurada en la imagen y su dirección. Ese evento se asigna a la tienda vinculada. Son cruces, no un censo de personas únicas: alguien que vuelve a entrar puede contarse otra vez. La calidad depende de visibilidad, dirección de línea, detección y seguimiento.

En Puku Puku se registraron **2 entradas y 3 salidas**. Esto no es imposible: alguien pudo estar dentro antes de empezar el video. No se debe afirmar que la ocupación es −1; para obtener ocupación interior hace falta conocer la ocupación inicial y observar todos los accesos sin huecos. Las salidas no se restan de las entradas para estimar ventas.

### Ingreso histórico por entrada

Para cada fecha comparable, se calcula:

`ingreso por entrada = ventas de esa hora / entradas de esa hora`

Después se toma la **mediana** de esos valores: se ordenan y se elige el valor central; si hay una cantidad par, se promedian los dos centrales. Esto reduce la influencia de un día con ventas extraordinarias, pero no garantiza exactitud.

Solo se consideran fechas anteriores, del mismo día de semana y hora, con entradas positivas y al menos 55 minutos observados. Se exigen tres fechas como mínimo; en el ejemplo hay ocho. Estos mínimos son reglas del prototipo, no un nivel de confianza estadístico.

No es el ticket promedio. **Ticket promedio = ventas / transacciones**. El ingreso por entrada divide entre todos los cruces de entrada, incluidos los que no generan compra.

### Valor estimado del tramo observado

`estimación del tramo = entradas del video × mediana histórica de ventas / entradas`

Puku Puku: `2 × 4,83681795 = S/ 9,67`, después de redondear el importe final. La pantalla muestra el coeficiente aproximado S/ 4,84, pero calcula con todos sus decimales. Esto explica que multiplicar solo los números redondeados pueda diferir un céntimo.

Frase para exponer: «Si esas entradas se comportaran como el histórico de referencia, su valor comercial estimado sería S/ 9,67. No afirmamos que hayan comprado ni que esa venta se haya producido».

Se estima el tramo de 59,6 segundos. **No se multiplica el resultado por 60 para inventar una hora completa.**

### Pronóstico de la siguiente hora

Se consulta el histórico de la siguiente franja, también del mismo día de semana:

`entradas esperadas = mediana de las entradas históricas de esa franja, redondeada a entero`

`pronóstico = entradas esperadas × mediana histórica de ventas / entradas de esa franja`

Puku Puku, 07:00–08:00: `70 × 4,82288136 = S/ 337,60`.

Frase para exponer: «Para la siguiente hora, el histórico indica unas 70 entradas. Con su ingreso histórico por entrada, el sistema pronostica S/ 337,60. Es una referencia para planificar y después contrastar con las ventas reales».

El pronóstico actual es una **base estadística por medianas**, no una red neuronal entrenada ni una predicción validada. Las dos entradas del video no se convierten en 70: esas 70 proceden del histórico de la siguiente hora. Falta medir el error sobre datos reales y evaluar estacionalidad, vuelos, promociones y cambios operativos antes de usarlo para decisiones importantes.

### Conversión histórica

`conversión histórica = suma de transacciones / suma de entradas históricas × 100`

Puku Puku: `88 / 508 × 100 = 17,3 %`.

Frase para exponer: «En el histórico de ejemplo hubo aproximadamente 17 transacciones por cada 100 entradas. Este cociente permite estudiar si la afluencia se acompaña de actividad comercial».

No significa que identificamos al 17,3 % de personas como compradores: una persona puede entrar más de una vez, una compra puede ser grupal o alguien puede hacer varias transacciones. Tampoco es la conversión del video actual. Para esta última hacen falta transacciones de esa misma franja, entradas positivas y cobertura suficiente. La cámara no observa el pago.

## Resultados reproducibles de los tres Excel

Todos usan el análisis del 7 de octubre a las 06:04:30, con 59,6 segundos observados. Las cantidades monetarias dependen de históricos ficticios.

| Tienda | Entradas | Salidas | Estimación del tramo | Pronóstico 07:00–08:00 | Conversión histórica |
|---|---:|---:|---:|---:|---:|
| Tanta To Go | 6 | 6 | S/ 43,46 | S/ 576,00 | 20,1 % |
| Grab & Go | 2 | 1 | S/ 5,99 | S/ 178,08 | 15,0 % |
| Puku Puku | 2 | 3 | S/ 9,67 | S/ 337,60 | 17,3 % |

Estos importes no demuestran que Tanta sea comercialmente mejor: los históricos fueron inventados y las tiendas pueden tener precios, productos y públicos distintos.

## Para qué podría servirle a LAP

| Pregunta de gestión | Aporte del sistema | Condición para usarlo |
|---|---|---|
| ¿Cuándo reciben más entradas las tiendas? | Tráfico por negocio y franja para coordinar atención, limpieza y circulación con los operadores. | Observar accesos completos y acumular periodos representativos. |
| ¿Aumentan las transacciones cuando aumenta la afluencia? | Relacionar tráfico y ventas mediante la conversión y el ingreso por entrada. | Ventas reales y tráfico del mismo periodo; comparar contextos equivalentes. |
| ¿Qué actividad comercial podría haber la siguiente hora? | Pronóstico de referencia para conversar sobre personal y abastecimiento. | Historial real y evaluación del error del pronóstico. |
| ¿Qué pasa alrededor de una aglomeración? | Revisar incidentes y ventas del periodo correspondiente. | Datos suficientes; no atribuir causalidad a una coincidencia. |

Son **ventas estimadas de los negocios**, no ingresos directos de LAP. Para calcular ingresos del aeropuerto harían falta reglas contractuales y otros datos que este ensayo no incorpora. El sistema apoya decisiones; no justifica automáticamente cambios de alquileres, sanciones o redistribución de locales.

## Qué son las otras pestañas

- **Prueba con Excel:** un ensayo reproducible por tienda y monitoreo. El archivo cargado y sus resultados se guardan aparte; no reemplazan las ventas operativas.
- **Datos guardados:** consulta de tráfico y ventas que ya se registraron para una tienda, fecha, hora y origen. Cambiar estos filtros cambia el periodo consultado.
- **Estimación y pronóstico:** aplica los cálculos al histórico persistido de la aplicación. Si ese histórico difiere del Excel de un ensayo, sus importes también pueden diferir.
- **Aglomeraciones y ventas:** compara ventas de la hora que contiene un incidente con una referencia histórica. No obtiene ventas minuto a minuto durante el incidente y no demuestra que la aglomeración causó una variación. Si el incidente atraviesa varias horas, el código evita calcular esa variación.
- **Señal de objeto nuevo:** indicador experimental sobre salidas emparejadas con entradas. Detectar un objeto que antes no se veía no demuestra una compra. Si no hay emparejamientos fiables, no hay una conclusión comercial que exponer.

Para esta exposición conviene centrar la demostración en **Prueba con Excel**, los accesos vinculados y los cálculos reproducibles. Presenta las otras pestañas como capacidades con sus límites y datos requeridos, no como resultados ya comprobados por este minuto de video.

## Preguntas probables del profesor

**¿Entraron dos personas y vendieron S/ 9,67?** No. Hubo dos cruces; S/ 9,67 es una estimación bajo el comportamiento del histórico.

**¿De dónde salen las ventas?** De un histórico comercial. Aquí es ficticio; en producción lo tendría que entregar la tienda o su sistema de ventas.

**¿Esto es inteligencia artificial?** La detección y el seguimiento del video usan modelos de visión. El cálculo comercial mostrado es estadístico. No estamos entrenando un modelo de ventas con estos Excel.

**¿Por qué la mediana?** Para reducir la influencia de días extremos y disponer de una referencia sencilla y explicable. Su utilidad debe compararse con otros métodos usando datos reales.

**¿Cómo sabrías si predice bien?** Guardaría los pronósticos antes de conocer las ventas, los contrastaría después y mediría, por ejemplo, el error absoluto medio en soles. La evaluación debe reservar fechas futuras que no se usaron para calcular la referencia. Aún no tenemos esa validación real.

**¿Qué significa falta historial?** No hay suficientes fechas comparables con cobertura válida. No se resuelve copiando la misma fila ni repitiendo el mismo video.

**¿Qué se guarda?** Por proyecto, PostgreSQL conserva el ensayo, la tienda, el monitoreo, fecha de cálculo, nombre y huella del archivo, sus filas normalizadas y los resultados. El Excel original se conserva en la carpeta local de entrega. Los videos son archivos o fuentes externas; no se confunden con las filas comerciales.

**¿Las cámaras de Tokio prueban la parte comercial?** Prueban recepción y análisis de una fuente en vivo. En esa prueba no se configuraron accesos comerciales, y el plano LAP no corresponde a Tokio. Por ello no son una validación de ventas ni de proyección geográfica.

## Cierre sugerido

«El avance demostrado es la integración trazable entre accesos de cámaras, tiendas e históricos comerciales. Ya puedo repetir un ensayo, explicar sus fórmulas y recuperar el resultado. Para una validación con LAP necesitamos históricos reales, accesos bien configurados y comparar las estimaciones con ventas posteriores. No presentamos datos ficticios como resultados del aeropuerto».
