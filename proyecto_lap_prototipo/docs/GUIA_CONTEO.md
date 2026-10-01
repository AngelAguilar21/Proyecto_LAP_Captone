# AeroTrack: conteo y aglomeraciones

Para instalar **todo el sistema integrado**, sigue [INSTALACION.md](../../INSTALACION.md). Los pasos siguientes se limitan al módulo especializado de conteo.


Este módulo procesa una fuente por sesión con P2PNet en CPU. Estima cabezas,
ocupación por zonas, concentración espacial y episodios que superan un umbral
durante un tiempo definido. No requiere plano ni calibración.

## Preparar otra laptop (Windows, Python 3.12 y Node.js)

Desde la raíz del repositorio, en PowerShell:

```powershell
git submodule update --init proyecto_lap_prototipo/external/P2PNet
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r proyecto_lap_prototipo/requirements-counting.txt
.venv/Scripts/python.exe proyecto_lap_prototipo/setup_counting.py
cd proyecto_lap_prototipo/dashboard
npm ci
npm run build
cd ../..
./iniciar_conteo.ps1
```

El módulo está integrado en AeroTrack. Para trabajar en la dirección habitual,
mantener el servidor anterior abierto y ejecutar en una segunda terminal:

```powershell
cd proyecto_lap_prototipo/dashboard
npm run dev -- --port 5173 --strictPort
```

Abrir http://127.0.0.1:5173/?view=overview y elegir **Conteo y aglomeraciones**.
Vite conecta todas las funciones con el mismo backend en 8765. Si ya estaba
ejecutándose una versión antigua del backend, reiniciarla con el Python de `.venv`.
No iniciar dos servidores sobre la misma configuración. La interfaz compilada
también está disponible en 8765; después de editarla, repetir `npm run build`.

La vista general ofrece acceso a los dos análisis. Configuración administra el
proyecto y las cámaras compartidas. Conteo contiene preparación y resultados;
Reportes agrupa el historial de conteo y los reportes de tracking. Las acciones
de conteo aparecen en Auditoría. El borrador de conteo se conserva al navegar por
el panel, y el procesamiento continúa en el servidor. Recargar la página recupera
la configuración guardada, no cambios pendientes. No se ejecutan conteo y tracking
simultáneamente en esta versión para limitar el uso de CPU.

`setup_counting.py` aplica un parche reproducible de compatibilidad al submódulo
y comprueba una inferencia real. `--check` solamente comprueba la instalación.
No hay que modificar manualmente los archivos del modelo.

## Primera prueba

La vista general es un panel de estado: muestra el análisis activo o el último
resultado disponible, identifica su fuente y periodo, destaca zonas e intervalos
y permite abrir informes recientes. No suma conteos de grabaciones independientes.
El plano permanece en Seguimiento, porque los puntos de conteo no representan
posiciones calibradas sobre el suelo.

En Resultados y mapas, video y métricas se presentan lado a lado. Las pestañas
Zonas e Intervalos separan el detalle; la gráfica de evolución es desplegable.
En pantallas estrechas se adapta la distribución para mantener legibles los datos.
La decisión sigue el criterio de información principal visible de un vistazo y
detalle separado de la guía de diseño de Microsoft:
https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips

1. Seleccionar uno de los videos existentes o cargar otro. También se acepta una
   ruta local del equipo que ejecuta el servidor; así se evita copiar archivos
   mayores de 1 GB.
2. Pulsar **Obtener imagen**. Se puede elegir otro segundo para reconocer la escena.
3. Usar toda la imagen o dibujar polígonos sobre las áreas visibles que interesan.
   Las zonas se definen según la posición de las cabezas en la imagen. Excluir
   reflejos, pantallas y otros niveles cuando no deban formar parte del análisis.
4. Asignar nombre, umbral de personas y permanencia a cada zona. El umbral inicial
   es un ejemplo configurable, no un estándar de seguridad aeroportuaria.
5. Pulsar **Analizar video**. Consultar cabezas, concentración instantánea,
   acumulación, conteos y episodios. Se puede pausar una grabación o detenerla.
6. Exportar CSV o JSON desde el análisis o **Sesiones y reportes**.

Comenzar con una muestra por segundo y resolución máxima de 768 píxeles. El video
se analiza por tiempo de contenido, aunque el procesamiento sea más lento que su
reproducción. Aumentar a 1024 o 1536 puede ayudar con cabezas pequeñas, a costa de
tiempo de cálculo. No se promete tiempo real en una laptop sin GPU.

La cámara debe permanecer fija para interpretar zonas y calor acumulado. Un video
que panea o cambia de plano puede servir para explorar el conteo por fotograma,
pero mezcla lugares diferentes en las mismas celdas; su calor acumulado no es un
mapa espacial válido. Separar tomas o estabilizar antes de ese análisis.

## Modelo, datos y significado de las métricas

La interfaz operativa prioriza el resumen del periodo: máximo simultáneo y su
momento, promedio de personas presentes, zonas con concentración e intervalos
con inicio, fin, duración y máximo. El conteo de la última imagen aparece junto
al video con su instante; no representa el total del análisis. La unidad interna
personas × segundos se mantiene para cálculos y datos completos, pero no se
presenta como un número de personas en la pantalla ni en el informe CSV principal.

En Reportes, **Ver resumen** permite consultar también sesiones anteriores.
La fecha de análisis identifica cuándo se procesó la fuente. La fecha de grabación
es opcional y debe introducirse al preparar el video para situar eventos en hora
real; sin ella se utilizan minutos y segundos transcurridos. Los streams muestran
hora de recepción del servidor, no una hora de cámara verificada. Los resúmenes
distinguen grabaciones completas de análisis parciales. No se deduce la fecha de
grabación a partir del nombre del archivo ni de su fecha de carga.

P2PNet es un modelo existente de localización de personas mediante puntos. Se
reutiliza el código oficial de `external/P2PNet` y su checkpoint `SHTechA.pth`,
entrenado en ShanghaiTech A. El hash de pesos y los parámetros quedan en el reporte.
No se entrena al cargar videos y no hace falta descargar UCF-QNRF para inferencia.
UCF-QNRF puede usarse posteriormente para evaluación o ajuste, respetando sus
condiciones de uso; sus imágenes no prueban tracking entre cámaras.

- **Conteo:** estimación en la última muestra. El global usa la unión de zonas;
  una cabeza en dos zonas cuenta una sola vez en el global.
- **Promedio:** ocupación ponderada por el tiempo observado. Se mantiene la última
  muestra hasta la siguiente dentro de la tolerancia de muestreo. No es visitantes
  únicos. Una misma persona puede aparecer en muchas muestras.
- **Concentración instantánea:** distribución de los puntos de la última muestra.
- **Acumulación:** personas × segundos por celda de imagen. Es una aproximación
  temporal de ocupación, no tiempo de permanencia de una persona individual.
- **Episodio:** umbral alcanzado durante la permanencia configurada, a resolución
  del muestreo. Una pérdida prolongada de observación rompe la continuidad.

El calor se normaliza visualmente respecto al máximo mostrado. Sus celdas son
píxeles de imagen, no metros cuadrados: la perspectiva afecta las comparaciones
entre zonas lejanas y cercanas. No proyectar puntos de cabeza directamente al suelo
con la homografía del módulo de tracking. No sumar cámaras superpuestas como si
fueran personas distintas. Este módulo no identifica personas, no reconstruye
trayectorias ni cuenta entradas a tiendas; eso corresponde al módulo de tracking.

## Validación para el curso

Usar muestras de distintas escenas: poca gente, multitud, cabezas pequeñas,
oclusiones y reflejos. Elegir segundos fijos, contar manualmente las cabezas dentro
de las mismas zonas y comparar con los registros CSV. Reportar MAE (promedio del
error absoluto) y RMSE (raíz del promedio del error cuadrático), número de muestras,
resolución, confianza, intervalo y tiempo de procesamiento. Separar videos usados
para ajustar parámetros de los usados para evaluar. Un conteo visible en pantalla
no demuestra precisión; hace falta referencia manual.

```powershell
.venv/Scripts/python.exe -m unittest discover -s proyecto_lap_prototipo/tests -v
```

Las pruebas automáticas verifican lógica y ciclo de ejecución con detecciones
controladas. `setup_counting.py` comprueba carga e inferencia del modelo real;
ninguna de esas pruebas sustituye la evaluación de exactitud en videos de LAP.

En la prueba inicial con los dos archivos del proyecto la inferencia CPU funcionó.
Una sesión completa de unos 36 segundos produjo 37 muestras. La revisión visual
mostró falsos positivos en detalles de tiendas y carteles: ese resultado sirve para
validar el recorrido del software, no para afirmar exactitud. La siguiente tarea
experimental es etiquetar muestras manuales, comparar parámetros y decidir si el
checkpoint necesita ajuste con datos de la escena.

## Organización y persistencia

- `src/counting/source.py`: lectura y tiempo de video.
- `src/counting/engine.py`: ejecución, modelo, pausa y parada.
- `src/counting/analytics.py`: zonas, integración temporal y episodios.
- `src/counting/storage.py`: SQLite y exportaciones.
- `src/counting/api.py`: endpoints `/api/counting/*` del servidor local.
- `dashboard/src/counting/`: preparación, visualización e historial.
- `tests/test_counting.py`: regresiones del módulo.

Configuración local: `config/counting.local.json`. Métricas: `config/counting.sqlite`.
Ambos se excluyen de Git. Se guardan agregados y muestras, no imágenes ni IDs de
personas. Los videos cargados permanecen en `data/uploads` salvo gestión manual
o cleanup habilitado explícitamente. Cleanup está apagado por defecto: sólo
puede eliminar uploads con completitud verificable, edad estrictamente superior
a la retención y sin actividad ni referencias protegidas. Legacy sin marker,
parciales o recursos inciertos se omiten. Véase [UPLOADS_CLEANUP.md](UPLOADS_CLEANUP.md);
no modifica los defaults ni elimina todas las copias derivadas.
El historial conserva las métricas; no vuelve a reproducir los fotogramas anteriores.

## Conexión futura con LAP

La fuente acepta URL RTSP/HTTP mediante OpenCV/FFmpeg, además de archivos. Esta
integración debe probarse con la URL, acceso a red y formato que LAP autorice.
Un stream se detiene en lugar de pausarse. Una desconexión produce un error, no un
conteo de cero. La primera entrega es un prototipo local de una fuente por sesión.
Para varias cámaras simultáneas hacen falta trabajadores por cámara, dimensionar
CPU/GPU, controlar buffers y reconexiones, sincronización y pruebas de carga.
La adaptación del lector no equivale a soportar todas las cámaras del aeropuerto.
