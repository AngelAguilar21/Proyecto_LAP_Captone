# Proyecto LAP Capstone

Proyecto interdisciplinario de análisis de afluencia de personas con Computer Vision para Lima Airport Partners (LAP).

## AeroTrack

AeroTrack (`proyecto_lap_prototipo/`) analiza video de cámaras fijas: detecta personas con YOLO, las sigue en cada cámara con
ByteTrack, las ubica en el plano con una homografía de puntos del suelo, reconoce a la misma persona entre cámaras con OSNet y mide
ocupación, aglomeraciones, flujos y accesos de locales. Asigna IDs anónimos; no usa rostros ni guarda imágenes de personas.

- **Instalar y ejecutar:** [INSTALACION.md](INSTALACION.md)
- **Usarlo paso a paso:** [proyecto_lap_prototipo/docs/GUIA_DE_USO.md](proyecto_lap_prototipo/docs/GUIA_DE_USO.md)
- **Cómo funciona y en qué literatura se apoya:** [proyecto_lap_prototipo/docs/ARQUITECTURA.md](proyecto_lap_prototipo/docs/ARQUITECTURA.md)

## Contenido del repositorio

```text
Proyecto_LAP_Captone/
├── proyecto_lap_prototipo/   aplicación AeroTrack (servidor Python, interfaz web, modelos, pruebas y herramientas)
├── datos_ucf_qnrf/           calidad de datos del dataset UCF-QNRF (ver su README)
├── informe/                  informe final, presentación, anexos, Gantt, proyecto de Overleaf y antecedentes
├── Tareas equipo.md          tareas y responsables del equipo
├── requirements.txt          dependencias de Python
├── preparar_sistema.cmd/.ps1 primera instalación (entorno, modelos, mapas e interfaz)
└── iniciar_sistema.cmd/.ps1  inicia AeroTrack en http://127.0.0.1:8765
```

Dentro de `proyecto_lap_prototipo/`:

```text
live_server.py   servidor y API local          src/        núcleo: seguimiento, identidad, análisis y reportes
dashboard/       interfaz web (React + Vite)   tests/      pruebas automáticas
config/          proyectos y ajustes locales   tools/      evaluación, rendimiento y mantenimiento
models/          YOLO y OSNet                  docs/       guías y arquitectura
data/            demo, videos y resultados
```

Los videos, los proyectos de cada usuario y las credenciales locales no se versionan.
