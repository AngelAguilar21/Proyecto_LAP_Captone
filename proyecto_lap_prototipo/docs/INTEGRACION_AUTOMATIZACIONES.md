# Candidata integrada de AeroTrack — Fases 1–8

Esta vista corresponde a la rama de desarrollo
`jose/automations-main-integration-v2`, con entrada de Fase 8
`0b611e0c23f485103b7e51866f77967d06292d41`. No es una publicación en main ni una
auditoría aprobada. Las evidencias de cierre están en [FASE8_VALIDACION.md](FASE8_VALIDACION.md).

## Recorrido y matriz de integración

`live_server.main()` crea Engine, registra explícitamente cuatro callbacks en
AutomationService y arranca su bucle. El constructor por sí solo no ejecuta
las tareas. Cada tick lee configuración validada, ejecuta secuencialmente las
tareas habilitadas con presupuesto cooperativo y registra resultados durables.
Los métodos de notificación, episodios y uploads se integran en sus productores;
no son tareas periódicas adicionales. La salud de artefactos es parte de reports
y backups, no un quinto callback.

Rutas de módulos y tests relativas a `proyecto_lap_prototipo/`:

| Funcionalidad | Módulo / arranque y ejecución | Configuración | Persistencia | Shutdown / recursos | Tests / documentación | Estado y pendientes |
| --- | --- | --- | --- | --- | --- | --- |
| Notificación durable (F1) | `src/incident_notifications.py`; Engine crea y recupera gestor; `dispatch_alerts` registra y solicita envío | `notifier` / `correo.local.json` | `incident_notifications`, UNIQUE incidente + clase, en SQLite de negocio | Registro de writers; reintento exclusivo de persistencia tras aceptación; reconciliación al reiniciar | `test_incident_notifications`, `test_notifier`; [escalamiento](ESCALAMIENTO_INCIDENTES.md) | Integrado; UX de uncertain pendiente |
| Episodios estables (F2) | `zone_episodes.py`, `live_core.Occupancy`; observación → episodio → dispatch por sesión/scope/ID | Umbral y dwell de zonas; IDs estables | Incidentes, historial y resumen del replay | Finalización cierra episodios; un hueco no inventa observación cero | `test_zone_episodes`; contratos frontend `check-zone-alerts.mjs` | Integrado; cierre inmediato tras observación válida bajo umbral |
| Runtime (F3) | `automation.AutomationService`; registro explícito en `main` | `automation_settings`; tick 60 s, runtime configurable | `config/automation.sqlite`: executions/audit | Stop cooperativo; presupuesto por tarea y plazo global de drenaje | `test_automation`, settings/store/task_control/shutdown | Integrado; **AT-06 PARCIAL** |
| Recursos (F3) | `resource_control`, decorators HTTP/workers, leases de productores/lectores | Roots del Engine; proceso propietario | Registro de actividad sólo en RAM | `shutdown_control` conserva recursos mientras hay owners; cierre diferido | `test_resource_control`, `test_automation_shutdown`; [cleanup](UPLOADS_CLEANUP.md) | Integrado; no exclusión distribuida/interproceso |
| Reportes (F4) | `automation_reports.ScheduledReports`; snapshot permitido → `business_report_data` → `business_pdf_bytes` | enabled/time; fecha Lima, proyecto capturado | `data/reports/<proyecto>/business-<fecha>.pdf`, ejecución y hash | Lease, mutex PDFium, checkpoints; publicación atómica con reconciliación | `test_automation_reports`, artifacts/snapshot; [reportes](REPORTES_PROGRAMADOS.md) | Integrado; snapshot de una sesión, **no** rollup diario; sin UI de artefactos |
| Artifact health (F4/F5) | `automation_artifacts.check_successes`; después de tarea reports/backups vencida y habilitada | Hereda habilitación/horario de su tarea | Tabla artifact_health separa éxito histórico de salud actual | Lease de lectura, checkpoints; conserva fingerprint original | `test_automation_artifacts`, reports/backups | Integrado; no repara ni regenera automáticamente |
| Backups (F5) | `automation_backups.ProjectBackups`; snapshot de cada SQLite con API backup; ZIP verificado | enabled/time/retention | `config/backups/projects-<fecha>.zip` y AutomationStore | Leases, presupuesto; retención sólo de backups verificados | `test_automation_backups`, backup_format; [backups](BACKUPS_PROYECTOS.md) | Integrado; todos los proyectos del árbol; consistencia por componente, sin restore |
| Escalamiento (F6) | `automation_escalation.AlertEscalation`; selección + claim atómico + notificador durable | enabled/delay_minutes/recipients; **proyecto activo capturado** | Historial aditivo, reviewed_at irreversible y notification_kind independiente | Envío bloqueante dentro del runtime, writers protegidos | `test_automation_escalation`, incident_history/http; [escalamiento](ESCALAMIENTO_INCIDENTES.md) | Integrado; legacy desconocido excluido; supervisión multiproyecto pendiente |
| Uploads (F7) | `POST /api/upload` → `uploads.receive`; publicación part → final → marker | Formatos actuales, límite 1 GiB; no switch periódico | Original en uploads + identidad/tamaño/SHA/completed_at | Lease de escritura hasta evidencia completa; retira sólo temporales propios | `test_upload_cleanup`; [uploads/cleanup](UPLOADS_CLEANUP.md) | Integrado; legacy/desconocidos no se promueven ni eliminan automáticamente |
| Cleanup (F7) | `automation_cleanup.RetentionCleanup`; PLAN read-only → gate → revalidación APPLY | enabled/retention_days; edad estrictamente superior | Auditoría delete_planned/deleted/omitted; enlaces incident_replay_links | Locks sin espera, actividad/leases protegen, revalida referencias de todos los proyectos | `test_automation_cleanup`, incident_references; [uploads/cleanup](UPLOADS_CLEANUP.md) | Integrado; **AT-11 PARCIALMENTE MITIGADO** |

La matriz identifica consumidores y contratos; los tests aislados de cierre
verifican el registro real y el lifecycle, no sólo la existencia de clases.
No se han activado automatizaciones sobre datos reales para comprobarlo.

## Configuración efectiva por defecto

`config/automation.local.json` ausente equivale a los siguientes valores.
Esta muestra documenta el contrato; no es una instrucción para habilitarlo:

```json
{
  "timezone": "America/Lima",
  "runtime": {"task_timeout_seconds": 120, "shutdown_timeout_seconds": 30},
  "reports": {"enabled": false, "time": "18:00"},
  "backups": {"enabled": false, "time": "02:00", "retention": 7},
  "escalation": {"enabled": false, "delay_minutes": 15, "recipients": []},
  "cleanup": {"enabled": false, "retention_days": 30}
}
```

No hay UI específica para configurar estas tareas ni listar/descargar los PDFs
automáticos. Los reportes manuales existentes no son ese catálogo. La API de
incidentes permite validar historial legacy expresamente; no sustituye una UX
completa para revisión de historial desconocido o entrega uncertain.

Los alcances distintos son deliberadamente visibles: reports y escalation usan
el proyecto capturado; backups incluye el árbol de proyectos; cleanup examina
referencias globales. No existe `escalation.project_ids` en este contrato.

## Operación y límites

Correcciones posteriores de la candidata `9bc6988`: véase
[CORRECCIONES_POST_AUDITORIA.md](CORRECCIONES_POST_AUDITORIA.md). No cambian
defaults, alcance de las cuatro tareas, retención ni destinatarios. Los reportes
de sesiones nuevas verifican completitud de JSONL contra finalización del writer;
evidencia inconsistente no habilita publicación normal. Los históricos sin ese
contrato siguen explícitamente no verificables, sin fabricar hashes de origen.

- Un incidente revisado nunca vuelve a ser elegible aunque cambie a pendiente.
  Validar que un legacy nunca fue atendido no equivale a atenderlo. `sent` y
  `uncertain` bloquean reenvío automático; sólo `failed` puede reintentarse.
- Un plazo de shutdown vencido no demuestra que los writers hayan terminado.
  No se liberan sus recursos anticipadamente. Inferencia, lectura nativa,
  SQLite, SMTP o renderizado individuales pueden sobrepasar el presupuesto;
  el proceso puede permanecer drenando. **AT-06 sigue PARCIAL**.
- Cleanup protege evidencia de todos los incidentes conservados, incluso
  revisados, resueltos y falsas alarmas. Incertidumbre, base con WAL pendiente,
  actividad concurrente, origen desconocido o fingerprint cambiado impiden
  borrar. Un sistema continuamente ocupado puede postergar indefinidamente.
- Reportes, backups, SQLite, replays e IdentityMemory tienen alcances distintos.
  Cleanup de uploads/replays no elimina todas las copias individuales ni prueba
  cumplimiento de privacidad. Véase [inventario factual](INVENTARIO_PERSISTENCIA.md).
- Backups verificados no autorizan sobreescribir SQLite activa ni retroceder
  sent/reviewed_at/validaciones. **No hay restore soportado en esta candidata**.
  Una recuperación requiere un encargo separado y reconciliación operativa.
- El almacenamiento presupone un único proceso propietario y directorios bajo
  control del operador. Hashes no son firmas ni protección frente a un mutador
  privilegiado; filesystem y SQLite no forman una transacción global.

## Calibración asistida: propuesta prioritaria pendiente del equipo

**PROPUESTA, NO IMPLEMENTADA, NO APROBADA.** En puesta en servicio o recalibración,
colocar temporalmente ArUco o AprilTag en posiciones conocidas; detectar los
marcadores, construir correspondencias con el plano, calcular homografía y error
de reproyección, validar geometría, obtener confirmación humana, guardar perfil
y retirar marcadores. Mantener el método manual como alternativa avanzada.
No se ha iniciado CAL-1 ni implementado solvePnP o calibración automática.

Recalibrar responde a cambios físicos de posición, orientación, zoom, lente o
montaje. Una variación en número de personas no justifica por sí sola recalibrar.
La validez geométrica de correspondencias manuales sigue siendo autoridad del
backend; disponer de suficientes referencias no demuestra que sean válidas.

## Decisiones pendientes (sin resolver en Fase 8)

1. Calibración asistida ArUco/AprilTag.
2. Agregación de todas las sesiones para el reporte diario.
3. Backup ampliado de otros almacenes.
4. Restore soportado y reconciliación del estado posterior al backup.
5. Escalamiento de todos los proyectos frente al proyecto activo.
6. Liberación de evidencia ligada a incidentes.
7. Retención de IdentityMemory y otros almacenes/copia de datos derivados.
8. UX de historial legacy y estados uncertain.
9. Perfil opcional NVIDIA/CUDA y eventual selector Automático/CPU/NVIDIA GPU,
   con soporte backend y pruebas; no existe como opción UI implementada.
10. Apple Silicon/MPS; no declarar soporte sin pipeline validado.
11. Latencia/FPS objetivo para piloto.
12. Hardware mínimo.

La aceptación del alcance de consulta local, las firmas de apariencia y sus
plazos de conservación requiere comparar [el inventario](INVENTARIO_PERSISTENCIA.md)
con requisitos aprobados. Esta entrega no resuelve esa aceptación ni atribuye
decisiones al líder sin evidencia. El [protocolo live](PRUEBA_LIVE.md) queda
separado de las pruebas unitarias y no autoriza una operación productiva.
