# Ejecutar AeroTrack desde cero

Requisitos: Windows de 64 bits, Git, Python 3.12 de 64 bits con el lanzador `py`, Node.js 22 LTS con npm, conexión a Internet y varios GB libres. No se requiere GPU. La instalación descarga dependencias y pesos; la velocidad de análisis depende del equipo.

En PowerShell:

```powershell
git clone --branch monitoreo-integrado --recurse-submodules https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
cd Proyecto_LAP_Captone
.\preparar_sistema.ps1
.\iniciar_sistema.ps1
```

Abre http://127.0.0.1:8765/?view=overview. El servidor entrega la interfaz compilada; no necesitas otro servidor. Si PowerShell bloquea scripts, puedes ejecutarlos mediante `powershell -ExecutionPolicy Bypass -File .\preparar_sistema.ps1` y la misma opción para iniciar; esto no cambia permanentemente la política del equipo.

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

## Desarrollo en el puerto 5173

Mantén `iniciar_sistema.ps1` abierto. En otra terminal:

```powershell
cd proyecto_lap_prototipo/dashboard
npm run dev -- --port 5173 --strictPort
```

Abre http://127.0.0.1:5173. Para verificar el backend: `.venv/Scripts/python.exe -m unittest discover -s proyecto_lap_prototipo/tests`.

La inferencia CPU y el arranque están separados de la precisión: P2PNet puede sobreestimar en escenas distintas de sus datos de entrenamiento. Contrasta las estimaciones con anotaciones manuales antes de usar umbrales operativos.
