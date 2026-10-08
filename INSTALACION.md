# Ejecutar la versión candidata de AeroTrack

Corte: **4 de octubre de 2026, America/Lima**. Rama candidata:
**`jose/automations-main-integration-v3`**. Combina las revisiones publicadas
`90ba03d7d150d3db3b60b593dca18021ef6e03a0` y
`de44a7ec7dfbe68512b25cef707dc9f23c42d5bf`. El SHA de integración se verifica
con `git rev-parse HEAD`; las dos revisiones de origen no son su SHA final.

La candidata incluye las correcciones REV-01/02/05 y las novedades de `main`.
Se conserva la versión anterior en `jose/automations-main-integration-v2`.
Revisa esta candidata en una **carpeta nueva** para conservar esa copia y sus
parches locales de P2PNet. Los comandos de actualización siguientes se aplican
solamente a una copia que ya esté en la rama candidata indicada.

## Si recibiste esto como `.zip`

1. Descomprímelo en una carpeta con ruta corta (por ejemplo `C:\AeroTrack`; evita rutas muy largas o dentro de OneDrive).
2. Instala **Python 3.12 de 64 bits** (marca «Add python.exe to PATH»). Debe ser la 3.12: con la 3.13 las dependencias fijadas (numpy, scipy) no tienen instalador en Windows. Si ya tienes la 3.13 u otra, no la desinstales: la 3.12 convive con ellas y el instalador la elige solo (`py -3.12`). Node.js **no** hace falta: el paquete ya trae la interfaz compilada.
3. Ejecuta `preparar_sistema.cmd` (solo la primera vez; descarga dependencias y puede tardar varios minutos) y luego `iniciar_sistema.cmd`.
4. Abre http://127.0.0.1:8765. En el primer ingreso se crea el usuario operador.
5. Para probarlo con los videos incluidos, sigue «Prueba rápida en un equipo nuevo» más abajo.

El paquete no incluye proyectos, usuarios, correo, resultados ni videos de nadie: empiezas con un sistema limpio.

## Primera instalación

Los controles de esta integración y sus límites están en
[INTEGRACION_MAIN_20261004](docs/INTEGRACION_MAIN_20261004.md). El registro del
1 de octubre se conserva como antecedente en
[AVANCE_EQUIPO](docs/AVANCE_EQUIPO.md).

## Acceso y versión que se comparte

Repositorio: [AngelAguilar21/Proyecto_LAP_Captone](https://github.com/AngelAguilar21/Proyecto_LAP_Captone).
La URL de clonación está debajo y no contiene credenciales. Se consultó la rama
remota con el acceso Git del equipo de trabajo; no se comprobó acceso anónimo ni
los permisos de cada compañero. Hace falta permiso de lectura y autenticarse
con su propia cuenta cuando GitHub lo requiera. No incluir tokens en comandos,
capturas o documentación ni copiar credenciales de otro equipo.

## Plataforma y preparación

La plataforma documentada es Windows de 64 bits con Git, Python 3.12 AMD64 con el lanzador `py` o como `python`/`python3.12` en el PATH, Node.js con `npm`, acceso a Internet para preparar dependencias y
espacio para entorno, modelos, interfaz y datos. Python y Node deben instalarse
previamente: `preparar_sistema.ps1` comprueba que existan; no instala sus runtimes.

Entorno observado en la revisión Fase 8: Windows 11 build 26200 AMD64,
Python 3.12.10 en `.venv`, Node 24.19.0 y npm 11.17.0. No se ha demostrado aquí
un pipeline equivalente en macOS/Apple Silicon. Estos datos no fijan hardware
mínimo ni capacidad de cámaras.

Para una **instalación nueva** de esta candidata:

```powershell
git clone https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
cd Proyecto_LAP_Captone
git rev-parse HEAD
git branch --show-current
git status --short
```

La rama puede avanzar: conserva el SHA usado en cada validación. No uses estos
pasos para reemplazar un checkout con trabajo local. Los parches del instalador
en P2PNet pueden dejar ese submódulo modificado; no deben limpiarse como parte de
la preparación de esta candidata.

### Actualizar una copia existente

Con el servidor y los escritores propios cerrados, inspecciona primero desde
la raíz de **tu copia**, sin reemplazarla ni descartar cambios:

```powershell
git branch --show-current
git status --short
git fetch origin --prune
git log --oneline --left-right HEAD...origin/jose/automations-main-integration-v3
git diff --submodule=short HEAD..origin/jose/automations-main-integration-v3 -- proyecto_lap_prototipo/external/P2PNet
```

Sólo si ya estás en `jose/automations-main-integration-v3`, la actualización es
fast-forward, no cambió el gitlink de P2PNet y no tienes trabajo propio pendiente
en el repositorio padre:

```powershell
git -c submodule.recurse=false pull --ff-only origin jose/automations-main-integration-v3
git rev-parse HEAD
git status --short
```

El cambio local esperado de P2PNet debe evaluarse aparte: si su gitlink no cambió,
se conserva. El comando evita actualizarlo recursivamente. Si cambió el gitlink,
hay otros cambios propios, otra rama o commits divergentes, detener esta secuencia
y revisar con su autor; no prescribir reset, clean, stash automático, rebase ni
actualización forzada del submódulo. Tampoco volver a ejecutar el preparador sobre
una copia con trabajo propio como supuesto chequeo inocuo.

Para revisar exactamente el SHA publicado sin cambiar tu rama ni tus archivos,
hazlo en una copia nueva, con un nombre de carpeta que no exista. Sustituye
`SHA_PUBLICADO` por el hash comunicado en el cierre de esta entrega:

```powershell
git clone --branch jose/automations-main-integration-v3 https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git AeroTrack-revision-intermedia
git -C AeroTrack-revision-intermedia switch --detach SHA_PUBLICADO
git -C AeroTrack-revision-intermedia submodule update --init --recursive
git -C AeroTrack-revision-intermedia rev-parse HEAD
```

Estos comandos se aplican sólo a la copia nueva; no actualizan el P2PNet de una
copia de trabajo anterior. Inicializar el submódulo obtiene su contenido fijado,
pero todavía falta la preparación de compatibilidad descrita abajo.

### Preparar una instalación nueva

| Terminal | Preparar instalación nueva | Iniciar después |
|---|---|---|
| CMD | `preparar_sistema.cmd` | `iniciar_sistema.cmd` |
| PowerShell | `powershell -NoProfile -ExecutionPolicy Bypass -File .\preparar_sistema.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar_sistema.ps1` |

`preparar_sistema` se usa una sola vez por computadora, o cuando cambien las dependencias. Crea `.venv`, instala las dependencias de Python y Node, descarga los pesos de YOLO, prepara los mapas y compila la interfaz. Puede tardar varios minutos y necesita Internet.

Tampoco se ejecutó el instalador durante esta actualización documental. Estos
comandos se contrastaron con [preparar_sistema.ps1](preparar_sistema.ps1),
[iniciar_sistema.ps1](iniciar_sistema.ps1) e
[iniciar_conteo.ps1](iniciar_conteo.ps1); no son una instalación limpia recién
validada. Aunque el último script se llame «conteo», inicia `live_server.py`
integrado con el Python de `.venv`.

La instalación conserva una configuración existente. En una instalación nueva prepara los cuatro mapas, selecciona nivel 3 y deja vacía la lista de cámaras. Agrega tus videos o cámaras desde Configuración (ver `proyecto_lap_prototipo/docs/GUIA_DE_USO.md`). Los videos, rutas personales y resultados de otro equipo no se distribuyen.

## Modelos

| Componente | Cómo llega al equipo |
|---|---|
| YOLO11n, pesos COCO (detección de personas) | `setup_objects.py --download` descarga el archivo oficial y comprueba una inferencia |
| ByteTrack (seguimiento por cámara) | Código del proyecto en `src/tracking.py`; dependencias en `requirements-vision.txt` |
| OSNet (reidentificación entre cámaras) | `models/osnet.onnx` viene con el repositorio |
| Mapas LAP y frontend | Archivos versionados; `npm ci` instala dependencias y `npm run build` compila la interfaz |

Cómo encajan las piezas: `proyecto_lap_prototipo/docs/ARQUITECTURA.md`.

### Qué proporciona Git y qué falta preparar

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
