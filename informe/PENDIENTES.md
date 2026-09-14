# PENDIENTES.md

Registro de los puntos abiertos del informe.

**Responsable del archivo:** Fabián Moreno Ugarte — Validación ética/legal y documentación
**Proyecto:** Capstone I, Universidad ESAN — Estimación de aglomeraciones, Aeropuerto Jorge Chávez (cliente: LAP)
**Última actualización:** 14 de septiembre de 2026 (formato pedido por Liderazgo: Sección 3 comprimida y Anexo B)

> **Numeración de la Sección 3 desde el 14/09/2026.** La Sección 3 del PDF se
> comprimió a cuatro subapartados y su desarrollo completo pasó, sin recortes,
> al **Anexo B** (`secciones/anexo_b_marco_normativo.md`). Los «§3.1» a «§3.9»
> que este archivo cita en entradas anteriores a esa fecha corresponden hoy a
> **B.1 a B.9**. En el cuerpo: 3.1 resume B.1; 3.2 resume B.2 a B.4; 3.3 resume
> B.5 a B.8; 3.4 resume B.9.

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
| A-10 | Ciclo académico y fecha de entrega que deben figurar en la portada. | `main.tex`, portada | **Abierto.** La portada ya lleva ambas líneas, cada una con marcador `[VERIFICAR]` en lugar de valor. Desde el 13/09/2026 el campo **no se imprime en absoluto** cuando falta el dato (`\campoportada`, ver a.3): no queda ni la etiqueta «Ciclo academico:» ni una linea de relleno, de modo que la portada no muestra huecos. **Falta confirmar los dos datos contra el sílabo del curso** —no contra una estimación ni contra lo que figure en otro documento del equipo— y sustituir los dos marcadores. Es de este frente y se cierra en cuanto se tenga el sílabo delante. Se rectifica lo que decía este punto antes: la portada ya no está «sin línea de fecha». |
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

### a.3 Marcadores `[VERIFICAR]` en el cuerpo

**Cambio de mecanismo (13/09/2026).** Antes, `md2tex.py` convertia
`[VERIFICAR: ...]` en `\textit{[VERIFICAR: ...]}` y el marcador **se
imprimia en el PDF**. Ahora lo convierte en `\verificar{...}`, macro
definida en `main.tex` que **no produce ninguna salida**. El texto sigue
integro en el `.md` de origen y en el `.tex` generado; lo que desaparece es
su impresion.

Conviene no confundir esta macro con la retirada `\pendiente{}{}`, que hace
lo contrario y **debe seguir sin existir**: si alguien la escribe, la
compilacion falla, y esa salvaguarda se mantiene intacta.

Para que ocultar no equivalga a olvidar, cada marcador deja rastro en el log
de compilacion y al final se emite el recuento:

```
[VERIFICAR 1] marcador oculto en pagina 11.
...
MARCADORES [VERIFICAR] EN EL CUERPO: 9
```

Las macros **no** terminan en `\ignorespaces`. Terminaban, y se comian el espacio *posterior* al marcador: como los marcadores se escriben pegados al punto de la frase anterior, el PDF salia con «evalua.Si puede» sin separacion. Corregido el 13/09/2026; afectaba tambien a los seis marcadores de la Seccion 3. TeX colapsa los espacios consecutivos, asi que quitarlo no introduce espacios dobles.

En la portada se usa `\campoportada{marcador}{formato}{dato}`. Imprime el campo
entero --- etiqueta, parentesis y espaciado incluidos --- **solo si {dato} no
esta vacio**; si falta, no sale nada: ni etiqueta colgando ni linea de relleno.
Para cerrar el marcador basta con escribir el dato en el tercer argumento, que
es lo que se hizo con los cuatro codigos de alumno.

**Los 12 marcadores vigentes (14/09/2026).** Esta es la lista autoritativa. Los de la Seccion 3 y del Anexo B **se corrigen en el `.md` y se reconvierte**, nunca en el `.tex`. Pasaron de 9 a 12 porque la Seccion 3 se comprimio y su desarrollo completo se traslado al Anexo B: cada una de las tres reservas normativas se afirma ahora en los dos sitios y lleva marcador en ambos. **Al cerrar una, hay que cerrarla en los dos `.md`.**

| # | Fuente (se edita aqui) | `.tex` generado | Qué falta verificar | Ficha |
|---|---|---|---|---|
| 1 | `secciones/03_marco_normativo.md:41` y `secciones/anexo_b_marco_normativo.md:37` | `03_marco_normativo.tex:49`, `anexo_b_marco_normativo.tex:56` | Solo la fecha de entrada en vigor del D.S. 016-2024-JUS (30/03/2025). Expedicion, publicacion y disposicion derogatoria confirmadas contra la separata de *El Peruano* | A-13 |
| 2 | `secciones/03_marco_normativo.md:43` y `secciones/anexo_b_marco_normativo.md:41` | `03_marco_normativo.tex:69`, `anexo_b_marco_normativo.tex:93` | Denominacion oficial y fecha de publicacion del D.L. 1218 y de la Ley 30120 | A-20 |
| 3 | `secciones/03_marco_normativo.md:71` y `secciones/anexo_b_marco_normativo.md:135` | `03_marco_normativo.tex:215`, `anexo_b_marco_normativo.tex:588` | Texto literal del RNF-01 y documento en que consta | D-04 |
| 4 | `main.tex:288` | — | Ciclo academico segun silabo | A-10 |
| 5 | `main.tex:289` | — | Fecha de entrega segun silabo | A-10 |
| 6 | `secciones/introduccion.tex:61` | — | Como se decide hoy la dotacion de personal y la apertura de mostradores | C-08 |
| 7 | `secciones/introduccion.tex:106` | — | Incidentes de aglomeracion, tiempos de cola y quejas documentados por LAP | C-07 |
| 8 | `secciones/introduccion.tex:112` | — | Aforo declarado del terminal y superficie por zona | C-07 |
| 9 | `secciones/introduccion.tex:216` | — | Numero de zonas a cubrir y de camaras disponibles por zona | C-09 |

Los marcadores 1 a 3 cuentan dos veces en el log (uno por la Seccion 3 y otro por el Anexo B), de ahi el total de 12. La Seccion 4 no tiene ninguno.

**Las reservas 1-3 ya se leen en el PDF (14/09/2026).** Hasta el 13/09/2026, ocultar los marcadores tenia un efecto que este apartado advertia: la prosa visible afirmaba el dato en indicativo y la reserva no se veia, y la nota de la pagina iii del informe suplia esa carencia remitiendo aqui. Por pedido del frente de Liderazgo e Integracion, esa nota se elimino y las tres reservas se **redactaron como prosa** dentro del parrafo que afirma cada dato, en la Seccion 3 y en el Anexo B, que es la via que este mismo apartado recomendaba. La fecha de entrada en vigor pasa ademas a condicional («se habria producido»). El marcador `[VERIFICAR]` se mantiene junto a cada reserva como nota de trabajo y para el recuento del log; la prosa no lo sustituye. Los cuatro de la Introduccion (6-9) se editan directamente en el `.tex`, que ahi **si** es la fuente.

**A-10b.** ✅ **Cerrado el 13/09/2026.** Los cuatro integrantes aportaron sus codigos y sus apellidos completos, y ya figuran en la portada: Aguilar Contreras, Angel (22200133); Rivadeneyra Huaman, Stephano Williams (22101822); Ortega Olazabal, Jose (25200719); Moreno Ugarte, Fabian (25200717). Se mantiene el orden historico de la portada, no el alfabetico. Cerro los cinco marcadores 7-11 de la lista anterior. Texto original del punto: La portada pide los integrantes como «Apellidos, Nombres
(codigo)». No consta en el repositorio **ningun codigo de alumno**, y de
Aguilar, Rivadeneyra y Ortega solo consta el apellido paterno. Los cuatro
codigos y los tres apellidos maternos hay que pedirselos a los propios
integrantes. Es de este frente recogerlos y sustituirlos; nadie mas los tiene.

**A-29 (nuevo).** No hay **logo de ESAN** en el repositorio. `main.tex` lo
carga con `\IfFileExists` desde `informe/imagenes/logo-esan.pdf` (o `.png`) y,
mientras no exista, compone un recuadro con la leyenda «Logo ESAN» del mismo
tamano, de modo que anadir el archivo no altera la maquetacion ni exige tocar
el `.tex`. Preferible PDF vectorial; si es PNG, a 300 ppp o mas.

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
| E-02 | **Overleaf abandonado.** La compilación dejó de funcionar por el límite de la cuenta gratuita. En su momento esto llevó a declarar el `.docx` como entregable; **esa parte quedó revertida por E-10**, y el entregable es `main.pdf`. | ✅ **Cerrado el 11/09/2026** en cuanto al abandono de Overleaf, que no se revierte: se compila en local. La elección de entregable se decidió en **E-10** (12/09/2026). **Queda abierto** el procedimiento de integración `.md` → `.docx`, por si el frente de integración mantiene su copia en Word: ver **E-07**. |
| E-03 | **El `.docx` y el `.tex` divergieron en Antecedentes.** El `.docx` (últ. mod. 09/09/2026, Ángel) añade MOTRv2, GeneralTrack, seguimiento multicámara por clustering y MCBLT, que no están en `antecedentes.tex`; y `fichas_antecedentes/` cubre PET, MeMOTR y ByteTrack, que tampoco coinciden con los del `.docx`. | **Abierto.** Las tres contradicciones de la sección (d) proceden justamente de los antecedentes nuevos del `.docx`. |
| E-04 | **Título de la sección.** El `.tex` archivado la titula «Marco ético y legal aplicable»; el `.md` vigente, «Marco normativo aplicable». Las referencias cruzadas dicen solo «Sección 3», así que ninguna se rompe. | ✅ **Cerrado por consecuencia de E-01:** manda el `.md`, luego el título es «Marco normativo aplicable». |
| E-05 | **Extensión.** La Sección 3 quedó en 4.744 palabras frente al objetivo inicial de 2.500–3.500. | ✅ **Cerrado el 11/09/2026:** se mantiene en 4.744. El límite era arbitrario y recortar exigía retirar citas verificadas. |
| E-06 | **Normas legales fuera de `referencias.bib`.** Se respetó la regla 4 del `README`: las normas se citan en prosa y su trazabilidad va a `NOTAS_FUENTES.md`. | ✅ **Cerrado** por decisión de 11/09/2026. Se deja constancia porque el encargo inicial pedía lo contrario. |
| E-07 | **Integración `.md` → `.docx`.** Falta acordar cómo se convierten las Secciones 3 y 4 al `.docx` y cómo se deja constancia de qué versión del `.md` está incorporada. Sin eso, ambos divergen en silencio, que es el problema que E-01 acaba de resolver para el `.tex`. | **Abierto.** Depende de Ángel (integración) y de este frente. |
| E-08 | **Migración del resto de secciones.** `introduccion`, `antecedentes`, `metodologia`, `resultados`, `conclusiones` y `anexo_cartel` siguen en `.tex`. El Anexo A importa especialmente, porque las Secciones 3.5 y 3.7 lo citan como modelo de cartel. | **Abierto, pero menos urgente desde el 11/09/2026 (tarde):** al reincorporarse las Secciones 3 y 4 al `.tex`, el PDF vuelve a contener el informe completo y la convivencia de formatos deja de partir el documento en dos mitades. Sigue abierto decidir el formato único. Ver E-10. |
| E-09 | **`referencias.bib` y `papers/citas_oficiales.txt` habían divergido.** El `.bib` tenía **10** entradas; `citas_oficiales.txt`, **6**. Las cuatro de más son `Zhang_2023_CVPR` (MOTRv2), `Qin_2024_CVPR` (GeneralTrack), `Huang_2023_CVPR` (multicámara con *clustering*) y `Wang_2025_ICCV` (MCBLT). Las añadió el *commit* `a68c7c5` del 08/09/2026, ajeno a este frente, y proceden de `fichas_antecedentes/C1`–`C4`. | **Parcialmente resuelto el 12/09/2026; el resto es BLOQUEO EXTERNO.** Hecho por este frente: las cuatro entradas se incorporaron a `papers/citas_oficiales.txt` copiadas literalmente del `.bib`, con la URL de `openaccess.thecvf.com` de cada una verificada (HTTP 200) y anotando que `Huang_2023_CVPR` es de **CVPR2023W** y `Wang_2025_ICCV` de **ICCV2025W** —ambas de *Workshops*, no de la conferencia principal—. La correspondencia `.bib` ↔ `.txt` vuelve a ser literal, 10 entradas por 10, comprobable con `diff` ignorando comentarios, de modo que la **regla 4 del `README`** ya no está infringida. Conviene mantener la precisión de siempre: **no son citas indefinidas y no bloquean nada.** Ninguna de las cuatro se cita en el informe —no hay `\cite` a ellas en ningún `.tex` ni en los `.md`—, así que no producen aviso alguno, no aparecen en el PDF, y la bibliografía imprime solo las tres entradas efectivamente citadas (`Li_2018_CVPR`, `Song_2021_ICCV`, `Lin_2025_CVPR`). Causa verificada de la divergencia: `papers/` está en `.gitignore`, de modo que `citas_oficiales.txt` **solo existe en la máquina de este frente** y quien añadió las entradas no tenía cómo consultarlo; queda dicho de forma explícita en el `README`. **Lo que sigue abierto y no depende de este frente:** decidir si las cuatro se citan desde unos Antecedentes ampliados (ver E-03) o se retiran del `.bib`. Es decisión de la reunión, con **Stephano** (las aportó) y **Ángel** (Antecedentes). Hasta entonces no se cita ninguna. |
| E-10 | **Dos entregables en paralelo.** El `README` de la mañana del 11/09/2026 declaraba el PDF «legado» y el `.docx` como único entregable. Por la tarde el informe se consolidó en LaTeX y el PDF volvió a estar completo y compilando (40 páginas, 0 errores). Ambos coexistían sin que se hubiera decidido cuál manda, y el `README` describía un flujo que ya no era el vigente. | ✅ **Cerrado el 12/09/2026.** Entregable: **`main.pdf`, compilado desde `main.tex`**. El `.docx` pasa a ser copia de trabajo del frente de integración y se añadió a `informe/.gitignore` (binario de 2 MB que Git no fusiona y que ya está en el repositorio como fuente); `informe.zip` seguía ya ignorado en el `.gitignore` de la raíz. El `README` se reescribió completo al flujo vigente: se eliminaron los apartados «Cambio de herramienta», «Dónde se edita el documento» con el `.docx` como entregable y «Cómo compilar (legado)», y el **«Qué NO hacer»** ya no prohíbe reintroducir las Secciones 3 y 4 en el `.tex` —prohibía justo lo que se hizo— sino editar a mano los dos `.tex` **generados**, que es el riesgo real del flujo nuevo. Se documentó además la conversión con `herramientas/md2tex.py` y `verificar_fidelidad.py`, y que `papers/` está ignorado y por eso `citas_oficiales.txt` solo existe en local (causa de E-09). **Lo que NO cierra aquí:** el procedimiento de integración `.md` → `.docx` sigue abierto en **E-07**, por si el frente de integración mantiene su copia en Word. |
| E-11 | **El `README` afirmaba que quedaban «siete `[VERIFICAR]`, todos sobre el articulado del D.S. 016-2024-JUS».** | ✅ **Cerrado el 12/09/2026 por este frente**, en la misma reescritura del `README` de E-10. Recuento verificado sobre el `.md` y sobre el `.tex` generado: en el cuerpo hay **seis**, no siete —el séptimo era el ejemplo `[VERIFICAR: ...]` del comentario de cabecera—, todos en la Sección 3 (la Sección 4 no tiene ninguno), y **solo dos** versan sobre el articulado del D.S. 016-2024-JUS: el artículo que consagra privacidad por diseño y por defecto (`03_marco_normativo.tex:286`) y el que fija el alcance extraterritorial (`:452`). Los otros cuatro son las fechas y la disposición derogatoria del propio D.S. (A-13, `:50`), la vigencia de la Directiva 01-2020-JUS/DGTAIPD (`:62`), la denominación del D.L. 1218 y la Ley 30120 (`:79`) y el texto literal del RNF-01 (D-04, `:555`). El `README` ya lo dice así. Los seis `[VERIFICAR]` en sí **siguen abiertos**: son A-13, D-04 y las verificaciones documentales de la sección (a.2), no este punto. |
| E-12 | **`secciones/_archivo/README.md` era el último rastro del flujo viejo.** Seguía declarando el `.docx` como entregable y describiendo las Secciones 3 y 4 como mantenidas en Markdown fuera del `.tex`, que es el flujo que E-10 revirtió. Al estar dentro de `secciones/`, era lo primero que leería quien abriera la carpeta buscando las versiones antiguas. | ✅ **Cerrado el 12/09/2026 por este frente.** Reescrito de 54 a 12 líneas, con solo lo que hace falta saber: que la carpeta es material archivado y congelado, que el entregable vigente se compila desde `main.tex` con los `.tex` generados desde los `.md`, y que **nada de ahí se reintroduce sin revisarlo antes contra esos `.md`**, porque el texto divergió y volver a meterlo tal cual reabriría la duplicidad de fuente que cerró E-01. Se corrigió además la frase del `README` de `informe/` que remitía a este archivo describiéndolo como desactualizado. |

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
| E-13 | **`secciones/introduccion.tex` la reescribio este frente, y `CLAUDE.md` la lista como seccion de otro integrante** («no se edita su contenido»). El encargo viene del frente de Liderazgo e Integracion: abrir por el problema **operativo** del terminal (aforo, aglomeraciones, tiempos de cola) en vez de por el marco normativo. | 🟡 **Abierto: falta que lo revise su responsable original.** Se reescribieron 1.1 Contexto y 1.2 Objetivos, y se anadio a 1.3 una precision sobre numero de zonas y camaras. La estructura y los `label` se conservan intactos (`sec:introduccion`, `sec:contexto`, `sec:objetivos`, `sec:alcance`), y las nueve referencias cruzadas que la seccion emite siguen resolviendo. No se uso **ninguna** cifra del terminal porque **no existe ninguna en el repositorio**: lo que falta quedo en cuatro `\verificar{...}` (C-07, C-08, aforo/superficie, numero de zonas y camaras). Este punto se cierra cuando el responsable de la seccion revise el texto o confirme el traspaso. |

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
