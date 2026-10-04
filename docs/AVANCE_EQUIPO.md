# AeroTrack — avance del equipo

## Actualización del 4 de octubre de 2026 (America/Lima)

La rama **`jose/automations-main-integration-v3`** reúne nuestras correcciones
publicadas en `90ba03d` y las novedades de `main` hasta `de44a7e`, manteniendo
las ramas originales. Consulta [el informe de integración](INTEGRACION_MAIN_20261004.md)
para los resultados nuevos, las exclusiones, los conflictos resueltos y la copia
que debe descargar el equipo. La candidata mantiene el dictamen **REQUIERE
CORRECCIONES**: REV-03/04/06 y la causa histórica de NMS permanecen abiertos.

En la revisión anterior `90ba03d`, el piloto del 4 de octubre acreditó
**300.188 s LIVE Windows/CPU**, **1392 inferencias YOLO**, **40 inferencias P2PNet**
y **503 solicitudes HTTP de frames**, con salida 0 y cierre cooperativo. La
confirmación visual del usuario y el motivo del cese de solicitudes al final
siguen pendientes. No es una validación LIVE/CUDA de esta nueva integración.
El ZIP externo y su hash están identificados en el informe enlazado; no se
publican medios, credenciales ni los resultados privados completos.

## Registro histórico del 1 de octubre de 2026

El contenido siguiente conserva su corte y resultados originales. Sus referencias
a «piloto no iniciado», «host no validado» y a la rama v2 describen ese intento;
el estado posterior está arriba y en el informe de integración.

# AeroTrack — avance y evidencias para el equipo

Corte: **1 de octubre de 2026, America/Lima**, publicación intermedia para revisión
autorizada después del control fallido del host experimental de las 22:13.
El diagnóstico NMS de las 15:57 y los cierres documentales se conservan como
antecedentes; esta entrega incorpora su resumen y el resultado E5.

**Dictamen: REQUIERE CORRECCIONES. El piloto LIVE no se inició.** Esta entrega
comparte el avance para revisión; no equivale a aprobación de producción ni
integración a `main`. REV-03/04/06 siguen pendientes y NMS permanece abierto.

## Qué recibirá un compañero mediante Git

Repositorio: [AngelAguilar21/Proyecto_LAP_Captone](https://github.com/AngelAguilar21/Proyecto_LAP_Captone).
Rama: `jose/automations-main-integration-v2`.
Base anterior a esta entrega intermedia, comprobada local y remotamente:
**`4f43cb9bd15896cd930477c5e0ea829971fef175`**.
La nueva revisión incluye el código indicado abajo; su SHA final se comunica
después de comprobar el push. Identifica tu copia con `git rev-parse HEAD` y
contrasta ese hash con el cierre de publicación. No se inventa aquí el hash del
commit que contiene este mismo documento.

| Estado | Contenido al corte |
|---|---|
| Incluido en commit y publicado | Integración F1–F8 y correcciones AUD-01–11 hasta `4f43cb9`; documentos históricos enlazados abajo |
| Incluido en esta entrega intermedia | REV-01/02/05, en seis archivos de código/tests; `4f43cb9` por sí solo no los contiene |
| Documentación incluida en la misma entrega | Esta nota, `INSTALACION.md` y README; disponibles junto al código al obtener la revisión publicada |
| Pendiente | REV-03/04/06, causa original de NMS y piloto LIVE Windows; el primer control del host experimental falló antes de abrir captura |
| Excluido de publicación | Cambios preexistentes de P2PNet, vault, credenciales, datos, modelos locales, videos y evidencia externa completa |

El usuario sustituyó expresamente, para esta publicación intermedia, la condición
anterior de esperar al cierre de todos los hallazgos. Se seleccionan sólo seis
archivos de código/tests y tres documentos; quedan fuera P2PNet y los activos
locales. No se presentan los seis hallazgos como resueltos ni se inicia otro
piloto. La [guía de ejecución](../INSTALACION.md) contiene comandos
para obtener la versión realmente compartida y revisar una copia con trabajo
propio sin descartarlo. El acceso de cada compañero requiere permisos de lectura.

## Mejoras observables ya incluidas en la rama

El trabajo mejora integridad y recuperación, además de la operación cotidiana;
no hay un porcentaje acreditado de mejora de velocidad o precisión.

- Las automatizaciones integradas permiten programar reportes, mantener
  notificaciones durables por incidente, generar backups consistentes y aplicar
  retención con protecciones de recursos activos/referenciados. Permanecen
  **deshabilitadas por defecto**; una configuración previa puede habilitarlas.
  Alcance y límites: [matriz de integración](../proyecto_lap_prototipo/docs/INTEGRACION_AUTOMATIZACIONES.md),
  [reportes](../proyecto_lap_prototipo/docs/REPORTES_PROGRAMADOS.md),
  [escalamiento](../proyecto_lap_prototipo/docs/ESCALAMIENTO_INCIDENTES.md),
  [backups](../proyecto_lap_prototipo/docs/BACKUPS_PROYECTOS.md) y
  [cleanup de uploads](../proyecto_lap_prototipo/docs/UPLOADS_CLEANUP.md).
- La configuración y calibración muestran rechazos y contexto obsoleto en lugar
  de dar por guardado lo que no se confirmó. La recuperación de sesiones conserva
  configuración histórica y evidencia para reportes sin reactivar cámaras.
  La validación geométrica no acredita precisión física.
- Las correcciones AUD añadieron rechazo seguro de usuarios corruptos, validación
  de integridad del replay v1, control de pertenencia en rutas de historial y
  cierre cooperativo que distingue recursos todavía activos. El documento
  [CORRECCIONES_POST_AUDITORIA](../proyecto_lap_prototipo/docs/CORRECCIONES_POST_AUDITORIA.md)
  conserva la tabla AUD-01–11, sus regresiones y límites. La revisión posterior
  detectó los casos REV de la tabla siguiente: aquella entrega no implica que
  todos los recorridos relacionados estén resueltos.

## Hallazgos de la revisión posterior y estado real

Los identificadores de evidencia E1–E5 se resuelven al final. Los archivos
enlazados son rutas del repositorio e incluyen las correcciones REV-01/02/05
en esta entrega. Una copia detenida en `4f43cb9` todavía contiene la versión anterior.

| ID | Problema e impacto | Cambio o comportamiento pendiente | Evidencia | Estado |
|---|---|---|---|---|
| REV-01 · alto | Guardar reglas de alertas de A mientras se abre B podía escribir en la configuración de B | Identidad esperada de proyecto; lock cubre contexto y persistencia; React descarta confirmaciones/errores tardíos | E1/E2; tres regresiones HTTP nuevas en [test_audit_http.py](../proyecto_lap_prototipo/tests/test_audit_http.py), tres casos React nuevos en [audit-browser-regression.tsx](../proyecto_lap_prototipo/dashboard/scripts/audit-browser-regression.tsx); control de archivos JSON/SQLite A/B y guardado legítimo | **Corregido e incluido en esta entrega intermedia para revisión** |
| REV-02 · medio | Un histórico con `end=10**400` producía OverflowError y podía impedir el arranque | Validación numérica controlada por artefacto; rechazo conserva bytes y permite recuperar otro histórico sano; controles de duración cero y muestras desbordadas | E1/E2; [test_audit_recovery.py](../proyecto_lap_prototipo/tests/test_audit_recovery.py) y [replay.py](../proyecto_lap_prototipo/src/replay.py) | **Corregido e incluido en esta entrega intermedia para revisión** |
| REV-03 · medio | `cameraAnalytics.C.crossings=null` termina la conexión al exportar PDF | Pendiente de manejar metadatos anidados inválidos; lo observado fue TypeError/RemoteDisconnected, no caída global o corrupción SQLite demostradas | E1: probe adversarial de exportación | **Pendiente** |
| REV-04 · medio contractual | El helper acepta cámaras legacy en `config.cameras`, pero la capa HTTP rechaza ese formato | Alinear el contrato; impacto sobre históricos reales emitidos con ese formato aún no demostrado | E1: contraste helper/HTTP; acota la afirmación legacy del documento de correcciones previo | **Pendiente** |
| REV-05 · medio, test | Elección de la última sesión dependía de fechas reales y orden de enumeración | Fechas sintéticas distintas y prueba en ambos órdenes; sin sleep ni nuevo desempate de producción | E1/E2; [test_audit_recovery.py](../proyecto_lap_prototipo/tests/test_audit_recovery.py) | **Corregido e incluido en esta entrega intermedia para revisión** |
| REV-06 · bajo documental | El inventario niega un control de pertenencia que el código sí aplica | Sigue la contradicción del apartado de autorizaciones; esta nota la señala, no declara reparado el documento fuente | E1; [INVENTARIO_PERSISTENCIA.md](../proyecto_lap_prototipo/docs/INVENTARIO_PERSISTENCIA.md) | **Pendiente** |
| NMS · incidente abierto | Cuatro tests fallaron al registrar `torchvision::nms` durante importación | Nuevos procesos pasan, pero no se demostró el primer mecanismo de fallo; no hay reparación acreditada. El usuario adoptó una excepción limitada para un piloto, sin cerrar el incidente | E2/E3; cuatro IDs exactos más abajo. E5 no reprodujo el error ni llegó a ejecutar su probe explícito | **Abierto, causa no demostrada; excepción experimental condicionada** |
| Preparación del host experimental | La primera carga de YOLO/Ultralytics intentó DNS externo y después leer `.git`, operaciones bloqueadas por las guardas | Se detuvo el intento; no se cambió producción, no se abrió cámara ni se repitió el arranque | E5: 12 controles negativos esperados pasan; los bloqueos posteriores son fallos del intento, no controles esperados | **Host NO VALIDADO; piloto no iniciado** |

Los seis archivos incluidos de REV-01/02/05 son `proyecto_lap_prototipo/live_server.py`,
`src/replay.py`, `tests/test_audit_http.py`, `tests/test_audit_recovery.py`,
`dashboard/src/aero/SecurityAlerts.tsx` y `dashboard/scripts/audit-browser-regression.tsx`
(todos los abreviados bajo `proyecto_lap_prototipo/`). El SHA256 del diff conjunto,
sin el marcador dirty de P2PNet, es
`9338cd16bf352589172f18ba08ce86dd736146688de2ed487f95d07e1526c208`.
No es un commit ni un hash de toda la instalación.

Antes de publicar se contrastaron individualmente los SHA256 de los seis archivos
con `final.json` del estado validado E2: **6/6 idénticos, sin cambios técnicos
posteriores**. Se conservaron las pruebas anteriores como antecedentes, incluidos
los errores originales; no se repitió la suite completa ni frontend para este
commit. Sólo se actualizó documentación y se comprobó su contenido y enlaces.
El índice y el commit se verifican por lista explícita, y el cierre registra el
SHA remoto. La equivalencia de contenido no resuelve los fallos históricos de NMS.

## Validaciones por versión y ejecución

Las suites siguientes son **resultados históricos**, contrastados para esta
nota. La tarea documental anterior no ejecutó tests, builds, inferencia, cámaras
o instalaciones. El control posterior del host E5 se registra por separado.
F/E/S significa failures/errors/skipped. Las filas se superponen: no deben
sumarse como cobertura ni como una sola suite.

| Versión o ejecución | Resultado | Duración unittest | Fuente y límite |
|---|---|---:|---|
| Entrada F8, `0b611e0` | 500; 498 pasan, **1F/1E/0S** | 48.805 s | [Fase 8](../proyecto_lap_prototipo/docs/FASE8_VALIDACION.md); fallos de fixture conservados |
| Cierre F8, incluido en `9bc6988` | 508/508, 0F/0E/0S | 56.937 s | Mismo documento; checks, smoke y límites diferenciados |
| Correcciones incluidas en `4f43cb9` | 530/530, 0F/0E/0S | 61.161 s | [Correcciones AUD](../proyecto_lap_prototipo/docs/CORRECCIONES_POST_AUDITORIA.md), E4; no es la revisión independiente posterior |
| Revisión independiente de `4f43cb9`, lote dirigido válido | 63; 62 pasan, **1F/0E/0S** | 5.115 s | E1, `directed_contracts_valid.log`; no era suite completa |
| Misma revisión, adversariales | 7; 3 pasan, **3F/1E/0S** | 0.825 s | E1, `adversarial_contracts.log`; expone casos no cubiertos por el verde anterior |
| REV-01/02/05 locales, dirigidos | 39/39, 0F/0E/0S | 4.878 s | E2, diff local identificado arriba |
| Primera suite completa de ese diff | 536, **0F/4E/0S** | 39.777 s | E2, `full_suite.log`; no se oculta este intento |
| Detector aislado posterior | 5/5, 0F/0E/0S | 6.625 s | E2; no demuestra causa del fallo completo |
| Segunda suite completa, diagnóstico | 536/536, 0F/0E/0S | 37.276 s | E2, `full_suite_diagnostic.log`; mismos 536 IDs/orden, no una corrección demostrada |
| Diagnóstico NMS: cuatro afectados | 4/4, 0F/0E/0S | 8.843 s | E3, proceso nuevo, sin precargar Torchvision |
| Diagnóstico NMS: siete VideoTests + cuatro afectados | 11/11, 0F/0E/0S | 13.115 s | E3, otro proceso nuevo; repite los cuatro anteriores |

Frontend: F8 registra 19 checks dinámicos de calibración; `4f43cb9` registra 20
checks y cinco casos de navegador; E2 registra 20 checks y seis casos React,
además de TypeScript/build correctos. Los seis de E2 no se suman a los cinco
anteriores como una única ejecución. E3 no repitió frontend ni la suite completa.

E3 ejecutó **15 casos unittest contando repeticiones, 11 IDs únicos y cuatro
probes NMS reales en CPU**. Cada probe conservó `[0,2]` con cajas/scores sintéticos;
no se sustituyó el operador. El discovery de 536 IDs no fue otra ejecución de
536 tests. Las guardas de configuración/datos, SMTP, captura sintética y red
loopback no registraron violaciones. Inferencia P2PNet sólo en los tests
existentes autorizados con su fixture oficial local; no datos operativos.

Los cuatro IDs originales son:

```text
test_detector_cache.DetectorCacheTests.test_p2pnet_ajusta_el_tamano_de_analisis_sin_recargar_los_pesos
test_detector_cache.DetectorCacheTests.test_p2pnet_de_verdad_detecta_igual_con_el_detector_reutilizado
test_detector_cache.DetectorCacheTests.test_p2pnet_procesa_dos_camaras_en_un_solo_lote
test_detector_cache.DetectorCacheTests.test_p2pnet_se_carga_una_vez_y_la_segunda_vez_es_mucho_mas_rapido
```

El mensaje literal fue `RuntimeError: operator torchvision::nms does not exist`,
durante importación/registro, antes de inferencia P2PNet. No demuestra fallo
CUDA, DLL concreta ni incompatibilidad de versiones. La hipótesis de primera
carga fallida seguida por imports parciales sigue sin traza causal. Que ahora
pase no acredita que se haya reparado; tampoco justifica reinstalar a ciegas.

E5 ejecutó **una única validación sin cámara del host externo**, el 1 de octubre
a las 22:13 (Lima), durante **16.109756 s**, con salida **2**. Sus 12 controles
negativos esperados de las guardas pasaron. Durante la primera carga real de
YOLO/Ultralytics, las guardas bloquearon intentos DNS de `one.one.one.one` y
`dns.google`; después bloquearon una lectura de `.git`. Esas llamadas no salieron
a la red externa. Los fallos se conservaron y no hubo un segundo arranque.

El resultado fue **0 modelos cargados completamente, 0 inferencias, 0 muestras,
0 capturas y 0 s LIVE**. No hubo servidor atendiendo ni recorrido UI acreditado.
El probe explícito NMS no llegó a ejecutarse y el error histórico no reapareció;
no se declara NMS aprobado en este proceso. El cierre registró
`quiescent=true`, sólo `MainThread` y posteriormente PID propio ausente.
La comprobación de guardas y cierre no convierte el host en validado: falló su
preparación. Esta ejecución no es otra suite de 536 tests ni un piloto abreviado.

## Estado LIVE y significado de las métricas

| Elemento | Estado comprobado tras E5 |
|---|---|
| Piloto integrado Windows | **No iniciado: control del host fallido; cámara no abierta; duración efectiva 0 s** |
| Fuente identificada/autorizada en el equipo original | Integrated Camera de Lenovo Legion, índice DirectShow 0; autorización para un único ensayo de 300 s, sin video/audio/imágenes ni screenshots de cámara guardados |
| Modelo/dispositivo efectivos de ese piloto | **No medidos**, porque no se inició; el entorno y probes observados son CPU |
| Imagen real procesada en UI, FPS procesados, edad/latencia, recuperación y cierre LIVE | **No acreditados**; sí se comprobó cierre del proceso de preparación E5, sin captura |
| Scripts externos | `pilot_live_host.py` antiguo: intacto, no ejecutado. Nuevo `pilot_host.py`: primer control fallido, **NO VALIDADO**. Ninguno incluido en Git ni presentado como comando de producción |

El criterio anterior exigía demostrar la causa NMS antes de abrir la cámara;
E2/E3 se cerraron bajo esa regla y sus informes permanecen intactos. Después,
el usuario adoptó expresamente `LAP_Piloto_LIVE_Controlado_NMS_Abierto.md`.
**Sólo para un piloto experimental**, permite mantener la causa histórica
desconocida y exige preparación verificada, precheck satisfactorio en el mismo
proceso y detención ante cualquier fallo actual. No declara cumplida la regla
anterior ni autoriza ignorar fallos nuevos. E5 quedó detenido por su fallo de
preparación, antes de captura, bajo este criterio nuevo.

La misma Integrated Camera ya está autorizada: no corresponde solicitar otro
permiso para esa fuente. Sí hay que revalidar su identidad DirectShow por
metadata; índice 0 con otro backend no la demuestra. La autorización no cubre
fuentes de otros compañeros ni otros dispositivos.

Las condiciones experimentales incluyen raíces externas de prueba, SMTP y
automatizaciones deshabilitados, conexiones externas bloqueadas y límites
de arranque, falta de avance y cierre declarados. Antes de captura, el mismo
proceso debe cargar los detectores reales del perfil, ejecutar NMS CPU con
resultado `[0,2]` e inferencia sintética y comprobar CPU efectivo. La preparación
deliberada se documenta: no es necesariamente el arranque histórico.
El perfil `hybrid` conserva YOLO y P2PNet/AVIE; si no se activa P2PNet durante
LIVE, no se afirmará validada esa activación.

La ventana de 300 s comienza con la primera muestra real procesada; una pausa
planificada se incluye y se informa aparte. No sumar intentos ni llamarla
procesamiento continuo. Los frames sólo se muestran en memoria; se conservan
métricas y derivados mínimos del ensayo, sin imágenes, video, audio o capturas
de pantalla de la cámara. Un error nuevo, falta de avance o violación de
aislamiento exige detenerse sin reinicios para encontrar un verde. Incluso
completar el ensayo dejaría NMS **abierto con causa no demostrada**.

El [protocolo existente](../proyecto_lap_prototipo/docs/PRUEBA_LIVE.md) distingue
FPS fuente, tasa de procesamiento, inferencia y edad captura/pantalla. Una cifra
de FPS de cámara o duración de inferencia no equivale a latencia extremo a
extremo. Un piloto de cinco minutos tampoco valida estabilidad prolongada,
multitudes, capacidad multicámara o precisión física.

Antecedente MacBook/iPhone: **reportado por el usuario**, 35 s, 517 frames,
14.75 FPS, YOLO11n/MPS y ByteTrack. No se recuperaron logs originales ni SHA;
no acredita el Windows integrado, RTSP ni multitudes. Las grabaciones CPU de E4
y los probes sintéticos son evidencias distintas, no sustitutos de LIVE.

## Cronología verificable

Fechas de los commits según Git; no representan horas trabajadas. Todos los
commits siguientes son ancestros del HEAD publicado. Consultar
`git log --oneline` y `git show <SHA>` permite revisar sus cambios.

| Fecha | Commit | Hito |
|---|---|---|
| 2026-09-30 | `9b2a75b` | F1: notificaciones durables |
| 2026-09-30 | `01b253f` | F2: identidad estable por episodio |
| 2026-09-30 | `9f0ab4b` | F3: runtime y apagado cooperativo |
| 2026-09-30 | `f7c1b75` | F4: reportes programados y salud de artefactos |
| 2026-09-30 | `3c5988b` | F5: backups verificados y retención |
| 2026-09-30 | `b1904f9` | F6: escalamiento durable |
| 2026-09-30 | `0b611e0` | F7: cleanup de uploads |
| 2026-10-01 | `9bc6988` | F8: integración y validación |
| 2026-10-01 | `4f43cb9` | Correcciones AUD-01–11, luego sometidas a revisión independiente |
| 2026-10-01 | Sin commit | E1 encuentra REV-01–06; E2 corrige localmente REV-01/02/05 |
| 2026-10-01 | Sin cambio de código | E3 termina con causa NMS no demostrada y LIVE pendiente |
| 2026-10-01 | Sin commit documental | README, esta nota y guía preparados; publicación condicionada al cierre vigente |
| 2026-10-01 | Sin commit | Adopción expresa del criterio experimental limitado con NMS abierto; no reescribe los cierres anteriores |
| 2026-10-01, 22:13 Lima | Sin cambio de producción | E5: único control del host falla en 16.109756 s; cierre comprobado, cámara no abierta y piloto no iniciado |
| 2026-10-01, publicación intermedia | Commit de esta entrega | Autorización expresa para compartir REV-01/02/05 y estos tres documentos; 6/6 hashes coinciden con E2. REV-03/04/06, NMS y LIVE siguen pendientes |

## Evidencias disponibles y originales externos

Las guías históricas enlazadas existen en Git. Este resumen incorpora conteos,
casos y límites relevantes para que no sea necesario acceder a un disco local
para comprender el resultado. Los originales externos siguientes **no están
incluidos en el repositorio ni tienen un enlace compartido comprobado**. Los IDs
permiten pedir una copia revisada al responsable; no prometen acceso remoto.

| ID | Directorio de ejecución, fecha 2026-10-01 | Originales externos relevantes |
|---|---|---|
| E1 | `revision_4f43cb9_20261001_094427_bb536896` | `INFORME_REVISION.md`, `RESULTADOS_PRUEBAS.json`, `CHECKPOINT.md`, logs dirigidos/adversariales |
| E2 | `prioridad_live_4f43cb9_20261001_135702_0ebc532d` | `INFORME_AVANCE.md`, `RESULTADOS_PRUEBAS.json`, `CHECKPOINT.md`, ambas suites completas y diff local |
| E3 | `diagnostico_nms_20261001_154226_d4d47fa4` | `INFORME_DIAGNOSTICO_NMS.md`, `RESULTADOS_PRUEBAS.json`, `CHECKPOINT.md`, `TRACEBACKS_ORIGINALES.txt`, logs/trazas por proceso |
| E4 | `correcciones_9bc698_20261001_080245_d3898481` | `INFORME_CORRECCIONES.md`, resultados/checkpoint; resumen versionado en CORRECCIONES_POST_AUDITORIA |
| E5 | `piloto_live_nms_abierto_20261001_215751_4d6ab791` | `INFORME_PILOTO_LIVE.md`, `RESULTADOS_PRUEBAS.json`, `CHECKPOINT.md`; control fallido del host, cierre y resultado no iniciado |

El informe original, resultados y checkpoint de E3 permanecen intactos. Los
hashes de logs históricos de E2 verificados en ese cierre son:

```text
full_suite.log             c915975168df4cb855dca82a244cc7c99fdb9306400b05a71e96309aa3bb6e91
full_suite_diagnostic.log  ac8212e5be8fa6c0e99de4046be66d2d429f7694d923cda2a79073309c96fb77
```

Son referencias de integridad de esos archivos, no firmas de confianza ni
equivalentes a haber entregado sus bytes. No se copiaron logs íntegros, rutas
personales, conversaciones, credenciales, bases, pesos, videos o el vault para
hacerlos accesibles. Esta documentación resume evidencia sin alterar originales.

## Decisiones y pendientes del equipo

- Cerrar REV-03/04/06 y mantener la investigación causal de NMS abierta; los
  verdes posteriores y la excepción experimental no son una reparación.
  Resolver y validar el fallo de preparación E5 antes de proponer otro intento;
  no repetir arranques hasta encontrar uno verde ni abrir captura sin precheck.
- Mantener los límites del [inventario](../proyecto_lap_prototipo/docs/INVENTARIO_PERSISTENCIA.md):
  hay coordenadas, IDs temporales y firmas de apariencia persistidas; AT-11 y
  la matriz de lecturas/roles R-01 siguen pendientes. No se declara anonimato,
  privacidad aprobada ni aislamiento multi-tenant. REV-06 acota la contradicción
  de ese documento; no repetirla como contrato confirmado.
- AT-06 sigue parcial: un timeout no termina una llamada nativa ni autoriza a
  liberar un writer activo. Quedan coordinación entre instancias, costo lineal
  de lectura JSONL y política de frescura de resultados P2PNet, entre los límites
  descritos en la documentación de correcciones.
- El alcance de la webcam y el ensayo de 300 s ya fue adoptado; no requiere una
  nueva solicitud de permiso para esa misma fuente. Escenarios adicionales
  requieren su propio alcance de fuente/escena, responsables, retención y
  revisión humana. Los límites del ensayo no son SLA ni criterios aprobados
  de precisión/FPS/latencia. CUDA/MPS e instalación limpia siguen sin validar.
- Esta publicación intermedia de código y documentación está autorizada para
  revisión, con selección explícita y verificación del SHA remoto. No cierra
  los pendientes ni autoriza producción, otro piloto, PR, merge a main, cambios
  de permisos o mensajes al grupo. P2PNet, entornos, datos y evidencia externa
  permanecen fuera de la entrega.
