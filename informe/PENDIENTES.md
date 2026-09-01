# PENDIENTES.md

Registro de los puntos abiertos del informe.

**Responsable del archivo:** Fabián Moreno Ugarte — Validación ética/legal y documentación
**Proyecto:** Capstone I, Universidad ESAN — Estimación de aglomeraciones, Aeropuerto Jorge Chávez (cliente: LAP)
**Última actualización:** 1 de septiembre de 2026

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
| A-12 | Transcripción literal del artículo 2, incisos 6 y 7 de la Constitución, desde la edición oficial. | Nivel constitucional |
| A-13 | **Prioritario.** Las cuatro fechas del D.S. 016-2024-JUS contra *El Peruano*: publicación (30/11/2024), vigencia (30/03/2025), derogación del D.S. 003-2013-JUS. Un error aquí arrastra todo el análisis de régimen transitorio. | Ley 29733 y reglamento |
| A-14 | Numeral exacto del artículo 2 de la Ley 29733 sobre dato sensible; si el D.S. 016-2024-JUS precisó la definición. | Datos biométricos |
| A-15 | Artículo que regula la EIPD, contenido mínimo exigido y supuestos en que la consulta previa a la ANPD pasa de facultativa a obligatoria, con su plazo. | EIPD |
| A-16 | Artículo del plazo de notificación de brechas; desde qué hecho se computa; horas hábiles o calendario; destinatario (ANPD, titulares o ambos); umbral de gravedad. | Brechas |
| A-17 | Artículo del cronograma del ODP; umbrales de ingresos de cada tramo y sus fechas; comunicación de la designación a la ANPD; requisitos de independencia. | ODP |
| A-18 | Artículo del alcance extraterritorial y sus criterios de conexión. | Extraterritorialidad |
| A-19 | Denominación oficial completa de la Directiva 01-2020-JUS/DGTAIPD y número y fecha de la resolución directoral que la aprueba. Su vigencia ya está verificada; falta descartar una derogación parcial revisando las disposiciones derogatorias del D.S. 016-2024-JUS. | Directiva |
| A-20 | D.L. 1218: denominación oficial, fecha, obligaciones de entrega de imágenes a PNP y Ministerio Público, plazos de conservación. | D.L. 1218 y Ley 30120 |
| A-21 | Ley 30120: denominación oficial, fecha y, sobre todo, si alcanza a establecimientos privados abiertos al público. Decide si aplica al terminal. | D.L. 1218 y Ley 30120 |
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

## Los tres pendientes que caducan

El resto puede esperar. Estos tres, no:

1. **B-04 — horas de GPU.** Si no se registran desde el inicio del
   entrenamiento, no se pueden reconstruir después.
2. **B-06 — licencias de los conjuntos de datos.** Si alguno restringe el uso
   comercial, hay que saberlo *antes* de entrenar con él.
3. **A-13 — fechas del D.S. 016-2024-JUS.** Es el dato del que cuelga el
   análisis de régimen transitorio, y hoy proviene del encargo interno del
   proyecto y no del diario oficial.
