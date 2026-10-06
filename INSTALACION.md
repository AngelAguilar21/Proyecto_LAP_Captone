# Ejecutar AeroTrack desde cero

Requisitos: Windows de 64 bits, Git, Python 3.12 de 64 bits (con el lanzador `py` o como `python`/`python3.12` en el PATH), Node.js 22 LTS con npm, conexión a Internet y varios GB libres. No se requiere GPU. La instalación descarga dependencias y pesos; la velocidad de análisis depende del equipo.

Puedes usar PowerShell o CMD. Los archivos `.ps1` son scripts de PowerShell; si los escribes directamente en una consola que los tenga asociados al Bloc de notas, Windows los abrirá como texto. Los archivos `.cmd` evitan ese problema.

## Si recibiste esto como `.zip`

1. Descomprímelo en una carpeta con ruta corta (por ejemplo `C:\AeroTrack`; evita rutas muy largas o dentro de OneDrive).
2. Instala **Python 3.12 de 64 bits** (marca «Add python.exe to PATH»). Debe ser la 3.12: con la 3.13 las dependencias fijadas (numpy, scipy) no tienen instalador en Windows. Si ya tienes la 3.13 u otra, no la desinstales: la 3.12 convive con ellas y el instalador la elige solo (`py -3.12`). Node.js **no** hace falta: el paquete ya trae la interfaz compilada.
3. Ejecuta `preparar_sistema.cmd` (solo la primera vez; descarga dependencias y puede tardar varios minutos) y luego `iniciar_sistema.cmd`.
4. Abre http://127.0.0.1:8765. En el primer ingreso se crea el usuario operador.
5. Para probarlo con los videos incluidos, sigue «Prueba rápida en un equipo nuevo» más abajo.

El paquete no incluye proyectos, usuarios, correo, resultados ni videos de nadie: empiezas con un sistema limpio.

## Primera instalación

Clona el repositorio con Git y entra a la carpeta:

```powershell
git clone https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
cd Proyecto_LAP_Captone
```

Después ejecuta según tu terminal:

| Terminal | Primera vez: prepara dependencias, modelos y mapa | Cada vez: inicia AeroTrack |
|---|---|---|
| CMD | `preparar_sistema.cmd` | `iniciar_sistema.cmd` |
| PowerShell | `powershell -NoProfile -ExecutionPolicy Bypass -File .\preparar_sistema.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar_sistema.ps1` |

`preparar_sistema` se usa una sola vez por computadora, o cuando cambien las dependencias. Crea `.venv`, instala las dependencias de Python y Node, descarga los pesos de YOLO, prepara los mapas y compila la interfaz. Puede tardar varios minutos y necesita Internet.

`iniciar_sistema` se usa cada vez que quieras trabajar. Inicia el backend y la interfaz compilada en un solo proceso. Deja esa terminal abierta y abre http://127.0.0.1:8765/?view=overview. Para cerrarlo, vuelve a la terminal y presiona `Ctrl + C`.

La instalación conserva una configuración existente. En una instalación nueva prepara los cuatro mapas, selecciona nivel 3 y deja vacía la lista de cámaras. Agrega tus videos o cámaras desde Configuración (ver `proyecto_lap_prototipo/docs/GUIA_DE_USO.md`). Los videos, rutas personales y resultados de otro equipo no se distribuyen.

## Modelos

| Componente | Cómo llega al equipo |
|---|---|
| YOLO11n, pesos COCO (detección de personas) | `setup_objects.py --download` descarga el archivo oficial y comprueba una inferencia |
| ByteTrack (seguimiento por cámara) | Código del proyecto en `src/tracking.py`; dependencias en `requirements-vision.txt` |
| OSNet (reidentificación entre cámaras) | `models/osnet.onnx` viene con el repositorio |
| Mapas LAP y frontend | Archivos versionados; `npm ci` instala dependencias y `npm run build` compila la interfaz |

Cómo encajan las piezas: `proyecto_lap_prototipo/docs/ARQUITECTURA.md`.

## Modo normal y modo de desarrollo

El modo normal con `iniciar_sistema` es el recomendado para usar y demostrar el sistema.

El modo de desarrollo se usa solo si vas a modificar la interfaz y quieres ver los cambios al guardar. Deja `iniciar_sistema` abierto y, en otra terminal:

```powershell
cd proyecto_lap_prototipo/dashboard
npm run dev -- --port 5173 --strictPort
```

Abre http://127.0.0.1:5173. Al terminar, ejecuta `npm run build` en `proyecto_lap_prototipo/dashboard` para actualizar el modo normal (puerto 8765).

## Negocios y ventas

**Negocios y accesos** y **Ventas y análisis** se inician con los mismos comandos; no necesitan un servidor de base de datos adicional (SQLite por proyecto). Consulta `proyecto_lap_prototipo/docs/PLAN_COMERCIAL.md` para importar ventas y vincular accesos.

## Prueba rápida en un equipo nuevo

El repositorio incluye lo necesario para una prueba reproducible: los videos `data/camera_A.mp4` y `data/camera_B.mp4` (la misma explanada vista desde dos ángulos), el modelo `models/osnet.onnx` y una configuración demo (`config/ejemplos/demo_camaras_A_B.json`).

Tras `preparar_sistema`, con el entorno `.venv` del proyecto:

```powershell
cd proyecto_lap_prototipo
..\.venv\Scripts\python.exe tools\prueba_completa.py --seconds 120
```

Levanta su propio servidor en el puerto 8799 con una configuración aislada (no toca tus proyectos), inicia una sesión unificada A+B y comprueba que se detectan personas, que OSNet está activo, que alguna persona se asocia entre cámaras, que la grabación queda con los IDs finales reagrupados y que se calculan los insights. Termina con `PRUEBA COMPLETA OK` o con el motivo del fallo.

Para verlo en la interfaz: inicia el sistema, crea un proyecto nuevo, importa `config/ejemplos/demo_camaras_A_B.json` desde Configuración y pulsa Iniciar con **Asociar recorridos** encendido.

Otras comprobaciones, desde `proyecto_lap_prototipo`: pruebas unitarias (`..\.venv\Scripts\python.exe -m unittest discover -s tests`), comprobaciones de la interfaz (`npm run check:lod`, `check:aislamiento`, `check:seguimiento` y `check:kpis` en `dashboard`) y `tools\preparar_hardware.py` (perfil de CPU/GPU elegido). Cómo se mide la identidad entre cámaras: `docs/EVALUACION_IDENTIDAD.md`.
