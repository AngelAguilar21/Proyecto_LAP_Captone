# Calidad de datos UCF-QNRF

Trabajo de Data Engineering sobre el dataset de conteo de multitudes **UCF-QNRF**: validación, limpieza y trazabilidad.
Es independiente de AeroTrack (la aplicación está en `../proyecto_lap_prototipo`), que ya no incluye un modelo de conteo de multitudes.

## Estado

Completado: validación estructural del dataset RAW, correspondencia imagen/anotación, auditoría espacial, identificación de muestras
inconsistentes, cuarentena, limpieza reproducible, dataset procesado con manifest de trazabilidad, auditoría posterior y documentación
de Data Quality.

Resultado de la auditoría final del dataset procesado: **1.532 muestras utilizables**, **1.244.115 anotaciones válidas** y
**0 puntos fuera de los límites (OOB)**.

## Estructura

```text
datos_ucf_qnrf/
├── configs/ucf_qnrf_quarantine.csv        muestras en cuarentena
├── reports/data_quality/                   informe de calidad, incidencias y resumen
├── scripts/exploration/                    inspección y validación exploratoria
└── src/
    ├── data_quality/                       auditoría del dataset RAW y del procesado
    └── preprocessing/                      limpieza reproducible
```

## Requisitos

Python 3.9.6 con matplotlib 3.9.4, NumPy 2.0.2, Pillow 11.3.0 y SciPy 1.13.1. Las dependencias del repositorio están en
`../requirements.txt`.

## Ejecución

El dataset no se guarda en el repositorio: mantenlo en una carpeta aparte. Los comandos se ejecutan desde esta carpeta
(`datos_ucf_qnrf`) y no modifican el dataset RAW.

```bash
# 1. Auditoría del dataset RAW
python src/data_quality/audit_ucf_qnrf.py --dataset "/ruta/UCF-QNRF_ECCV18" --quarantine configs/ucf_qnrf_quarantine.csv

# 2. Limpieza: genera el dataset procesado
python src/preprocessing/clean_ucf_qnrf.py --dataset "/ruta/UCF-QNRF_ECCV18" --output "/ruta/UCF-QNRF_ECCV18_PROCESSED" --quarantine configs/ucf_qnrf_quarantine.csv

# 3. Auditoría del dataset procesado
python src/data_quality/audit_processed_ucf_qnrf.py --raw "/ruta/UCF-QNRF_ECCV18" --processed "/ruta/UCF-QNRF_ECCV18_PROCESSED"
```
