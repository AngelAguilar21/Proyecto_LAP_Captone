# Automatizaciones del piloto

Todas las tareas permanecen deshabilitadas por defecto. Este documento no
habilita ninguna tarea ni selecciona proyectos reales.

## Supervisión explícita

`automation.local.json`, dentro de la carpeta de ajustes, admite
`escalation.project_ids`: una lista de identidades del índice `projects/index.json`.
Para habilitar escalamiento deben indicarse tanto esta lista como los destinatarios.
El piloto debe configurar exactamente el proyecto autorizado. No se usa el
proyecto seleccionado en la interfaz ni se incluyen automáticamente otros proyectos.
Una configuración anterior habilitada sin esta lista se rechaza de forma segura.

Un proyecto eliminado, no indexado o inaccesible se informa en `errors`; los demás
proyectos configurados pueden continuar. No se crea una base vacía para buscar
incidentes. Se mantienen los bloqueos por restauración, entrega incierta e historial
legacy desconocido, y la exclusión permanente de incidentes atendidos.

## Persistencia de resultados SMTP

La aceptación SMTP captura su fecha antes de intentar guardar el resultado.
Un fallo de almacenamiento provoca hasta tres intentos inmediatos de persistencia,
nunca otro envío. Si persiste el fallo, el resultado sin contenido ni credenciales
se conserva en memoria y la reclamación durable sigue bloqueando duplicados.
La siguiente reconciliación reintenta únicamente guardar ese resultado.
`deliveryPersistence` en el estado de correo informa resultados pendientes y errores.
Si se pierde esa memoria al reiniciar, la reclamación se convierte en `uncertain`,
con `sent_at=NULL` y sin reenvío automático. Un almacenamiento inaccesible puede
impedir incluso escribir `uncertain`: mientras tanto permanece `attempting`, bloqueado.

## Cancelación y cierre

`runtime.task_timeout_seconds` (120 por defecto) y
`runtime.shutdown_timeout_seconds` (30 por defecto) aceptan segundos positivos,
finitos, hasta 3600. Las tareas siguen siendo secuenciales. Comprueban cancelación
entre elementos y antes de publicar o borrar; SQLite Backup también la comprueba
durante la copia. Una operación nativa ya iniciada puede exceder su presupuesto:
no se matan hilos ni se interrumpe el registro de un resultado SMTP aceptado.

El cierre solicita parar todos los componentes antes de esperar y comparte un
único plazo global. Si vence, informa cierre pendiente. Un guardián de cierre
mantiene el proceso, los recursos y la exclusión de restauración hasta que terminen
todos los escritores y solicitudes HTTP. No ejecuta tareas nuevas. Por tanto, el
plazo limita la espera del controlador, no garantiza matar el proceso en ese tiempo.
No se debe forzar una restauración mientras permanezca ese bloqueo.

## Salud de artefactos

El registro `executions.status='succeeded'` conserva el éxito histórico. La tabla
aditiva `artifact_health`, consultable con `AutomationStore.health(task, scope, date)`,
registra por separado `healthy`, `missing`, `corrupt`, `unverifiable`,
`retention_pending` o `retired`, con fecha de comprobación y motivo. Las transiciones
quedan en `audit`. Hash SHA-256 y tamaño originales se guardan al publicar el éxito.
Cada ejecución habilitada y vencida revisa también los éxitos de fechas/proyectos
anteriores para su tipo de artefacto. No es un monitor en tiempo real.

Los PDF deben tener cierre válido, referencias cruzadas válidas, páginas legibles
y renderizables mediante PDFium (dependencia ya existente), además de conservar
su hash. Los ZIP se verifican contra su manifiesto, CRC y hash original externo.
Los registros antiguos sin huella original se marcan `unverifiable`; validar su
estructura actual no demuestra que sean el archivo original. No se inventa una
huella histórica ni se regenera ningún éxito perdido/corrupto. La intervención
humana debe conservar evidencia y resolver el problema fuera de la ejecución
automática; no hay API nueva para reemplazar o regenerar artefactos.

La retención autorizada de backups se registra antes de borrar y se distingue de
una pérdida inesperada. Los archivos sospechosos se conservan para revisión y no
se cuentan como copias utilizables para decidir qué backups antiguos retirar.
