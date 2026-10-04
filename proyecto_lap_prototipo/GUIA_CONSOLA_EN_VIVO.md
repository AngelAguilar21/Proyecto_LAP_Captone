# Consola LAP: cámaras, recorridos y zonas de ocupación

La nueva interfaz conecta con `live_server.py`. La consola anterior se conserva en `/?view=replay`. No se modificó el pipeline histórico `main.py` ni el submódulo P2PNet.

## Iniciar

Desde `proyecto_lap_prototipo`, usando el Python que ya tiene las dependencias del proyecto:

```powershell
python live_server.py
```

En otra terminal, desde `proyecto_lap_prototipo/dashboard`, con los módulos ya presentes:

```powershell
node node_modules/vite/bin/vite.js
```

Abrir `http://127.0.0.1:5173`. La interfaz envía `/api` al servidor Python local en el puerto 8765. El botón **Abrir otra vista en ventana** abre el laboratorio o el plano en otra ventana; ambas comparten la misma sesión. Solo una sesión puede usar las cámaras a la vez.

Si existe una compilación actualizada en `dashboard/dist`, el servidor Python también la sirve en `http://127.0.0.1:8765`.

## Primera prueba

1. En **Prueba con cámara**, seleccionar una cámara. Una fuente `0` es la primera cámara USB del equipo que ejecuta Python; también se admite una ruta de archivo o una URL RTSP. No es una cámara del navegador de otro equipo.
2. Seleccionar **YOLO** (predeterminado). Dejar la ruta de pesos vacía para usar `models/yolo11n.pt`. La instalación de este equipo ya está preparada. En otro equipo, instalar las dependencias del proyecto y ejecutar explícitamente `python setup_detector.py --download`. HOG queda como referencia básica.
3. Pulsar **Probar esta cámara**. Ver el video con IDs temporales y el estado real de la fuente. Detener para liberar la cámara o editar geometría.
4. Para probar el plano sin captura, usar **Ver demo**. La interfaz y los IDs indican expresamente que los datos son sintéticos. No hay video real en ese modo.
5. En la vista general, **Iniciar cámaras** procesa las fuentes configuradas. Cada cámara mantiene un tracker independiente. Las fuentes que no abren muestran un error.

No se descargan modelos ni se instalan dependencias automáticamente. P2PNet reutiliza el checkpoint existente. YOLO requiere `ultralytics` y pesos locales compatibles; si faltan, la sesión muestra el error correspondiente. Este trabajo no elige un detector ganador sin evaluación anotada.

## Plano y calibración

- En configuración, crear un plano con ancho y alto o cargar una imagen PNG/JPEG/WebP. Guardar/exportar/importar permite trasladar la configuración completa. El archivo local, excluido de Git, es `config/live.local.json`.
- Añadir cámaras y colocarlas con **Colocar cámara**. El icono es una referencia visual; no define la homografía ni descubre automáticamente la cobertura.
- Obtener un frame iniciando y deteniendo una prueba. Elegir **Calibrar suelo**, marcar una referencia del piso en la imagen y marcar su correspondencia en el plano. Repetir al menos cuatro veces; preferir seis a ocho puntos bien distribuidos. Guardar.
- Las coordenadas del video se guardan normalizadas entre 0 y 1; el cambio de resolución mantiene las correspondencias si la imagen conserva exactamente el encuadre y la relación de aspecto.
- Revisar las correspondencias al mover, girar o hacer zoom en una cámara, cambiar la fuente, sustituir el plano o alterar sus dimensiones. No hay detección automática de esos cambios.
- La homografía solo aproxima puntos del plano del suelo. HOG/YOLO utilizan el centro inferior de la caja como estimación del apoyo de los pies; las oclusiones pueden desplazarlo. P2PNet entrega cabezas: se muestran con IDs en video, pero no se proyectan como pies al mapa ni se usan para asociación geométrica entre cámaras en esta integración.
- Sin medidas físicas, usar unidades relativas. Elegir metros exige haber medido las correspondencias; cambiar el selector no convierte automáticamente una escala relativa. No se informa personas/m².

La interfaz permite dibujar polígonos de zonas y consultar ocupación. Las aglomeraciones se dibujan como círculos: al menos N personas observadas dentro del radio configurado, durante el tiempo establecido. Radio, N y duración pueden ajustarse durante la sesión con **Aplicar reglas**. Guardar después de detener para conservarlos. Cambiar reglas reinicia la permanencia de las alertas.

## Continuidad entre cámaras

- Escribir los IDs de destino en **Cámaras de destino**, separados por comas. Los enlaces son dirigidos: para asociación en ambos sentidos, configurar ambos enlaces.
- En archivos, el offset indica cuántos segundos se omiten al inicio de cada video para alinear el instante cero. Los frames se muestrean por FPS de cada archivo, no suponiendo FPS idénticos. Se procesan pasos de 0.2 segundos de fuente; el procesamiento puede ir más lento que la reproducción normal.
- No se mezclan archivos y cámaras en vivo en una misma sesión. Para streams se usa el reloj local de adquisición; la sincronía de contenido entre cámaras debe verificarse de forma externa. La llegada de dos streams al mismo equipo no garantiza que sus imágenes correspondan al mismo instante.
- Solo se habilita asociación entre cámaras al declarar la sincronización verificada. Se comparan posiciones de suelo, tiempo, enlaces y, si se dispone de cajas, embeddings OSNet (o, sin modelo, histogramas de color del torso). Con cámaras que se solapan la posición manda y la apariencia solo desempata.
- En solape se compara proximidad espacial. En discontinuidades se usa una extrapolación de velocidad suavizada y una ventana temporal. El filtro Kalman del tracker local ayuda con pérdidas cortas dentro de cada cámara; no demuestra identidad en una zona ciega.
- Una asociación aceptada conserva el ID y se etiqueta **estimada**. Candidatos demasiado próximos en puntuación se marcan como asociación incierta con nuevo ID. No se fuerza una fusión para reducir artificialmente el número de IDs. La interfaz no muestra nodos inventados en zonas ciegas.
- No hay garantía de mantener la identidad bajo oclusión intensa, ropa similar o largos recorridos sin cobertura. La estrategia de asociación es una base comprobable, no un sistema validado de reidentificación multicámara.

## Interpretación de zonas futuras

El mapa acumula **personas × segundos observados** por celda fija y muestra los sectores con más ocupación. Deduplica por ID global observado y excluye posiciones predichas. Si una asociación falla y crea dos IDs, puede persistir sobreconteo: debe medirse en validación.

El ranking es una señal exploratoria. No estima rentabilidad, intención de compra ni distingue por sí mismo una cola normal de congestión problemática. El análisis exportado incluye modo, sesión, unidad y tiempo de fuente para distinguir demostraciones de mediciones.

Los recorridos visuales se limitan a 180 posiciones recientes por identidad; los IDs expiran tras la ventana de asociación si no vuelven a observarse. El historial completo y analítica persistente entre sesiones quedan fuera de esta primera integración. No se guardan videos, recortes ni descriptores automáticamente; los datos de sesión están en memoria. La configuración puede contener URLs de cámaras: se excluye de Git y su exportación debe manejarse como configuración interna.

## Validación antes de la entrega

Pruebas añadidas: `tests/test_live_core.py`. Cubren sincronización, solape, asociación ambigua, exclusión de dobles IDs en una cámara, transición con hueco, expiración, calibración y alertas con permanencia. Su estado de ejecución debe comprobarse en la entrega; escribir pruebas no implica haberlas superado.

Comandos previstos, sujetos a las reglas Kluster del proyecto:

```powershell
python -m unittest discover -s tests -p test_live_core.py -v
```

Desde `dashboard`:

```powershell
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
```

En la semana restante, anotar fragmentos separados para ajuste y evaluación: una persona que cambia de cámara, dos que se cruzan, ropa parecida, oclusión y concentración real. Comparar conteo por zona, cambios incorrectos de ID, fragmentaciones, precisión/recall de transiciones y tiempo de alerta. No reutilizar los fragmentos usados para elegir umbrales como única evaluación final.

## Alcance operativo

Servidor restringido a `127.0.0.1`, con control de origen y token para operaciones de escritura. Es un prototipo de operador local, sin login empresarial, gestión de roles, auditoría ni despliegue distribuido. No debe publicarse como sistema del aeropuerto tal como está. No hace reconocimiento facial. Con `models/osnet.onnx` calcula embeddings de apariencia (OSNet) para reidentificar; viven solo en memoria, no se guardan en disco ni se publican por la API, y se descartan con el ID temporal. Que un ID no contenga un nombre no demuestra que toda la información asociada deje de ser dato personal.

Referencias técnicas: [homografía en OpenCV](https://docs.opencv.org/4.12.0/d9/dab/tutorial_homography.html), [tracking en Ultralytics](https://docs.ultralytics.com/modes/track/). El tracker existente del proyecto es una adaptación de ByteTrack a puntos; esta integración no lo presenta como una implementación oficial completa de ByteTrack.

## Verificación de esta actualización

Compilación de producción con TypeScript y Vite completada; 21 pruebas automatizadas aprobadas. Se verificó captura simultánea de camera_A.mp4 y camera_B.mp4 con YOLO: la muestra inicial produjo hasta cinco tracks en B y cinco IDs reaparecieron en varios frames. Esto verifica ejecución, no exactitud ni continuidad entre cámaras; esas métricas necesitan anotaciones manuales.

El servidor sirve la aplicación compilada en http://127.0.0.1:8765; no es necesario iniciar Vite para usarla. El asistente de Configuración permite preparar fuentes, plano y calibración.

## Reidentificación con OSNet, filtros y hardware

**OSNet.** El repositorio incluye `models/osnet.onnx` (OSNet x0.25 entrenado con MSMT17, export de [anriha/osnet_x0_25_msmt17](https://huggingface.co/anriha/osnet_x0_25_msmt17), de un tercero: revisa su licencia antes de redistribuirlo). Si falta, `python tools/preparar_hardware.py --osnet` lo baja e instala `onnxruntime` (`onnxruntime-gpu` con GPU NVIDIA). Cada cámara muestra `reid: osnet` o `reid: color` si no hay modelo. Medido en dos cámaras con ángulos muy distintos, la distancia entre embeddings de una misma persona fue casi igual a la de personas distintas (0.52 contra 0.54): entre cámaras la geometría (calibración) pesa más que la apariencia. Dentro de una misma cámara OSNet sí recupera tracks perdidos.

**Asociar recorridos.** En Monitoreo, ese interruptor activa la asociación entre cámaras. Arranca encendido si el proyecto tiene la sincronización verificada y 2 o más cámaras.

**Falsos positivos.** Dos filtros generales: detecciones dudosas mucho más pequeñas que las personas seguras de esa cámara (gorros, caras de pósters) y tracks inmóviles de baja confianza. Las cajas cortadas por el borde se conservan. Se apagan con `clutterFilter: false` en la configuración. Espejos y vidrios que reflejan personas no se distinguen automáticamente: delimita la zona útil de cada cámara sobre el suelo real.

**Hardware.** `src/hardware.py` detecta CPU, RAM y GPU y elige modelo YOLO, resolución, FP16 y proveedor de OSNet (con GPU NVIDIA: yolo11m a 1280 px, o 1920 px con cámaras elevadas; solo CPU: yolo11n a 960 px). `python tools/preparar_hardware.py` muestra el perfil y `--download` baja los pesos que falten; nada se descarga solo. Con GPU hace falta una versión CUDA de PyTorch: si se detecta una NVIDIA sin CUDA, el sistema avisa y usa la CPU. Se puede forzar con `hardware: "cpu"`, `yoloWeights` o `yoloImgsz`. Los niveles son criterios de diseño, no mediciones por GPU.

**Evaluación sin repetir YOLO.** `tools/capturar_observaciones.py <proyecto>` guarda las observaciones y `tools/evaluar_asociacion.py <archivo.pkl>` mide cambios de ID, retraso hasta el ID definitivo y fusiones dudosas. Sin verdad de campo esas métricas miden estabilidad, no acierto.
