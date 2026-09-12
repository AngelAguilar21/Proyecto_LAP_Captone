# NOTAS_FUENTES.md

Trazabilidad de las afirmaciones del informe.

**Responsable:** Fabián Moreno Ugarte — Validación ética/legal y documentación
**Proyecto:** Capstone I, Universidad ESAN — Estimación de aglomeraciones, Aeropuerto Jorge Chávez (cliente: LAP)

---

## Cómo leer este archivo

Cada afirmación del informe cae en una de estas cuatro categorías. La columna
**Estado** dice de dónde sale y cuánto se puede confiar en ella hoy.

| Estado | Significado |
|---|---|
| **VERIFICADO-PDF** | Extraído directamente del PDF del artículo en `./papers/` y contrastado en el texto. |
| **VERIFICADO-PDF (parcial)** | Extraído del PDF, pero de una tabla cuya conversión a texto se degrada. Contrastado contra prosa del mismo artículo cuando fue posible. |
| **ENCARGO** | Proviene del enunciado del encargo interno del proyecto, **no** de la fuente primaria. Requiere contraste antes de la entrega. |
| **VERIFICADO-FML** | Verificado por Fabián Moreno Ugarte y aportado al informe como hallazgo confirmado. Se redacta en indicativo. Ver §2.6 para el detalle y lo que queda abierto en cada uno. |
| **NO VERIFICADO** | Conocimiento general de la materia, escrito en el informe de forma deliberadamente genérica. **No citar como dato firme.** |
| **RETIRADA** | Cifra que se leyó en el PDF pero que **ya no aparece en el informe**, por proceder de una tabla cuya extracción no es fiable y no constar en la prosa del artículo. Se conserva aquí el registro de dónde salía. |

> **Regla que se aplicó al redactar:** ningún artículo, numeral, fecha o cifra
> se escribió de memoria como si fuera dato firme.
>
> **Cómo se señala hoy lo no verificado.** El informe llevaba marcadores en
> ámbar dentro del cuerpo (`\pendiente{VERIFICAR}{...}` y
> `\pendiente{DECISIÓN FABIÁN}{...}`). Se retiraron el 1 de septiembre de 2026:
> cada afirmación afectada quedó reformulada en condicional o atribuida
> expresamente a su fuente dentro del propio texto —«se recoge en paráfrasis»,
> «procede del encargo del proyecto y no del texto de la norma»—, y las tareas
> de verificación se trasladaron a `PENDIENTES.md`. Este archivo sigue siendo el
> registro de por qué cada afirmación está donde está.

---

## 1. Papers (`./papers/`)

Los tres PDF fueron leídos íntegramente (extracción de texto con `pdftotext -layout`).

> ### ⚠ Regla aplicada a las cifras (2026-09-01)
>
> El informe **solo reproduce las cifras que constan en el texto en prosa** de
> cada artículo: resumen, introducción o discusión de resultados. Las que
> figuraban únicamente en una tabla de resultados fueron **retiradas del
> informe**, aunque resultaran favorables al argumento.
>
> El motivo es que la extracción de texto de las tablas a varias columnas de
> estos tres artículos mezcla filas y columnas de forma comprobable. En la
> Tabla 5 de CSRNet, por ejemplo, los pares MAE/MSE quedan desplazados respecto
> de la fila que los encabeza; en la Tabla 1 de P2R, las etiquetas de fila y los
> valores pertenecen a bloques distintos, y las anotaciones de la Figura 5 se
> interleaban con ellos. Atribuir una cifra al conjunto de datos equivocado es
> un error indetectable para quien lee el informe, y por eso se prefirió no
> arriesgarlo.
>
> Las tablas que siguen conservan el registro completo de lo que se leyó en cada
> PDF. La columna **Estado** indica ahora, además, si la afirmación **está en el
> informe** o si fue **retirada**. Las retiradas se conservan aquí a propósito:
> si alguien verifica visualmente las tablas de los PDF, este registro dice
> exactamente qué se podría reincorporar y de dónde salía.

### 1.1 CSRNet — `A1_CSRNet_CVPR2018.pdf`

Cita bibliográfica: `Li_2018_CVPR`, copiada literalmente de `papers/citas_oficiales.txt`.

| Afirmación en el informe | Estado | Ubicación en el PDF |
|---|---|---|
| Front-end = primeras 10 capas de VGG-16; back-end = convoluciones dilatadas | VERIFICADO-PDF | Abstract y §3.1 |
| Las columnas de MCNN aprenden características casi idénticas (motivación del diseño) | VERIFICADO-PDF | §1 y Fig. 2 / Tabla 1 |
| Ground truth por kernels gaussianos geométricamente adaptativos; pérdida euclídea | VERIFICADO-PDF | §3.2.1 y §3.2.3 |
| ~~MAE 68,2 en ShanghaiTech Parte A~~ | **RETIRADA** — solo en Tabla 5, sin respaldo en prosa | Tabla 5 (fila CSRNet, extracción desplazada) |
| ~~MAE 10,6 en ShanghaiTech Parte B~~ | **RETIRADA** — solo en Tabla 5, sin respaldo en prosa | Tabla 5 |
| 7 % menos MAE que CP-CNN en Parte A | VERIFICADO-PDF, **en el informe** | §4.3.1 (prosa) e introducción |
| 47,3 % menos MAE que CP-CNN en Parte B | VERIFICADO-PDF, **en el informe** | Abstract y §4.3.1 (prosa) |
| 15,4 % menos MAE que el mejor previo en TRANCOS | VERIFICADO-PDF, **en el informe** | Abstract (prosa) |
| **Limitación:** en UCSD superan a la mayoría de métodos previos *excepto a MCNN en MAE* | VERIFICADO-PDF, **en el informe** | §4.3.4 (prosa) |
| CSRNet obtiene 1,16 de MAE en UCSD | VERIFICADO-PDF, **en el informe** | Introducción (prosa): «we achieve high performance on the UCSD dataset with 1.16 MAE» |
| ~~MCNN obtiene 1,07 de MAE en UCSD~~ | **RETIRADA** — solo en Tabla 9, sin respaldo en prosa | Tabla 9 |
| **Limitación:** resolución 238×158 obliga a reescalar a 952×632 por interpolación bilineal | VERIFICADO-PDF | §4.3.4 |

> Nota: CSRNet **no tiene** una sección de limitaciones. Las dos anteriores se
> tomaron de admisiones explícitas de los autores dentro de la evaluación. La
> ausencia de posiciones individuales es una propiedad del paradigma de mapa de
> densidad, no una limitación que los autores declaren como tal; en el informe
> se presenta así.

### 1.2 P2PNet — `A2_P2PNet_ICCV2021.pdf`

Cita bibliográfica: `Song_2021_ICCV`, copiada literalmente de `papers/citas_oficiales.txt`.

| Afirmación en el informe | Estado | Ubicación en el PDF |
|---|---|---|
| Crítica a las representaciones intermedias (mapas de densidad, cajas pseudo-generadas) | VERIFICADO-PDF | Abstract y §1 |
| Predicción directa de puntos con coordenadas y confianzas | VERIFICADO-PDF | Abstract, §1, Fig. 1 |
| Emparejamiento uno a uno con algoritmo húngaro como pieza crítica | VERIFICADO-PDF | Abstract y §1 |
| Métrica nAP: evalúa localización y conteo, no ignora variación de densidad ni deja sin penalizar duplicados | VERIFICADO-PDF | Abstract y §1 |
| ~~MAE 52,74 (ShTech A), 6,25 (ShTech B), 172,72 (UCF_CC_50)~~ | **RETIRADAS** — solo en Tabla 2, sin respaldo en prosa | Tabla 2, fila «Ours» |
| MAE 85,32 en UCF-QNRF | VERIFICADO-PDF, **en el informe** | §4.3 (prosa): «our P2PNet achieves an MAE of 85.32» |
| ~~MAE global 77,44 en NWPU-Crowd~~ | **RETIRADA** — solo en Tabla 3; la prosa dice «best overall MAE» sin la cifra | Tabla 3 |
| Reducciones relativas: 4,8 % MAE y 12,9 % MSE en ShTech A frente a ADSCNet; 2,3 % MAE en ShTech B; 2,1 puntos de MAE en UCF_CC_50; 12,4 % en NWPU-Crowd frente a DM-Count | VERIFICADO-PDF, **en el informe** | §4.3 (prosa), apartados por conjunto |
| nAP₀.₅ ≈ 90 % en la mayoría de conjuntos | VERIFICADO-PDF, **en el informe** | §4.2 (prosa): «the P2PNet could achieve a nAP0.5 of nearly 90%» |
| nAP₀.₂₅ por encima del 55 % | VERIFICADO-PDF, **en el informe** | §4.2 (prosa) |
| F1/Precisión/Recall = 71,2 / 72,9 / 69,5 % en NWPU-Crowd | VERIFICADO-PDF, **en el informe** | §4.2 (prosa) |
| **Limitación:** en UCF-QNRF su precisión «no es tan competitiva» frente a ADSCNet | VERIFICADO-PDF, **en el informe** | §4.3, apartado UCF-QNRF (prosa) |
| **Limitación:** en NWPU-Crowd, MAE[S] inferior por usar un único mapa de características de una sola escala, elegido por simplicidad | VERIFICADO-PDF, **en el informe** | §4.3, apartado NWPU-Crowd (prosa) |
| **Limitación:** nAP₀.₀₅ notablemente más bajo por efecto de las desviaciones de etiquetado | VERIFICADO-PDF, **en el informe** | §4.2 (prosa) |
| ~~Rango del nAP₀.₀₅: 5,0 %–23,8 %~~ | **RETIRADA** — solo en Tabla 1; la prosa describe la caída sin cuantificarla | Tabla 1 |

### 1.3 P2R — `A3_Point2Region_SemiSup_CVPR2025.pdf`

Cita bibliográfica: `Lin_2025_CVPR`, copiada literalmente de `papers/citas_oficiales.txt`.

| Afirmación en el informe | Estado | Ubicación en el PDF |
|---|---|---|
| Motivación: coste de anotar cientos o miles de puntos por imagen | VERIFICADO-PDF | Abstract y §1 |
| La confianza de la pseudo-etiqueta no se propaga al fondo bajo P2P | VERIFICADO-PDF | Abstract y §1 |
| PSAM (mapa de activación específico por punto) como herramienta de diagnóstico | VERIFICADO-PDF | Abstract y §4.2 |
| Vecindario de cada píxel de primer plano queda sobre-activado y se lee como instancia distinta | VERIFICADO-PDF | Abstract y §7 (Conclusión) |
| P2R segmenta una región local en lugar de detectar un punto | VERIFICADO-PDF | Abstract |
| P2R elimina la necesidad del algoritmo húngaro, que los autores identifican como componente costoso | VERIFICADO-PDF | §5.1 y §7 |
| Conjuntos usados: ShTech A/B, UCF-QNRF, JHU++ (**no** NWPU-Crowd) | VERIFICADO-PDF | §6 (Experimentos) |
| Protocolos de 5 %, 10 % y 40 % de datos etiquetados | VERIFICADO-PDF | §6 |
| MAE 93,7 / MSE 155,2 — ShTech A, 5 % etiquetas, solo supervisado | VERIFICADO-PDF, **en el informe** | §6.4 (prosa, ablación de λ): «the model trained with only 5% labeled data (MAE: 93.7, MSE: 155.2)» |
| Usar 5 % de datos con P2R supera al totalmente supervisado con 10 % y equivale a otros semi-supervisados con 10 % | VERIFICADO-PDF, **en el informe** | §6.1 (prosa) |
| ~~MAE 69,9 — ShTech A, 5 % etiquetas, con P2R~~ | **RETIRADA** — solo en Tabla 1, que es justamente la de extracción degradada | Tabla 1 |
| Con 100 % de etiquetas, P2R supera a P2PNet en los cuatro conjuntos | VERIFICADO-PDF, **en el informe** | §6.1 (prosa): «P2R performs better than P2PNet on all crowd counting datasets» |
| Coste de la pérdida: 0,4307 s (P2P) vs. 0,0064 s (P2R) sobre imagen de 576×960 con 775 puntos; ~68× más rápido | VERIFICADO-PDF, **en el informe** | §6.1 (prosa) |
| **Limitación:** caso de fallo por desenfoque de movimiento de la multitud | VERIFICADO-PDF, **en el informe** | §6.1 (prosa) y Fig. 5 |
| ~~Escena con 61 personas reales y 227 predichas~~ | **RETIRADA** — anotaciones de la Fig. 5, que la extracción interleava con las filas de la Tabla 1; hay dos escenas con 61 de verdad de campo y no es posible atribuir la predicción con certeza | Fig. 5 |
| **Limitación:** brecha de dominio; sin adaptación el desempeño se degrada de forma marcada y los autores lo señalan expresamente | VERIFICADO-PDF, **en el informe** | §6.2 (prosa) |
| ~~MAE 25,6 sin adaptación vs. 10,6 con adaptación (A→B)~~ | **RETIRADA** — solo en Tabla 2, y la asignación de columnas al par de conjuntos A→B no es verificable en la extracción | Tabla 2, filas «P2R (w/o DA)» y «P2R (w/ DA)» |

> ⚠ **Advertencia sobre la Tabla 1 de este artículo.** Es una tabla a varias
> columnas cuya conversión de PDF a texto plano mezcla filas, y además queda
> interleavada con las anotaciones de la Figura 5. Ninguna cifra procedente de
> ella figura ya en el informe. **Antes de reincorporar cualquiera, hay que
> abrir el PDF y leerla visualmente**; hecho eso, las filas marcadas como
> RETIRADA en la tabla anterior indican qué se podría recuperar y de dónde
> salía. El informe ya no lleva marcador sobre este punto: en su lugar, la
> sección de antecedentes explica el criterio en una caja de aviso, y el archivo
> `PENDIENTES.md` no lo lista como pendiente porque no lo es: es una decisión
> tomada, no una tarea abierta.

---

## 2. Fuentes normativas

> **Actualización del 11 de septiembre de 2026.** El enunciado que sigue dejó de
> ser cierto para una parte de las normas. Al redactar
> `secciones/03_marco_normativo.md` y `secciones/04_analisis_impacto.md` se
> consultaron en texto primario la **Ley 29733** y el **D.S. 007-2020-IN**, y en
> reproducción íntegra de fuente secundaria la **Directiva 01-2020-JUS/DGTAIPD**
> y los **incisos 6 y 7 del artículo 2 de la Constitución**. Lo verificado se
> detalla en §2.7 y se cita entrecomillado en el informe. El **D.S. 016-2024-JUS
> sigue sin contrastarse contra su texto**: su articulado continúa marcado
> `[VERIFICAR]` en el cuerpo de la Sección 3.
>
> Se añade un estado nuevo a la leyenda de este archivo:
>
> | Estado | Significado |
> |---|---|
> | **VERIFICADO-PRIMARIA** | Contrastado contra el texto de la norma publicado por fuente oficial (portal del Estado, *El Peruano*). Se cita entrecomillado en el informe. |
> | **VERIFICADO-SECUNDARIA** | Contrastado contra una reproducción íntegra del texto en fuente secundaria fiable, **no** contra el documento oficial. Se cita entrecomillado pero conserva su `[VERIFICAR]` de contraste. |

> **Lo que sigue conserva el enunciado original**, aplicable a las normas que
> todavía no se contrastaron. El informe las cita en términos generales y marca
> con `[VERIFICAR]` todo numeral, fecha o redacción literal. Esta tabla es la
> lista de trabajo de verificación.

### 2.1 Nivel constitucional

| Norma | Qué afirma el informe | Estado | Dónde verificar |
|---|---|---|---|
| Constitución 1993, art. 2 inc. 6 | Derecho a que los servicios informáticos no suministren informaciones que afecten la intimidad personal y familiar; base del hábeas data | NO VERIFICADO (parafraseado) | Edición oficial de la Constitución / portal del Congreso |
| Constitución 1993, art. 2 inc. 7 | Derecho al honor, buena reputación, intimidad personal y familiar, voz e imagen propias | NO VERIFICADO (parafraseado) | Ídem |

**Acción pendiente:** transcribir literalmente ambos incisos y citar la fuente.
El informe explicita que están parafraseados.

### 2.2 Protección de datos personales

| Dato | Estado | Observación |
|---|---|---|
| Ley 29733, Ley de Protección de Datos Personales | NO VERIFICADO (denominación) | Verificar fecha de publicación y texto vigente (puede haber modificatorias) |
| Ley 29733 — datos biométricos que por sí mismos identifican al titular como dato sensible | NO VERIFICADO (numeral) | Verificar el numeral exacto del art. 2 y si el D.S. 016-2024-JUS precisó la definición |
| D.S. 016-2024-JUS — reglamento vigente | ENCARGO | Dato tomado del encargo del proyecto |
| Publicación 30/11/2024 | ENCARGO | **Contrastar contra El Peruano** |
| Vigencia desde 30/03/2025 | ENCARGO | **Contrastar contra El Peruano.** Un error aquí invalidaría el análisis de régimen transitorio |
| Deroga el D.S. 003-2013-JUS | ENCARGO | Contrastar contra la disposición derogatoria |
| Notificación de brechas en 48 horas | ENCARGO | Verificar: artículo, hecho desde el que se computa, si son horas hábiles o calendario, destinatario (ANPD / titulares / ambos), y si hay umbral de gravedad |
| Oficial de Datos Personales (ODP) | ENCARGO | Verificar: artículo, supuestos de designación obligatoria, obligación de comunicar a la ANPD, requisitos de independencia |
| Alcance extraterritorial | ENCARGO | Verificar: artículo y criterios de conexión |
| **EIPD exigible antes de tratamientos de alto riesgo** | **VERIFICADO-FML** | Ver §2.6-A. Cerró el `VERIFICAR` que preguntaba si existía figura equivalente al art. 35 RGPD |
| **Privacidad por diseño y por defecto como exigencia** | **VERIFICADO-FML** | Ver §2.6-B |
| **ODP con cronograma escalonado por ingresos anuales** | **VERIFICADO-FML** | Ver §2.6-C |
| Rangos de sanción (en UIT) | NO VERIFICADO | No se consignó ninguna cifra en el informe. Verificar régimen sancionador y valor de la UIT vigente |

### 2.3 Videovigilancia

| Norma | Qué afirma el informe | Estado | Acción |
|---|---|---|---|
| **Directiva 01-2020-JUS/DGTAIPD — vigencia** | **Vigente y aplicable pese al D.S. 016-2024-JUS** | **VERIFICADO-FML** | Ver §2.6-D. Redactado en indicativo, con nota al pie sobre lo que falta |
| Directiva 01-2020-JUS/DGTAIPD — contenido | Exige carteles informativos y aplica el principio de proporcionalidad | NO VERIFICADO | Verificar denominación oficial completa y número y fecha de la resolución directoral que la aprueba |
| D.L. 1218 | Regula el uso de cámaras de videovigilancia | NO VERIFICADO | Verificar denominación, fecha, obligaciones de entrega a PNP/Ministerio Público y plazos de conservación |
| Ley 30120 | Apoyo a la seguridad ciudadana con cámaras en áreas de dominio público | NO VERIFICADO | Verificar denominación, fecha y **si alcanza a establecimientos privados abiertos al público** |

**Zona gris registrada:** la naturaleza jurídica del terminal (espacio privado
de gestión concesionada, abierto al público, con función de interés público y
regulación sectorial aeronáutica) no se resolvió. El informe la plantea
expresamente como cuestión a elevar al área legal de LAP y **no** la da por
resuelta en ningún sentido.

### 2.4 Referencia comparada (no aplicable por territorio)

| Norma | Estado | Acción |
|---|---|---|
| RGPD art. 35 (evaluación de impacto) | NO VERIFICADO (parafraseado) | Verificar redacción literal antes de citarla textualmente |
| Reglamento (UE) 2024/1689 (AI Act) | NO VERIFICADO | El informe **no cita numerales**. Verificar los artículos sobre identificación biométrica remota y sobre alto riesgo, y el calendario de aplicación |
| ISO/IEC 27001 | NO VERIFICADO | Verificar año de edición vigente; averiguar si LAP ya está certificada |
| ISO/IEC 42001 | NO VERIFICADO | Verificar año de edición vigente y denominación en español |

> El informe advierte de forma explícita que **no** puede afirmarse sin más que
> el sistema «no está regulado por el AI Act» ni que «no es de alto riesgo»,
> porque la clasificación depende de la finalidad declarada y del contexto de
> uso, no solo de la técnica.

### 2.5 Licencias de conjuntos de datos

> **La verificación conjunto por conjunto se trasladó a
> `CHECKLIST_CUMPLIMIENTO.md`, sección B, como tarea asignada a Data
> Engineering.** Requiere acceso a los portales de descarga y a los formularios
> de solicitud, que es trabajo del frente de datos. El informe conserva los
> criterios que esa verificación debe satisfacer y los riesgos que debe
> descartar.

| Conjunto | Estado | Dónde se hace el seguimiento |
|---|---|---|
| ShanghaiTech (A y B) | NO VERIFICADO | Checklist B-01 |
| UCF-QNRF | NO VERIFICADO | Checklist B-02 |
| NWPU-Crowd (licencia) | NO VERIFICADO | Checklist B-03 |
| **NWPU-Crowd: no libera etiquetas de test; evalúa vía servidor externo** | **VERIFICADO-FML** | Ver §2.6-E. Checklist B-07 |

> **Decisión de redacción:** el informe **no transcribe** el texto de ninguna
> licencia y no afirma cuál es. En estos conjuntos los términos suelen figurar
> en la página del grupo de investigación, en un formulario de solicitud o en
> el propio artículo, y no en un archivo de licencia estándar. Reproducirlos de
> memoria habría sido exactamente el tipo de afirmación no verificable que este
> proyecto debe evitar.
>
> Sigue siendo, junto con las fechas del reglamento, el punto de verificación
> con mayor consecuencia práctica: si algún conjunto restringe el uso comercial,
> afecta a la posibilidad de desplegar el modelo en LAP y debe resolverse
> **antes** de entrenar.

### 2.6 Hallazgos verificados incorporados al informe

Aportados por Fabián Moreno Ugarte tras revisión de fuentes. Se redactaron en
indicativo en el informe. Esta tabla registra **qué se afirma** y **qué queda
abierto** en cada uno, para que la distinción no se pierda.

#### A — EIPD exigible (§Evaluación de Impacto en Protección de Datos)

- **Se afirma:** el D.S. 016-2024-JUS exige la EIPD **antes de iniciar**
  tratamientos de alto riesgo. Los supuestos incluyen expresamente
  videovigilancia masiva, perfilado automatizado con IA y tratamiento de datos
  biométricos a escala. Debe documentarse y puede requerir consulta previa a la
  ANPD.
- **Consecuencia en el informe:** cerró el `VERIFICAR` de §Referencia comparada.
  El RGPD art. 35 pasó de ser el fundamento a ser solo aporte metodológico. La
  §Análisis de impacto se reencuadró como insumo sustantivo de la EIPD. Se
  añadió el criterio E-00 a la auditoría, como no conforme.
- **Queda abierto:** artículo exacto, contenido mínimo del documento, y en qué
  supuestos la consulta previa a la ANPD pasa de facultativa a obligatoria
  (checklist A-07b).

#### B — Privacidad por diseño y por defecto (§Privacidad desde el diseño y por defecto)

- **Se afirma:** el reglamento la establece como **exigencia**, en su doble
  dimensión de por diseño y por defecto (configuraciones más privadas como
  estándar). No es buena práctica opcional.
- **Consecuencia en el informe:** las medidas M-01…M-10 pasaron de «lo que este
  frente propone» a requisitos. Se añadió el desarrollo de la dimensión «por
  defecto» y el criterio E-09 a la auditoría.
- **Queda abierto:** artículo que consagra ambos principios y si la norma
  detalla criterios o contenidos mínimos de acreditación (checklist A-07c).

#### C — ODP con cronograma escalonado (§Oficial de Datos Personales)

- **Se afirma:** la designación del ODP sigue un cronograma escalonado en
  función de los ingresos anuales de la empresa.
- **Consecuencia en el informe:** la pregunta al cliente cambió de «¿tienen
  ODP?» a «¿en qué tramo están y desde cuándo les es exigible?».
- **Queda abierto:** artículo, umbrales de cada tramo y sus fechas, obligación
  de comunicar la designación a la ANPD, requisitos de independencia
  (checklist A-05).

#### D — Vigencia de la Directiva 01-2020-JUS/DGTAIPD (§Directiva sobre videovigilancia)

- **Se afirma:** la Directiva está vigente y es aplicable. El D.S. 016-2024-JUS
  no la desplazó.
- **Evidencia:** el Congreso de la República la invoca como base legal de su
  propio sistema de videovigilancia en la **Resolución 088-2025**, posterior al
  nuevo reglamento.
- **Consecuencia en el informe:** cerró el `VERIFICAR` sobre vigencia; redactado
  en indicativo.
- **Queda abierto — y consta como nota al pie en el informe:** la confirmación
  definitiva exige revisar las disposiciones derogatorias y complementarias del
  D.S. 016-2024-JUS, para descartar una derogación parcial. Que un organismo del
  Estado la cite como base legal vigente es un indicio sólido, pero no equivale
  a la lectura del texto derogatorio (checklist A-08b).

#### E — Servidor de evaluación de NWPU-Crowd (§Licencias de los conjuntos de datos públicos)

- **Se afirma:** NWPU-Crowd no libera las etiquetas del conjunto de prueba; la
  evaluación se hace enviando las predicciones a un servidor externo
  administrado por los responsables del conjunto.
- **Consecuencia en el informe:** se incorporó como tercer riesgo de la sección
  de licencias, con una regla de uso propuesta. En fase académica el riesgo es
  acotado (se envían predicciones sobre datos públicos, no material del
  terminal); evaluar así material de LAP sería transferencia internacional.
- **Queda abierto:** términos del servicio del servidor de evaluación y
  jurisdicción del operador (checklist B-07).

---

### 2.7 Normas contrastadas al redactar las Secciones 3 y 4 (11/09/2026)

Todo lo que en `03_marco_normativo.md` y `04_analisis_impacto.md` aparece
**entrecomillado** procede de esta tabla. Lo que no pudo contrastarse quedó
marcado `[VERIFICAR]` dentro del propio cuerpo del informe, no aquí.

#### Ley 29733 — VERIFICADO-PRIMARIA

Texto consultado: Ley de Protección de Datos Personales, reproducción oficial
publicada por el Estado peruano (portal institucional, documento PDF completo).

| Precepto | Qué se cita en el informe | Dónde se usa |
|---|---|---|
| Art. 1 | Objeto: garantizar el derecho del art. 2 numeral 6 de la Constitución | §3.1 |
| Art. 2.4 | «Toda información sobre una persona natural que la identifica o la hace identificable a través de medios que pueden ser razonablemente utilizados» | §3.2 |
| **Art. 2.5** | Definición de datos sensibles, incluidos «los datos biométricos que por sí mismos pueden identificar al titular» | §3.2, §3.9 |
| Art. 2.6 | Encargado del banco de datos personales | §3.8 |
| Art. 2.8 | Flujo transfronterizo de datos personales | §3.8 |
| **Art. 2.12** | Anonimización: «El procedimiento es **irreversible**» | §3.2 — base de la contradicción D-02 |
| **Art. 2.13** | Disociación: «El procedimiento es **reversible**» | §3.2 — base de la contradicción D-02 |
| Art. 5 / 13.5 | Consentimiento «previo, informado, expreso e inequívoco» | §3.3 |
| **Art. 6** | Principio de finalidad; prohibición de extender el tratamiento a otra finalidad | §3.3 — base de la contradicción D-03 |
| **Art. 7** | Proporcionalidad: «adecuado, relevante y no excesivo a la finalidad» | §3.4 |
| **Art. 8** | Calidad: conservar «solo por el tiempo necesario para cumplir con la finalidad» | §3.6 |
| Art. 11 / 15 | Nivel de protección adecuado y flujo transfronterizo | §3.8 |
| Art. 14 | Limitaciones al consentimiento; **numeral 9** (intereses legítimos) y numeral 8 (anonimización o disociación) | §3.3 |
| Arts. 18–25 | Derechos del titular. **Art. 23**, tratamiento objetivo, citado literalmente | §3.7, §4.3 |
| **Art. 28.4** | «No utilizar los datos personales […] para finalidades distintas de aquellas que motivaron su recopilación» | §3.3 — contradicción D-03 |
| **Art. 28.7** | Deber de supresión cuando los datos dejan de ser necesarios | §3.6 |
| Art. 30 | Prestación de servicios de tratamiento por cuenta de terceros | §3.8 |

> **Nota sobre el art. 14 numeral 9.** Su redacción peruana —«salvaguardar
> intereses legítimos **del titular de datos personales** por parte del titular
> de datos personales o por el encargado»— **no coincide** con el interés
> legítimo del responsable del RGPD. El informe lo advierte expresamente en §3.3
> y **no** afirma que ampare la finalidad del proyecto. Es una de las preguntas
> a elevar al área legal de LAP (C-02).

#### D.S. 007-2020-IN — VERIFICADO-PRIMARIA

Reglamento del D.L. 1218 y de la Ley 30120, consultado en *El Peruano*.
Publicación: 24/04/2020. **Hallazgo nuevo, no registrado antes en este archivo.**

| Precepto | Qué se cita | Consecuencia |
|---|---|---|
| **Art. 3** | Ámbito: «establecimientos comerciales abiertos al público con un aforo de cincuenta (50) personas o más» | El terminal supera el umbral: el régimen **prima facie** lo alcanza (§3.1). Cierra parcialmente A-21 |
| **Art. 17.1** | Entrega a PNP o Ministerio Público «en un plazo máximo de veinticuatro (24) horas» | §3.6 |
| **Art. 17.2** | «Almacenar las imágenes, videos o audios grabados por un plazo **mínimo de cuarenta y cinco (45) días calendario**» | §3.6. **Tensión con el techo de 60 días de la Directiva**; sostiene la recomendación de separar el subsistema de conteo del CCTV de seguridad |

#### Directiva 01-2020-JUS/DGTAIPD — VERIFICADO-SECUNDARIA

Denominación oficial: «Directiva de Tratamiento de Datos Personales mediante
Sistemas de Videovigilancia». Aprobada por **Resolución Directoral
02-2020-JUS/DGTAIPD**, publicada el **16/01/2020**. Cierra A-19 en cuanto a
identificación formal.

| Numeral | Qué se cita | Dónde |
|---|---|---|
| 6.3 | Bases de legitimación: consentimiento, ley, o supuestos del art. 14 de la Ley 29733 | §3.3 |
| 6.4 | Proporcionalidad: «adecuado, pertinente y no excesivo en relación con el ámbito y las finalidades» | §3.4 |
| 6.11 | Contenido mínimo del cartel y dimensión mínima **297 × 210 mm** | §3.7, Anexo A |
| 6.13 y 7.18 | Conservación de imágenes: **de 30 a 60 días como máximo** | §3.6 |

> **Pendiente A-19b:** estos numerales proceden de una reproducción del texto
> íntegro, no del documento oficial. Contrastar antes de la entrega.

#### Constitución de 1993, art. 2 — VERIFICADO-SECUNDARIA

Incisos 6 y 7 obtenidos en su redacción literal y citados como tales en §3.1.
Queda contrastarlos contra la edición oficial del Congreso (A-12).

#### D.S. 016-2024-JUS — SIN CONTRASTAR

Se confirmaron en varias fuentes secundarias concordantes la fecha de
publicación (30/11/2024), la de entrada en vigor (30/03/2025), la derogación del
D.S. 003-2013-JUS, el plazo de 48 horas para notificar brechas y el carácter
exigible de la EIPD para tratamientos de alto riesgo —con la videovigilancia
masiva entre los supuestos—. **No se obtuvo el articulado.** Por eso §3.5 y §3.8
conservan marcadores `[VERIFICAR]` sobre los artículos concretos, y A-13 sigue
siendo el pendiente prioritario de este frente.

---

## 3. Afirmaciones de elaboración propia

No provienen de ninguna fuente externa; son análisis del frente ético-legal.
Se registran aquí para que quede claro que **no** deben citarse como si
tuvieran respaldo normativo.

| Afirmación | Dónde |
|---|---|
| El paso de mapa de densidad → puntos → semi-supervisado desplaza el perfil de riesgo, no solo la capacidad técnica | `antecedentes.tex`, síntesis |
| La eficiencia de etiquetado de P2R es utilizable como argumento de minimización | `antecedentes.tex`, `marco_etico_legal.tex` |
| La diferencia entre estimar aglomeraciones y seguir personas es de política de persistencia, no de algoritmo | `antecedentes.tex` |
| El riesgo principal es de gobernanza (deslizamiento de finalidad), no técnico | `analisis_impacto.tex` |
| Las medidas de minimización convergen con las de sostenibilidad ambiental | `analisis_impacto.tex` |
| Conviene tratar el sistema de conteo como subsistema separado del CCTV de seguridad | `marco_etico_legal.tex` |
| Los requisitos derivados R-01 a R-03 y las medidas M-01 a M-10 | `marco_etico_legal.tex` |
| La declaración de finalidades excluidas en el cartel (no exigida por la norma) | `anexo_cartel.tex` |

---

## 4. Registro de cambios

| Fecha | Cambio |
|---|---|
| 2026-08-30 | Creación. Papers leídos y volcados; fuentes normativas registradas como pendientes de verificación. |
| 2026-08-30 | Incorporados cinco hallazgos verificados (§2.6): EIPD exigible, privacidad por diseño y por defecto como exigencia, cronograma escalonado del ODP, vigencia de la Directiva 01-2020 vía Resolución 088-2025 del Congreso, y servidor de evaluación externo de NWPU-Crowd. Cerrados dos `VERIFICAR`. Verificación de licencias trasladada al checklist como tarea de Data Engineering. |
| 2026-09-01 | **Retiradas del informe las cifras procedentes de tablas sin respaldo en prosa** (§1): tres de CSRNet, cinco de P2PNet y cuatro de P2R, incluidas las de la Tabla 1 y la Tabla 2 de este último. Se incorporaron en su lugar las magnitudes relativas que los autores sí enuncian en prosa. Este archivo conserva el registro completo de lo retirado. |
| 2026-09-01 | **Retirados del cuerpo del informe todos los marcadores en ámbar.** Las afirmaciones que se apoyaban en ellos se reformularon en condicional o se atribuyeron expresamente a su fuente; las tareas y decisiones se trasladaron a `PENDIENTES.md`, agrupadas por quién puede cerrarlas. La macro `\pendiente` se eliminó de `main.tex`, de modo que su reaparición rompe la compilación. |
