# Ejecutar AeroTrack desde cero

Requisitos: Windows de 64 bits, Git, Python 3.12 de 64 bits con el lanzador `py`, Node.js 22 LTS con npm, conexión a Internet y varios GB libres. No se requiere GPU. La instalación descarga dependencias y pesos; la velocidad de análisis depende del equipo.

Puedes usar PowerShell o CMD. Los archivos `.ps1` son scripts de PowerShell; si los escribes directamente en una consola que los tenga asociados al Bloc de notas, Windows los abrirá como texto. Los archivos `.cmd` evitan ese problema.

## Primera instalación

Clona el repositorio con Git y entra a la carpeta:

```powershell
git clone --branch monitoreo-integrado --recurse-submodules https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
cd Proyecto_LAP_Captone
```

Después ejecuta según tu terminal:

| Terminal | Primera vez: prepara dependencias, modelos y mapa | Cada vez: inicia AeroTrack |
|---|---|---|
| CMD | `preparar_sistema.cmd` | `iniciar_sistema.cmd` |
| PowerShell | `powershell -NoProfile -ExecutionPolicy Bypass -File .\preparar_sistema.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar_sistema.ps1` |

`preparar_sistema` se usa una sola vez por computadora, o cuando cambien las dependencias. Crea `.venv`, instala Python y Node, descarga YOLO, prepara P2PNet, verifica ambos modelos y compila la interfaz. Puede tardar varios minutos y necesita Internet.

`iniciar_sistema` se usa cada vez que quieras trabajar. Inicia el backend y la interfaz compilada en un solo proceso. Deja esa terminal abierta y abre http://127.0.0.1:8765/?view=overview. Para cerrarlo, vuelve a la terminal y presiona `Ctrl + C`.

La instalación conserva una configuración existente. En una instalación nueva prepara los cuatro mapas, selecciona nivel 3 y deja vacía la lista de cámaras. Agrega tus videos o cámaras desde Configuración, delimita sus zonas y calibra las referencias. Los videos, rutas personales y resultados de otro equipo no se distribuyen.

## Código y pesos

| Componente | Cómo llega al equipo |
|---|---|
| P2PNet, código oficial | Submódulo Git `proyecto_lap_prototipo/external/P2PNet`, fijado a un commit |
| P2PNet, pesos SHTechA | El submódulo incluye `weights/SHTechA.pth`, aproximadamente 86 MB |
| Compatibilidad P2PNet | `setup_counting.py` aplica el parche versionado y verifica una inferencia CPU |
| YOLO y ByteTrack | Dependencia Ultralytics fijada en `requirements-tracking.txt`; integración en `src/following` |
| YOLO11n, pesos COCO | `setup_tracking.py --download` descarga el archivo oficial y comprueba una inferencia |
| Mapas LAP y frontend | Archivos versionados; `npm ci` instala dependencias y `npm run build` compila la interfaz |

No necesitas UCF-QNRF para ejecutar los modelos preentrenados. Ese dataset se utiliza para experimentos de evaluación o entrenamiento. Descargar un ZIP de GitHub no incorpora el contenido de los submódulos: utiliza Git.

## Modo normal y modo de desarrollo

El modo normal con `iniciar_sistema` es el recomendado para usar y demostrar el sistema. No requiere abrir el puerto 5173.

El modo de desarrollo se usa solo si vas a modificar código de la interfaz y quieres ver cambios al guardar. Primero inicia el backend en una terminal con `iniciar_sistema.cmd` o su comando PowerShell. En una segunda terminal ejecuta:

Mantén `iniciar_sistema.ps1` abierto. En otra terminal:

```powershell
cd proyecto_lap_prototipo/dashboard
npm run dev -- --port 5173 --strictPort
```

Abre http://127.0.0.1:5173. Al terminar cambios de interfaz, ejecuta `npm run build` desde `proyecto_lap_prototipo/dashboard` para actualizar el modo normal de 8765. Para verificar el backend: `.venv/Scripts/python.exe -m unittest discover -s proyecto_lap_prototipo/tests`.

La inferencia CPU y el arranque están separados de la precisión: P2PNet puede sobreestimar en escenas distintas de sus datos de entrenamiento. Contrasta las estimaciones con anotaciones manuales antes de usar umbrales operativos.
