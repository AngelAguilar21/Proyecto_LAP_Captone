# Proyecto LAP Capstone

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

## Datos

## Ejecución del pipeline UCF-QNRF

El pipeline se ejecuta sobre el dataset RAW sin modificarlo directamente.

### 1. Auditoría del dataset RAW

```bash
python src/data_quality/audit_ucf_qnrf.py \
  --dataset "/ruta/al/dataset/UCF-QNRF_ECCV18" \
  --quarantine configs/ucf_qnrf_quarantine.csv

Los datasets completos se mantienen normalmente fuera del repositorio. Los datasets públicos completos, como UCF-QNRF (RAW y procesado), continúan fuera de Git.

El dataset piloto propio es una excepción controlada: sus nueve derivados de privacidad fueron publicados mediante Git LFS dentro de `data/pilot_videos/` y están disponibles en la rama `pilot-video-lfs`. El [PR #2](https://github.com/AngelAguilar21/Proyecto_LAP_Captone/pull/2) está abierto hacia `main`.

Los RAW canónicos del piloto permanecen externos e intactos en `data_collection/raw/`. El catálogo `data/pilot_videos/videos_metadata.csv` utiliza `distribution_published_lfs` para los nueve derivados; los hashes RAW y de distribución y la trazabilidad se documentan junto con `DATA_HANDOFF.md` y `DISTRIBUTION_REPORT.md`.

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

python src/preprocessing/clean_ucf_qnrf.py \
  --dataset "/ruta/al/dataset/UCF-QNRF_ECCV18" \
  --output "/ruta/al/dataset/UCF-QNRF_ECCV18_PROCESSED" \
  --quarantine configs/ucf_qnrf_quarantine.csv

python src/data_quality/audit_processed_ucf_qnrf.py \
  --raw "/ruta/al/dataset/UCF-QNRF_ECCV18" \
  --processed "/ruta/al/dataset/UCF-QNRF_ECCV18_PROCESSED"
