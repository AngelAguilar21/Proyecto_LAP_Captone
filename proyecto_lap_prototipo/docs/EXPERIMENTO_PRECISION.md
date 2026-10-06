# Experimento de precisión de detección (MOT20)

Rama local `experimento-precision`, sobre `main` en `f0f2a5e`. No cambia el código del prototipo: las tres
variantes se definen en `tools/evaluar_deteccion_mot.py`.

## Montaje

- **Datos:** MOT20-01 (1920×1080, 30 personas por cuadro en promedio) y MOT20-03 (1173×880, nocturna,
  cámara alta, 116 personas por cuadro). Se usó uno de cada cinco cuadros (5 fps, el paso de 0,2 s del modo
  preciso): 86 y 481 cuadros. Los datos van en `data/raw/MOT20/` (fuera de git).
- **Referencia:** `gt.txt`, clase 1 con visibilidad ≥ 0,25. Las personas más tapadas, las que van en
  vehículos, las estáticas, los distractores y los oclusores son zona ignorada. Emparejamiento húngaro con
  IoU ≥ 0,5.
- **Etapas:** `yolo` (cajas de YOLO), `filtros` (tras `SizeFilter`) y `tracks` (tracks activos menos los que
  suprime `StaticClutter`, que es lo que cuenta el servidor). Sin calibración, así que la zona útil no
  descarta nada.
- **Equipo:** GTX 1650 de 4 GB, torch 2.14.0+cu126, ultralytics 8.3.203. Los tiempos son medianas: «ms YOLO»
  es solo el detector y «FPS» el pipeline de una cámara sin OSNet ni motor de identidad.

| Variante | Modelo | imgsz | conf | NMS IoU | max_det | Reduce a 1280 | Umbral track | SizeFilter | StaticClutter | Precisión numérica |
|---|---|---|---|---|---|---|---|---|---|---|
| actual | yolo11n | 1280 | 0.15 | 0.5 | 300 | sí | 0.4 | ratio 0.62 | edad 2 s, score 0.6 | FP16 |
| mejoras | yolo11n | 1280 | 0.15 | 0.65 | 500 | no | 0.25 | ratio 0.35 | edad 4 s, score 0.35 | FP16 |
| mejoras_m | yolo11m | 1280 | 0.15 | 0.65 | 500 | no | 0.25 | ratio 0.35 | edad 4 s, score 0.35 | FP32 (FP16 da NaN) |

«actual» es lo que elige `hardware.py` en una GPU de 4 GB con cámaras elevadas (≥ 3 m).

## Resultados

R = recall, P = precisión (en %). MAE en personas por cuadro; un sesgo negativo indica que se cuentan de menos.

| Secuencia | Variante | Etapa | R | P | R 40-100 px | R >100 px | MAE | MAE % | Sesgo | ms YOLO | FPS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MOT20-01 | actual | yolo | 82.8 | 79.9 | 40.9 | 83.9 | 2.4 | 8.0 | +1.1 | 84 | 10.0 |
| MOT20-01 | actual | filtros | 72.3 | 92.9 | 30.3 | 73.4 | 6.8 | 22.4 | −6.7 | | |
| MOT20-01 | actual | tracks | **70.5** | 94.0 | 27.3 | 71.6 | 7.5 | **25.0** | −7.5 | | |
| MOT20-01 | mejoras | yolo | 83.6 | 75.7 | 40.9 | 84.8 | 3.9 | 12.9 | +3.2 | 86 | 8.3 |
| MOT20-01 | mejoras | filtros | 83.6 | 79.6 | 40.9 | 84.8 | 2.9 | 9.5 | +1.5 | | |
| MOT20-01 | mejoras | tracks | **82.2** | 83.0 | 30.3 | 83.5 | 2.6 | **8.7** | −0.3 | | |
| MOT20-01 | mejoras_m | yolo | 80.7 | 87.4 | 45.5 | 81.6 | 3.0 | 10.0 | −2.3 | 121 | 6.8 |
| MOT20-01 | mejoras_m | filtros | 80.7 | 88.2 | 45.5 | 81.6 | 3.2 | 10.5 | −2.6 | | |
| MOT20-01 | mejoras_m | tracks | **79.1** | 89.1 | 40.9 | 80.1 | 3.6 | **11.9** | −3.4 | | |
| MOT20-03 | actual | yolo | 68.4 | 87.1 | 61.0 | 80.0 | 24.8 | 21.5 | −24.7 | 152 | 3.4 |
| MOT20-03 | actual | filtros | 67.1 | 90.0 | 58.4 | 79.9 | 29.4 | 25.4 | −29.3 | | |
| MOT20-03 | actual | tracks | **65.5** | 91.4 | 57.0 | 78.1 | 32.8 | **28.4** | −32.8 | | |
| MOT20-03 | mejoras | yolo | 69.2 | 84.5 | 61.5 | 81.1 | 21.4 | 18.5 | −20.9 | 154 | 3.0 |
| MOT20-03 | mejoras | filtros | 69.2 | 84.5 | 61.5 | 81.1 | 21.5 | 18.6 | −20.9 | | |
| MOT20-03 | mejoras | tracks | **68.6** | 85.8 | 61.0 | 80.5 | 23.4 | **20.3** | −23.2 | | |
| MOT20-03 | mejoras_m | yolo | 49.7 | 92.8 | 33.8 | 68.3 | 53.7 | 46.4 | −53.7 | 179 | 3.7 |
| MOT20-03 | mejoras_m | filtros | 49.7 | 92.8 | 33.8 | 68.3 | 53.7 | 46.4 | −53.7 | | |
| MOT20-03 | mejoras_m | tracks | **48.6** | 93.4 | 32.9 | 67.1 | 55.5 | **48.0** | −55.5 | | |

Personas por franja de altura: MOT20-01 tiene 1 (<40 px), 66 (40-100) y 2.522 (>100); MOT20-03 tiene 1.973,
27.070 y 26.568. El recall bajo 40 px solo es representativo en MOT20-03: 15,0 % en actual, 15,0 % en
mejoras y 17,1 % en mejoras_m (en la etapa yolo).

### Barrido de confianza (etapa yolo, imgsz 1280, NMS 0.65)

| Secuencia | Modelo | conf 0.05 | conf 0.10 | conf 0.15 | conf 0.25 |
|---|---|---|---|---|---|
| MOT20-03 | yolo11n FP16 | R 78.3 / P 67.1 | R 73.3 / P 78.4 | R 69.5 / P 84.5 | R 61.8 / P 90.9 |
| MOT20-03 | yolo11s FP32 | R 75.4 / P 78.2 | R 68.5 / P 85.5 | R 62.0 / P 89.5 | R 49.1 / P 93.6 |
| MOT20-03 | yolo11m FP32 | R 69.0 / P 84.4 | R 58.2 / P 90.1 | R 49.6 / P 93.1 | R 35.0 / P 95.5 |
| MOT20-01 | yolo11n FP16 | R 88.8 / P 52.9 | R 86.5 / P 67.0 | R 83.8 / P 76.1 | R 79.1 / P 86.0 |
| MOT20-01 | yolo11s FP32 | R 88.7 / P 63.9 | R 86.6 / P 75.3 | R 83.5 / P 81.6 | R 78.9 / P 89.7 |
| MOT20-01 | yolo11m FP32 | R 87.6 / P 72.9 | R 84.1 / P 81.4 | R 80.9 / P 87.2 | R 73.5 / P 91.9 |

## Conclusiones

1. **Las mejoras 1 a 3 corrigen el conteo sin costo de GPU.** MOT20-01: MAE de 25,0 % a 8,7 %, recall de
   tracks de 70,5 a 82,2. MOT20-03: MAE de 28,4 % a 20,3 %. La precisión baja de 94 a 83 % en MOT20-01. El
   detector tarda lo mismo; el pipeline pierde un 10-15 % de FPS porque sigue más tracks.
2. **En main, la pérdida está en los filtros, no en YOLO.** En MOT20-01, YOLO encuentra al 82,8 %, pero
   `SizeFilter` baja el recall a 72,3 % y el umbral de track de 0.4 a 70,5 %: se cuentan 7,5 personas menos
   por cuadro.
3. **yolo11m no conviene con la misma confianza.** Es más conservador: a confianza 0.15 en MOT20-03 pierde 20
   puntos de recall. Con una precisión similar (~84 %), n y m quedan iguales en MOT20-03 (R 69,5 a 0.15 contra
   69,0 a 0.05), y en MOT20-01 m gana poco. Cuesta 1,4 veces más en YOLO y exige FP32. Si se usa, hay que
   bajar su confianza a ~0.05-0.10.
4. **FP16 en la GTX 1650 rompe los modelos s y m en silencio.** Las salidas crudas son NaN (s: 3,6 %, m:
   100 %) y el filtro de confianza las descarta: el detector devuelve menos personas, o ninguna, sin dar
   error. `hardware.py` activa FP16 en toda GPU; en las GTX 16xx debería usar FP32. yolo11n en FP16 da
   igual que en FP32.
5. **Las personas de menos de 40 px casi no se detectan (15-17 %) con ningún modelo COCO a 1280.** Ahí
   ayudarían los mosaicos (SAHI) o pesos entrenados en multitudes (CrowdHuman), que son las mejoras 4-6.

## Reproducir

```
python tools/evaluar_deteccion_mot.py data/raw/MOT20/MOT20-01 data/raw/MOT20/MOT20-03 --variantes actual,mejoras
python tools/evaluar_deteccion_mot.py data/raw/MOT20/MOT20-01 data/raw/MOT20/MOT20-03 --variantes mejoras_m --fp32
```

Cada carpeta necesita `img1/` (uno de cada cinco cuadros), `gt/gt.txt` y `seqinfo.ini` de MOT20 (licencia
CC BY-NC-SA 3.0).
