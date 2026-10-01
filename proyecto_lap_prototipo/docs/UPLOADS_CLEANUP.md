# Uploads durables y retención conservadora — Fase 7

La tarea global considera únicamente `data/replays/<sesión>/` y uploads nuevos
completados en `data/uploads/`. La incertidumbre impide borrar. No es una política
completa de retención ni una declaración de cumplimiento de privacidad.

## Defaults y ejecución

```json
{"cleanup": {"enabled": false, "retention_days": 30}}
```

La validación existente exige entero de 1 a 3650 días. Todas las automatizaciones
continúan apagadas por defecto. `live_server.main()` registra explícitamente
`reports`, `backups`, `escalation`, `cleanup`; construir Engine o AutomationService
no ejecuta tareas. Cleanup usa el runtime secuencial y su presupuesto/cancelación;
no crea threads ni espera a que el sistema quede inactivo.

Solo `age > retention_days` permite ser candidato: exactamente en el límite se
conserva el recurso. Upload usa completed_at verificado. Replay exige fecha de
creación ISO con zona horaria y, conservadoramente, que también sean antiguos los
mtime de ambos archivos. Así un replay creado hace mucho pero recién finalizado
no se elimina. Fechas futuras se conservan.

## Recepción de uploads

`POST /api/upload` conserva origen/token, autorización por rol, límite
`0 < Content-Length <= 1 GB`, formatos `.mp4/.avi/.mov/.mkv/.webm/.m4v`, logging y
respuesta `{"path": "ruta absoluta final"}`. Usa `engine.data_root`, también en
tests aislados. El nombre suministrado solo aporta el sufijo validado.

`uploads.receive()`:

1. Reserva un nombre aleatorio de 32 caracteres hexadecimales y un `.part` exclusivo.
2. Mantiene lease de escritura sobre uploads durante toda la recepción/publicación.
3. Lee exactamente los bytes declarados por chunks y calcula SHA-256 al escribir.
4. Hace flush/fsync, comprueba tamaño e identidad y publica el final con os.replace.
5. Obtiene su identidad final, escribe metadata temporal exclusiva y hace flush/fsync.
6. Publica `<token>.<ext>.completed.json` con os.replace. Solo después retorna el
   path y el endpoint responde éxito. Nunca devuelve el `.part`.

El marker contiene exclusivamente format=`aerotrack-upload`, version=1,
status=`completed`, path (basename canónico), completed_at (epoch), expected_size,
final_size, identity y sha256. Identity contiene device, inode/file index, tamaño,
mtime_ns y ctime_ns. No guarda el nombre original, contenido, credenciales ni datos
de personas. El hash sirve para detectar cambios, no es una firma autenticada.

Una excepción elimina solo temporales cuyo device/inode demuestra que pertenecen
a esa operación; no elimina finales desconocidos ni temporales ajenos. Si no
puede probar propiedad, los deja para revisión. Una caída abrupta puede dejar:

| Punto de caída | Resultado y política |
| --- | --- |
| Durante `.part` | Sin evidencia de completitud; el parcial no se borra por cleanup. |
| Tras publicar final, antes del marker | Final con completitud desconocida; se omite. |
| Durante metadata temporal | Final sin marker publicado y posible tmp; se omiten. |
| Tras publicar marker final | Upload verificable; si se perdió la respuesta HTTP, el cliente puede no conocer el resultado, pero la evidencia ya existe. |

No se reconstruyen markers automáticamente. Uploads legacy sin marker siempre
son `omitted / upload_completion_unknown`, independientemente de su antigüedad.

## Verificación y paths

`uploads.completed_fingerprint()` es read-only: exige ruta plana dentro de
uploads, basename canónico, sufijo válido, marker de formato conocido y claves
exactas, tamaños e identidad concordantes, hash de todos los bytes y estabilidad
de archivo y marker durante la lectura. Un marker alterado, archivo reemplazado,
hash distinto o hard link impide la elegibilidad.

`path_security.py` es un helper independiente: uploads no importa cleanup.
Rechaza `..`, componentes ambiguos, NUL, ADS, drives relativos, nombres reservados,
UNC/namespace especiales, symlinks, junctions y reparse points en ancestros. Los
archivos deben ser regulares, con inode demostrable y nlink=1. No se recorren
destinos de links. Los strings con `://` se excluyen del análisis de paths locales.

Los fingerprints de replay incluyen identidad del directorio y, para cada archivo,
device/inode, tamaño, mtime/ctime y SHA-256. Se exige exactamente la estructura
actual de ReplayWriter: `samples.jsonl` y `manifest.json`, sin extras ni faltantes.

## Referencias durables de incidentes

La migración aditiva crea `incident_replay_links(incident_id, resolution,
session_id)`, con PK/FK y restricciones linked/unknown. No cambia IDs ni borra
datos históricos. Se llena desde `detalle` ya persistido, no desde una nueva
observación de un incidente existente. `detalle.sesion` válido (8–32 caracteres
hexadecimales) produce linked; si no es demostrable produce unknown y NULL.

La lectura de cleanup nunca llama a business_data.connect ni migra. Acepta un
esquema legacy sin links cuando detalle conserva una sesión válida. Si hay link,
debe coincidir exactamente con detalle. Missing/invalid session, unknown, link
contradictorio, fila huérfana, esquema desconocido o base ilegible impiden afirmar
ausencia de referencias. Se conservan replays de **todos los incidentes retenidos**,
incluidos revisados, resueltos y falsas alarmas.

`reference_lock` coordina creación/migración de enlaces con APPLY. El registro
normal conserva el lock hasta el commit. Engine.dispatch_alerts lo mantiene durante
todo su lote con commit=False, incluido commit/rollback. Otros llamadores que
usen commit=False deben respetar el mismo contrato. La referencia y el incidente
se confirman juntos; un plan anterior a un nuevo enlace no autoriza borrarlo.

Los backups SQLite de Fase 5 conservan naturalmente la nueva tabla y sus valores;
no se cambia el formato del ZIP.

## Inventario de referencias

Cleanup es global, a diferencia del escalamiento. Lee todos los proyectos del
índice validado, incluyendo proyectos no activos y JSON huérfanos conservados,
configuración legacy live/cámaras, configuración counting, configuración activa y
runtime capturada, historia counting completa sin LIMIT de UI, bases de negocios
retenidas (incluidas huérfanas), enlaces/detalle de incidentes y campos textuales
de tablas comerciales conocidas. También lee fuentes y paths de manifests de
otros replays; no interpreta su propio campo session como una referencia externa.

Un índice corrupto, identidad duplicada, proyecto faltante, JSON inválido,
almacenamiento de proyectos desconocido o información ilegible produce
`uncertain_references`. No se ignora silenciosamente un proyecto para permitir
borrado de recursos globales.

Las lecturas SQLite usan mode=ro, query_only y no crean bases ni migraciones.
Para garantizar que PLAN tampoco cree/modifique WAL/SHM, se usa immutable
**solo después de rechazar WAL/journal no vacíos**. Con sidecars pendientes se
omite cleanup: nunca se ignoran sus filas para declarar un recurso libre. No se
fuerza checkpoint ni recuperación; una operación posterior normal de SQLite puede
consolidarlos. Se comprueba identidad antes/después de leer. Este comportamiento
es deliberadamente más conservador que intentar operar sobre una base activa.

## PLAN y APPLY

`plan_cleanup()` no elimina, renombra, repara markers, escribe auditoría ni crea
SQLite. Produce Decision(path, disposition, reason, fingerprint):

- protected: recurso reciente, sesión activa, referencia conocida o lease concreto.
- omitted: completitud desconocida/inválida, estructura insegura, actividad o
  referencias inciertas.
- candidate: expirado, identidad conocida y sin protección demostrada.

El wrapper captura Engine/Counting bajo locks sin esperar. Si un lock o el estado
de actividad no es confiable, se omiten candidatos. APPLY toma por cada candidato
el gate de recursos, Engine, Counting si existe y referencias; todos con adquisición
no bloqueante. Excluye únicamente la actividad del thread actual del scheduler de
la cuenta global: otros HTTP requests/workers, escritores de notificaciones o
resultados pendientes bloquean la eliminación. Los leases concretos protegen tanto
un recurso como sus ancestros/descendientes.

Para cada candidato, APPLY reconstruye el plan con referencias y actividad
actuales y compara el fingerprint y la decisión. Si cambia, retorna
`omitted / plan_changed`. Después de registrar delete_planned vuelve a validar;
no confía en un plan antiguo ni en paths forjados. Los locks coordinan los
productores de la aplicación durante decisión y eliminación, y se liberan ante
excepciones. Se comprueba cancelación durante escaneo/hash y antes de eliminar.

No se usa rmtree ni borrado recursivo. Para replay se borran samples, manifest al
final y luego solo el directorio vacío. Para upload, final exacto y marker exacto.
Se comprueba de nuevo cada fingerprint antes de su unlink. Un fallo parcial deja
estructura incompleta o marker huérfano que el siguiente planner omite; no intenta
terminar automáticamente ese borrado.

AutomationStore audita path relativo, decisión y motivo: delete_planned antes
del primer unlink, deleted al finalizar, delete_failed_or_changed ante fallos.
También registra resultados protegidos/omitidos. Si falla la auditoría previa,
no borra. Si falla el registro posterior, queda delete_planned y la tarea falla;
filesystem y SQLite no forman una transacción atómica. No se continúa borrando
otros candidatos después de ese error. No se registran videos ni secretos.

## Alcance excluido, límites y producto

No se borra config, projects, automation.sqlite, counting.sqlite, bases de negocio,
IdentityMemory, reports, backups, modelos, P2PNet, proyectos ni videos externos.
La retención de backups continúa perteneciendo exclusivamente a Fase 5.

AT-11 queda **PARCIALMENTE MITIGADO**. Sigue pendiente comparar con requisitos
aprobados la retención de IdentityMemory, counting, bases comerciales, reportes,
backups y otras copias derivadas. No se declara cumplimiento completo de privacidad.
La liberación futura de evidencia ligada a incidentes y el tratamiento de uploads
legacy/parciales son decisiones de producto; por ahora siempre se conservan.

La coordinación es de un proceso AeroTrack con sus productores cooperantes. No
autoriza varios servidores, edición directa de SQLite ni mutadores externos
concurrentes en esos directorios: la revalidación detecta cambios observables,
pero no equivale a una exclusión filesystem frente a un proceso privilegiado.
Los timestamps dependen del reloj local; los markers no autentican a quien pueda
reescribir archivo y metadata. fsync y replace no sustituyen pruebas de corte
eléctrico del dispositivo. Escanear/hash de todos los candidatos y replanificar
por candidato puede ser costoso; el presupuesto cancela cooperativamente y puede
postergar retención en almacenes grandes. Un sistema ocupado prefiere conservar.

Tests usan datos sintéticos y TemporaryDirectory. Hard links se prueban realmente;
symlinks/reparse/junctions se simulan para no exigir privilegios de Windows. No hay
SMTP real, cámaras, RTSP, cleanup de datos del usuario ni dependencias nuevas.
Restore, UI extensa e integración final permanecen fuera de esta fase.
