# Base multicámara: implementación y pruebas del 7 de octubre de 2026

Rama: `codex/base-multicamara-postgis`. Cambios locales, sin publicar al remoto.

## Qué funciona ahora

- PostgreSQL 17 + PostGIS 3.5 en Docker, puerto local 5433 y volumen persistente. Contraseña generada en `.env`, excluida de Git.
- Archivo transaccional de sesiones, observaciones espaciales, rutas y diagnósticos. Reimportar reemplaza la sesión sin duplicarla. Una importación fallida revierte sus cambios.
- Cola persistente local con reintentos y recuperación al reiniciar. El monitoreo no espera a PostgreSQL. Los archivos originales se conservan.
- Grafo dirigido configurable; filtros por cámaras relacionadas y ventanas temporales antes de comparar apariencia. Las cadenas A→B→C no exigen una arista A→C. El cierre también comprueba el grafo.
- Cámaras 4 y 5 enlazadas como vistas compartidas; se conservaron los enlaces 1↔2 y Tokio 1↔2 y se respaldó la configuración previa.
- Selección explícita de las cámaras que entran al análisis. No se inicia con selección vacía. Se rechaza mezclar archivos y fuentes en vivo antes de abrirlas.
- La validación geométrica ya no rechaza una homografía únicamente porque cubra una parte pequeña de todo el aeropuerto. Continúa comprobando correspondencias repetidas, degeneración, horizonte y consistencia. Una escala físicamente correcta sigue requiriendo referencias reales.
- OSNet ligero y candidato OSNet-AIN MSMT17 seleccionables. Los modelos usan memorias distintas identificadas por la huella de sus pesos. Un modelo solicitado que falta no se sustituye silenciosamente por otro.
- Configuración → Continuidad entre cámaras → Almacenamiento de resultados permite consultar conexión, sesiones archivadas y pendientes.

## Docker o Podman

Se conserva Docker Desktop porque ya estaba instalado y funcionando. Podman también necesita una máquina virtual en Windows; no se midió una ventaja que justifique cambiar de plataforma. Docker aloja la base; la inferencia sigue en Python en el equipo, sin añadir otra capa a la captura local.

Fuentes: [Docker WSL](https://docs.docker.com/desktop/features/wsl/), [Podman machine](https://docs.podman.io/en/latest/markdown/podman-machine.1.html).

## Pruebas conservadas

Están en el proyecto existente **proyecto 3**, que contiene las cámaras 4 y 5; no se creó otro proyecto.

| Sesión | Modelo | Duración procesada | Condiciones |
|---|---|---:|---|
| `cf033017` | OSNet ligero | 41.2 s | Copia de prueba sin homografías; apariencia y tiempo |
| `00f1cf86` | OSNet-AIN | 42.0 s | Copia de prueba sin homografías; apariencia y tiempo |
| `4556c8d8` | OSNet ligero | 41.2 s | Calibraciones guardadas del usuario y grafo explícito |
| `844d4e26` | OSNet ligero | 37.6 s | Iniciada y detenida manualmente desde la interfaz, solo cámaras 4/5, memoria de apariencia activa |

Las dos primeras produjeron los IDs compartidos P00001, P00002, P00003 y P00004 tras el cierre. Esto **no equivale a cuatro personas correctamente reidentificadas**: no hay anotaciones verificadas de todas las correspondencias. Tampoco prueba que AIN sea superior. Los umbrales del modelo ligero no constituyen una calibración validada para AIN.

La tercera prueba terminó sin errores del motor, descartó 542 candidatas por tiempo y realizó 613 comparaciones de apariencia. No se interpretan estas cifras como una mejora porcentual de velocidad frente a otra ejecución con configuración distinta.

La sincronización de las grabaciones fue heredada del indicador del proyecto, no validada manualmente. No se cambiaron los puntos del usuario para conseguir coincidencias. La geometría aprobada por el código no demuestra que el plano corresponda al lugar real del video.

El intento manual `98805e96` incluyó todas las fuentes y falló al abrir una cámara. Motivó el selector explícito y el rechazo previo de fuentes mezcladas; no es una prueba exitosa de ReID.

La prueba manual posterior `844d4e26` confirmó inicio, procesamiento de las dos fuentes y detención con guardado. El perfil preciso automático anterior se mostró entre 3.9 y 7 veces más lento que el video mientras se usaba la interfaz. Ahora Automático en CPU elige Equilibrado a partir de dos cámaras; Preciso sigue disponible explícitamente. Esto reduce resolución/frecuencia de análisis: puede perder detecciones pequeñas o cruces rápidos y no promete tiempo real.

Validación: suite de 345 pruebas (344 aprobadas y una de PostgreSQL omitida por no definir conexión en esa ejecución); la prueba de PostgreSQL se ejecutó por separado contra la base real y aprobó. Verifica idempotencia, coordenadas SRID 0, ausencia de credenciales en metadatos y rollback. Build Vite y TypeScript aprobados. La comprobación manual de almacenamiento mostró 34 sesiones archivadas, sin pendientes, antes de la última prueba.

## Comparación de modelos

YOLO11n y YOLO26n: diez cuadros iguales de las cámaras 4 y 5, resolución 640, CPU, cuatro hilos, calentamiento previo. Mediana: 98.46 ms y 98.72 ms respectivamente. No se midió precisión con ground truth; por eso YOLO11n continúa como detector operativo. YOLO26 se ejecutó con Ultralytics 8.4.174 aislado; el entorno normal se conservó.

Repetir con `tools/comparar_detectores.py`, indicando `--config`, `--cameras D E`, `--models` y `--output`. El JSON incluye los cuadros, conteos y huellas de los modelos. No confundir más detecciones con más aciertos.

OSNet-AIN se descargó del [Model Zoo oficial](https://kaiyangzhou.github.io/deep-person-reid/MODEL_ZOO.html), con pesos MSMT17 y arquitectura x1.0. `tools/preparar_osnet_ain.py` verifica carga estricta de pesos y equivalencia numérica PyTorch/ONNX antes de publicar el archivo. No se entrenó una red nueva. Es más grande que x0.25 y sigue como opción experimental.

KPR/BPBreID y otros modelos por partes todavía no están integrados. Su instalación sola no garantiza mejores resultados; necesitan preprocesamiento específico, pesos adecuados y una evaluación con positivos y negativos difíciles.

## Cómo probar

Desde CMD, dentro de la raíz del repositorio:

```bat
iniciar_base.cmd
iniciar_sistema.cmd
```

La primera orden inicia y comprueba PostgreSQL en Docker. La segunda inicia la aplicación. Docker debe estar abierto y las dependencias de `requirements.txt` instaladas. El backend carga las variables locales de `.env` sin imprimir la contraseña. Si ya están corriendo, basta abrir http://127.0.0.1:8765/.

1. Entrar al proyecto que contiene las cámaras deseadas.
2. Vista general → Cámaras del análisis → marcar solo Cámara 4 y Cámara 5.
3. Mantener Asociar recorridos activo y Prueba con videos para estas grabaciones.
4. Iniciar el análisis. Detener monitoreo permite cerrar y guardar sin esperar al final del archivo.
5. Abrir Videos y resultados y seleccionar la sesión nueva. Reportes e información derivada utilizan las sesiones guardadas.
6. En Configurar proyecto → Procesamiento del equipo se puede elegir OSNet-AIN para una comparación nueva. Los análisis antiguos conservan su modelo y sus resultados.

Para instalar el candidato en otra máquina: instalar `requirements-reid-export.txt` y ejecutar `tools/preparar_osnet_ain.py`. Sus pesos no se suben a Git.

## Actualización: migración operativa completada

Usuarios, configuración, negocios y ventas ahora usan PostgreSQL. Consulta
[Almacenamiento PostgreSQL](ALMACENAMIENTO_POSTGRESQL.md) para el alcance, los
respaldos y las 349 pruebas aprobadas. El iniciador levanta la base automáticamente
en instalaciones migradas. Los videos, la reproducción y la memoria de apariencia
conservan almacenamiento local explícito.

## Límites pendientes, sin presentarlos como terminados

- La memoria operativa de apariencia sigue en SQLite con cálculo en RAM; la reproducción sigue leyendo JSONL y videos locales. El resto de la migración operativa indicada anteriormente quedó completado.
- Falta evaluación anotada de precisión ReID, sincronización verificada de 4/5 y prueba continua de Tokio en vivo con recuperación de red.
- No se desplegó en AWS/GCP ni se contrató GPU. El selector de aceleración requiere runtimes compatibles; no crea capacidad GPU donde no existe.
- No se añadieron KPR, seguimiento de cabeza como identidad independiente ni un detector entrenado de bolsas de compra.
- El repositorio externo continúa excluido en `referencias-locales/`. No se incorporó código de ese repositorio en esta entrega.
