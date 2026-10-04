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

**REQUIERE CORRECCIONES:** REV-03/04/06 y la causa histórica de NMS siguen
pendientes. El piloto CPU verificado el 4 de octubre utilizó `90ba03d`, no esta
integración. Se acreditaron captura real e inferencias y entrega HTTP de imágenes;
la confirmación visual y el motivo por el que cesaron las solicitudes de frames
al final de ese piloto siguen pendientes. No se acredita aquí LIVE/CUDA de la
candidata ni una instalación completa desde un clon limpio.

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
git clone --branch jose/automations-main-integration-v3 --recurse-submodules https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
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

La preparación crea `.venv` si falta, comprueba Python 3.12, instala las
dependencias declaradas, ejecuta `pip check`, aplica la compatibilidad de P2PNet,
comprueba su inferencia CPU, descarga/carga YOLO, prepara mapas y ejecuta
`npm ci` y `npm run build`. Requiere Internet y escribe en el entorno/proyecto;
no es una comprobación de sólo lectura. No se ejecutó nuevamente durante la
revisión documental Fase 8.

Tampoco se ejecutó el instalador durante esta actualización documental. Estos
comandos se contrastaron con [preparar_sistema.ps1](preparar_sistema.ps1),
[iniciar_sistema.ps1](iniciar_sistema.ps1) e
[iniciar_conteo.ps1](iniciar_conteo.ps1); no son una instalación limpia recién
validada. Aunque el último script se llame «conteo», inicia `live_server.py`
integrado con el Python de `.venv`.

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

### Qué proporciona Git y qué falta preparar

El submódulo oficial está declarado en [.gitmodules](.gitmodules):
`TencentYoutuResearch/CrowdCounting-P2PNet`, gitlink
`5c91a81ca062b1c7fd3db3ad1c55b1c21f0a7455`. El checkpoint ShanghaiTech A
`weights/SHTechA.pth` **sí está versionado dentro de ese submódulo**; la exclusión
`*.pth` del repositorio padre no lo elimina. En cambio, `models/yolo11n.pt` es un
activo local no versionado. [setup_objects.py](proyecto_lap_prototipo/setup_objects.py)
lo obtiene mediante `attempt_download_asset` de Ultralytics desde sus assets
oficiales y comprueba las clases. El proyecto no fija un SHA de descarga en ese
script; los hashes observados históricamente figuran en
[FASE8_VALIDACION.md](proyecto_lap_prototipo/docs/FASE8_VALIDACION.md).

Los cambios locales conocidos de P2PNet en `models/backbone.py` y `util/misc.py`
son compatibilidad necesaria del entorno documentado: evitan cargar pesos
ImageNet heredados y corrigen el manejo de versión de Torchvision. No se copian
como diff mediante clone/pull. La receta **ya versionada**
[aplicar_parche_p2pnet.py](proyecto_lap_prototipo/src/aplicar_parche_p2pnet.py),
invocada por [setup_counting.py](proyecto_lap_prototipo/setup_counting.py) y por el
preparador, aplica esos ajustes de forma idempotente y rechaza fuentes distintas
a las esperadas. No compartir ni limpiar el submódulo sucio para transmitirlos.
Los `__pycache__` generados tampoco son activos a publicar.

La receta existe y su uso previo está documentado; **no se comprobó aquí todo el
proceso desde un clon limpio** ni se volvió a aplicar. Incluso
`setup_counting.py --check` carga el modelo y hace inferencia: no es un chequeo
meramente estático. Una descarga o dependencia ausente debe diagnosticarse con
su error; no suplantar NMS, cambiar de modelo o instalar CUDA para ocultarlo.

### Versiones observadas y límites de reproducción

El diagnóstico NMS del 1 de octubre volvió a observar Python 3.12.10 AMD64,
torch 2.14.0+cpu, torchvision 0.29.0+cpu, NumPy 2.0.2, OpenCV 4.12.0.88 y
Ultralytics 8.3.203. Node 24.19.0/npm 11.17.0 son versiones observadas en la
validación anterior; no son una nueva medición ni todos los scripts las exigen.

[requirements.txt](requirements.txt) y los requisitos incluidos fijan los
componentes principales, pero `pandas`, `tqdm`, `PyYAML` no están fijados y
`yt-dlp` tiene sólo un mínimo. No existe un lock completo de Python que pruebe
identidad de instalaciones futuras. El frontend sí utiliza
[package-lock.json](proyecto_lap_prototipo/dashboard/package-lock.json) mediante
`npm ci`. No se actualizaron dependencias ni lockfiles para redactar esta guía.

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

### Primer acceso y configuración de prueba sin secretos

En un entorno nuevo, la interfaz ofrece **Crear primer usuario**, que queda con
rol **operador**; después muestra **Entrar**. No hay usuario/contraseña universal.
Cada responsable elige su propia contraseña; el mínimo actual es seis caracteres.
Los nombres de roles no implican una jerarquía convencional: operador configura
y gestiona usuarios; administrador consulta y ajusta umbrales. El alcance exacto
está en [auth.py](proyecto_lap_prototipo/src/auth.py); no afirmar que el login
protege uniformemente todas las rutas de lectura (R-01 sigue pendiente).

Las sesiones son locales en memoria y al reiniciar hay que entrar otra vez.
Si el almacén de usuarios es inválido o ilegible, el servidor rechaza el acceso
con 503: no borrarlo ni crear otro primer usuario como recuperación improvisada.

En una instalación nueva, [setup_workspace.py](proyecto_lap_prototipo/setup_workspace.py)
crea `config/live.local.json` sólo si falta, usa mapas versionados niveles 1–4,
selecciona nivel 3 y deja `cameras: []`, `setupComplete: false`. El arranque
incorpora la configuración inicial como «Proyecto principal». En la interfaz
puede crearse un proyecto «Prueba equipo» sin fuentes hasta disponer de un
alcance y una fuente autorizados. Los ejemplos heredados A/B no aportan videos
incluidos ni calibraciones válidas para una cámara nueva.

Ejemplo del contrato de `config/automation.local.json`, sin tareas habilitadas
ni destinatarios, conforme a
[automation_settings.py](proyecto_lap_prototipo/src/automation_settings.py):

```json
{
  "timezone": "America/Lima",
  "reports": {"enabled": false},
  "backups": {"enabled": false},
  "escalation": {"enabled": false, "recipients": []},
  "cleanup": {"enabled": false}
}
```

Es una referencia de formato para una configuración nueva, no una instrucción
de sobrescribir la de un compañero. La ausencia del archivo también deshabilita
las cuatro tareas. Correo permanece deshabilitado; no hace falta configurar SMTP
para abrir la interfaz. `correo.local.json`, `usuarios.local.json`, proyectos,
bases locales, pesos y videos no deben incluirse en una entrega documental.

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

Una configuración existente puede tener tareas ya habilitadas: el arranque no
las deshabilita ni aísla los datos automáticamente. `--config-path` y
`testRun:true` tampoco constituyen por sí solos un sandbox completo. Para una
prueba aislada hay que revisar todas las raíces de datos, servicios y salidas;
no basta con cambiar el nombre del proyecto.

## Estado y procedimiento del piloto LIVE

El procedimiento siguiente conserva el contexto del intento del 1 de octubre.
Para el estado posterior y los límites de esta integración, consultar
[INTEGRACION_MAIN_20261004](docs/INTEGRACION_MAIN_20261004.md).

El [protocolo LIVE existente](proyecto_lap_prototipo/docs/PRUEBA_LIVE.md) conserva
su carácter histórico de propuesta; no es por sí solo un script validado ni una
autorización para abrir fuentes. El usuario adoptó después el encargo externo
`LAP_Piloto_LIVE_Controlado_NMS_Abierto.md`: permite un único ensayo experimental
de 300 segundos con la fuente ya autorizada, aunque la causa histórica de NMS
siga desconocida. Para este ensayo sustituye la condición causal anterior por
preparación verificada, precheck en el mismo proceso y detención ante fallos
actuales. Aquella excepción no autorizaba publicar; la autorización intermedia
posterior se describe al inicio. Los informes anteriores permanecen intactos.

Resultado del intento del 1 de octubre a las 22:13 (Lima): **piloto no iniciado;
cámara no abierta; 0 s LIVE**. La única validación del host duró 16.109756 s y
terminó con código 2. Pasaron sus 12 controles negativos esperados de las
guardas; durante la primera carga de YOLO/Ultralytics aparecieron bloqueos
inesperados de DNS para `one.one.one.one` y `dns.google`, seguidos por el bloqueo
de una lectura de `.git`. Esas llamadas no salieron a la red externa.
No se completó la carga de modelos ni hubo inferencias, muestras o capturas.
No hubo servidor atendiendo ni imagen procesada en UI acreditada.

Se comprobó el cierre: estado `quiescent=true`, sólo `MainThread` al registrar
el cierre y PID propio ausente después. No se hizo un segundo arranque. El probe
explícito NMS no llegó a ejecutarse y el error histórico no se reprodujo:
**NMS sigue abierto, causa no demostrada**. Los probes previos aprobados no
sustituyen el precheck que faltó en este proceso. Véase E5 en
[AVANCE_EQUIPO](docs/AVANCE_EQUIPO.md) para evidencia y límites.

La webcam integrada Lenovo Legion del equipo original fue identificada como
`Integrated Camera`, índice **DirectShow 0**, y tiene autorización para un piloto
de cinco minutos. No equivale al índice 0 de otro backend ni autoriza cámaras
de compañeros. No se necesita pedir nuevamente permiso para esa misma webcam;
sí revalidar su identidad por metadata antes de usarla. Cada otro equipo necesita
identificar inequívocamente su fuente y obtener su propio alcance operativo.
No explorar otras cámaras o streams.

El borrador antiguo `pilot_live_host.py` de prioridad LIVE permanece intacto y
no ejecutado. El nuevo `pilot_host.py` externo es **NO VALIDADO**: su primer
control sin cámara falló. Ninguno está incluido en Git ni es un comando de
producción de esta guía. No repetir arranques para buscar un resultado verde.

Antes de abrir captura, el criterio experimental exige demostrar raíces de
prueba separadas, correo/automatizaciones apagados, red externa bloqueada y
detención controlada, con plazos de arranque, falta de avance y cierre declarados.
En el mismo proceso del host deben cargar los detectores reales del perfil
integrado, pasar NMS CPU con resultado `[0,2]` e inferencia sintética de sus
componentes, y comprobar CPU efectivo. Si la UI solicita `hybrid`, se mantienen
YOLO y P2PNet/AVIE. Preparar o precargar componentes deliberadamente debe quedar
registrado; no reproduce necesariamente el arranque histórico.

La ventana autorizada es de 300 segundos desde la primera muestra real
procesada; no sumar intentos. Una pausa/reanudación cuenta dentro de esa ventana
y se informa aparte, sin llamarla procesamiento continuo ni desconexión física.
Los frames sólo pueden mostrarse en memoria: sin guardar video, audio, imágenes
ni capturas de pantalla que contengan la cámara. Se exige verificar imagen
procesada y observaciones en la UI, métricas con método declarado y cierre real
de recursos. Ante fallo nuevo, falta de avance o violación de aislamiento,
interrumpir conservando la primera evidencia, sin cambiar de modelo/dispositivo.
Un timeout no acredita finalización de escritores ni autoriza liberarlos.

Este recorrido no se ha acreditado de extremo a extremo en Windows. Incluso un
piloto completado no repararía NMS ni validaría estabilidad prolongada, RTSP,
multitudes, precisión física, CUDA o instalación limpia. No añadir otra fuente
ni ensayos de 30 minutos. REV-03/04/06 y el dictamen global siguen pendientes.

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
guía histórica no acredita la versión actual. Las últimas validaciones se
hicieron con un runner externo que bloquea datos operativos, SMTP, capturas
reales, escritura fuera de temporales y red no loopback. El comando de discovery
anterior no instala esas guardas por sí mismo; no equipararlo sin más con esa
ejecución aislada ni aplicarlo a una copia con datos operativos para acreditar
la misma seguridad. Los tests P2PNet existentes cargan pesos y su imagen oficial
local; esa excepción autorizada no representa una cámara LIVE. La tarea
documental anterior no ejecutó pruebas, build, inferencia ni instalación. Esta
actualización incorpora el control externo fallido del host E5, separado de las
suites históricas; no se repitió la suite completa ni la batería frontend.

El proxy de desarrollo Vite apunta al backend 8765. El arranque acepta otro
puerto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar_sistema.ps1 -Port 8766
```

Cambiarlo no actualiza el proxy de Vite. Usar el mismo puerto documentado para desarrollo o revisar esa
configuración explícitamente, sin atribuir una desconexión al detector.

## Qué está verificado y qué queda pendiente

| Control | Alcance de la evidencia disponible |
|---|---|
| Rama y SHA compartidos | Integración de `90ba03d` y `de44a7e`; comparar HEAD con el cierre y la rama candidata remota. No prueba acceso de cada compañero |
| Comandos, rutas y configuración de ejemplo | Revisión estática de scripts/código; instalación completa y prueba de videos no ejecutadas en esta integración |
| Entorno instalado y modelos CPU | Validaciones históricas identificadas en [AVANCE_EQUIPO](docs/AVANCE_EQUIPO.md), con sus fallos y límites |
| Clon limpio + preparación + primer arranque | Pendiente de verificación de extremo a extremo; no se hizo una instalación para redactar esta guía |
| Parche P2PNet | Receta versionada existente; cambios locales preservados y excluidos de la entrega |
| Causa inicial NMS | Pendiente; no inferir incompatibilidad, DLL o CUDA por el nombre del operador |
| Preparación del host experimental | E5 fue el intento fallido del 1 de octubre; pilotos posteriores CPU de `90ba03d` completaron. No se ejecutó aquí el host Windows integrado |
| LIVE Windows e imagen procesada en UI | Piloto de `90ba03d`: 300.188 s, captura/inferencia real y frames HTTP; confirmación visual pendiente. LIVE de esta integración aún no probado |
| macOS/MPS y NVIDIA/CUDA integrados | No acreditados por las pruebas Windows/CPU ni por el antecedente MacBook reportado |

Los originales externos de pruebas se identifican por ejecución en
[AVANCE_EQUIPO](docs/AVANCE_EQUIPO.md); no se incluyen logs completos, entornos,
vault, conversaciones, bases ni medios. Las guías históricas conservan sus
fechas: `GUIA_CONSOLA_EN_VIVO.md` no debe usarse como contrato vigente de login
o persistencia; REV-04/06 y R-01 mantienen limitaciones documentadas.

## Negocios y ventas

Negocios, accesos, ventas e incidentes usan SQLite por proyecto. Reinicia el
servidor tras actualizar código. La señal opcional de objetos añade inferencia
YOLO aparte del seguimiento y sigue siendo experimental. Consulta
[PLAN_COMERCIAL.md](proyecto_lap_prototipo/docs/PLAN_COMERCIAL.md); sus sesiones
de ejemplo son antecedentes locales, no datos que deban existir en un clon nuevo.

## Prueba rápida en un equipo nuevo (reidentificación OSNet)

La herramienta de `main` se conserva para su evaluación; su prueba completa aún no se ejecutó en esta integración. No sustituye el piloto con guardas ni acredita estabilidad LIVE. El repositorio incluye los videos `data/camera_A.mp4` y `data/camera_B.mp4` (la misma explanada vista desde dos ángulos), su calibración (`config/calibracion.json`, `config/alcance.json`), el modelo `models/osnet.onnx` y una configuración demo (`config/ejemplos/demo_camaras_A_B.json`).

Tras `preparar_sistema`, con el entorno `.venv` del proyecto:

```powershell
cd proyecto_lap_prototipo
..\.venv\Scripts\python.exe tools\prueba_completa.py --seconds 120
```

Levanta su propio servidor en el puerto 8799 con una configuración aislada (no toca tus proyectos), inicia una sesión unificada A+B y comprueba que el servidor responde, que se detectan personas, que OSNet está activo (`reid: osnet`) y que alguna persona se asocia entre cámaras. Termina con `PRUEBA COMPLETA OK` o con el motivo del fallo.

Para verlo en la interfaz: inicia el sistema, crea un proyecto nuevo, importa `config/ejemplos/demo_camaras_A_B.json` desde Configuración y pulsa Iniciar con **Asociar recorridos** encendido.

Otras comprobaciones: pruebas unitarias (`..\.venv\Scripts\python.exe -m pytest tests -q`), `tools\probar_reid.py` (compara OSNet contra color sobre estos mismos videos) y `tools\preparar_hardware.py` (perfil de CPU/GPU elegido).
