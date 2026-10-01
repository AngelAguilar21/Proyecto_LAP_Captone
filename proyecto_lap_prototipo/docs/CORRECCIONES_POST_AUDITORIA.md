# Correcciones de la candidata auditada

Base `9bc69885834a87dc842b546c78ab6585d5f05415`, rama
`jose/automations-main-integration-v2`, Windows/CPU, 2026-10-01.
Este documento describe los arreglos y su propia validación; no constituye
auditoría independiente, autorización de piloto o integración a main.

La evidencia externa de esta ejecución se conserva en
`D:\Projects\AeroTrack_evidencias\correcciones_9bc698_20261001_080245_d3898481`.
`INFORME_CORRECCIONES.md` registra comandos, resultados, SHA final, preservación,
fallos de los primeros intentos y límites. La auditoría previa permanece intacta.
508/508 fue la validación anterior de Fase 8; 364/364 y 19 checks corresponden
a la auditoría dirigida anterior. Ninguno se presenta como resultado nuevo.

## Contratos corregidos

| ID | Cambio | Regresión y control |
|---|---|---|
| AUD-01 | `Engine.configure(expected_project=...)` verifica propietario dentro del mismo lock que elige archivos y persiste. Handler delega esa verificación. | `test_audit_http`: barrera HTTP A→B; rechazo sin cambios en JSON/SQLite de ambos; guardado legítimo en B. |
| AUD-02 | Almacén de usuarios corrupto, ilegible o de esquema inválido produce `UserStoreError`; no bootstrap ni mutaciones. POST consume cuerpo antes de responder 503; GET de auth responde 503 seguro. | HTTP con JSON/esquemas inválidos, lectura denegada portable, cuenta y sesión sintéticas, archivo previo inalterado, control autorizado. |
| AUD-03 | Una sola recuperación histórica validada; cada artefacto inválido se conserva y diagnostica por ID. Resúmenes de duración cero siguen disponibles; no equivalen a evidencia suficiente para reporte automático. | Writer real; created/config/end ausentes o inválidos, estructuras/JSON malformados, sano disponible y bytes inalterados. Regresión existente de resumen t=0 conservada. |
| AUD-04 | Señales cooperativas preceden a la consulta del registro; adquisiciones del coordinador no bloquean. Cancelaciones que necesitan locks de componentes son operaciones poseídas. | Barreras reteniendo registry y componente; timeout incompleto, ownership intacto, drenaje posterior y cierre normal. |
| AUD-05 | `save()` mantiene propiedad de proyecto; los callers de PlanWorkspace no reasignan el snapshot anterior después de await. Callers que inician otra operación no continúan después de un cambio de proyecto. | React real con hook y componente reales: respuesta diferida, edición posterior, segundo guardado, rechazo y apertura de B. |
| AUD-06 | Writer/reader verifican finalización v1 antes de publicar desde JSONL; HTTP y recuperación estricta rechazan inconsistencia. Se normaliza `analysis:null` legítimo de YOLO sin combined a objeto vacío, sin fabricar métricas. | Dos muestras t=10/count=1 y t=20/count=3; truncamiento por línea completa, cola malformada, estado/end/finalización incoherentes; no PDF/no_data; PDF íntegro y muestreo legítimo como controles. |
| AUD-07 | Engine y reproyección comparten snapshot de cámaras, incluidos pares y zona útil. Se respeta cambio de source y se soporta el formato legacy reconocido. | Writer real, identidad conservada con misma configuración, cambio de fuente sin reutilizar personas, calibración distinta con asociación local, formatos contradictorios y redacción LIVE. |
| AUD-08 | Bounds de video/plano y geometría compartidos en backend. Identidad del check incluye proyecto/servidor/cámara/fuente/plano/pares/dimensiones/unidad. | HTTP 12×8/x=12.5 y UV inválido; cambio de ancho, control válido, borrador/archivo previo intactos. React+navegador con HTTP Python real y respuesta anterior retrasada. |
| AUD-09 | Historial y rutas directas capturan el mismo contexto de proyecto; una sesión conocida de B no se recupera ni reproyecta desde A. | Reproducción HTTP nueva: A/B, history/data/video/current, acceso legítimo, cambio de proyecto y legacy sin propietario. |
| AUD-10 | `load_tests` recoge una vez cada una de seis funciones de continuidad. Fixture sintético sin camaras.json real. | Discovery pasó de 0 a 6; fusión, distancia, ventana, descriptor, purga y Kalman conservan assertions. |
| AUD-11 | Guías alineadas con AVIE y retención opt-in; antecedente LIVE histórico etiquetado. | Contraste estático con implementación; resultados antiguos conservados como antecedentes. |

Se corrigieron también fixtures que impedían una regresión aislada: cámaras
sintéticas explícitas en `test_live_core`/`test_reintento_fusion_tardia`, eliminación
del reload global en `test_proyecto_nuevo_limpio`, contexto de servidor en el test
de rangos HTTP y fecha de manifiesto válida en `test_session_reports`. No se
rebajaron assertions. El script de fusión tardía conserva assertions al importar:
no se cuenta como casos `unittest` adicionales ni como porcentaje de cobertura.

## Compatibilidad y evidencia histórica

Los manifiestos nuevos declaran `evidenceVersion=1` desde el inicio. Al cerrar,
`completion` guarda versión, cantidad de muestras, bytes, SHA-256, último t,
end y estado. El digest/conteo se acumula durante escritura, nunca a partir de un
archivo posiblemente truncado después. El lector compara todos esos valores.
No exige que la última observación sea igual al final de sesión: puede ser
anterior. Acepta muestras en t=0, tiempos repetidos, intervalos variables y cero
personas. El conteo de observaciones no son visitantes únicos.

- `verified`: archivo y finalización v1 concuerdan. No es autenticación frente
  a cambios deliberados en archivo y manifiesto por un escritor privilegiado.
- Inconsistente o finalización ausente en v1: error explícito; recuperación no
  habilita un reporte programado normal y éste queda `no_data`.
- `unknown`: formato legacy sin prueba de completitud. Conserva la compatibilidad
  de lectura y política previa de reportes, con estructura/tiempos coherentes;
  **no se afirma íntegro**. Truncamiento por líneas completas de un legacy puede
  ser indetectable. Decidir una política futura más restrictiva requiere al equipo.

`GET /api/report/session?session=...` expone `evidenceIntegrity`; sin sesión
archivada indica `in_memory`. No hay reescritura histórica ni migración de datos.
Los checksums no acreditan completitud de todo el video original: acreditan las
muestras que el writer escribió, con el muestreo del pipeline.

La reproyección admite cámaras en el nivel superior y el formato histórico
`config.cameras`. Datos contradictorios se rechazan. Un histórico que no guardó
pares suficientes no acredita asociaciones globales con la calibración actual;
se mantienen locales. Una fuente LIVE redactada no permite verificar identidad
actual y no se reproyecta por suposición. Se pueden seguir leyendo sus muestras
originales. No se incorporan URLs/credenciales de stream al snapshot.

Legacy sin `projectId` permanece visible/consultable como desconocido según el
historial existente; `projection=current` se rechaza. No se le asigna el proyecto
abierto ni se autoriza su uso como evidencia de reporte de un proyecto conocido.
Una política de reasignación humana queda pendiente; proyectos no son tenants.

Clientes antiguos de calibration-check que sólo envían pares siguen recibiendo
diagnóstico geométrico con `contextValidated:false`. La UI actual envía dimensiones
y exige confirmación contextual; un número suficiente de pares por sí solo no
significa Preparado. Un cambio físico requiere nueva calibración: este check
matemático no mide precisión física. No se duplican umbrales en TypeScript.

## Regresiones ejecutables

Python: `python -B -m unittest discover -s proyecto_lap_prototipo/tests` en el
entorno CPU existente. Para esta ejecución se usó un runner externo que proporciona
defaults sintéticos, bloquea acceso a config/data reales, escritura externa al
workspace de evidencia, captura no sintética y SMTP, y permite sólo loopback.
Los tests de P2PNet mantienen pesos/fixture existentes y no escriben bytecode.

Frontend: `node scripts/check-calibration.mjs`, checks existentes, TypeScript
y Vite. `scripts/build-audit-browser.mjs <directorio-externo-nuevo>` compila la
regresión React real de `scripts/audit-browser-regression.tsx` con dependencias
existentes. Servirla en loopback y abrir su index ejecuta los tres casos AUD-05;
`body[data-result]` y `#results` contienen el resultado. Para `?calibration`, el
mismo origen debe servir `/api/calibration-check` mediante Handler/Engine con
ROOT temporal, token sintético del fixture, sin cuentas reales y con cámaras,
modelos y SMTP bloqueados. `calibration_browser_host.py` externo conserva el
host exacto usado en esta validación. Así las dos regresiones AUD-08 consultan
el backend real; sólo se retrasa su entrega al componente.

## Límites y decisiones que permanecen

La validación final de este diff ejecutó **530/530** casos Python únicos en
**61.161 s**, sin failures, errors, skipped ni violaciones de aislamiento.
Incluye 14 nuevas regresiones HTTP/recuperación, dos de cierre y las seis funciones
de continuidad ahora recogidas. Pasaron los 20 checks de calibración, los otros
checks frontend aplicables, TypeScript, build y cinco casos de navegador real.
El smoke grabado CPU verificó writer, recuperación, reproyección y PDF con
IMG_1735 (0–15.6 s) y el híbrido IMG_1555/1556 (0–60 s, 182 llamadas P2PNet).
No es una prueba LIVE ni un benchmark de capacidad. Advertencias, ejecuciones
fallidas previas, inventario y estado de publicación constan en el informe externo.

- AT-06 **PARCIAL**: timeout no mata operaciones nativas ni autoriza cerrar un
  writer que sigue trabajando. Se distingue cancelación, incompleto y drenado.
- AT-11 **PARCIAL**: siguen persistiendo coordenadas, IDs temporales y firmas de
  apariencia según el inventario; no se declara anonimato ni cumplimiento legal.
- R-01: matriz de lecturas locales/roles y redacción general de secretos pendiente.
  No se cambió esa política; fallar cerrado ante usuarios corruptos sí era un bug.
- R-02: posible exceso de solicitudes al arrastrar referencias, **HIPÓTESIS**;
  invalidación de respuestas no aborta el fetch. Medir antes de fijar coalescencia.
- R-03: cola sólo por instancia; timeout HTTP no prueba que el servidor no guardó.
  No hay coordinación de escritores externos ni transacción distribuida.
- R-04: scan completo de JSONL sigue O(n), aunque se reduzca la serie retenida;
  hash añade trabajo lineal, sin cargar otro archivo completo en memoria.
- R-05: el último P2PNet puede seguir disponible con timestamp antiguo. La
  auditoría previa midió edades de hasta 65.2 s, no inferencias de 65.2 s.
  Frescura admisible, FPS, capacidad y latencia objetivo requieren decisión.

Cuatro automatizaciones siguen disabled por defecto. No se implementan CUDA/MPS,
CAL-1, restore ni nuevas políticas de privacidad, retención, roles o negocio.
El [LIVE histórico MacBook](PRUEBA_LIVE.md) fue reportado; esta ejecución procesa
grabaciones en CPU. Revalidación LIVE integrada, escenarios multicámara, oclusiones,
cruces, referencia humana y perfil NVIDIA/CUDA posterior siguen separados.
