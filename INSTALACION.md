# Ejecutar la versión candidata de AeroTrack

Esta guía describe la rama de desarrollo `jose/automations-main-integration-v2`,
con base de revisión Fase 8 en `0b611e0`. No es una versión declarada de producción
ni una afirmación de que estos cambios estén integrados en `main`.

## Plataforma y preparación

La plataforma documentada es Windows de 64 bits con Git, Python 3.12 AMD64 y su
lanzador `py`, Node.js con `npm`, acceso a Internet para preparar dependencias y
espacio para entorno, modelos, interfaz y datos. Python y Node deben instalarse
previamente: `preparar_sistema.ps1` comprueba que existan; no instala sus runtimes.

Entorno observado en la revisión Fase 8: Windows 11 build 26200 AMD64,
Python 3.12.10 en `.venv`, Node 24.19.0 y npm 11.17.0. No se ha demostrado aquí
un pipeline equivalente en macOS/Apple Silicon. Estos datos no fijan hardware
mínimo ni capacidad de cámaras.

Para una **instalación nueva** de esta candidata:

```powershell
git clone --branch jose/automations-main-integration-v2 --recurse-submodules https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
cd Proyecto_LAP_Captone
git rev-parse HEAD
```

La rama puede avanzar: conserva el SHA usado en cada validación. No uses estos
pasos para reemplazar un checkout con trabajo local. Los parches del instalador
en P2PNet pueden dejar ese submódulo modificado; no deben limpiarse como parte de
la preparación de esta candidata.

| Terminal | Preparar instalación nueva | Iniciar después |
|---|---|---|
| CMD | `preparar_sistema.cmd` | `iniciar_sistema.cmd` |
| PowerShell | `powershell -NoProfile -ExecutionPolicy Bypass -File .\preparar_sistema.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar_sistema.ps1` |

La preparación crea `.venv` si falta, comprueba Python 3.12, instala las
dependencias declaradas, ejecuta `pip check`, aplica la compatibilidad de P2PNet,
comprueba su inferencia CPU, descarga/carga YOLO, prepara mapas y ejecuta
`npm ci` y `npm run build`. Requiere Internet y escribe en el entorno/proyecto;
no es una comprobación de sólo lectura. No se ejecutó nuevamente durante la
revisión documental Fase 8.

## Dependencias, modelos y dispositivo

| Componente | Contrato actual |
|---|---|
| Python | `requirements.txt` incluye los requisitos de conteo y comerciales |
| PyTorch | `torch==2.14.0+cpu` y `torchvision==0.29.0+cpu` en `requirements-counting.txt`; perfil CPU |
| P2PNet | Código oficial en submódulo fijado; pesos `external/P2PNet/weights/SHTechA.pth`; `setup_counting.py` aplica el parche y prueba un frame sintético en CPU |
| YOLO11n | Ultralytics 8.3.203; `setup_objects.py --download` prepara `models/yolo11n.pt`, carga el modelo y verifica clases; ese script no ejecuta una inferencia |
| Seguimiento integrado | YOLO proporciona cajas; `src/tracking.py:ByteTrackPuntos` asocia detecciones por cámara; `src/live_core.py` hace asociación entre cámaras |
| Frontend | Dependencias del lockfile con `npm ci`; TypeScript/Vite mediante los scripts existentes |

No hace falta UCF-QNRF para ejecutar pesos preentrenados. Un ZIP del repositorio
no sustituye la inicialización del submódulo mediante Git.

La inferencia sintética de revisión observó **CPU para YOLO y P2PNet**, aun con
una GPU NVIDIA presente. El entorno instalado es CPU-only: no es el caso de
CUDA instalado pero temporalmente indisponible. El conteo independiente pide
CPU explícitamente; P2PNet integrado puede elegir CUDA si otro entorno lo
ofrece; YOLO integrado delega dispositivo al backend porque Engine no lo fija.
Eso no acredita un perfil CUDA reproducible. No hay selector CPU/GPU en la UI.
NVIDIA/CUDA y Apple Silicon/MPS quedan como trabajos posteriores, sin cambiar
dependencias ni drivers en esta fase. Evidencia y límites en
[PRUEBA_LIVE.md](proyecto_lap_prototipo/docs/PRUEBA_LIVE.md).

## Arranque y uso

`iniciar_sistema` sirve backend e interfaz compilada en el equipo local.
Mantén abierta la terminal y visita [AeroTrack local](http://127.0.0.1:8765/?view=overview).
`Ctrl+C` solicita cierre cooperativo. Si aparece «Cierre incompleto», todavía
pueden existir trabajadores: no borres ni reemplaces sus archivos mientras
sigan activos. Un timeout no puede interrumpir por sí mismo una llamada nativa.

La preparación conserva configuración existente. Una instalación nueva prepara
mapas y deja las cámaras por configurar. Rutas, videos y resultados locales
de otro equipo no constituyen fixtures garantizados de instalación.

La prueba de cámara del asistente usa YOLO a 640. El monitoreo integrado solicita
`hybrid`: YOLO principal y P2PNet de densidad bajo demanda de AVIE. El backend
también acepta `yolo`, `p2pnet` y `demo`; son contratos distintos, no un modelo
único. Véase [GUIA_SEGUIMIENTO.md](proyecto_lap_prototipo/docs/GUIA_SEGUIMIENTO.md).
Arranque e inferencia correcta no demuestran precisión de conteo o asociación.

Las automatizaciones permanecen deshabilitadas por defecto. El arranque normal
lee configuración y datos existentes: no sirve como smoke test aislado. No
activar tareas ni cámaras reales para comprobar la instalación sin el alcance
operativo correspondiente. La persistencia efectiva está inventariada en
[INVENTARIO_PERSISTENCIA.md](proyecto_lap_prototipo/docs/INVENTARIO_PERSISTENCIA.md).

## Desarrollo frontend y comprobaciones

Con backend local iniciado y sólo si necesitas desarrollo de interfaz:

```powershell
cd proyecto_lap_prototipo/dashboard
npm run dev -- --port 5173 --strictPort
```

Abre [Vite local](http://127.0.0.1:5173). `npm run build`, desde ese directorio,
actualiza la interfaz servida en 8765. `.\node_modules\.bin\tsc.cmd --noEmit`
comprueba tipos con el ejecutable local instalado. Para
la suite Python, desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s proyecto_lap_prototipo\tests
```

Registra SHA, directorio, intérprete y resultado real; el número de tests de una
guía histórica no acredita la versión actual. No hacen falta instalaciones
adicionales ni iniciar cámaras para ejecutar los tests aislados del proyecto.

## Negocios y ventas

Negocios, accesos, ventas e incidentes usan SQLite por proyecto. Reinicia el
servidor tras actualizar código. La señal opcional de objetos añade inferencia
YOLO aparte del seguimiento y sigue siendo experimental. Consulta
[PLAN_COMERCIAL.md](proyecto_lap_prototipo/docs/PLAN_COMERCIAL.md); sus sesiones
de ejemplo son antecedentes locales, no datos que deban existir en un clon nuevo.
