# Proyecto LAP Capstone

## Ejecutar el sistema AeroTrack

Consulta [INSTALACION.md](INSTALACION.md) para clonar esta rama con P2PNet, instalar YOLO y ByteTrack, preparar los mapas e iniciar el sistema desde cero. En Windows, el instalador es `preparar_sistema.ps1`.

## Avance de AeroTrack para el equipo — 1 de octubre de 2026

- [Avance, correcciones, evidencias y pendientes](docs/AVANCE_EQUIPO.md).
- [Guía de ejecución, actualización y requisitos externos](INSTALACION.md).

Esta entrega intermedia de `jose/automations-main-integration-v2` incorpora
**REV-01/02/05 y su documentación para revisión del equipo**, sobre la base
`4f43cb9`. Esa base por sí sola no contiene las correcciones REV. El usuario
autorizó publicar este avance sin esperar al cierre de todos los hallazgos.
Consulta el SHA descargado con `git rev-parse HEAD` y contrástalo con el SHA
publicado comunicado en el cierre; los pasos seguros están en la guía enlazada.
Los parches locales de P2PNet, pesos YOLO, entornos, datos y evidencias externas
no forman parte de esta entrega; la guía distingue qué debe preparar cada equipo.
El usuario adoptó un único piloto experimental de 300 segundos con la webcam
ya autorizada, manteniendo NMS abierto y exigiendo preparación verificada y
comprobaciones previas en el mismo proceso. La primera validación del host,
el 1 de octubre a las 22:13 (Lima), falló antes de abrir captura: las guardas
bloquearon intentos de DNS externo y una lectura de `.git` durante la carga
inicial de YOLO/Ultralytics. El proceso cerró y no hubo segundo arranque.
El piloto **no se inició: 0 capturas y 0 s LIVE**; NMS no se reprodujo ni se
ejecutó su probe explícito. Su causa histórica sigue sin demostrarse.
El dictamen sigue siendo **REQUIERE CORRECCIONES**; REV-03/04/06 permanecen
pendientes. La publicación intermedia no acredita imagen procesada en la interfaz,
estabilidad ni aprobación de producción. Detalles y límites en el avance enlazado.

Las guías enlazadas resumen lo necesario sin acceso a discos locales y
distinguen documentos incluidos en Git de logs externos no publicados.

## Antecedente: pipeline de Data Engineering

El contenido siguiente conserva el trabajo de UCF-QNRF. Sus versiones y comandos
históricos no sustituyen los requisitos actuales de AeroTrack en
[INSTALACION.md](INSTALACION.md), que utiliza Python 3.12 en Windows/CPU.


Proyecto interdisciplinario orientado al análisis de afluencia de personas mediante Computer Vision para Lima Airport Partners (LAP).

Este repositorio contiene el trabajo de Data Engineering asociado a la preparación, validación, limpieza y trazabilidad de datasets utilizados en experimentos de crowd counting.

## Estado actual

El primer dataset integrado al pipeline es **UCF-QNRF**.

Actualmente se ha completado:

- validación estructural del dataset RAW;
- verificación de correspondencia imagen/anotación;
- auditoría espacial de anotaciones;
- identificación de muestras inconsistentes;
- definición de cuarentena;
- limpieza reproducible de anotaciones;
- generación de dataset procesado;
- generación de manifest de trazabilidad;
- auditoría posterior al preprocessing;
- documentación de Data Quality.

Resultado de la auditoría final del dataset procesado:

- **1,532 muestras utilizables**
- **1,244,115 anotaciones válidas**
- **0 puntos Out-of-Bounds (OOB)**

## Estructura del repositorio

```text
Proyecto_LAP_Captone/
├── configs/
│   └── ucf_qnrf_quarantine.csv
│
├── reports/
│   └── data_quality/
│       ├── UCF_QNRF_DATA_QUALITY.md
│       ├── ucf_qnrf_issues.csv
│       └── ucf_qnrf_summary.json
│
├── scripts/
│   └── exploration/
│       ├── inspect_outlier.py
│       ├── inspect_top_outliers.py
│       ├── inspect_ucf_qnrf.py
│       ├── rank_invalid_points.py
│       ├── rank_severe_outliers.py
│       ├── validate_after_quarantine.py
│       └── validate_ucf_qnrf.py
│
├── src/
│   ├── data_quality/
│   │   ├── audit_ucf_qnrf.py
│   │   └── audit_processed_ucf_qnrf.py
│   │
│   └── preprocessing/
│       └── clean_ucf_qnrf.py
│
├── .gitignore
├── requirements.txt
└── README.md
```

## Requisitos

El pipeline fue desarrollado y validado utilizando:

- Python 3.9.6
- matplotlib 3.9.4
- NumPy 2.0.2
- Pillow 11.3.0
- SciPy 1.13.1

Las dependencias Python se encuentran definidas en `requirements.txt`.

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/AngelAguilar21/Proyecto_LAP_Captone.git
cd Proyecto_LAP_Captone

python3 -m venv lap_env

source lap_env/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Datos

## Ejecución del pipeline UCF-QNRF

El pipeline se ejecuta sobre el dataset RAW sin modificarlo directamente.

### 1. Auditoría del dataset RAW

```bash
python src/data_quality/audit_ucf_qnrf.py \
  --dataset "/ruta/al/dataset/UCF-QNRF_ECCV18" \
  --quarantine configs/ucf_qnrf_quarantine.csv
```

Los datasets no se almacenan dentro del repositorio Git.

Se recomienda mantener los datos en un directorio separado del código fuente.

Una estructura local posible es:

```text
Proyecto_Interdisciplinario_I/
├── Proyecto_LAP_Captone/
│   ├── configs/
│   ├── reports/
│   ├── scripts/
│   ├── src/
│   ├── requirements.txt
│   └── README.md
│
└── Datasets/
    ├── UCF-QNRF_ECCV18/
    └── UCF-QNRF_ECCV18_PROCESSED/
```

```bash
python src/preprocessing/clean_ucf_qnrf.py \
  --dataset "/ruta/al/dataset/UCF-QNRF_ECCV18" \
  --output "/ruta/al/dataset/UCF-QNRF_ECCV18_PROCESSED" \
  --quarantine configs/ucf_qnrf_quarantine.csv

python src/data_quality/audit_processed_ucf_qnrf.py \
  --raw "/ruta/al/dataset/UCF-QNRF_ECCV18" \
  --processed "/ruta/al/dataset/UCF-QNRF_ECCV18_PROCESSED"
```
