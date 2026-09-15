# Seguimiento de personas

## Uso desde AeroTrack

1. Iniciar el sistema con `iniciar_sistema.ps1` desde la raíz (levanta ambos módulos en el entorno correcto).
2. En **Configuración → Cámaras**, cargar un video o configurar una URL RTSP/IP o cámara USB. Guardar.
3. Ir a **Seguimiento → Pruebas de seguimiento**, seleccionar la cámara e **Iniciar seguimiento**. El modelo predeterminado ya está instalado; no escribir una ruta de pesos.
4. Revisar cajas, IDs temporales y trazos recientes. Pausar para inspeccionar. El tiempo mostrado corresponde al contenido del video.
5. Para el plano y la asociación entre cámaras: usar cámaras fijas, definir área útil, calibrar al menos cuatro puntos de suelo bien distribuidos por cámara, declarar cámaras vecinas y verificar sincronización/desfases sobre el mismo contenido. Iniciar todas las cámaras desde Seguimiento.
6. Dibujar zonas sobre el plano (por ejemplo, interior de un comercio). **Flujo y ocupación** muestra entradas y salidas confirmadas en dos observaciones; **Reportes → Seguimiento → Entradas y salidas** exporta agregados.

Una persona que ya aparece dentro no se registra como entrada. Una pérdida de detección no se registra como salida. Una desaparición superior a un segundo reinicia la evidencia del cruce. Los cruces son eventos, no visitantes únicos. Los IDs pueden fragmentarse o confundirse; medir la precisión con anotaciones antes de interpretar resultados comerciales.

## Instalación en otra laptop

Desde la raíz, con el servidor detenido y el entorno Python creado:

```powershell
.venv/Scripts/python.exe -m pip install -r proyecto_lap_prototipo/requirements-tracking.txt
.venv/Scripts/python.exe proyecto_lap_prototipo/setup_tracking.py --download
```

No instalar simultáneamente `opencv-python-headless` y `opencv-python`: comparten `cv2`. Si el entorno anterior usa headless, desinstalarlo antes de instalar los requisitos. El script descarga YOLO11n oficial, comprueba inferencia CPU y guarda origen y SHA-256 en `models/yolo11n.json`. Los pesos `.pt` no se suben a Git.

## Componentes

| Código | Responsabilidad |
|---|---|
| `src/counting/` | Conteo P2PNet, mapas y episodios de multitudes |
| `src/following/detector.py` | YOLO11n preentrenado COCO: personas, CPU, imagen 960 px |
| `src/following/tracker.py` | ByteTrack oficial: Kalman, asociación IoU en dos etapas, estado por cámara |
| `src/following/appearance.py` | Histograma HSV del torso como apoyo entre cámaras |
| `src/following/source.py` | Recepción IP de imagen reciente con el lector compartido de conteo |
| `src/following/flow.py` | Cruces de zonas con confirmación temporal |
| `src/live_core.py` | Homografía, asociación global por espacio/tiempo/vecindad/apariencia, rechazo de ambigüedades y ocupación |
| `src/live_metrics.py`, `src/live_reports.py` | Agregación y exportación |
| `live_server.py` | Orquesta fuentes, modelos, algoritmos y API de ambos módulos |
| `dashboard/src/aero/CameraPanel.tsx` | Selección, controles, imagen y tiempo de fuente |
| `src/tracking.py`, `src/cross_camera.py` | Implementación histórica por puntos/offline; YOLO web no usa ese tracker |

Flujo: fuente → YOLO → filtro de área útil → ByteTrack por cámara → pies/homografía → asociación global → ocupación y cruces → video/plano/reportes. No se suman resultados P2PNet y YOLO. En CPU se ejecuta un módulo a la vez.

## Modelos y límites

YOLO es un modelo existente; ByteTrack es un algoritmo que no requiere entrenamiento. No necesitan dataset para iniciar. UCF-QNRF sirve para conteo de cabezas, pero no aporta identidades temporales para evaluar seguimiento. Anotar cajas e IDs en fragmentos de sus videos y revisar precisión de detección, cambios de ID, IDF1/HOTA y errores de cruces.

Ultralytics 8.3.203 fijado y YOLO11n. ByteTrack: umbral alto 0.25, bajo 0.1, creación de ID 0.35, coste de asociación 0.8, retención 3 s a 5 muestras/s. Base funcional, todavía no optimizada con anotaciones LAP. Las grabaciones pueden tardar más que su duración real en CPU.

La apariencia es un histograma, **no ReID neuronal**. La continuidad entre cámaras es estimada y requiere calibración/sincronización fiables. No resuelve de manera fiable huecos grandes sin cobertura o ropa idéntica. Los videos grabados caminando permiten probar detección, pero una homografía fija y ByteTrack sin compensación de movimiento no son adecuados para medir flujo con una cámara móvil.

Con LAP deben acordar acceso RTSP/VMS o entrega de grabaciones y marcas de tiempo; muchas cámaras requieren dimensionar servidor/GPU, red y permisos. La laptop no garantiza procesar todas las cámaras del aeropuerto. Las fuentes IP usan hora de recepción local: por sí sola no verifica sincronización del contenido.

Los IDs/recorridos se eliminan al terminar; los agregados de seguimiento permanecen en memoria hasta otra sesión o reinicio. Exportar antes de reiniciar. El video del operador no está difuminado: IDs anónimos no equivalen a anonimización de la imagen.

## Fuentes

- https://docs.ultralytics.com/models/yolo11/
- https://github.com/ultralytics/ultralytics/tree/v8.3.203/ultralytics/trackers
- ByteTrack, ECCV 2022: https://arxiv.org/abs/2110.06864
- Licencia del código/modelos Ultralytics: AGPL-3.0 o Enterprise; revisar https://www.ultralytics.com/license al definir distribución comercial.
