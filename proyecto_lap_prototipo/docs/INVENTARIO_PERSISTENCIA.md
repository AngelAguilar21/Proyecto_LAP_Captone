# Inventario de persistencia posterior a Fases 1–7

**HECHO VERIFICADO por inspección de código**, base `0b611e0` de la candidata
`jose/automations-main-integration-v2`. Este documento no inspecciona ni revela
valores reales de usuarios, credenciales o fuentes. No declara cumplimiento de
privacidad ni decide aceptabilidad. AT-11 continúa **PARCIALMENTE MITIGADO**.

Las ubicaciones son relativas a `proyecto_lap_prototipo` en arranque gestionado.
Una configuración alternativa cambia algunos roots; no convierte por sí sola
todos los módulos/rutas en un entorno aislado. El usuario del SO que tenga acceso
a los archivos puede leerlos; no se encontró cifrado de estos almacenes.

## Individuales temporales y persistidos

| Almacén / generación | Datos y persistencia | Lectores | Retención / eliminación | Evidencia |
|---|---|---|---|---|
| RAM de `IdentityStore`, una instancia por sesión | ID global temporal, coordenadas, velocidad, historia hasta 180 posiciones, galería de apariencia hasta 12 y eventos hasta 150 | Pipeline, estado HTTP, UI | IDs reiniciados por sesión; expiran por `handoffSeconds`; no se recuperan desde SQLite para reconocer sesiones siguientes | `src/live_core.py:IdentityStore`; `live_server.py:Engine.run` |
| `data/identidad/<project_id>.sqlite`, apertura automática durante tracking | Tabla `identity_observations`: session,pid,camera,t,x,y,association,color BLOB,box_w,box_h,height_m,speed,created; muestra individual por segundo aproximadamente | `IdentityMemory.summary/trajectory` y lectores locales SQLite; no endpoint dedicado localizado | Default 24 h, rango 1–168 h; purga al abrir y cada 600 s de grabación; no tarea activa con aplicación cerrada. `purge_all()` existe como método, no UI. Fallo SQLite al registrar deshabilita memoria | `src/identity_memory.py:SCHEMA/record/purge`; `live_server.py:Engine.run` |
| `data/replays/<session>/manifest.json` y `samples.jsonl` de tracking | Incluso LIVE: IDs, cajas normalizadas, pixel, punto en plano, asociación, historia de 30 posiciones y analítica; configuración/estado de sesión | Reproducción, reportes, recuperación, consultas de negocio, cleanup | Fase 7 sólo borra candidatos vencidos demostrablemente libres; evidencia ligada a cualquier incidente conservado se protege. Deshabilitado por defecto | `live_server.py:Engine.run`; `src/replay.py:ReplayWriter/get`; `src/automation_cleanup.py` |
| Replays de conteo de archivos | Puntos de cabeza por muestra y conteos, sin IDs; referencia al video original | Replay y reportes | Misma política conservadora de recursos; no implica borrar SQLite de conteo | `src/counting/engine.py:CountingEngine.run` |
| Frames y JPEG en RAM | Imagen de fuente con overlays, sin difuminado; buffers actuales/preview | `/api/frame`, UI local | No archivo de captura de frames encontrado en monitoreo; puede quedar último preview en RAM al finalizar. Terminar sesión no equivale a retirar copias guardadas por un cliente | `live_server.py:Engine.run/Handler.do_GET` |
| Pipeline CLI histórico `main.py` | Base indicada por `--salida-bd`: personas y posiciones individuales; CSV por utilidades | Herramientas offline y SQLite | Sin retención general propia localizada; distinto del servidor web | `main.py`; `src/persistence.py` |

Las firmas son histogramas HSV/Lab de franjas del cuerpo, comprimidos a float16
al persistir. Se usan para asociación estimada, con geometría y tiempo; no hay
reconocimiento facial ni Re-ID neuronal en esta ruta. La clasificación regulatoria
de apariencia/medidas no queda resuelta por comentarios que digan «sin biometría».
Un ID temporal no demuestra anonimización de coordenadas ni de una imagen.

La base IdentityMemory no extiende por sí misma la ventana de asociación; el
pipeline escribe allí, pero no la consulta para reconocer personas entre días.
Cerrar sesión cierra la conexión, no borra automáticamente esas filas.

## Agregados, estados durables y auditoría

| Almacén / generación | Datos y persistencia | Lectores | Retención / eliminación | Evidencia |
|---|---|---|---|---|
| `config/counting.sqlite` | `sessions.payload` con configuración y métricas; `samples` con t,count,zones. SQLite excluye points/series del payload, pero conserva muestras agregadas | Conteo, historial, reportes y lectura protectora de cleanup | No retención general. El límite 30 del listado no borra sesiones antiguas. El replay separado puede conservar puntos | `src/counting/storage.py:CountStore`; `src/counting/engine.py` |
| `config/projects/<id>.negocios.sqlite` | Negocios/accesos/referencias, ventas, tráfico, incidentes/detalle, revisión durable/validación legacy, notificaciones y vínculo replay | Negocios/comercial, incidentes, reportes, notificaciones, escalamiento, backup y cleanup | No TTL general. Políticas existentes por operación comercial no equivalen a retención. Incidentes conservados protegen replay independientemente de estado | `src/business_data.py:ESQUEMA`; `src/commercial.py`; `src/cleanup_references.py` |
| `incident_notifications` en DB de proyecto | Estado attempting/failed/sent/uncertain por incidente+kind, timestamps de intento/éxito | Entrega durable y escalamiento | Sent/uncertain bloquean reenvío automático; no se guarda cuerpo, destinatarios ni secreto SMTP en esa tabla | `src/incident_notifications.py`; `src/business_data.py` |
| `config/automation.sqlite` | Ejecuciones, paths/hashes de artefactos, salud actual, auditoría de tareas/cleanup con hora y motivo | Runtime, reports/backups/artifact health, inspección SQLite | Sin retención general; éxito histórico se conserva aunque artefacto desaparezca/corrompa | `src/automation.py`; `src/automation_store.py` |
| Auditoría UI en RAM | Últimas 300 acciones del operador con detalle/hora | `/api/state` y pantalla auditoría | Se pierde con proceso; diferente de auditoría durable de automatizaciones | `live_server.py:Engine.record/snapshot` |
| Logs de terminal | Mensajes HTTP/errores y diagnósticos según ejecución | Operador/proceso que capture stdout/stderr | No política central de archivo/retención localizada; una captura externa tiene su propio ciclo | `live_server.py`; `src/shutdown_control.py` |
| Señal comercial de objetos | Galería de apariencia y asociaciones en RAM; resultados comerciales agregados | Módulo experimental y comercial | Caducidad de galería propia; sin imágenes guardadas por esa señal. No sustituye retención de otros almacenes | `src/bag_signal.py`; `src/commercial.py` |

## Artefactos, configuración y credenciales

| Almacén / generación | Contenido | Lectores | Retención / eliminación | Evidencia |
|---|---|---|---|---|
| `data/uploads/<token>.<ext>` y marcador de completitud | Video original completo, tamaño, identidad filesystem y SHA256; recepción con temporal | Configuración de fuentes, captura, replay, cleanup | Sólo completado verificable, edad estrictamente superior a retención y sin actividad/referencias. Legacy/parciales/desconocidos se omiten | `src/uploads.py`; [UPLOADS_CLEANUP.md](UPLOADS_CLEANUP.md) |
| `data/reports/<proyecto>/...` | PDF comercial agregado fechado de una sesión, no agregado automático de todas las sesiones del día | Archivos locales, verificador de salud; no API/UI nueva de catálogo de PDFs automáticos | Sin retención ni regeneración automática; missing/corrupt requiere intervención | `src/automation_reports.py`; [REPORTES_PROGRAMADOS.md](REPORTES_PROGRAMADOS.md) |
| `config/backups/...` | ZIP verificado de index/JSON proyectos y snapshots consistentes de bases de negocio; manifiesto/hashes | Verificador de salud y operador local; sin restore soportado | Retención de últimos N válidos demostrados; default 7 si habilitado. Copias manuales/huérfanas no se borran indiscriminadamente | `src/automation_backups.py`; [BACKUPS_PROYECTOS.md](BACKUPS_PROYECTOS.md) |
| Configuración de proyectos y legacy | Fuentes, nombres, calibración, zonas, parámetros, posibles rutas/URLs sensibles e imágenes de plano embebidas si fueron importadas | Engine, UI/config API, backup, cleanup | Sin borrado temporal general; borrado de proyecto es otra operación y no garantiza eliminar todos sus derivados | `src/projects.py`; `src/live_core.py`; `src/plan_import.py` |
| `config/automation.local.json` | Horarios, retención, destinatarios supervisores y límites runtime | Servicio/settings local | Persistencia hasta edición; todas tareas disabled por defecto | `src/automation_settings.py` |
| `config/correo.local.json` | Configuración y contraseña SMTP necesaria para autenticar | Mailer local; representación `public()` excluye password | Sin TTL. No volcar archivo en evidencia. Excluido del backup de proyectos actual | `src/notifier.py`; `src/automation_backup_format.py` |
| `config/usuarios.local.json`; sesiones RAM | Usuarios/roles y hashes PBKDF2 con sal propia; sesiones activas en memoria | Auth y administración de usuarios | Administración explícita, duración de sesión 12 h; no cleanup genérico | `src/auth.py` |
| Exportaciones manuales, datos de prueba/copias históricas | CSV/XLSX/PDF y archivos creados por scripts o descargados por operador | Usuarios/herramientas locales | Fuera de cleanup de Fase 7; no inferir eliminación a partir del borrado de un replay | `src/live_reports.py`, utilidades, configuración del operador |

El backup copia JSON de proyecto completo: una URL de cámara con credenciales
embebidas puede entrar en el ZIP si existe en esa configuración. La exclusión de
`correo.local.json` no es una redacción general de todos los secretos. El
manifiesto de tracking LIVE normal omite URL remota; configuración y otros
almacenes no deben suponerse igualmente redactados. El conteo independiente
persiste su configuración, incluida la fuente.

El monitoreo no graba automáticamente video remoto, pero **uploads sí son video
persistido**. Los planos importados pueden ser imágenes codificadas dentro de
configuración. «No persistir frames de inferencia» no significa «ninguna imagen
en ningún archivo».

## Lectura HTTP y separación efectiva

El servidor escucha en 127.0.0.1 y valida Host/Origin/Sec-Fetch-Site. Eso limita
acceso de red/navegador, pero no equivale a comprobar usuario en cada GET:

- GET de replay, state, frame, config e incidents no requiere sesión en la
  ruta inspeccionada. Config devuelve configuración y token de control local.
- GET comercial/negocios exige sesión cuando existen usuarios configurados.
- Historial replay filtra proyecto activo y permite entradas legacy sin
  projectId. Data/video por session no comprueban pertenencia al proyecto activo.
- `replay.report_snapshot` sí comprueba projectId al exportar una sesión.
- No se encontró endpoint dedicado de trayectoria/borrado IdentityMemory.

Evidencia: `live_server.py:Handler.allowed/do_GET`, `src/replay.py:get/public/report_snapshot`.
Este es inventario del acceso existente, no aprobación del control de acceso ni
una ampliación de auditoría o implementación de permisos. Debe compararse con el
requisito de privacidad/autorización que acuerde el equipo.

## Cobertura real de retención y pendientes

Fase 7 sólo elimina replays/uploads demostrablemente seguros. Ante referencias
ambiguas, SQLite con escritura pendiente, actividad, symlinks/junctions o falta
de prueba de completitud, conserva. No borra IdentityMemory, counting, bases de
negocio, PDFs, backups ni copias externas. Backup tiene su retención separada.
Los incidentes conservados protegen evidencia, incluidos atendidos/resueltos/
falsas alarmas. No hay política aprobada de liberación.

Por eso AT-11 permanece parcialmente mitigado: borrar ciertos archivos no
elimina todas las representaciones de una trayectoria ni todas sus copias.
Un DELETE SQL tampoco demuestra borrado físico seguro de páginas/copias del SO.

Decisiones pendientes, sin resolverlas aquí: retención de IdentityMemory y otros
almacenes; liberación de evidencia de incidentes; tratamiento de uploads legacy
y parciales; backup ampliado y restore; acceso local/por proyecto; presentación
humana de historial legacy y entrega uncertain. La clasificación y aceptación
de datos de apariencia/medidas corresponde a revisión de requisitos del equipo.
