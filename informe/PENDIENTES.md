# PENDIENTES.md

Registro de los puntos abiertos del informe.

**Responsable del archivo:** Fabián Moreno Ugarte — Validación ética/legal y documentación
**Proyecto:** Capstone I, Universidad ESAN — Estimación de aglomeraciones, Aeropuerto Jorge Chávez (cliente: LAP)
**Última actualización:** 11 de septiembre de 2026 (segunda revisión del día: consolidación del informe en LaTeX)

---

## Por qué existe este archivo

El informe llevaba, dentro del cuerpo del texto, marcadores en ámbar de dos
tipos: `VERIFICAR` para las afirmaciones cuyo respaldo documental exacto no se
había contrastado, y `DECISIÓN FABIÁN` para los puntos que dependían de un
criterio del equipo o de información que solo puede aportar LAP. Servían
mientras el documento se escribía; en un PDF que se enseña, se leen como
texto sin terminar.

Los marcadores se retiraron del `.tex` y su contenido se trasladó aquí sin
perder nada. En el informe, cada punto quedó reformulado en condicional, o
atribuido expresamente a su fuente, o enunciado como cuestión abierta. Ninguna
afirmación quedó sostenida sobre un marcador que ya no está.

La macro `\pendiente` se eliminó de `main.tex` a propósito y **no** se dejó
definida como no-op: si alguien vuelve a escribir `\pendiente{...}{...}` en una
sección, la compilación falla. Esa es la salvaguarda que impide que un marcador
reaparezca en el PDF sin que nadie lo advierta.

El criterio de agrupación es **quién puede cerrar cada punto**. Un pendiente
mal agrupado se queda esperando a la persona equivocada.

---

## (a) Decisiones mías — frente ético-legal y documentación

### a.1 Decisiones de criterio

Varias de estas ya quedaron resueltas en el texto, en el sentido de que el
informe toma posición. Se listan igualmente porque la posición debe sostenerse
ante el equipo y ante el cliente, y eso todavía no ha ocurrido.

| # | Punto | Dónde impacta | Estado |
|---|---|---|---|
| A-01 | ¿Se ofrece la declaración de finalidades excluidas como entregable formal del proyecto? | `analisis_impacto.tex`, impacto ético | El informe la propone como entregable. Falta sostenerlo ante el equipo. |
| A-02 | ¿Se incluye la exclusión del uso laboral de los datos en esa misma declaración? | `analisis_impacto.tex`, impacto social | El informe lo propone. Falta acordarlo. |
| A-03 | ¿Se mantiene la recomendación de no presentar ninguna cifra de desempeño antes de la validación en sitio? | `antecedentes.tex`, P2R | El informe la mantiene de forma expresa, aun a costa de presentar el proyecto sin cifras atractivas. Es la que más fricción puede generar con el equipo. |
| A-04 | ¿R-01, R-02 y R-03 son entregables del ciclo o requisitos de puesta en producción? | `marco_etico_legal.tex`, brechas | El informe los documenta como requisitos de puesta en producción. |
| A-05 | ¿Se expone ante el cliente que la documentación de cumplimiento es la mitigación principal del riesgo principal? | `analisis_impacto.tex`, síntesis | El informe lo sostiene y recomienda decirlo explícitamente. |
| A-06 | ¿Se propone a LAP prohibir la persistencia de coordenadas individuales, o permitirla con anonimización y retención corta? | `antecedentes.tex`, P2PNet | **Abierto.** La prohibición es más defendible; la segunda opción es más útil operativamente y probablemente lo que el cliente pedirá. |
| A-07 | ¿M-02 en versión estricta, o versión atenuada con M-04? | `marco_etico_legal.tex`, privacidad desde el diseño | **Abierto.** La estricta es más defendible jurídicamente; la atenuada es la única que permite mejorar el modelo con datos del terminal. |
| A-08 | ¿La EIPD se compromete como entregable formal del Capstone, o se entrega su estructura y contenido sustantivo? | `marco_etico_legal.tex`, EIPD | **Abierto.** Lo que no admite ambigüedad es que se diga cuál de las dos se ofrece. |
| A-09 | Si algún conjunto de datos restringe el uso comercial: ¿se excluye, o se usa solo en fase académica documentándolo? | `marco_etico_legal.tex`, licencias | **Abierto.** Depende del resultado de B-06. |
| A-10 | Ciclo académico y fecha de entrega que deben figurar en la portada. | `main.tex`, portada | **Abierto.** La portada quedó sin línea de fecha, en lugar de con un marcador. |
| A-11 | Cursar la solicitud formal a LAP de acceso a material del terminal. | `marco_etico_legal.tex`, auditoría | **Abierto.** Sin ese acceso, dos hallazgos de la auditoría no cierran. Ver C-14. |

### a.2 Verificaciones documentales

Trabajo de este frente. El informe describe estas normas pero no las cita como
transcripción, y lo dice expresamente en cada caso. La trazabilidad completa
está en `NOTAS_FUENTES.md`.

| # | Qué verificar | Dónde |
|---|---|---|
| A-12 | ~~Transcripción literal del artículo 2, incisos 6 y 7 de la Constitución~~ → **texto obtenido y citado literalmente en §3.1.** Queda contrastarlo contra la edición oficial del Congreso. | Nivel constitucional |
| A-13 | **Prioritario y aún abierto.** Las fechas del D.S. 016-2024-JUS (publicación 30/11/2024, vigencia 30/03/2025, derogación del D.S. 003-2013-JUS) se confirmaron en varias fuentes secundarias concordantes, **pero no contra *El Peruano***. Un error aquí arrastra todo el análisis de régimen transitorio. | Ley 29733 y reglamento |
| A-14 | ~~Numeral exacto del artículo 2 sobre dato sensible~~ → **cerrado: art. 2 numeral 5**, citado literalmente en §3.2. Sigue abierto si el D.S. 016-2024-JUS precisó la definición. | Datos biométricos |
| A-15 | Artículo que regula la EIPD, contenido mínimo exigido y supuestos en que la consulta previa a la ANPD pasa de facultativa a obligatoria, con su plazo. | EIPD |
| A-16 | Artículo del plazo de notificación de brechas; desde qué hecho se computa; horas hábiles o calendario; destinatario (ANPD, titulares o ambos); umbral de gravedad. | Brechas |
| A-17 | Artículo del cronograma del ODP; umbrales de ingresos de cada tramo y sus fechas; comunicación de la designación a la ANPD; requisitos de independencia. | ODP |
| A-18 | Artículo del alcance extraterritorial y sus criterios de conexión. | Extraterritorialidad |
| A-19 | ~~Denominación oficial y resolución que aprueba la Directiva~~ → **cerrado:** «Directiva de Tratamiento de Datos Personales mediante Sistemas de Videovigilancia», Resolución Directoral 02-2020-JUS/DGTAIPD, 16/01/2020. **Sigue abierto** descartar una derogación parcial revisando las disposiciones derogatorias del D.S. 016-2024-JUS. | Directiva |
| A-19b | Contrastar contra el texto oficial los numerales de la Directiva ya citados en §3.3, §3.4, §3.6 y §3.7: 6.3, 6.4, 6.11, 6.13 y 7.18. Se obtuvieron de una reproducción del texto íntegro, no del documento oficial. | Directiva |
| A-20 | D.L. 1218: **reglamento identificado y verificado contra *El Peruano* — D.S. 007-2020-IN (24/04/2020)**, art. 17.1 (entrega a PNP/Ministerio Público en máx. 24 h) y art. 17.2 (almacenamiento mínimo 45 días calendario). Falta la fecha y denominación del propio D.L. | D.L. 1218 y Ley 30120 |
| A-21 | Ley 30120: **hallazgo relevante.** El art. 3 del D.S. 007-2020-IN incluye en su ámbito los «establecimientos comerciales abiertos al público con un aforo de cincuenta (50) personas o más», umbral que el terminal supera con holgura. El régimen prima facie lo alcanza; la calificación definitiva es de LAP (ver C-13). | D.L. 1218 y Ley 30120 |
| A-22 | Redacción literal del artículo 35 del RGPD antes de citarlo textualmente. | Referencia comparada |
| A-23 | Artículos del Reglamento (UE) 2024/1689 sobre identificación biométrica remota y sobre alto riesgo, y su calendario de aplicación escalonada. | Referencia comparada |
| A-24 | Año de edición vigente y denominación oficial en español de ISO/IEC 27001 e ISO/IEC 42001. | Referencia comparada |
| A-25 | Artículo del D.S. 016-2024-JUS que consagra la privacidad por diseño y por defecto, y si detalla criterios de acreditación. | Privacidad desde el diseño |
| A-26 | Rangos de sanción de la Ley 29733 en UIT y valor de la UIT del ejercicio. El informe no consigna ninguna cifra. | Impacto económico |
| A-27 | Normativa peruana de accesibilidad aplicable a señalización en establecimientos de uso público. | Anexo A, criterios de colocación |
| A-28 | Contrastar los campos del cartel, uno por uno, contra la Directiva y el D.S. 016-2024-JUS: que no falte ningún elemento exigido ni sobre alguno. | Anexo A |

---

## (b) Decisiones del equipo

| # | Punto | Por qué importa | Dónde impacta |
|---|---|---|---|
| B-01 | **Arquitectura definitiva y granularidad de la salida.** | Es la decisión de la que depende la mitad del análisis. La auditoría está redactada de forma condicional sobre los tres enfoques porque esta elección no consta por escrito. | `antecedentes.tex` (síntesis), `marco_etico_legal.tex` (auditoría) |
| B-02 | **Inferencia *on-premise* en el terminal o en nube externa.** | Es la decisión de arquitectura con mayor impacto legal del proyecto: determina si hay o no transferencia internacional de datos. Debe constar por escrito. | Alcance extraterritorial |
| B-03 | Incluir una evaluación de desempeño desagregada —al menos por franja de estatura y por presencia de equipaje voluminoso— en la campaña de validación en sitio. | Cierra el hallazgo «ausencia de sesgo demográfico no evaluada». Depende del acceso a datos del terminal (C-14). | Impacto ético, auditoría |
| B-04 | **Registrar las horas de GPU desde el inicio del entrenamiento.** | No es reconstruible a posteriori. Si no se lleva el registro desde ya, la huella del desarrollo queda definitivamente sin cuantificar. Es el pendiente más barato de cerrar y el que caduca antes. | Impacto ambiental |
| B-05 | Decidir si se incorpora literatura sobre efectos conductuales de la videovigilancia. | El informe formula esa afirmación en condicional porque no hay respaldo bibliográfico validado. Con literatura, pasa a indicativo; sin ella, se queda como está. | Impacto ético |
| B-06 | Verificación de licencias de ShanghaiTech A y B, UCF-QNRF y NWPU-Crowd. | Asignada a **Data Engineering**; seguimiento en `CHECKLIST_CUMPLIMIENTO.md`, sección B. Debe resolverse **antes** de entrenar, no después. Alimenta A-09. | Licencias |
| B-07 | Proponer un plazo de retención concreto para la medida M-05. | El equipo no puede fijarlo sin conocer las necesidades analíticas de LAP (C-05), pero la propuesta la formula el equipo. | Privacidad desde el diseño, Anexo A |
| B-08 | Redactar las secciones de Introducción, Metodología, Resultados y Conclusiones. | Sus apartados quedaron con la estructura y la numeración reservadas, y con una descripción en prosa de lo que debe ir en cada uno. Ya no llevan marcadores de relleno. | Secciones correspondientes |

---

## (c) Información que solo puede dar LAP

Conviene llevar esta lista como un único pedido al cliente y no en pedidos
sucesivos. Varias respuestas se condicionan entre sí.

| # | Dato solicitado | Para qué se necesita |
|---|---|---|
| C-01 | Razón social registral completa, RUC y domicilio fiscal. | Campo «Responsable» del cartel del Anexo A. |
| C-02 | Base de legitimación que LAP invoca para la videovigilancia, con su fundamento normativo. | Campo «Base legal» del cartel. Sin él, el cartel no cumple el deber de información. |
| C-03 | Correo del canal de atención de derechos y ubicación de la oficina física. | Campo «Sus derechos» del cartel. Sin canal indicado, el derecho es nominal. |
| C-04 | Dirección web de la política de privacidad de LAP. | Campo «Más información» del cartel. |
| C-05 | Necesidades analíticas: cuánto tiempo necesita conservar los conteos agregados. | Fija el plazo de la medida M-05 y el campo «Conservación» del cartel. Ver B-07. |
| C-06 | Tramo del cronograma de ingresos en que se ubica LAP y si ya designó a su Oficial de Datos Personales. | Determina desde cuándo le es exigible la designación y quién es el interlocutor del equipo. |
| C-07 | Incidentes por aglomeración documentados, tiempos de cola observados y quejas recibidas. | **El pedido más importante del análisis.** Sin esta evidencia, el examen de proporcionalidad en sentido estricto se sostiene sobre una premisa no acreditada. |
| C-08 | Cómo se decide hoy la dotación de personal en el terminal. | Permite dimensionar el beneficio social, que hoy se afirma sin cuantificar. |
| C-09 | Si la infraestructura de CCTV existente es reutilizable. | Es la pregunta económica decisiva: cambia el orden de magnitud del costo del proyecto. |
| C-10 | Si LAP está certificada en ISO/IEC 27001. | Si lo está, el sistema debe integrarse a su SGSI existente en lugar de definir controles propios. Cambia la estrategia de cumplimiento. |
| C-11 | Política institucional de sostenibilidad o compromisos de reporte ambiental. | De existir, el análisis ambiental debe alinearse con sus categorías en lugar de proponer un marco paralelo. |
| C-12 | Composición del tráfico de pasajeros por procedencia. | Decide si el cartel necesita idiomas adicionales al español y el inglés. |
| C-13 | Régimen jurídico del terminal y normativa aeronáutica aplicable en materia de vigilancia (contrato de concesión). | Zona gris identificada y **no resuelta** en el informe: de esta calificación depende qué régimen de videovigilancia resulta exigible. Primer punto a elevar al área legal de LAP. |
| C-14 | Acceso a material del terminal para la campaña de validación en sitio. | Sin él, dos hallazgos de la auditoría —exactitud validada en el dominio de destino y evaluación de sesgo— quedan sin cerrar, y así deben reportarse en las conclusiones. Ver A-11 y B-03. |

---

## (d) Contradicciones entre documentos del proyecto

Detectadas al redactar las Secciones 3 y 4 (11/09/2026) y **revisadas contra el
prototipo del frente técnico** tras incorporar los seis *commits* del remoto ese
mismo día. **Este frente las deja registradas y expresamente no las resuelve por
su cuenta:** afectan al alcance del sistema y no a la redacción del informe, de
modo que su cierre es una decisión del equipo.

La revisión del prototipo cambió el cuadro en dos sentidos, y conviene no
presentarlo solo como una lista de incumplimientos: **D-01 se cerró a favor del
frente técnico**, porque la implementación evita deliberadamente los *embeddings*
de reidentificación que la presentación sugería; y apareció **D-05**, que no
estaba previsto y que es el hallazgo más accionable de todo el análisis.

| # | Contradicción | Por qué importa | Dónde se trata |
|---|---|---|---|
| D-01 | ~~La presentación contempla reidentificación por *embeddings* de apariencia frente al RNF-01~~ | ✅ **No se confirma. Cerrado el 11/09/2026** tras revisar el prototipo (`proyecto_lap_prototipo/src/cross_camera.py`, `nodes.py`). La fusión entre cámaras es **asociación espacio-temporal sobre plano compartido** como capa obligatoria; el desempate usa un descriptor de histograma de color del torso más proporción alto/ancho, documentado como no biométrico, nunca como identificador único, y **no persistido**. No hay ReID ni *embeddings*. La decisión de diseño va en la dirección que exige el RNF-01 y así se reconoce en §3.9. **Queda vigilar** que el criterio se sostenga si se busca mayor exactitud en la fusión. | `03_marco_normativo.md` §3.9 |
| D-02 | El material del equipo habla de **«personas anonimizadas»** donde hay un identificador persistente que reconstruye trayectorias. **Ahora también en el código.** | La Ley 29733 separa ambas figuras: art. 2 numeral 12, anonimización, **procedimiento irreversible**; art. 2 numeral 13, disociación, **procedimiento reversible**. Un ID persistente es disociación, y **el dato disociado sigue siendo dato personal sujeto al régimen general**. El comentario de `proyecto_lap_prototipo/src/persistence.py` lo llama «el id temporal **no reversible**», pero ese id es `PRIMARY KEY` de la tabla `personas` y enlaza el historial completo de `posiciones`: es reversible por construcción. | `03_marco_normativo.md` §3.2 y §3.9 |
| D-03 | **Medir permanencia en zona comercial** se presenta junto a la estimación de aglomeraciones, y se vincula a un interés comercial del cliente. | Son finalidades distintas. El art. 6 prohíbe extender el tratamiento a una finalidad no establecida de forma inequívoca al momento de la recopilación, y el art. 28 numeral 4 lo repite como obligación. La finalidad comercial exigiría **declaración, base de legitimación y deber de información propios**. **Ya no es hipotética:** el esquema del prototipo guarda `zona` por posición y `primera_deteccion`/`ultima_deteccion` por persona, que es maquinaria de permanencia por zona. | `03_marco_normativo.md` §3.3 y `04_analisis_impacto.md` §4.5 |
| D-04 | El **texto literal del RNF-01** no consta en el repositorio. | Se buscó en `secciones/`, en los `.md` de seguimiento, en el `.docx` y en el árbol remoto tras el *pull*: no aparece. Su formulación se recoge en §3.9 con marcador `[VERIFICAR]`. Pierde urgencia al cerrarse D-01, pero sigue siendo necesario para poder afirmar la conformidad por escrito. | `03_marco_normativo.md` §3.9 |
| **D-05** | **La medida M-03 no se cumple en el prototipo.** M-03 exige salida agregada por zona **sin coordenadas individuales persistidas**; `persistence.py` escribe en SQLite una tabla `posiciones` con `id_persona, camara, x, y, t, zona` por detección. | **Hallazgo no conforme, y el más accionable de todo el análisis.** Es el tercer tipo de dato de §3.2 —espacio-temporal encadenado a un identificador persistente— escrito en disco. Excede lo que la finalidad de estimar aglomeraciones requiere (art. 7), y la defensa basada en que «la salida es agregada» deja de estar disponible. **M-02 sí se respeta:** no se almacenan fotogramas. Subsanable por el propio equipo, sin depender de LAP: agregar por zona antes de escribir, o fijar retención muy corta sobre `posiciones`. | `03_marco_normativo.md` §3.5 y §3.9; `04_analisis_impacto.md` §4.5 |

---

## (e) Puntos estructurales abiertos sobre el propio informe

Surgidos al redactar las nuevas secciones. No son cuestiones de contenido sino
de organización del documento, y conviene cerrarlos antes de la siguiente
entrega porque afectan a qué versión es la buena.

| # | Punto | Estado |
|---|---|---|
| E-01 | **Duplicidad de fuente para las Secciones 3 y 4.** | ✅ **Cerrado, con el mecanismo cambiado el 11/09/2026 (tarde).** Los `.md` **siguen siendo la fuente única**: es ahí donde se edita. Lo que cambió es que las Secciones 3 y 4 vuelven al PDF: se generan `secciones/03_marco_normativo.tex` y `secciones/04_analisis_impacto.tex` **desde** los `.md`, y `main.tex` los incluye. Esos dos `.tex` son producto derivado y **no se editan a mano**: se regeneran con `herramientas/md2tex.py` y la conversion se comprueba con `herramientas/verificar_fidelidad.py` (uso en el docstring de cada uno). `secciones/_archivo/` queda **fuera de la compilación** y obsoleto. La conversión se verificó palabra por palabra contra el `.md`: la Sección 3 coincide exactamente (5.461 palabras) y la Sección 4 solo difiere en un `\allowbreak` tipográfico. |
| E-02 | **Overleaf abandonado.** La compilación dejó de funcionar por el límite de la cuenta gratuita; el entregable es ahora el `.docx`. | ✅ **Cerrado el 11/09/2026** en cuanto a la decisión y al `README.md`. **Queda abierto** el procedimiento de integración `.md` → `.docx`: no hay acordado un método ni constancia de qué versión del `.md` está incorporada al `.docx` en cada momento. Ver E-07. |
| E-03 | **El `.docx` y el `.tex` divergieron en Antecedentes.** El `.docx` (últ. mod. 09/09/2026, Ángel) añade MOTRv2, GeneralTrack, seguimiento multicámara por clustering y MCBLT, que no están en `antecedentes.tex`; y `fichas_antecedentes/` cubre PET, MeMOTR y ByteTrack, que tampoco coinciden con los del `.docx`. | **Abierto.** Las tres contradicciones de la sección (d) proceden justamente de los antecedentes nuevos del `.docx`. |
| E-04 | **Título de la sección.** El `.tex` archivado la titula «Marco ético y legal aplicable»; el `.md` vigente, «Marco normativo aplicable». Las referencias cruzadas dicen solo «Sección 3», así que ninguna se rompe. | ✅ **Cerrado por consecuencia de E-01:** manda el `.md`, luego el título es «Marco normativo aplicable». |
| E-05 | **Extensión.** La Sección 3 quedó en 4.744 palabras frente al objetivo inicial de 2.500–3.500. | ✅ **Cerrado el 11/09/2026:** se mantiene en 4.744. El límite era arbitrario y recortar exigía retirar citas verificadas. |
| E-06 | **Normas legales fuera de `referencias.bib`.** Se respetó la regla 4 del `README`: las normas se citan en prosa y su trazabilidad va a `NOTAS_FUENTES.md`. | ✅ **Cerrado** por decisión de 11/09/2026. Se deja constancia porque el encargo inicial pedía lo contrario. |
| E-07 | **Integración `.md` → `.docx`.** Falta acordar cómo se convierten las Secciones 3 y 4 al `.docx` y cómo se deja constancia de qué versión del `.md` está incorporada. Sin eso, ambos divergen en silencio, que es el problema que E-01 acaba de resolver para el `.tex`. | **Abierto.** Depende de Ángel (integración) y de este frente. |
| E-08 | **Migración del resto de secciones.** `introduccion`, `antecedentes`, `metodologia`, `resultados`, `conclusiones` y `anexo_cartel` siguen en `.tex`. El Anexo A importa especialmente, porque las Secciones 3.5 y 3.7 lo citan como modelo de cartel. | **Abierto, pero menos urgente desde el 11/09/2026 (tarde):** al reincorporarse las Secciones 3 y 4 al `.tex`, el PDF vuelve a contener el informe completo y la convivencia de formatos deja de partir el documento en dos mitades. Sigue abierto decidir el formato único. Ver E-10. |
| E-09 | **`referencias.bib` dejó de ser copia literal de `papers/citas_oficiales.txt`.** El `.bib` tiene **10** entradas; `citas_oficiales.txt`, **6**. Las cuatro de más son `Zhang_2023_CVPR` (MOTRv2), `Qin_2024_CVPR` (GeneralTrack), `Huang_2023_CVPR` (multicámara con *clustering*) y `Wang_2025_ICCV` (MCBLT). Las añadió el *commit* `a68c7c5` del 08/09/2026, ajeno a este frente, y proceden de `fichas_antecedentes/C1`–`C4`. | **BLOQUEO EXTERNO — este frente no puede cerrarlo.** Conviene fijar una precisión, porque se venía describiendo mal: **no son citas indefinidas y no bloquean nada.** Ninguna de las cuatro se cita en el informe —no hay `\cite` a ellas en ningún `.tex` ni en los `.md`—, así que no producen aviso alguno, no aparecen en el PDF, y la bibliografía imprime solo las tres entradas efectivamente citadas (`Li_2018_CVPR`, `Song_2021_ICCV`, `Lin_2025_CVPR`). Lo que sí infringen es la **regla 4 del `README`**. Causa verificada: `papers/` está en `.gitignore`, de modo que `citas_oficiales.txt` **solo existe en la máquina de este frente** y quien añadió las entradas no tenía cómo consultarlo. Cierre: o se citan desde unos Antecedentes ampliados (ver E-03) y se incorporan a `citas_oficiales.txt`, o se retiran del `.bib`. Depende de **Stephano** (las aportó) y de **Ángel** (Antecedentes del `.docx`). |
| E-10 | **Dos entregables en paralelo.** El `README` de la mañana del 11/09/2026 declaraba el PDF «legado» y el `.docx` como único entregable. Por la tarde el informe se consolidó en LaTeX y el PDF vuelve a estar completo y compilando (40 páginas, 0 errores). Ambos coexisten sin que se haya decidido cuál manda. | **Abierto — decisión del equipo.** El `README` **quedó desactualizado** en sus apartados «Cambio de herramienta», «Dónde se edita el documento» —incluido el «Qué NO hacer», que prohíbe expresamente reintroducir las Secciones 3 y 4 en el `.tex`, que es justo lo que se acaba de hacer—, «Cómo compilar (legado)» y «Estado». Hay que elegir entregable y reescribir esos apartados; mientras no se haga, el `README` describe un flujo que ya no es el vigente. Depende de **Ángel** (integración) y de este frente. |
| E-11 | **El `README` afirma que quedan «siete `[VERIFICAR]`, todos sobre el articulado del D.S. 016-2024-JUS».** | **Abierto, menor — lo cierra este frente.** Verificado sobre el `.md`: en el cuerpo hay **seis**, no siete —el séptimo es el ejemplo `[VERIFICAR: ...]` del comentario de cabecera—, y **solo dos** versan sobre el articulado del D.S. 016-2024-JUS. Los otros cuatro son sobre las fechas y la disposición derogatoria del propio D.S. (A-13), la vigencia de la Directiva 01-2020-JUS/DGTAIPD, la denominación del D.L. 1218 y la Ley 30120, y el texto literal del RNF-01 (D-04). Corregir la frase del `README`. |

---

## (f) Estado de las secciones que no son de este frente

Añadida el 11/09/2026 al consolidar el informe en LaTeX. Este frente **integró
estas secciones sin tocar su contenido** y solo reporta qué les falta. La
numeración y los `\label` de todas ellas se conservaron intactos.

| Sección | Archivo | Estado real | Qué falta | Depende de |
|---|---|---|---|---|
| 1. Introducción | `secciones/introduccion.tex` | **Redactada.** ~1.225 palabras, con Contexto del problema, Objetivos y Alcance y limitaciones. No lleva caja de «sección en elaboración». | Nada estructural. Un solo detalle: en «Zonas cubiertas» remite a `PENDIENTES.md`, **punto C-09** (reutilización del CCTV existente) cuando lo que describe —qué cámaras y qué material audiovisual habilita LAP— encaja mejor en **C-14** (acceso a material del terminal). Conviene confirmarlo con su autor. | Su autor |
| 2. Antecedentes | `secciones/antecedentes.tex` | **Redactada.** Es de este frente. Cubre CSRNet, P2PNet y P2R, con síntesis y tabla comparativa. | No cubre los cuatro antecedentes de seguimiento que sí están en el `.docx` (MOTRv2, GeneralTrack, multicámara por *clustering*, MCBLT) ni los de `fichas_antecedentes/`. Es la divergencia **E-03**, y es la que deja huérfanas las cuatro entradas de `referencias.bib` de **E-09**. | Ángel / Stephano |
| 5. Metodología | `secciones/metodologia.tex` | **Esqueleto.** ~280 palabras contando comentarios. Los tres subapartados existen, pero cada uno es una sola frase en futuro («Este apartado documentará…»). | El contenido entero de 5.1 Arquitectura propuesta, 5.2 Datos y entrenamiento y 5.3 Métricas de evaluación. **Dos decisiones de aquí bloquean la auditoría de este frente:** la arquitectura y granularidad de salida (**B-01**) y el lugar donde se ejecuta la inferencia, *on-premise* o nube externa (**B-02**). Mientras no consten por escrito, la Sección 3.9 se queda redactada en condicional. | Su autor |
| 6. Resultados | `secciones/resultados.tex` | **Esqueleto.** ~205 palabras contando comentarios. Dos subapartados, una frase en futuro cada uno. | Las tablas de error de conteo y de localización (6.1) y los casos de éxito y de fallo (6.2). Regla ya escrita en el propio archivo y que hay que respetar: **cada cifra debe indicar sobre qué datos fue medida**, porque la brecha de dominio impide presentar resultados sobre conjuntos públicos como desempeño esperable en el terminal. Los casos de fallo alimentan además la capacitación de operadores de la Sección 4.3. | Su autor |
| 7. Conclusiones | `secciones/conclusiones.tex` | **Esqueleto.** ~175 palabras contando comentarios. Sin subapartados. | Las conclusiones del proyecto y las líneas de trabajo futuro. Los insumos ya existen: síntesis de antecedentes y Sección 4.5. **Dos resultados de la auditoría deben aparecer aquí sin atenuarlos:** la exactitud no está validada en el dominio de destino y el desempeño desagregado por características demográficas no ha sido evaluado. | Su autor |
| Anexo A. Cartel | `secciones/anexo_cartel.tex` | **Redactado.** Es de este frente. | Cinco campos en blanco que solo LAP puede completar: **C-01** a **C-05**. Sin ellos el cartel no cumple el deber de información del art. 18 y la medida **M-08** queda abierta. | LAP |

**Lectura corta:** de las cuatro secciones ajenas a este frente, **una está
redactada** (Introducción) y **tres son esqueletos** (Metodología, Resultados,
Conclusiones), que es lo que ya venía registrado en **B-08**. La que más
arrastra al resto es Metodología: de sus dos decisiones abiertas depende que la
auditoría de la Sección 3.9 pueda pasar de condicional a conclusión.

---

## Los tres pendientes que caducan

El resto puede esperar. Estos tres, no:

1. **B-04 — horas de GPU.** Si no se registran desde el inicio del
   entrenamiento, no se pueden reconstruir después.
2. **B-06 — licencias de los conjuntos de datos.** Si alguno restringe el uso
   comercial, hay que saberlo *antes* de entrenar con él.
3. **A-13 — fechas del D.S. 016-2024-JUS.** Es el dato del que cuelga el
   análisis de régimen transitorio, y hoy proviene del encargo interno del
   proyecto y no del diario oficial.
