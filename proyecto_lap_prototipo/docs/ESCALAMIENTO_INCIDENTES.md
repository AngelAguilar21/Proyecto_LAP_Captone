# Escalamiento durable de incidentes — Fase 6

El escalamiento notifica a supervisores que un incidente agregado continúa
pendiente y necesita atención humana. Es independiente del aviso original:
no exige que ese aviso haya sido enviado ni que haya tenido éxito. No es un
reintento del correo original ni una confirmación de lo ocurrido.

## Configuración y alcance

`config/automation.local.json` conserva todas las automatizaciones deshabilitadas
por defecto. Ejemplo que **no activa** el escalamiento:

```json
{
  "escalation": {
    "enabled": false,
    "delay_minutes": 15,
    "recipients": ["supervisor@example.invalid"]
  }
}
```

`automation_settings.save()` valida delay entero de 1 a 3650 minutos, hasta 20
direcciones simples de hasta 200 caracteres, sin espacios, separadores de listas
ni nombres de presentación. Activar requiere al menos un destinatario. La
validación es sintáctica: no comprueba que el buzón exista. No se admiten claves
SMTP en esta configuración. `Mailer` sigue necesitando la configuración normal
de correo habilitada; los destinatarios de escalamiento se pasan como alternativa
y nunca sustituyen `correo.recipients` en disco. El equipo debe configurar la
lista de supervisores apropiada; no se impone que ambas listas sean disjuntas.

Desde Fase 7, `live_server.main()` registra explícitamente `reports`, `backups`,
`escalation` y `cleanup` (ver `UPLOADS_CLEANUP.md`). Los constructores siguen inertes. El
runtime secuencial comprueba las tareas cada 60 segundos por defecto. El momento
de envío puede ser posterior al umbral por ese intervalo o por otras tareas.

Cada ejecución captura `project_id` y `config_path` bajo `Engine.lock`; luego
libera el lock y trabaja únicamente sobre esa referencia. Cambiar el proyecto
en la interfaz durante la tarea no cambia su destino. **No existe supervisión
global de todos los proyectos.** Una base de negocios inexistente produce
`no_incidents`, sin crear una base vacía. La base capturada mantiene un lease de
escritura durante selección, recuperación y envío.

## Historia y migración

La migración de `business_data.connect()` añade columnas mediante una transacción
SQLite, releyendo el esquema tras adquirir `BEGIN IMMEDIATE`. Es aditiva e
idempotente; no reconstruye tablas, renumera IDs ni fusiona incidentes. Conserva
empresa, ubicaciones, puertas, referencias, estados, ventas y `commercial_*`, así
como los estados de `incident_notifications`.

| Campo | Significado |
| --- | --- |
| `review_history_known` | 0 en todas las filas preexistentes: no se conoce la historia. 1 al crear un incidente nuevo, atenderlo o validar explícitamente su historia. |
| `reviewed_at` | Instante de la primera atención registrada bajo este esquema. No se borra ni cambia cuando vuelve a pendiente o recibe nuevas observaciones. No pretende reconstruir la fecha histórica de una atención legacy. |
| `history_validated_at` | Instante de la decisión humana explícita sobre un historial desconocido, tanto positiva como negativa. No se rellena por creación ni por actualización ordinaria de estado. |
| `escalated_at` | Proyección de `incident_notifications.sent_at` para kind escalation y status sent; no es otra columna ni fuente de verdad. |

Los nuevos incidentes empiezan con historia conocida y ambas fechas NULL. Los
preexistentes permanecen desconocidos incluso si su estado actual es pendiente,
revisado, resuelto o falsa alarma. No se infiere historia a partir de `actualizado`
ni de otros campos. Cambiar mediante la API a revisado, resuelto o falsa alarma
registra atención; posteriormente volver a pendiente nunca habilita escalamiento.
Estas garantías corresponden a las APIs: editar SQLite manualmente las elude.

## Validación humana legacy: backend disponible, UI pendiente

`Engine.validate_incident_history(id, never_attended, project_id)` usa
`business_data.validar_historial_incidente()`. La operación HTTP es:

```text
POST /api/incidents/history
X-LAP-Token: token local vigente
X-LAP-Session: sesión autenticada vigente
Content-Type: application/json

{"id":"incidente-ejemplo","projectId":"proyecto-ejemplo","never_attended":true}
```

Se aplican las comprobaciones actuales de host/origen y token. Se exige sesión
incluso si todavía no hay cuentas; operador y administrador pueden validar,
igual que atender incidentes. Un rol desconocido se rechaza. No se modifica la
matriz de autorización general ni se resuelve AT-01 en esta fase. El proyecto
debe coincidir con el activo al capturar la operación; con un Engine de archivo
aislado su ID es null. `projectId` debe aparecer explícitamente en la petición.

- `never_attended: true`: solo una fila desconocida, pendiente y sin revisión;
  establece historia conocida y fecha de validación. Mantiene reviewed_at NULL
  y pendiente: validar no equivale a atender. Si ya venció el delay, podrá escalar
  en el siguiente tick sin reiniciar su antigüedad.
- `never_attended: false`: confirma que fue atendida; establece estado revisado,
  reviewed_at y history_validated_at. Queda excluida para siempre aunque vuelva a
  pendiente.

Solo se acepta un booleano JSON. Una fila ya conocida, ya validada, inexistente o
con revisión no puede validarse otra vez. La actualización condicional es
atómica: dos decisiones concurrentes no pueden sobrescribirse. Una petición
inválida no modifica el historial. GET no tiene esta acción. Las respuestas y el
listado actual de incidentes incluyen los cuatro campos públicos de historia.

No se añade UI de validación ni configuración en esta fase. El responsable de
operación debe verificar el historial real antes de afirmar que nunca se atendió.

## Elegibilidad y claim

Para cada ejecución se fija `cutoff = now.timestamp() - delay_minutes * 60`.
Se usa tiempo de calendario desde `creado`, no duración de video ni `inicio`.
El límite es inclusivo (`creado <= cutoff`) y el orden estable es `creado, id`.

Un candidato debe estar pendiente, con historia conocida, reviewed_at NULL y
edad suficiente. Se excluyen escalaciones sent, uncertain o attempting; failed
permite otro intento. La recuperación de Fase 1 reconcilia intentando huérfano
como uncertain, sin convertir una entrega activa del proceso en reintentable.

La selección no concede permiso definitivo. La tarea llama a
`IncidentNotifications.send(..., kind="escalation", blocking=True,
escalation_due_before=cutoff, recipients=supervisores)`. `_claim()` revalida
estado, historia y edad dentro del mismo `BEGIN IMMEDIATE` que reclama el mensaje.
La clave SQLite `(incident_id, notification_kind)` y el UPDATE condicionado a
failed impiden dos claims ganadores, incluso sin el lock de Python.

Una revisión confirmada **antes del claim** impide SMTP y no crea claim. Si la
revisión llega **después del claim**, una entrega ya reclamada puede completarse:
no se retiene la transacción ni el lock de Engine durante SMTP, y no se puede
retirar un correo aceptado. El cutoff capturado no se amplía por el tiempo
transcurrido durante el envío ni por un cambio de configuración a mitad de tarea.

El argumento de cutoff es opcional en la API de bajo nivel para conservar la
compatibilidad de Fase 1; el scheduler siempre lo proporciona. Nuevos llamadores
de escalamiento automático deben usar la misma protección, no invocar el envío
genérico sin ella.

## Entrega y resultados

Original y escalation conservan registros independientes:

- sent: éxito confirmado, sent_at conservado; nunca se reenvía automáticamente.
- uncertain: resultado incierto o intento interrumpido; sent_at NULL y sin
  reenvío automático. Requiere auditoría humana, no se añade una UI de reenvío.
- attempting: reclamado o pendiente de persistir un resultado conocido; no se
  duplica. Un intento huérfano tras reinicio se reconcilia como uncertain.
- failed: fallo confirmado sin aceptación; puede reintentarse si el incidente
  sigue elegible. El cooldown de Mailer queda como defensa secundaria.

Después de aceptación SMTP, los reintentos son únicamente de persistencia.
La tarea devuelve `candidates` y `sent`; sent cuenta éxitos confirmados y
persistidos en esa llamada. Si la persistencia queda pendiente, puede ser cero
aunque SMTP haya aceptado: consultar los diagnósticos de notificaciones durables.
Una revisión concurrente que invalida el claim no hace fallar toda la tarea.
AutomationStore registra la ejecución del task; no duplica cada correo en
executions. La identidad del mensaje permanece en incident_notifications.

El cuerpo usa una lista explícita de campos agregados (ID de incidente, tipo,
zona, ID de proyecto y tiempo pendiente) y pide revisión humana. No se serializan
detalle, configuración de cámaras, posiciones, IDs de personas, Re-ID, firmas,
frames ni secretos. Etiquetas con URL, controles o más de 200 caracteres se
omiten. No se persiste contenido de correo ni destinatarios en la tabla durable.

## Cancelación, backups y límites

AlertEscalation no crea threads: envía en modo blocking dentro del runtime.
Comprueba checkpoint entre candidatos y antes del claim/transporte, respetando
cancelación y presupuesto. Una cancelación anterior al transporte deja el claim
como failed, sin SMTP. Una entrega aceptada completa la persistencia y sigue
contándose como writer hasta entonces. El apagado seguro de Fase 3 no libera
recursos mientras existan escritores o resultados por persistir.

La cancelación es cooperativa; no interrumpe una llamada SMTP o una espera de
SQLite ya en curso. La selección materializa candidatos en memoria. La garantía
de recuperación de writers activos es la de Fase 1: un proceso de aplicación
propietario; SQLite evita claims duplicados pero no es un coordinador de varios
servidores AeroTrack activos sobre la misma base.

Los backups de Fase 5 copian naturalmente las nuevas columnas y sus valores
mediante snapshots SQLite. No cambia su formato ni la lógica de reportes.
Restaurar manualmente una base antigua puede retroceder estados operativos; no
hay restauración soportada ni aprobación para hacerla en esta fase.

## Pruebas y pendientes

`test_automation_escalation.py` prueba límites de tiempo, persistencia, SMTP
simulado, carreras, proyecto capturado, privacidad, cancelación y registro runtime.
`test_incident_history.py` prueba migración real desde el esquema anterior,
preservación comercial, irreversibilidad y decisiones humanas concurrentes.
`test_incident_history_http.py` usa únicamente un servidor HTTP localhost temporal.
La prueba de backup moderno compara el dump completo, incluidas las fechas nuevas.
No se usan SMTP, cámaras, RTSP ni bases de usuario reales.

Pendientes de producto/UX: alcance futuro a proyectos distintos del activo, UI
de validación legacy/configuración y tratamiento humano de uncertain. Esta fase
no decide una política de supervisión global. Fase 7 añadió uploads durables y
cleanup conservador, deshabilitado por defecto. Restore sigue fuera de esta entrega.
La integración posterior y sus verificaciones se documentan en
[INTEGRACION_AUTOMATIZACIONES.md](INTEGRACION_AUTOMATIZACIONES.md).
