# Base multicámara y demostración comercial — 7 de octubre de 2026

## Qué cambió en esta entrega

| Antes | Ahora | Motivo y límite |
|---|---|---|
| Usuarios, configuración y comercio ya estaban migrados a PostgreSQL; la memoria de apariencia seguía en SQLite. | La memoria se importa una vez a PostgreSQL por instalación, proyecto y huella/dimensión del encoder. | Unifica la persistencia operativa y evita mezclar vectores de modelos incompatibles. La comparación sigue en RAM para no consultar SQL en cada cuadro. No hace más preciso al modelo por sí mismo. |
| Había rutas dirigidas entre cámaras, sin un grafo completo de las entidades comerciales. | Nodos tipados de cámaras, zonas, accesos y negocios; relaciones con claves foráneas e índices. | Permite auditar cámara → línea → tienda y las rutas que autorizan candidatos ReID. El grafo se deriva de la configuración, sin mantener dos configuraciones manuales. |
| Se recorrían las relaciones de cámaras repetidamente al buscar candidatos. | Vecinos de cada cámara precalculados en el asociador. | Reduce trabajo repetido; mantiene dirección, ventanas temporales, geometría y comprobación de apariencia. Estar cerca en el plano no demuestra que exista un paso. |
| Repeticiones de una misma hora podían influir varias veces en series/pronósticos. | Se elige una sesión por franja, con la mayor cobertura, sin sumar repeticiones. | Evita inflar el tráfico al ejecutar otra vez un video. Todavía no combina intervalos parciales disjuntos de varias sesiones. |
| La cobertura comercial podía seguir la duración de otra cámara. | Se limita a la cobertura de las cámaras asociadas al negocio. | Evita presentar una puerta como observada cuando su cámara dejó de aportar imágenes. |
| El número de días podía leerse como confianza estadística. | La pantalla muestra días de referencia; estimación, ventas y cobertura quedan separados. | Ocho días no equivalen a una probabilidad calibrada. La conversión exige transacciones y al menos 55 minutos observados en la misma hora. |
| Reporte comercial con poca trazabilidad. | CSV con sesión, cobertura, origen, entradas, transacciones, estimación, ingreso por entrada y pronóstico siguiente. | Permite reconstruir de dónde sale cada cifra. El Excel de esta entrega contiene fórmulas editables y los insumos exactos. |
| Línea de conteo siempre igual. | Resalta unos 0,8 s: verde entrada, azul salida, violeta si coinciden, con texto. | Hace visible el evento en monitoreo y reproducción. El color acompaña al texto, no lo sustituye. |
| Solo comparación entre variantes OSNet. | FastReID ResNet50/MSMT17 exportado a ONNX, validado contra PyTorch y probado con recortes de tus videos. | Es un candidato de evaluación, no el modelo activo: no se demostró mayor precisión. |

## Dónde se guarda cada cosa

PostgreSQL/PostGIS guarda usuarios con hashes, configuración JSONB, negocios y puertas,
ventas, tráfico comercial, incidentes, grafo y memoria de apariencia. Las sesiones finalizadas,
observaciones espaciales y sus rutas también se archivan allí. El plano usa coordenadas locales
SRID 0: no se inventaron latitud y longitud.

Videos, modelos, manifiestos y muestras de reproducción permanecen en archivos. Es deliberado:
la reproducción actual utiliza esos archivos y los binarios grandes no necesitan consultas
relacionales. La cola SQLite es un buzón para reintentar el archivo cuando PostgreSQL falla,
no una segunda base operativa. Respaldar solo PostgreSQL no basta: también conserva `data/`,
las fuentes de video, el marcador de instalación y `.env` en un respaldo privado.

La escritura de memoria es asíncrona. Si falla durante una sesión, se informa el fallo y la
inferencia sigue en RAM; esa persistencia no dispone todavía de la misma cola de reintentos
del archivo de sesiones. No se promete recuperación de esos vectores ante un cierre abrupto.

## Cómo funciona el grafo

- Una relación cámara → cámara define tránsito dirigido o vista compartida y sus tiempos.
- Cámara → zona indica dónde se analiza ocupación.
- Cámara → acceso → negocio atribuye entradas y salidas a una tienda.
- Zona → negocio atribuye análisis de esa zona cuando está configurado.
- Compartir tienda NO autoriza unir identidades. Tampoco basta arrastrar dos iconos juntos.
- El filtro multicámara usa la parte de rutas del grafo en RAM, seguida por tiempo,
  geometría y apariencia. La memoria de largo plazo limita candidatos según las rutas
  alcanzables y su retención. El grafo SQL permite persistir y auditar las relaciones;
  no se hace una consulta SQL por cada detección.

En **Configurar proyecto → Continuidad entre cámaras → Cámaras, zonas y accesos vinculados**,
pulsa **Consultar relaciones guardadas**. La instalación comprobada contiene 75 nodos y
12 relaciones: 7 cámaras, 3 accesos y 65 negocios. El soporte de zonas existe, pero estas
cámaras no tienen zonas de análisis configuradas en ese grafo.

## Prueba guardada con los videos del usuario

Se utilizó el proyecto que ya tenía las siete cámaras, **proyecto 3** (`p-493a0866`),
sin crear otro proyecto ni trasladar configuraciones. Sesión **4feb3f3e**,
7/10/2026, franja **06:00–07:00 Lima**, modo **Prueba con videos**.
Se seleccionaron únicamente cámaras 2, 3 y 4. El análisis sincronizado terminó a los
59,6 segundos. Es un tramo de video, no una hora completa.

| Cámara | Negocio vinculado | Entradas detectadas | Salidas detectadas | Estimación del tramo con historial ficticio |
|---|---|---:|---:|---:|
| 2 | Tanta To Go | 6 | 6 | S/ 43,46 |
| 3 | Grab & Go | 2 | 1 | S/ 5,99 |
| 4 | Puku Puku | 2 | 3 | S/ 9,67 |

Los conteos son resultados del algoritmo sobre los videos; no son un conteo manual
certificado. Los nombres de tiendas provienen de tus asociaciones en la configuración,
no del reconocimiento visual del local. La fecha usa el inicio de prueba si no se
configuró una fecha de grabación; no demuestra la fecha original del archivo.

Archivo PostgreSQL verificado: sesión finalizada, **2.152 observaciones**. La cola
de archivo no tenía pendientes al comprobarla. Los archivos de reproducción siguen
en `data/replays/4feb3f3e/`. El análisis filtró candidatos por grafo, pero estas tres
cámaras comerciales no constituyen una prueba de correspondencias entre dos cámaras:
no se debe presentar este resultado como precisión ReID.

## Qué contiene el Excel y cómo se calcula

Archivo local: `outputs/comercial-20261007/Demostracion_comercial.xlsx`, desde la raíz
del repositorio. Hoja **Resultados**: cruces del video, fórmulas y explicación.
Hoja **Historico**: ocho fechas anteriores del mismo día de semana para cada negocio,
en dos horas (06 y 07), con 48 registros en total. Esos antecedentes son **SINTÉTICOS**.

El CSV importable tiene una fila por negocio/fecha/hora:

| Campo | Significado |
|---|---|
| negocio_id | ID estable de la tienda del sistema. Es el vínculo, no solo el nombre. |
| negocio_nombre | Nombre legible de referencia. |
| fecha | Fecha civil de Lima, AAAA-MM-DD. |
| hora | Inicio de la franja, 0 a 23. 6 significa 06:00–07:00. |
| monto | Venta total de esa tienda y hora, en soles. |
| moneda | PEN. |
| transacciones | Cantidad de boletas/transacciones, no personas detectadas. |

En operación real esos datos vienen del POS o un Excel de ventas. El tráfico histórico
viene de cámaras; el CSV de ventas no inventa tráfico. Para esta demostración también
se creó tráfico histórico ficticio con una hora de cobertura por fila, guardado SOLO
en el conjunto de prueba. Se exportó aparte para que pueda auditarse.

1. **Ingreso histórico por entrada:** para cada día comparable, ventas ÷ entradas.
   Se toma la mediana de al menos tres días anteriores del mismo día de semana y hora,
   con al menos 3.300 segundos cubiertos. No es ticket promedio por compra.
2. **Estimación del tramo observado:** entradas del video × mediana anterior.
   No se multiplica el clip por 60 ni se proyecta automáticamente a una hora.
3. **Pronóstico siguiente hora:** mediana de entradas históricas de la siguiente franja
   × mediana del ingreso por entrada de esa franja. Para el ejemplo: Grab & Go
   60 entradas/S/178,08; Puku Puku 70/S/337,60; Tanta To Go 80/S/576,00.
   Esos pronósticos demuestran el cálculo con antecedentes ficticios, no demanda real.
4. **Conversión aproximada:** transacciones ÷ entradas × 100, solo con ventas y tráfico
   suficientes de la misma hora. No identifica compradores únicos; una persona puede
   entrar varias veces o efectuar varias transacciones. En esta prueba corta queda
   vacía correctamente. El umbral de 55 minutos es una regla de cobertura del prototipo,
   no una garantía estadística. En la hoja Historico sí se puede practicar el cálculo.

Los cálculos usan valores sin redondear; la pantalla redondea a dos decimales. Por eso
el ingreso visible S/3,00 multiplicado por 2 puede producir S/5,99 al usar su valor completo.

No se añadieron ventas ficticias a la hora del video para hacerlas pasar por reales.
Las correlaciones requieren incidentes y ventas comparables; la señal de objeto nuevo
sigue siendo experimental y no demuestra una compra.

## Cómo verlo y repetirlo

1. Abre Docker Desktop. Desde CMD, en la raíz: `iniciar_sistema.cmd`.
2. Entra como tu operador y abre **proyecto 3**.
3. **Ventas y análisis → Ver prueba guardada** selecciona origen de prueba, fecha y
   hora con tráfico. Cambia **Negocio** para ver Grab & Go, Puku Puku o Tanta To Go.
   En **Estimación y pronóstico** se ven ambas cifras; **Resumen horario** muestra
   entradas; **Exportar CSV** incluye el alcance, cobertura y sesión.
4. **Videos y resultados** permite seleccionar el monitoreo guardado **4feb3f3e**,
   reproducirlo y revisar las líneas y cruces. **Reportes** permite consultar la sesión.
5. Para otro análisis, vuelve a **Vista general**, activa **Prueba con videos**, marca
   cámaras 2, 3 y 4 y pulsa **Analizar videos de prueba**. Conserva los vínculos de las
   líneas con los negocios. Cada ejecución guarda una sesión distinta.
6. El cálculo comercial consulta fecha/hora, no suma todas las ejecuciones del mismo
   archivo. Selecciona la fecha y hora correctas; **Ver prueba guardada** ayuda a
   encontrarlas. Si cambias fecha, hora o tienda, puede faltar historial comparable.
7. Para preparar ocho fechas sintéticas compatibles con otra sesión FINALIZADA de
   prueba, ejecuta desde CMD en la raíz (reemplaza ID_SESION):

```bat
.venv\Scripts\python.exe proyecto_lap_prototipo\tools\preparar_demo_comercial.py ID_SESION
```

No requiere parar la app. Nunca escribe el conjunto real. Es idempotente: conserva
ventas existentes. Exporta los insumos realmente guardados y el resultado en
`proyecto_lap_prototipo/data/commercial-tests/ID_SESION/`.
El botón general **Generar datos de prueba** es una demostración sintética distinta;
no hace falta pulsarlo para ver esta prueba con videos.

Los archivos de esta entrega son `ventas_historicas_SINTETICAS.csv`,
`trafico_historico_SINTETICO.csv` y `resultado.json` en la carpeta de **4feb3f3e**.
El CSV de ventas ya está importado; no lo importes otra vez. El CSV de tráfico es
evidencia/exportación, no se carga en el importador de ventas. El Excel explica y
recalcula; el importador de la app acepta CSV, no XLSX.

## Evaluación del modelo alternativo

Se utilizó el [FastReID oficial](https://github.com/JDAI-CV/fast-reid),
configuración BagTricks ResNet50 y pesos MSMT17 del
[catálogo oficial](https://github.com/JDAI-CV/fast-reid/blob/master/MODEL_ZOO.md).
No se entrenó un modelo nuevo. El exportador valida carga de pesos, normalización
y equivalencia numérica PyTorch/ONNX antes de guardar el archivo.

En 14 recortes idénticos de las tres cámaras, CPU con dos hilos, medianas por llamada:
OSNet ligero 169,6 ms; OSNet-AIN 525,5 ms; FastReID 347,8 ms. Las exportaciones tienen
lotes fijos distintos (16, 4 y 1): son tiempos de este ensayo de una persona por
llamada, NO una comparación completa de rendimiento multicámara ni de precisión.
FastReID produce 2.048 dimensiones, OSNet 512. Más dimensiones no garantizan mejor ReID.

Se conserva OSNet activo. FastReID queda descargado/exportado para evaluación, no como
una opción lista de producción en la interfaz. La herramienta `tools/comparar_reid.py`
acepta parejas positivas y negativas verificadas manualmente para medir umbrales.
Sin ese etiquetado, declara `precisionEvaluated: false`; no usa los propios IDs
automáticos como verdad de referencia. Modelos, repositorio de referencia y recortes
son locales y están excluidos de Git.

## Validación y límites restantes

- 352 pruebas automatizadas pasaron, incluyendo migración real de memoria SQLite a
  PostgreSQL, reapertura, grafo, deduplicación de franjas y protección de conversión.
- Compilación de frontend y verificación TypeScript aprobadas.
- Inicio de análisis desde interfaz con cámaras 2/3/4, cierre natural y persistencia.
- Consulta API de grafo, CSV comercial, muestra guardada y archivo PostGIS correctos.
- Excel sin errores de fórmulas, importes contrastados con el backend; cambio de un
  insumo comprobado; hojas renderizadas y revisadas visualmente.
- Revisión manual de selección de tienda y resultados en Ventas y análisis.

No se garantiza que todas las personas conserven el mismo ID entre cámaras. Falta
un conjunto de correspondencias humanas y una prueba prolongada en vivo para medir
precisión, falsas uniones y pérdidas. También falta verificar físicamente los desfases
de reloj, las rutas y la calibración: un campo marcado como verificado no sustituye
esa comprobación. No se implementaron GPU/cloud por instrucción del usuario.
