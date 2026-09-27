# Variante LAP depurada

Todas las automatizaciones permanecen deshabilitadas por defecto. Hay un solo
AutomationService y los horarios utilizan America/Lima. Esta variante conserva
reportes, backups, escalamiento y cleanup; no incluye un sistema de restauración.

## Alcance e historial

El escalamiento captura el proyecto activo bajo el lock de Engine y completa ese
trabajo sobre el proyecto capturado, aunque cambie la selección de la interfaz.
No existe escalation.project_ids ni supervisión automática de otros proyectos.
Los incidentes legacy con historial desconocido no escalan. Confirmar expresamente
que nunca fueron atendidos es distinto de atenderlos; una atención registrada
los excluye permanentemente, incluso si regresan a pendiente.

## Episodios

Una alerta continua de zona mantiene un incidente por episodio. Una observación
válida bajo el umbral cierra inmediatamente el episodio; una observación inválida
no lo cierra, pero tampoco acumula el intervalo sin observación para el dwell.
Un cambio de regla o cierre de sesión termina el episodio. No se extiende la
identidad entre sesiones distintas ni se fusionan incidentes históricos.

## Evidencia y retención

Los replays referenciados por cualquier incidente conservado quedan protegidos,
incluidos revisados, resueltos y falsas alarmas. Se consultan también bases de
proyectos huérfanos y registros fuera del límite de la interfaz. Una referencia
desconocida o ilegible bloquea conservadoramente la purga de candidatos.
También se protegen recursos activos, referenciados por configuraciones o por
historial de conteo. Los uploads sin prueba de finalización se omiten.
No existe una política automática de liberación de evidencia: es una decisión
pendiente del equipo. La retención no garantiza eliminar todo al cumplir una
edad ni imponer una cuota de disco; las referencias pueden conservarlo sin plazo.

## Persistencia SMTP

La aceptación SMTP captura su fecha antes de intentar guardar el resultado.
Un fallo de almacenamiento provoca hasta tres intentos inmediatos de persistencia,
nunca otro envío. Si persiste el fallo, el resultado sin contenido ni credenciales
se conserva en memoria y la reclamación durable sigue bloqueando duplicados.
La siguiente reconciliación reintenta únicamente guardar ese resultado.
deliveryPersistence en el estado de correo informa resultados pendientes y errores.
Si se pierde esa memoria al reiniciar, la reclamación se convierte en uncertain,
con sent_at=NULL y sin reenvío automático. Un almacenamiento inaccesible puede
impedir incluso escribir uncertain: mientras tanto permanece attempting, bloqueado.
Original y escalation mantienen registros independientes.

## Cancelación y cierre

runtime.task_timeout_seconds (120 por defecto) y runtime.shutdown_timeout_seconds
(30) aceptan segundos positivos finitos hasta 3600. Las tareas siguen siendo
secuenciales y cooperan en checkpoints; no se matan threads ni se publican PDF/ZIP
después de observar cancelación. Un SMTP ya aceptado termina su persistencia.
La espera inicial de cierre está acotada; si quedan escritores, un hilo de drenaje
no daemon conserva el servidor y sus recursos hasta que terminen. El proceso puede
seguir vivo más allá del plazo si una operación no responde. No existe un lease
de almacenamiento ni coordinación de restauración entre procesos en esta variante.

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
