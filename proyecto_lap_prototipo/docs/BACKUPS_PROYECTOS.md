# Backups de proyectos — Fase 5

Esta tarea respalda proyectos, no el sistema AeroTrack completo. El ZIP es un
artefacto verificable; **no es una interfaz de restauración soportada**. Esta fase
no añade restore, escalamiento, cleanup general, UI ni dependencias.

## Inventario confirmado y alcance

El código moderno usa un árbol plano en `config/projects/`. En el checkout
inspeccionado había un índice, dos configuraciones y dos bases de negocios; no
había otros tipos de archivo dentro del árbol.

| Incluido | Productor / contenido |
| --- | --- |
| `index.json` | `projects.write_index`: proyecto activo y lista de proyectos |
| `<projectId>.json` referenciado por el índice | `projects.create`, `Engine.configure`, migración de IDs de zonas en `Engine.read_config_file`: configuración completa, planos, cámaras y reglas |
| `<projectId>.negocios.sqlite` | `business_data.path_for/connect`: negocios, empresa (columna de `negocios`), ubicaciones, puertas, referencias, estados, ventas, tráfico e incidentes |
| Tablas de la misma SQLite | `incident_notifications` escribe estados durables; `commercial.setup` crea `commercial_*` en la conexión de negocios, sin un almacén comercial separado |

Las bases `.negocios.sqlite` que permanezcan después de borrar un proyecto
también se conservan: `projects.remove` elimina su JSON y actualiza el índice,
pero no elimina esa base. El backup copia íntegra cada base, incluyendo tablas,
columnas y datos futuros; no reconstruye un esquema antiguo.

El índice debe ser un objeto con lista de IDs únicos (también sin colisiones de
mayúsculas Windows), activo válido y configuraciones presentes que sean objetos
JSON. No se aceptan JSON malformados, claves duplicadas ni números no finitos.
Un árbol ausente/vacío o índice vacío sin JSON huérfanos produce `no_data`. Un
índice faltante entre otros archivos, referencias rotas o archivos ambiguos hace
fallar la captura, sin publicar.

Solo se admiten las familias de archivos demostradas arriba. Un JSON no indexado,
otro almacén o un subdirectorio desconocido detiene la captura para revisar su
pertenencia al proyecto. No se incorpora por intuición ni se omite silenciosamente
un almacén desconocido. Los sidecars `-wal`, `-shm`, `-journal` y temporales `.tmp`
de familias conocidas se excluyen como miembros independientes.

**Expresamente fuera del ZIP:** `config/automation.sqlite`, configuración de
automatización, `config/counting.sqlite`, `data/identidad/`, replays, uploads,
reports, modelos/P2PNet, `correo.local.json`, contraseñas SMTP externas a los
proyectos, usuarios/sesiones de autenticación, caches, temporales generales,
frames y videos fuente externos. Las referencias de una configuración a archivos
externos se conservan como referencias; no se recorren para copiar esos archivos.

Las configuraciones se guardan completas y sin sanitización silenciosa. Un plano
ya embebido en el JSON sigue dentro de él. Si una URL de cámara tiene credenciales
embebidas, también queda dentro del ZIP. No se han inspeccionado ni usado
credenciales reales para las pruebas. El ZIP no está cifrado: sus permisos y el
acceso al directorio requieren control del operador.

## Configuración, ejecución y deduplicación

`config/automation.local.json` mantiene los valores actuales por defecto:

```json
{
  "backups": {"enabled": false, "time": "02:00", "retention": 7}
}
```

La ausencia de configuración deja todas las automatizaciones apagadas.
Desde Fase 7, el arranque registra explícitamente solo `reports`, `backups`,
`escalation` y `cleanup` (ver `ESCALAMIENTO_INCIDENTES.md` y `UPLOADS_CLEANUP.md`); los constructores de
`Engine` y `AutomationService` siguen sin iniciar tareas productivas. No se añade
ningún worker al runtime secuencial de Fase 3.

Solo con `backups.enabled == true` y hora Lima >= `backups.time` se intenta la
fecha actual. Antes devuelve `not_due`. No hay backfill de fechas perdidas. El
alcance son todos los proyectos guardados del árbol, independientemente del
proyecto seleccionado. La clave durable es `(backups, projects, YYYY-MM-DD Lima)`.
Un éxito previo impide otra publicación para esa fecha, incluso si su ZIP fue
retirado o desapareció. Un resultado `no_data` o fallo previo puede reintentarse.

## Consistencia y rutas de escritura

| Ruta de escritura | Protección observada |
| --- | --- |
| Crear/abrir/renombrar/eliminar/configurar desde Engine | `Engine.lock`; índice y configuraciones usan `projects.atomic_write` (temporal y reemplazo) |
| `projects.ensure_index` | Bootstrap anterior al arranque del worker; copia legacy inicial directamente y escribe el índice atómicamente |
| `Engine.read_config_file` | Migración de IDs al arrancar o al abrir proyecto; escritura atómica. Durante startup todavía no hay backup en ejecución |
| Negocios y operaciones comerciales HTTP | Normalmente `Engine.lock` + transacciones SQLite; `configure` también puede modificar SQLite antes del JSON |
| Actualización/consulta de incidentes y tráfico | SQLite; no todas las entradas sostienen `Engine.lock`, y `connect` puede ejecutar migraciones aditivas |
| `IncidentNotifications` | Conexiones SQLite propias, claims y resultados desde workers/sin `Engine.lock`; `ATTEMPT_LOCK` controla su estado local |

El backup adquiere un lease de lectura del árbol. Bajo `Engine.lock` enumera,
valida índice/configuraciones y copia sus bytes; identifica las SQLite leyendo
su cabecera, no confiando solo en `.sqlite`. Libera `Engine.lock` antes de los
snapshots SQLite, hashing, compresión y verificación. La espera del lock tiene
checkpoints y respeta el presupuesto cooperativo.

Cada base se abre mediante URI SQLite `mode=ro`; nunca se llama al conector de
negocios que podría migrarla. `Connection.backup()` escribe a una SQLite temporal,
con progreso por lotes de 128 páginas y checkpoints. Se ejecuta
`PRAGMA integrity_check`, se cierran ambas conexiones y se incorporan los bytes
del snapshot. Incluye las transacciones confirmadas en WAL; no incorpora cambios
sin commit. También se comprueba que la identidad del archivo no haya sido
reemplazada durante la captura. SQLite puede gestionar sus propios sidecars al
abrir una base WAL; no se copian ni se alteran manualmente.

**Garantía: consistencia por componente.** El corte JSON queda coordinado con
las operaciones del mismo Engine; cada SQLite contiene un snapshot consistente.
**No hay una transacción global multiarchivo.** Las bases pueden representar
instantes distintos entre sí y posteriores al corte JSON. Escritores externos,
otra instancia o llamadas directas a `projects.py` no comparten `Engine.lock`.
Los leases señalan uso, no bloquean automáticamente todas las escrituras.

## Formato y verificación

Ubicación final: `config/backups/projects-YYYY-MM-DD.zip`. Incluye miembros
canónicos `projects/<nombre>` y `backup-manifest.json`, con estos campos:

- `format`: `aerotrack-projects-v1`;
- `schema_version`: `2` (esta variante estricta);
- `created`: timestamp con zona;
- `scope`: `projects`;
- `files`: lista ordenada exacta de miembros de datos;
- `sha256`: hash SHA-256 por miembro de datos.

`verify_backup_bytes()` comprueba formato/versión, manifiesto y JSON estrictos,
miembros exactos, duplicados incluso por casefold, nombres seguros, semántica de
archivo regular, CRC (`testzip` con checkpoints), hashes y referencias del
índice. Rechaza rutas absolutas, `..`, backslashes, drives, ADS, subdirectorios,
entradas de directorio, symlinks y miembros cifrados.

También verifica la integridad de cada SQLite contenida: escribe sus bytes a un
nombre temporal generado por la aplicación y ejecuta `PRAGMA integrity_check`
en solo lectura. Nunca extrae utilizando el nombre arbitrario del miembro ZIP.
Los hashes verifican integridad; no constituyen una firma de autenticidad.

## Publicación y recuperación

1. Preparar captura y snapshots bajo un directorio temporal propio en backups.
2. Construir ZIP por bloques; verificarlo completo y calcular SHA-256/tamaño.
3. `flush`/`fsync` del ZIP temporal.
4. Bajo `BEGIN IMMEDIATE`, revalidar el registro y el destino: otra instancia
   puede haber publicado mientras se preparaba la captura.
5. Comprobar cancelación, ejecutar `os.replace` y registrar éxito/fingerprint
   juntos en SQLite, sin checkpoint entre reemplazo y registro.

Si falla antes del reemplazo, no se publica un final parcial. Solo se retiran
los temporales propios de ese intento. Una caída abrupta puede dejar temporales
huérfanos; no se borran mediante esta política de retención.

Un final existente sin éxito durable se valida incluyendo fecha del manifiesto;
si es válido, se reconcilia sin volver a capturar. Un final inválido queda como
evidencia, con salud `corrupt` y fallo explícito, sin sobrescribirlo. La
recuperación presupone un directorio bajo control de la aplicación; el formato
por sí solo no demuestra la procedencia de un ZIP plantado manualmente.

## Salud y retención

Se reutilizan `artifact_health`, `fingerprint()` y `check_successes()` de Fase 4.
No hay otro sistema de salud ni nueva base. `succeeded` es histórico: nunca se
reescribe por pérdida, corrupción ni retención. `healthy`, `missing`, `corrupt`
y `unverifiable` conservan su semántica. La verificación de salud incluye fechas
anteriores y no regenera artefactos. Un fingerprint histórico ausente no se
rellena a partir del archivo actual.

`retention=N` considera solo archivos del directorio oficial con nombre exacto
`projects-YYYY-MM-DD.zip`, fecha real, formato/estructura/hash válidos y fecha
del manifiesto coincidente. Además exige registro propio `succeeded`, ruta
coincidente y fingerprint durable SHA-256/tamaño igual. Ordena por fecha y
conserva los N más recientes; `retention=1` conserva el último válido.

Los corruptos, sospechosos, desconocidos, no registrados o sin fingerprint no
cuentan para N y no se eliminan. Se rechazan symlinks, junctions, reparse points,
hard links, rutas fuera del root y archivos no regulares. Los lectores/escritores
con leases activos impiden la eliminación y pueden dejar temporalmente más de N
backups; un tick posterior puede completar la retención.

La eliminación de cada candidato sigue este protocolo:

1. Validar contenido con lease de lectura, sin el lock global de recursos.
2. Bajo el lock de admisión de leases, comprobar que no haya otro usuario,
   tomar lease de escritura y revalidar identidad/tamaño/timestamps/fingerprint
   registrado. La compresión nunca sostiene este lock.
3. Confirmar `retention_pending` y evento `retention_planned` en una transacción
   durable **antes** de eliminar.
4. Volver a comprobar identidad y autorización SQLite; ejecutar `unlink`.
5. Confirmar salud `retired` y evento `retention_deleted` juntos, conservando
   `executions.status='succeeded'` y el fingerprint histórico.

Si `unlink` falla, queda `retention_pending` con el tipo de error y un evento
`retention_failed`; la excepción sigue visible en el runtime. No se marca
`retired`. En el siguiente tick se vuelve a validar antes de reintentar, y solo
si la política actual todavía permite retirarlo. Si quedó pendiente y el archivo
ya no existe tras una interrupción, se reconcilia a `retired` con auditoría.
Una ausencia sin intención durable previa es `missing`.

Si la política cambia y un pendiente ya no queda fuera de N, permanece pendiente
para revisión; no se borra contra la nueva política. Un archivo previamente
retirado que reaparezca tampoco recupera autoridad automática de borrado.

La auditoría usa `automation.sqlite`, fuera del ZIP: cada evento incluye task,
scope, fecha del backup, estado/motivo y timestamp. Fecha + scope determinan el
nombre canónico del archivo eliminado. Si no se puede confirmar la intención,
no se elimina. Si falla la persistencia después de eliminar, la intención previa
permite reconciliar el resultado en el siguiente tick.

## Recursos, cancelación y límites

- Actividad administrada durante toda la tarea; lease de lectura de proyectos
  durante captura/snapshots; leases de escritura de temporales/final; leases de
  lectura y verificación; lease de escritura durante retención. No se crean
  workers propios ni se debilita el cierre de Fase 3.
- Hay checkpoints en esperas, enumeración, lectura, progreso SQLite, integridad,
  compresión, hashing, CRC/verificación y retención. Se propaga `Cancelled` y se
  cierran conexiones/temporales. Tras publicar no se interrumpe voluntariamente
  el registro de éxito. **AT-06 sigue PARCIAL:** una llamada nativa o de filesystem
  individual puede demorar; no se matan hilos ni se liberan sus recursos activos.
- Un mutex serializa instancias de backup en el mismo proceso; SQLite coordina
  las transiciones finales para instancias que comparten base. Los leases no
  coordinan procesos diferentes. No se promete retención distribuida sobre una
  carpeta compartida ni seguridad frente a cambios adversariales del filesystem.
- Se requiere un directorio controlado por la aplicación. Se revalidan rutas,
  identidad y metadatos, pero permanece la carrera externa entre comprobación y
  apertura/borrado. Hashes sin una firma no autentican al autor.
- ZIP, JSON y snapshots se mantienen en memoria durante partes del proceso;
  archivos grandes consumen memoria/tiempo. Verificar SQLite y CRC de todo el
  historial tiene coste. El presupuesto puede posponer salud/retención; no hay
  cursor durable de avance histórico. `checked_at` permite detectar salud antigua.
- `fsync` y reemplazo reducen fallos parciales, pero no son una transacción única
  disco+SQLite ni una garantía frente a todo fallo de energía/controlador.
- No se eliminan replays, uploads, reports, identidad, archivos externos ni
  temporales generales. Esta retención solo afecta backups demostrablemente
  propios y válidos; no limita el espacio ocupado por evidencia sospechosa.

## Decisiones de producto pendientes

1. Si ampliar el alcance a automation.sqlite, counting, IdentityMemory, replays,
   uploads o reports. Nada de esto se incluye implícitamente.
2. Si desarrollar un restore soportado, incluyendo reconciliación del estado
   operativo posterior. Este ZIP no autoriza un rollback de notificaciones o
   revisiones de incidentes.
3. Política para credenciales embebidas en URLs de configuración y protección
   del archivo resultante; no hay sanitización ni cifrado no aprobados.

## Pruebas

`test_automation_backups.py` cubre programación, deduplicación, WAL activo,
preservación exacta de esquema/filas, publicación, recuperación, recursos,
retención, fallos y cancelación. `test_automation_backup_format.py` prueba ZIPs
alterados, miembros y rutas hostiles, JSON, manifiesto, CRC y SQLite corrupta.
Todos usan temporales y datos sintéticos; las eliminaciones son exclusivamente
de fixtures creadas por cada test. No se hacen backups ni retención sobre datos
reales y no se accede a SMTP, cámaras o RTSP.
