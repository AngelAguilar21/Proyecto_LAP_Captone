# Demostrar ventas y análisis con un Excel por tienda

## Prueba lista para exponer

1. Abre http://127.0.0.1:8765 e ingresa como operador.
2. Elige **proyecto 3**, donde están los videos usados en esta demostración.
3. Entra en **Ventas y análisis → Prueba con Excel**.
4. Elige el monitoreo **4feb3f3e**, del 7 de octubre de 2026, y **Tanta To Go**.
5. En «Archivo Excel (.xlsx) o CSV», carga `outputs/comercial-20261007/por-tienda/Tanta_To_Go_SINTETICO.xlsx` de la raíz del repositorio.
6. Pulsa **Calcular y guardar ensayo**. Aparece un resultado nuevo y queda disponible en **Ensayos guardados → Ver resultado**.

No necesitas volver a procesar el video para repetir el cálculo. Puedes cambiar de tienda y cargar su propio Excel:

| Tienda | Archivo en la misma carpeta | Entradas / salidas del video | Valor estimado del tramo | Pronóstico 07:00–08:00 |
|---|---|---:|---:|---:|
| Tanta To Go | Tanta_To_Go_SINTETICO.xlsx | 6 / 6 | S/ 43,46 | S/ 576,00 |
| Grab & Go | Grab___Go_SINTETICO.xlsx | 2 / 1 | S/ 5,99 | S/ 178,08 |
| Puku Puku | Puku_Puku_SINTETICO.xlsx | 2 / 3 | S/ 9,67 | S/ 337,60 |

Los cruces proceden del análisis guardado de 59,6 segundos. Los históricos de ventas y tráfico de los Excel son **ficticios**. No son ventas del aeropuerto ni compras confirmadas de las personas del video.

## Qué contiene cada Excel

La hoja **Guia** explica los pasos y permite revisar cálculos. La hoja **Historico** es la que lee la aplicación: 16 filas, correspondientes a ocho miércoles anteriores, con las franjas 06:00–07:00 y 07:00–08:00. Cada fila representa una hora de una tienda.

| Columna requerida | Significado y fuente en una operación real |
|---|---|
| negocio_id | Identificador de la tienda; relaciona el archivo con sus líneas y cámaras. |
| fecha | Fecha local AAAA-MM-DD. |
| hora | Inicio de la franja, de 0 a 23, hora de Lima. Un 6 representa 06:00–07:00. |
| ventas_pen | Total vendido en soles en esa hora, obtenido del sistema de ventas de la tienda. |
| transacciones | Número de boletas/transacciones de esa misma hora, no cantidad de productos. |
| entradas | Cruces históricos de entrada contabilizados por las cámaras de esa tienda. |
| cobertura_min | Minutos durante los cuales se observó el acceso, entre 0 y 60. |

La columna auxiliar ingreso_por_entrada muestra una fórmula en Excel; el sistema no la importa, sino que vuelve a calcular el cociente. No cambies el ID para hacer pasar el archivo de otra tienda. No se admiten filas repetidas para la misma fecha y hora. Las columnas requeridas deben contener valores, no fórmulas dependientes de Excel.

## Qué representa cada resultado

**Entradas del video:** cantidad de cruces de entrada por las líneas vinculadas al negocio. Una persona puede cruzar más de una vez. No representa compradores únicos; las salidas no se restan para calcular el ingreso por entrada.

**Valor estimado del tramo:** se seleccionan fechas anteriores del mismo día de la semana y la misma hora, con entradas positivas y al menos 55 minutos cubiertos. Se calcula ventas / entradas en cada fecha y se toma la mediana. Esa referencia se multiplica por las entradas observadas en el video. Se requieren al menos tres fechas comparables; los ejemplos tienen ocho. La mediana reduce la influencia de un día extraordinario, pero no elimina sesgos ni demuestra precisión.

Ejemplo: las seis entradas de Tanta se multiplican por aproximadamente S/ 7,24 históricos por entrada y dan S/ 43,46. La pantalla redondea el coeficiente; el cálculo conserva sus decimales. **Es una estimación para el tramo observado, no para una hora completa.**

**Pronóstico de la siguiente hora:** se busca el histórico de esa franja y día de semana. Mediana de entradas históricas, redondeada a entero, × mediana de ventas / entradas de esa franja. Para Tanta: 80 entradas esperadas × S/ 7,20 = S/ 576. Sirve como referencia de planificación. Es un método estadístico sencillo, no un modelo entrenado ni una garantía. El video actual no determina las entradas previstas de la siguiente hora.

**Conversión histórica:** suma de transacciones / suma de entradas de las fechas comparables × 100. Expresa transacciones por cada 100 cruces de entrada, no una probabilidad de compra individual. Para calcular la conversión del monitoreo actual hacen falta sus ventas/transacciones reales de la misma franja y cobertura suficiente de tráfico. Un minuto de video no debe compararse contra todas las boletas de una hora. Por eso esta prueba muestra únicamente la referencia histórica.

**Falta historial:** no hay tres fechas válidas para la franja correspondiente. Completa el histórico de esa tienda con datos comparables; no se corrige duplicando filas o repitiendo el mismo video. El umbral de tres fechas y 55 minutos es una regla de suficiencia de la aplicación, no una certificación estadística.

## Cómo hacer una prueba nueva

1. Configura la línea de conteo de la cámara y vincúlala a la tienda correcta.
2. En **Vista general**, activa **Prueba con videos**, selecciona las cámaras necesarias y establece la fecha/hora de la grabación. Inicia el monitoreo y espera a que finalice o detenlo para guardar el tramo.
3. En **Ventas y análisis → Prueba con Excel**, pulsa **Actualizar lista de monitoreos** y selecciona el nuevo análisis y su tienda. En este ensayo se usa el tramo de la primera hora del video, hasta el cambio de hora.
4. Pulsa **Descargar ejemplo para esta tienda (CSV)**. Se genera un archivo con el ID y fechas compatibles con el video elegido. Es un ejemplo ficticio y se puede abrir en Excel. Puedes cargar directamente el CSV, o guardar los datos como .xlsx en una hoja llamada Historico.
5. Carga ese archivo y pulsa **Calcular y guardar ensayo**. La descarga dinámica usa otros valores ficticios: no tiene por qué reproducir los importes de los tres Excel de esta entrega.
6. Abre **Ensayos guardados** para comparar resultados anteriores. Cada cálculo tiene su propio ID; repetir la prueba no sobreescribe el anterior.

Para demostrar que el cálculo responde a los datos, duplica un Excel y duplica ventas_pen en las ocho filas de la hora 7, sin cambiar lo demás. Al cargarlo, el pronóstico se duplica, pero el valor estimado del tramo de las 6 no cambia. Explica que es una prueba de sensibilidad, no una mejora de exactitud.

## Explicación breve para el profesor

«El video nos aporta entradas y salidas por tienda mediante una línea vinculada a su cámara. Las ventas vienen de la tienda, no de la imagen. En esta demostración uso un Excel ficticio para representar ese histórico. El sistema estima un valor para las entradas observadas y calcula una referencia para la siguiente hora con días comparables. No afirmamos que cada persona compró ni que esa venta ocurrió. Con históricos reales podríamos comparar el pronóstico con las ventas posteriores y medir su error».

Los ensayos se guardan por proyecto en PostgreSQL, tabla commercial_trials, con el archivo identificado por nombre y huella, sus filas normalizadas, sesión y cálculos. Los originales .xlsx permanecen en la carpeta de entrega. Estos ensayos no escriben ni sobreescriben las ventas operativas mostradas en las otras pestañas.

## Validación de esta entrega

Se cargaron manualmente los tres .xlsx desde la interfaz y se guardaron sus resultados. Se comprobó el rechazo de un archivo de otra tienda. Las fórmulas de los libros se recalcularon y contrastaron con los resultados del sistema. La suite de Python ejecutó 362 pruebas, con cuatro omitidas por condiciones de entorno; las restantes pasaron. Se compiló el frontend.
