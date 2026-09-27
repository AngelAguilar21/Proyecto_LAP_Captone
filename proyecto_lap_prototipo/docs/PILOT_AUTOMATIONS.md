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
