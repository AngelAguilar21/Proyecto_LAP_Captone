# Reportes programados — integración Fase 4

Fase 4 introdujo `reports`; desde Fase 7 el arranque de `live_server.main()`
registra explícitamente `reports`, `backups`, `escalation` y `cleanup` (ver
`BACKUPS_PROYECTOS.md`, `ESCALAMIENTO_INCIDENTES.md` y `UPLOADS_CLEANUP.md`).
Construir `Engine` o `AutomationService` no genera PDFs. Todas las
automatizaciones siguen deshabilitadas por defecto. No hay UI de configuración,
listado ni descarga de estos artefactos en esta fase.

## Configuración y horario

En una ejecución normal, los ajustes se leen de
`proyecto_lap_prototipo/config/automation.local.json`. Su ausencia equivale a
todos los valores por defecto. Ejemplo mínimo, que conserva reportes apagados:

```json
{
  "reports": {"enabled": false, "time": "18:00"},
  "runtime": {"task_timeout_seconds": 120, "shutdown_timeout_seconds": 30}
}
```

`automation_settings.save()` valida el documento y completa los valores por
defecto. `reports.time` usa `HH:MM`, de `00:00` a `23:59`, en America/Lima
(UTC−05:00). Solo `enabled: true` permite ejecutar la tarea. La configuración se
vuelve a leer en cada tick (intervalo predeterminado: 60 segundos). Antes de la
hora devuelve `not_due`; desde la hora configurada intenta la fecha Lima actual.
No recupera días perdidos ni activa otros proyectos en segundo plano.

Este documento describe cómo funciona la opción; no habilita ningún servicio.
Los campos históricos de configuración de otras tareas no significan que esas
tareas estén integradas en esta fase.

## Datos y elegibilidad

`ScheduledReports` toma una sola copia de `Engine.automation_snapshot()` con
contrato `{projectId, config, state}`. Usa las funciones modernas
`business_report_data(config, state)` y `business_pdf_bytes(data)`. No completa
campos posteriormente desde el Engine mutable ni cambia la whitelist de Fase 3.

La copia debe identificar proyecto y sesión, tener estado `running`, `paused`,
`stopped` o `ended`, `t > 0`, unidad de configuración y lista de cámaras con IDs
válidos, muestras `series` con `t`/`count`, los KPI
`totals.meanObservedSeconds` y `totals.alerts`, y `analytics.zones` con
`name`/`seconds`/`visits`/`peak` cuando haya zonas. Los valores numéricos deben ser
finitos y no negativos. Listas de zonas/cámaras vacías y conteos observados de
cero son válidos; ausencia de observaciones no equivale a cero.

Si faltan datos, registra `no_data` y permite otro intento después. Una ejecución
sin proyecto administrado deja un registro de auditoría sin inventar un scope.
El timestamp `generated` corresponde al tick recibido. Una sesión anterior que
siga en el snapshot puede ser elegible: no se exige que haya empezado ese día.

La etiqueta moderna `VIDEOS DE PRUEBA - PLANO ILUSTRATIVO` se conserva para
`testRun`; el modo demo usa `SIMULACIÓN SINTÉTICA`. Se exportan agregados, nunca
personas, posiciones, bounding boxes, firmas, Re-ID, frames, URLs o secretos.
La whitelist no incluye el estado operativo de cada cámara. Para una sesión en
marcha, el reporte indica cobertura desconocida si no recibió ese estado; no
afirma que haya cero cámaras activas.

**Decisión de producto pendiente:** un reporte diario significa aquí un snapshot
elegible del proyecto activo al tomar la copia, no la agregación de todas las
sesiones del día. Cambiar esa semántica necesita aprobación y otro diseño.

## Persistencia y publicación

El archivo final es:

```text
proyecto_lap_prototipo/data/reports/<projectId>/business-YYYY-MM-DD.pdf
```

La base `config/automation.sqlite` deduplica por
`(task='reports', scope=projectId, date=fecha Lima)`. `ScheduledReports` administra
sus propios resultados por proyecto; el runtime no crea además un falso éxito
`reports/service`. Reiniciar el proceso o repetir ticks no duplica un éxito.
Cambiar de fecha o proyecto permite un scope independiente.

La secuencia de publicación es:

1. Generar bytes solo desde la copia agregada y validar el PDF.
2. Calcular SHA-256 y tamaño en bytes.
3. Abrir `BEGIN IMMEDIATE` en SQLite y volver a comprobar éxito/archivo existente.
4. Escribir un temporal exclusivo en el directorio final, ejecutar `flush` y
   `fsync`, comprobar cancelación, y publicar con `os.replace()`.
5. Registrar éxito y fingerprint en la misma transacción SQLite, sin insertar
   un checkpoint entre `replace` y el registro.

Ante un fallo previo a `replace`, solo se retira el temporal de ese intento; un
archivo final previo no se trunca. Una caída abrupta puede dejar temporales
huérfanos: no se incorpora cleanup en esta fase.

Si el PDF final existe pero el éxito durable falta (por ejemplo, caída después
del `replace`), el siguiente intento valida el archivo y registra su fingerprint
sin renderizar otra vez. Un archivo final inválido se conserva y se informa fallo
para revisión humana. Un éxito ya registrado nunca pasa por esta reconciliación
ni se vuelve a publicar aunque su archivo haya desaparecido.

## Salud del artefacto

Migración aditiva e idempotente: tabla `artifact_health`, clave primaria
`(task, scope, date)`, columnas `sha256`, `size`, `status`, `checked_at` (Unix UTC)
y `error`. No se renumeran ni eliminan ejecuciones históricas. Publicación y
fingerprint inicial se confirman juntos; las comprobaciones posteriores conservan
el fingerprint original.

| Salud | Significado | Acción automática |
| --- | --- | --- |
| `healthy` | PDF estructuralmente válido; hash y tamaño coinciden | Actualizar comprobación |
| `missing` | Archivo ausente | Registrar incidencia; no regenerar |
| `corrupt` | PDF inválido o hash/tamaño distintos | Registrar incidencia; no sobrescribir |
| `unverifiable` | Ruta insegura/inaccesible o fingerprint histórico incompleto | Registrar incidencia; no inventar fingerprint |

Un `executions.status='succeeded'` describe un éxito histórico. Nunca se convierte
en fallo porque cambie la salud. `artifact_health` describe el último estado
verificado, no una garantía en tiempo real. Si se vuelve a colocar exactamente
el archivo original, una comprobación posterior puede devolverlo a `healthy`.
Los cambios de estado/motivo se registran en `audit`; las comprobaciones idénticas
no repiten el evento. Los errores de persistencia quedan visibles en el resultado
de la tarea y en `AutomationService.error`.

La comprobación recorre éxitos anteriores, incluso de otras fechas/proyectos,
después de atender la publicación actual. No repara ni regenera automáticamente.
Sin habilitación o antes de la hora configurada no se realiza ese recorrido.

## Validación, rutas y recursos

Se reutilizan las dependencias existentes ReportLab y pypdfium2; no se añade
ninguna. El validador requiere cabecera y cierre, documento legible con tabla de
referencias válida, páginas con dimensiones válidas y renderización de cada
página a escala limitada. No acepta un PDF solo por `%PDF-`, ni uno cuya tabla
de referencias PDFium haya tenido que reconstruir.

Las llamadas PDFium del validador y de la importación de planos comparten un
mutex: [PDFium no admite llamadas simultáneas entre hilos](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading).
La espera del mutex es cooperativa. El cambio en `plan_import` solo serializa
su entrada PDFium; no cambia el formato importado.

El helper propio de rutas restringe archivos al root explícito de reportes;
rechaza `..`, rutas externas, nombres ambiguos Windows/ADS, symlinks, junctions y
reparse points. La lectura rechaza hard links y archivos no regulares, y vuelve
a comprobar ruta e identidad al terminar. No depende de un módulo de cleanup.

La tarea mantiene una actividad administrada; la publicación/recuperación tiene
lease de escritura del directorio del proyecto (incluye final y temporal), y
la lectura/validación histórica tiene lease de lectura del artefacto. Se liberan
en las salidas normales, fallos y cancelaciones. No se añade un endpoint de
descarga: cualquier lector futuro deberá mantener el lease durante toda su
lectura/transmisión.

## Límites operativos

- La aplicación debe controlar permisos y contenido del root. Las comprobaciones
  de ruta no eliminan una carrera adversarial de reemplazo de directorios entre
  llamadas al sistema. La recuperación de un final válido sin registro presupone
  ese root controlado; no autentica que nadie haya plantado manualmente un PDF.
- `BEGIN IMMEDIATE` serializa publicación/reconciliación para instancias que
  cooperan usando la misma SQLite y el mismo root. El test usa dos instancias con
  conexiones independientes. No se promete coordinación distribuida ni una
  garantía global entre bases distintas, shares de red o escritores externos.
  Puede duplicarse el cálculo en memoria, pero se vuelve a comprobar antes de
  publicar. La contención que exceda el timeout SQLite produce fallo reintentable.
- Los leases son locales al proceso. No son locks de filesystem multiproceso.
- El PDF se genera y lee en memoria; documentos muy grandes consumen memoria.
  Hay checkpoints por página, bloque de lectura/hash/escritura, recorrido
  histórico y antes de publicar. ReportLab y una llamada nativa PDFium individual
  no se interrumpen a mitad de llamada; **AT-06 sigue PARCIAL**. El shutdown no
  mata hilos ni libera recursos de un escritor que siga activo.
- La publicación actual precede al recorrido histórico para evitar inanición de
  hoy. Un historial enorme puede agotar el presupuesto antes de completar su
  comprobación; `checked_at` permite detectar datos de salud antiguos. Todavía
  no hay cursor durable que reparta ese recorrido entre ticks.
- `fsync` del archivo y reemplazo atómico reducen la ventana de fallo, pero no
  equivalen a una transacción única disco+SQLite ni garantizan supervivencia ante
  todos los fallos de energía/controlador. La reconciliación y salud cubren las
  discrepancias observables al volver a ejecutar.
- No hay retención de PDFs/auditoría, reparación automática, UI ni alertas SMTP
  de salud en esta fase. Los backups de proyectos tienen su propia retención
  acotada en Fase 5. Escalamiento se integró en Fase 6 y retención conservadora de
  replays/uploads en Fase 7; restauración y retención de PDFs siguen pendientes.

## Verificación

`test_automation_reports.py` prueba horario, scope, reinicio, privacidad,
etiquetas de prueba, no_data, renderer real, publicación, crash recovery,
concurrencia entre instancias y conexión explícita del startup.
`test_automation_artifacts.py` prueba estructura, fingerprints, rutas Windows,
leases y cancelación sin sleep. `test_automation_store.py` añade migración desde
Fase 3, rollback conjunto y conservación del historial/fingerprint.
Usan datos sintéticos y directorios temporales; no ejecutan SMTP, cámaras,
automatizaciones ni borrado sobre datos reales.
