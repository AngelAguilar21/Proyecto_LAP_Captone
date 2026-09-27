# Restauración conservadora de proyectos

Backend manual en `src/backup_restore.py`; no hay endpoint HTTP ni ejecución programada.
No ejecutar sobre almacenamiento real sin la autorización operativa correspondiente.

1. Detener AeroTrack y esperar el cierre de sus trabajadores y envíos.
2. Usar un ZIP de `config/backups/` y una identidad de operador con
   `restore_backup(settings_root, archive_path, operator)`.
3. Revisar `preserved_databases`, `restored_databases` y `held_projects` del resultado.
4. Conservar `restore-work/<restore_id>/`: contiene el ZIP fuente, las bases del
   backup y la generación anterior. Esta API no elimina estas evidencias.
5. Un ámbito sin continuidad comprobable permanece bloqueado para notificaciones
   originales/escalamientos. Cleanup se bloquea conservadoramente mientras exista
   cualquier ámbito pendiente. No se convierten incidentes nunca enviados en
   intentos SMTP `uncertain`.
6. Tras reconciliación humana documentada, `release_hold(..., reviewer, evidence)`
   libera exclusivamente ese ámbito; no altera estados SMTP ni revisiones.
   La evidencia debe cubrir posibles entregas y atenciones posteriores al backup:
   esta función registra la decisión humana, no demuestra por sí misma su veracidad.

Las bases operativas actuales se preservan completas usando SQLite Backup API.
No se retroceden ventas, incidentes, notificaciones, referencias o revisiones.
Solo la configuración JSON se restaura; los proyectos creados posteriormente se
conservan en el índice. El proyecto activo vuelve al definido en el backup.
Una base ausente se recupera del ZIP con bloqueo, nunca con permiso automático de envío.

`operational_identity` identifica la procedencia de cada base. Los eventos de
seguridad se registran en la misma transacción que la modificación de incidentes
o notificaciones. La migración registra hechos iniciales sin inventar fechas pasadas.
La continuidad requiere la misma identidad y el ancla del diario del backup.
Backups legacy o procedencias incompatibles requieren revisión humana.

Una restauración no es una transacción global de filesystem. `restore.sqlite`,
fuera de `projects/`, mantiene el bloqueo durante preparación/publicación. El
arranque normal del servidor exige que no haya operaciones incompletas, y una
lease de almacenamiento impide ejecutar servidor y restauración simultáneamente.
Tras interrupción de una publicación preparada, usar `resume_restore(root, id)`;
se verifican hashes antes de completar los renombrados. Una preparación fallida
que nunca publicó puede cancelarse con `cancel_preparation(root, id, operator, reason)`.
No borrar ni editar manualmente el marcador para forzar el arranque.

El procedimiento no recupera hechos posteriores que ya no existan en ninguna
fuente fiable. En ese caso el bloqueo se mantiene hasta revisión humana.
No restaura medios, reportes, credenciales ni preferencias globales; tampoco
retrocede `automation.sqlite`. No admite escritores externos durante mantenimiento.
