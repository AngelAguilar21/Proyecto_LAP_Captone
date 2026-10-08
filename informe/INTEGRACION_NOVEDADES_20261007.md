# Integración local de novedades — 7 de octubre de 2026

Base local: `831d00a987aed7137b6bc94060f53862a26e7fb7`, rama
`jose/automations-main-integration-v3`.

Fuentes integradas: `origin/main` (`c1513e7`) y
`origin/mejoras-integradas-comercial-multicamara` (`d429f71`). Se conservan
las automatizaciones locales, control de recursos y apagado, integridad de
reproducciones, ámbitos de proyecto y corrección de cadencia de grabaciones.
La rama experimental de precisión no forma parte de esta integración.

Se resolvieron los conflictos en una copia Git separada antes de actualizar
la carpeta compartida. Los cambios locales originales se respaldaron en
`D:\Projects\AeroTrack_supervision\respaldos\antes_pull_20261007_215929`.
El P2PNet retirado de main se conserva físicamente para no perder sus cambios.

## Verificación realizada aquí

- Python: 746 casos, 740 aprobados, 6 omitidos, sin fallos (67,391 s).
  Tres omisiones corresponden a componentes retirados; tres requieren PG real.
- Se excluyeron los módulos `test_aerotrack`, `test_reid_embeddings` y
  `test_postgis_integration`, que requieren modelos o infraestructura externa.
- TypeScript: `tsc --noEmit` aprobado.
- Panel: `check:aislamiento`, `check:seguimiento`, `check:kpis`, `check:lod`
  y compilación Vite aprobados.
- Las pruebas de cadencia y zonas usan capturas, detector e identidad sintéticos.
  No se ejecutó inferencia GPU ni se validó precisión con cámaras reales.

Registro completo: `D:\Projects\AeroTrack_supervision\integraciones\PRUEBAS_INTEGRACION_FINAL.log`.
Se corrigieron incompatibilidades de restauración histórica, comprobación
de calibración, cargas grandes, deduplicación con evidencia de cierre y
reportes comerciales con análisis de cámara nulo.

## Instalación y límites

El código y panel compilado están preparados para la carpeta compartida.
Las configuraciones de cámaras y datos locales existentes se conservan.
No se instalaron modelos ni se migraron datos a PostgreSQL. En esta instalación
falta `psycopg`; no existe el marcador `config/storage.local.json` que activa PG.
Para activar esa capacidad se necesita el controlador indicado en
`requirements-storage.txt`, PostgreSQL/PostGIS disponible y la migración
verificada con `tools/migrar_operativo.py --migrate`, con AeroTrack detenido.
Las afirmaciones de PostgreSQL instalado en documentos provenientes de la rama
comercial describen la instalación del autor, no una prueba realizada aquí.

El supervisor de revisión es independiente. Esta integración no resuelve su
bloqueo de sandbox por `node_repl.exe` ocupado ni inicia revisiones pendientes.

## Instrucción para los otros chats

Trabaja en `D:\Projects\AeroTrack-integracion-v3`, rama
`jose/automations-main-integration-v3`. La carpeta ya integra main y
mejoras-integradas-comercial-multicamara. Lee este informe y vuelve a leer
los archivos de tu tarea antes de continuar. Comprueba HEAD y el estado Git;
no restaures versiones antiguas ni ejecutes otro pull/checkout/reset sobre
la carpeta compartida. Conserva configuraciones, datos y cambios de otros
chats. Si usas otra copia o worktree, primero identifica su ruta y cambios
pendientes para incorporar esta integración sin sobrescribirlos. Al terminar,
registra tu entrega mediante el procedimiento de GUIA_ENTREGAS.md del supervisor.
