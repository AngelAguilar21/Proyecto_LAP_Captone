# CHECKLIST_CUMPLIMIENTO.md

Estado de cumplimiento del sistema de estimación de aglomeraciones.

**Responsable:** Fabián Moreno Ugarte — Validación ética/legal y documentación
**Última actualización:** 2026-08-30

## Leyenda

| Símbolo | Significado |
|---|---|
| ✅ | Cerrado con evidencia |
| 🟡 | En curso / depende de una decisión interna |
| ⛔ | No conforme o sin evidencia — hallazgo abierto |
| ❓ | Bloqueado a la espera de información de LAP |
| ⬜ | No iniciado |

> El estado dominante es 🟡/❓ y eso es esperable en esta fase: la mayoría de
> los ítems dependen de decisiones de arquitectura aún no congeladas o de
> información que solo puede dar el cliente. Lo importante de este archivo no
> es la proporción de verdes, sino que **ningún ítem esté sin identificar**.

---

## A. Verificación documental de fuentes normativas

Detalle y trazabilidad en `NOTAS_FUENTES.md`.

| # | Ítem | Estado | Nota |
|---|---|---|---|
| A-01 | Transcribir literalmente Constitución art. 2 inc. 6 y 7 | ⬜ | Hoy parafraseados en el informe |
| A-02 | Confirmar fechas del D.S. 016-2024-JUS (publicación, vigencia, derogación) contra El Peruano | ⬜ | **Prioritario.** Un error invalida el análisis de régimen transitorio |
| A-03 | Numeral exacto de «dato sensible» en la Ley 29733 | ⬜ | Y si el reglamento de 2024 lo precisó |
| A-04 | Régimen de notificación de brechas: artículo, cómputo del plazo, destinatario, umbral | ⬜ | El informe solo afirma «48 horas» según el encargo |
| A-05 | Régimen del ODP: artículo, **umbrales de ingresos de cada tramo del cronograma escalonado** y sus fechas | 🟡 | Verificado que la designación sigue un cronograma escalonado por ingresos anuales. Falta el detalle de los tramos |
| A-06 | Alcance extraterritorial: artículo y criterios de conexión | ⬜ | Condiciona A-14 y B-07 |
| A-07 | EIPD en el D.S. 016-2024-JUS | ✅ | **Verificado.** Exigible antes de iniciar tratamientos de alto riesgo; incluye expresamente videovigilancia masiva, perfilado automatizado con IA y biométricos a escala. Debe documentarse y puede requerir consulta previa a la ANPD |
| A-07b | EIPD: artículo exacto, contenido mínimo del documento y supuestos en que la consulta previa a la ANPD es obligatoria | ⬜ | Detalle pendiente; no cambia la conclusión de A-07 |
| A-07c | Artículo que consagra privacidad por diseño y por defecto | ⬜ | Verificado que es exigencia, no buena práctica. Falta la referencia formal |
| A-08 | Directiva 01-2020-JUS/DGTAIPD: **vigencia tras el reglamento de 2024** | ✅ | **Verificado.** Vigente: el Congreso la cita como base legal en su Resolución 088-2025, posterior al D.S. Confirmación definitiva pendiente de A-08b |
| A-08b | Revisar disposiciones derogatorias y complementarias del D.S. 016-2024-JUS | ⬜ | Descartar derogación parcial. Registrado como nota al pie en el informe |
| A-08c | Denominación oficial completa de la Directiva y resolución directoral que la aprueba | ⬜ | Solo para citarla con la referencia formal correcta |
| A-09 | D.L. 1218: denominación, obligaciones de entrega a autoridades, plazos de conservación | ⬜ | |
| A-10 | Ley 30120: denominación y **si alcanza a establecimientos privados abiertos al público** | ⬜ | Define si la norma alcanza al terminal |
| A-11 | RGPD art. 35: redacción literal | ⬜ | Solo si se cita textualmente |
| A-12 | AI Act: artículos sobre biometría remota y alto riesgo; calendario | ⬜ | El informe no cita numerales |
| A-13 | ISO/IEC 27001 y 42001: edición vigente | ⬜ | Y si LAP ya está certificada en 27001 |
| A-14 | Régimen jurídico del terminal (¿dominio público, privado abierto al público?) y normativa aeronáutica | ❓ | Zona gris declarada. A elevar al área legal de LAP |
| A-15 | Régimen sancionador y valor de la UIT vigente | ⬜ | El informe no consigna cifras |

## B. Licencias de datos — **asignado a Data Engineering**

> **Responsable:** frente de Data Engineering. **Solicitado por:** frente ético-legal.
>
> Esta verificación se movió aquí desde `secciones/marco_etico_legal.tex` porque
> requiere acceso a los portales de descarga y a los formularios de solicitud de
> cada conjunto, que es trabajo del frente de datos. El informe conserva los
> criterios que la verificación debe satisfacer y los riesgos que debe descartar
> (§Licencias de los conjuntos de datos públicos).
>
> **Para cada conjunto hay que responder, por escrito y con el enlace a la fuente:**
> 1. ¿Cuál es el texto de licencia o los términos de uso vigentes, y dónde constan?
> 2. ¿Permiten uso comercial, o son solo para investigación no comercial?
> 3. ¿El acceso exige formulario, registro o aceptación expresa de condiciones?
> 4. ¿Exigen atribución específica? ¿En qué forma?
> 5. ¿Hay restricción de redistribución (del conjunto, o de modelos derivados)?

| # | Ítem | Estado | Nota |
|---|---|---|---|
| B-01 | Términos de uso de ShanghaiTech (Partes A y B) | ⛔ | Sin verificar. Introducido junto con MCNN |
| B-02 | Términos de uso de UCF-QNRF | ⛔ | Sin verificar. University of Central Florida |
| B-03 | Términos de uso de NWPU-Crowd | ⛔ | Sin verificar. Northwestern Polytechnical University |
| B-04 | Determinar si alguno restringe el uso comercial | ⛔ | **Resolver ANTES de entrenar,** no después. Si hay restricción, el modelo entrenado con ese conjunto no puede desplegarse en LAP sin analizar el alcance |
| B-05 | Documentar el linaje de datos (medida M-09) | ⬜ | Origen, licencia y transformaciones de cada conjunto |
| B-06 | Postura del equipo si algún conjunto es solo para investigación | 🟡 | Decisión abierta (ver D-08) |
| B-07 | **NWPU-Crowd: régimen del servidor de evaluación externo** | ⛔ | Ver recuadro abajo. Implica envío de datos a un tercero |
| B-08 | Dejar por escrito la regla de no enviar al servidor de NWPU-Crowd nada derivado de imágenes del terminal | ⬜ | Fácil de incumplir por inercia al montar el flujo de evaluación |

### B-07 — Transferencia a un tercero en la evaluación de NWPU-Crowd

**Dato verificado:** NWPU-Crowd **no libera las etiquetas del conjunto de
prueba**. La evaluación se realiza enviando las predicciones a un **servidor
externo** administrado por los responsables del conjunto.

**Por qué importa:** usar la métrica oficial de ese *benchmark* implica remitir
datos a un tercero situado fuera del Perú.

- En la fase académica el riesgo es **acotado**: lo que se envía son predicciones
  sobre imágenes del propio conjunto público, no material del terminal. Aun así,
  el flujo debe quedar documentado en el linaje de datos (B-05).
- Si en algún momento se planteara evaluar de esa forma material propio de LAP,
  se estaría ante una **transferencia internacional de datos personales** con
  todas sus consecuencias (ver A-06).

**Regla propuesta:** nunca enviar al servidor externo predicciones calculadas
sobre imágenes del Aeropuerto Jorge Chávez, ni ningún artefacto derivado de
ellas. El servidor es una herramienta legítima para comparar contra el estado
del arte sobre datos públicos; deja de serlo cuando el insumo proviene del
terminal.

## C. Requisitos técnicos derivados y medidas de privacidad desde el diseño

Medidas definidas en `secciones/marco_etico_legal.tex`, §Privacidad desde el
diseño y por defecto.

> **Estas medidas son requisitos, no recomendaciones.** El D.S. 016-2024-JUS
> establece la privacidad por diseño y por defecto como exigencia. Omitir una de
> ellas no es una decisión de producto sino un incumplimiento; las decisiones
> abiertas de la sección D son decisiones sobre *cómo* cumplir, no sobre *si*
> cumplir.
>
> La dimensión **«por defecto»** añade un requisito propio, que aún no está
> cubierto (ver C-DEF): donde una opción admita un ajuste más protector y otro
> menos protector — resolución de captura, frecuencia de muestreo, granularidad
> de la salida, plazo de retención —, el valor de fábrica debe ser el más
> protector, y cualquier configuración menos restrictiva debe ser una desviación
> deliberada, documentada y justificada.

| # | Medida | Estado | Verificable por |
|---|---|---|---|
| R-01 | Registro de auditoría inmutable de accesos | 🟡 | Revisión de la matriz de roles y de los registros |
| R-02 | Inventario de flujos y ubicaciones de almacenamiento | 🟡 | Revisión documental |
| R-03 | Procedimiento de respuesta a incidentes | 🟡 | Documento + ensayo. Puede exceder el alcance del Capstone (ver D-03) |
| M-01 | Procesamiento en el borde; el fotograma no sale del perímetro | ❓ | Inspección de arquitectura de red. Depende de D-04 |
| M-02 | No persistencia del fotograma | 🟡 | Revisión de código y de esquema de almacenamiento. Depende de D-05 |
| M-03 | Salida agregada por zona, sin coordenadas individuales | 🟡 | Inspección del esquema de base de datos. Depende de D-01 |
| M-04 | Difuminado irreversible de rostros en material conservado | 🟡 | Muestreo del material conservado |
| M-05 | Plazo de retención definido y purga automática | ❓ | Requiere que LAP fije el plazo (ver D-06) |
| M-06 | Control de acceso por roles + auditoría | 🟡 | Matriz de roles |
| M-07 | Cifrado en tránsito y en reposo | ⬜ | Configuración |
| M-08 | Carteles informativos según el Anexo A | 🟡 | Inspección física + registro fotográfico |
| M-09 | Documentación del linaje de datos | ⬜ | Revisión documental (ver B-05) |
| M-10 | Supervisión humana: el sistema alerta, no decide | 🟡 | Diseño del flujo operativo |
| C-DEF | **Fijar los valores por defecto más protectores** y documentar toda desviación | ⛔ | Requisito de la dimensión «por defecto». Sin cubrir mientras sigan abiertas D-01, D-05 y D-06 |

## C-bis. Evaluación de Impacto en Protección de Datos (EIPD)

> **Obligación verificada (A-07).** El D.S. 016-2024-JUS exige la EIPD **antes de
> iniciar** el tratamiento. El proyecto cae en el supuesto por partir de
> captación masiva en un terminal aeroportuario. Es el único hallazgo no conforme
> que el equipo puede cerrar **sin depender de terceros ni de datos que no tenga**.

| # | Ítem | Estado | Nota |
|---|---|---|---|
| P-01 | Redactar la EIPD como documento formal | ⛔ | **Prioridad 1.** El análisis sustantivo ya existe en §Análisis de impacto; falta formalizarlo |
| P-02 | Verificar el contenido mínimo que la norma exige (ver A-07b) | ⬜ | Condiciona la estructura de P-01 |
| P-03 | Determinar si el riesgo residual obliga a consulta previa a la ANPD | ⬜ | Y el plazo de respuesta aplicable |
| P-04 | Registrar M-01…M-10 en la EIPD como medidas de mitigación | ⬜ | Es donde el trabajo de este frente queda acreditado ante la autoridad |
| P-05 | Decidir si la EIPD se compromete como entregable del Capstone | 🟡 | Ver D-14 |
| P-06 | Someter la EIPD a revisión del ODP cuando exista | ⬜ | Depende de A-05 |

## D. Decisiones abiertas

Cada una correspondía a un marcador `DECISIÓN FABIÁN` dentro del informe. Desde
el 1 de septiembre de 2026 esos marcadores ya no están en el `.tex`: el cuerpo
del documento quedó sin texto de relleno y las decisiones se registran en
**`PENDIENTES.md`**, agrupadas por quién puede cerrarlas. Esta tabla mantiene el
seguimiento del estado; `PENDIENTES.md` mantiene el enunciado completo de cada
una y dónde impacta.

| # | Decisión | Estado | Bloquea a |
|---|---|---|---|
| D-01 | ¿Prohibir la persistencia de coordenadas individuales, o permitirla con anonimización y retención corta? | 🟡 | M-03 |
| D-02 | ¿Sostener que ninguna cifra de desempeño llegue al cliente sin validación en sitio? | 🟡 | E-01 |
| D-03 | ¿R-01…R-03 son entregables del equipo o requisitos de puesta en producción? | 🟡 | R-01…R-03 |
| D-04 | ¿Inferencia *on-premise* o en nube externa? | ❓ | M-01, A-06. **La decisión de arquitectura con mayor impacto legal** |
| D-05 | ¿M-02 estricta (nada se guarda) o atenuada con M-04 (difuminado + plazo corto)? | 🟡 | M-02, E-01 |
| D-06 | Plazo de retención concreto de los datos derivados | ❓ | M-05, cartel |
| D-07 | ¿Solicitar formalmente a LAP acceso a material del terminal? | 🟡 | E-01, E-02 |
| D-08 | Si un conjunto restringe el uso comercial, ¿excluirlo o usarlo solo en fase académica? | 🟡 | B-04, B-06 |
| D-09 | ¿Incluir la declaración de finalidades excluidas como entregable formal? | 🟡 | Mitigación del riesgo principal |
| D-10 | ¿Excluir expresamente el uso de los datos para evaluación de desempeño del personal? | 🟡 | Impacto social |
| D-11 | ¿Qué arquitectura eligió el equipo técnico? | ❓ | Cierra la auditoría (sección E) |
| D-12 | Idiomas adicionales del cartel | ❓ | Anexo A |
| D-13 | Nombres del equipo y ciclo/fecha de entrega en la portada | ⬜ | Portada |
| D-14 | ¿La EIPD se compromete como entregable del Capstone, o se entrega su contenido sustantivo dejando la formalización a LAP? | 🟡 | P-01, P-05. Debe quedar explícito cuál de las dos se ofrece |

## E. Auditoría de las técnicas del equipo

Corresponde a `secciones/marco_etico_legal.tex`, §Auditoría de conformidad.
Redactada de forma condicional mientras D-11 siga abierta.

| # | Criterio | Estado | Nota |
|---|---|---|---|
| E-00 | **EIPD realizada antes de iniciar el tratamiento** | ⛔ | **Hallazgo abierto y el más grave en términos formales:** obligación normativa incumplida, no una carencia de evidencia. También el más fácil de cerrar (sección C-bis) |
| E-09 | Privacidad por diseño y por defecto | 🟡 | Parcial: M-01…M-10 definidas, pero la dimensión «por defecto» sin fijar (C-DEF) |
| E-01 | Exactitud validada en el dominio de destino | ⛔ | **Hallazgo abierto.** La brecha de dominio documentada en el paper de P2R impide extrapolar cifras publicadas |
| E-02 | Ausencia de sesgo demográfico evaluada | ⛔ | **Hallazgo abierto.** Ninguno de los tres artículos reporta desempeño desagregado |
| E-03 | No se extraen rasgos biométricos identificantes | 🟡 | Favorable en los tres métodos, condicionado a que no se añada reidentificación aguas abajo |
| E-04 | La salida no permite identificar personas | 🟡 | Favorable con CSRNet; a validar con P2PNet/P2R |
| E-05 | Minimización en el proceso de anotación | 🟡 | Favorable si se adopta el enfoque semi-supervisado |
| E-06 | Política de retención definida | ❓ | Depende de D-05 y D-06 |
| E-07 | Localización del procesamiento | ❓ | Depende de D-04 |
| E-08 | Trazabilidad de licencias de datos | ⛔ | Asignado a Data Engineering (B-01…B-04, B-07) |

> **Los tres hallazgos no conformes no son iguales.**
>
> **E-00 (EIPD)** es una obligación normativa incumplida, no una carencia de
> evidencia — y es el único que el equipo puede cerrar por sí solo, con el
> material que ya tiene redactado. Debería ser lo primero.
>
> **E-01 y E-02** son ausencias de evidencia: subsanables con una campaña de
> validación en sitio y con una evaluación de desempeño desagregada, pero ambas
> requieren acceso a datos del terminal (D-07). Si ese acceso no se obtiene,
> **deben reportarse como abiertos en las conclusiones**, no presentarse como
> resueltos.

## F. Información que debe pedirse a LAP

| # | Dato | Para qué |
|---|---|---|
| F-01 | **¿En qué tramo del cronograma escalonado de designación del ODP se ubica LAP,** según sus ingresos anuales? ¿Ya lo designó? | La designación no es uniforme: sigue un cronograma por ingresos. La pregunta no es si lo tienen, sino desde cuándo les es exigible (A-05) |
| F-12 | ¿LAP ha realizado ya alguna EIPD para su sistema de CCTV existente? | Si existe, este proyecto debe articularse con ella en lugar de partir de cero (P-01) |
| F-02 | Incidentes por aglomeración registrados; cómo se decide hoy la dotación de personal | Sostiene el juicio de proporcionalidad en sentido estricto y dimensiona el beneficio social |
| F-03 | ¿La infraestructura de CCTV existente es reutilizable? | Cambia el orden de magnitud del costo y la huella ambiental |
| F-04 | Base de legitimación que invoca LAP | Campo del cartel |
| F-05 | Razón social exacta, RUC y domicilio fiscal | Campo del cartel |
| F-06 | Canal de atención de derechos (correo y oficina) y URL de la política de privacidad | Campos del cartel |
| F-07 | Plazo de retención requerido por sus necesidades analíticas | M-05, D-06 |
| F-08 | Composición de tráfico del aeropuerto | Idiomas del cartel (D-12) |
| F-09 | ¿Certificación ISO/IEC 27001 vigente? | Si la hay, integrarse a su SGSI en vez de definir controles propios |
| F-10 | ¿Política institucional de sostenibilidad o compromisos de reporte ambiental? | Alineación del análisis ambiental |
| F-11 | Régimen del contrato de concesión y normativa aeronáutica de vigilancia | A-14 |

## G. Mediciones que debe registrar el frente técnico

| # | Medición | Estado | Nota |
|---|---|---|---|
| G-01 | Horas de GPU consumidas en desarrollo | ⬜ | **No es reconstruible a posteriori.** Pedirlo cuanto antes |
| G-02 | Consumo de la inferencia continua | ⬜ | Convierte el análisis ambiental de cualitativo en cuantitativo |
| G-03 | Frecuencia de muestreo elegida | ⬜ | Sirve a la vez a minimización y a sostenibilidad |
| G-04 | Desempeño desagregado (estatura, equipaje voluminoso) | ⬜ | Cierra E-02. Requiere D-07 |

---

## Ruta crítica sugerida

Si hay que priorizar, este es el orden con mayor rendimiento:

1. **P-01 / E-00** (redactar la EIPD) — es obligación exigible, es hallazgo no conforme, y es el único que se cierra sin depender de nadie. El contenido sustantivo ya está escrito.
2. **D-04** (¿on-premise o nube?) — desbloquea M-01, A-06, C-DEF y todo el análisis de transferencia internacional.
3. **B-01…B-04 y B-07** (licencias y servidor de NWPU-Crowd) — asignado a Data Engineering; hay que resolverlo *antes* de entrenar, no después.
4. **A-02** (fechas de vigencia del reglamento) — sostiene el resto del marco. A-08 ya está cerrado; queda A-08b como confirmación.
5. **D-07 / F-02** (acceso a datos y evidencia del problema) — sin ellos, E-01, E-02 y el juicio de proporcionalidad quedan sin cerrar.
6. **G-01** — cuesta casi nada si se empieza ya, y es irrecuperable si no.
