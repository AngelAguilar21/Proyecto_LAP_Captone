# Almacenamiento operativo y pruebas de la base

## Estado del 7 de octubre de 2026

PostgreSQL/PostGIS ya es la fuente operativa de usuarios, proyectos, configuración,
negocios, puertas, ventas, incidentes e indicadores comerciales en esta instalación.
Los usuarios conservan los hashes PBKDF2 y sus contraseñas existentes. Las sesiones
de login siguen en memoria: al reiniciar hay que volver a entrar.

La migración verificó los cuatro documentos JSON y todas las filas de los dos
proyectos activos, dentro de una transacción. Se conservaron 145 negocios, 29
franjas de ventas comerciales, 35 filas de tráfico comercial y 133 incidentes de
bitácora. Las bases de proyectos antiguos que ya no están en el índice no se
borraron ni se activaron.

Cada proyecto tiene un esquema PostgreSQL separado, con claves primarias y
foráneas. Los planos, cámaras y calibraciones están en documentos JSONB bajo una
clave de instalación y ruta lógica; no se convirtieron en tablas de columnas
individuales. Las ubicaciones de negocios tienen una vista PostGIS
`negocio_geometrias`, en coordenadas locales SRID 0. No son coordenadas GPS.

Los archivos locales anteriores quedan como respaldo, no como una segunda fuente
de escritura. Una caída de PostgreSQL no activa silenciosamente los datos antiguos.
La API responde con un error de disponibilidad para que se restaure la conexión.

## Qué permanece en archivos

- Videos y modelos: archivos, fuera de PostgreSQL.
- Muestras y manifiestos de monitoreo: JSONL/JSON recuperables; las sesiones
  finalizadas también se archivan en PostgreSQL. La reproducción aún lee esos archivos.
- Memoria de apariencia: migrada también a PostgreSQL, separada por proyecto,
  huella del modelo y dimensión. La comparación sigue en RAM, con escritura
  asíncrona y retención configurable. El SQLite anterior se conserva como respaldo
  y solo se importa una vez si coincide el modelo. En instalaciones sin migrar
  se mantiene SQLite. No se requiere una consulta de red por cada cuadro.
- Cola de archivo: SQLite local para poder reintentar si PostgreSQL no responde.
- Ajustes locales de correo y herramientas: permanecen locales.

No borres los videos, `data/`, `.env`, `config/storage.local.json` ni el volumen
Docker. Respaldar únicamente PostgreSQL no alcanza para reproducir los videos.
El marcador identifica la instalación; cambiarlo no es una forma válida de revertir
la migración. Los archivos originales estarán desactualizados después de editar en PG.

## Encendido desde CMD

```bat
cd /d "C:\PROYECTO LAP\Proyecto_LAP_Captone"
iniciar_sistema.cmd
```

Abre Docker Desktop antes. En una instalación migrada, el iniciador también levanta
y comprueba PostgreSQL. La aplicación está en http://127.0.0.1:8765/.
No hace falta iniciar un backend, frontend o servidor SQL adicional manualmente.

## Migrar otra instalación existente

1. Instalar las dependencias del proyecto y abrir Docker Desktop.
2. Ejecutar `iniciar_base.cmd` desde la raíz.
3. Detener el servidor y los monitoreos.
4. Ejecutar `.venv\Scripts\python.exe proyecto_lap_prototipo\tools\migrar_operativo.py --migrate`.
5. Revisar el informe en `config/backups/postgres-<fecha>/verification.json`.
6. Ejecutar `iniciar_sistema.cmd` y comprobar el login y ambos proyectos.

El migrador rechaza volver a importar archivos antiguos sobre una instalación ya
migrada. No elimina originales. El respaldo incluye credenciales cifradas con hash:
es privado y está excluido de Git, igual que el marcador y las claves de conexión.

## Validación

- 352 pruebas automatizadas aprobadas con PostgreSQL real disponible.
- Pruebas comerciales existentes ejecutadas adicionalmente sobre PostgreSQL:
  CSV, aislamiento de datos reales/prueba, pronósticos, negocios y puertas.
- Migración de un proyecto temporal, verificación fila por fila, cambio de clave,
  conservación de caracteres Unicode, actualización de secuencias y rollback.
- Prueba de que un archivo local obsoleto no sustituye los datos en PostgreSQL.
- Compilación Vite aprobada.
- TypeScript sin errores. Nueva prueba manual `520dacc9` en **proyecto 3**:
  cámaras 4 y 5, 82 segundos, inicio y detención desde la interfaz. Se conservaron
  1.426 observaciones en PostGIS y sus archivos de reproducción. El cierre calcula
  12 identidades; no son 12 identidades correctas verificadas manualmente.
- Corrección del selector de nivel de Negocios: incluye el plano activo aunque
  `plans` solo contenga los planos secundarios. La validación de guardado usa la
  misma regla y tiene una prueba de regresión.

## Base completada y trabajo pendiente

Ya están implementados el grafo dirigido de cámaras y sus ventanas temporales,
filtros de candidatos antes de comparar apariencia, separación de memoria por modelo,
selección explícita de cámaras, perfiles CPU/GPU, opción OSNet-AIN, archivo PostGIS
y migración operativa. Se conserva YOLO11n porque la comparación local con YOLO26n
no mostró una ventaja de velocidad ni se midió una mejora de precisión.

Falta medir precisión ReID con correspondencias anotadas, comprobar sincronización
real de las cámaras y ejecutar una prueba prolongada de Tokio con recuperación de
red. Un ID compartido demuestra una asociación del algoritmo, no que sea correcta.
No están implementados KPR/BPBreID, un detector entrenado de bolsas de compra ni
un despliegue GPU en la nube. Tampoco se ha georreferenciado el plano LAP contra
puntos físicos verificados. Estas tareas no se presentan como completadas.
