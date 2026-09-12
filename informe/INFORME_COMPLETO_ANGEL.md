> **Nota editorial (frente de Liderazgo e Integración — Ángel Aguilar).**
> Este documento consolida en un solo archivo todo el contenido real ya
> redactado en `informe/secciones/` (Introducción, Antecedentes, Marco
> normativo, Análisis de impacto, Anexo A — convertidos de LaTeX/Markdown a
> texto corrido, sin cambiar una palabra de su contenido) junto con cuatro
> secciones nuevas (Especificación de Requerimientos, Diseño del Sistema,
> Planificación y Gestión, y este Resumen Ejecutivo), siguiendo la estructura
> de un informe Capstone de otro equipo revisado como referencia de forma
> (no de contenido). **No es el entregable.** El entregable sigue siendo
> `main.pdf`, compilado desde `main.tex`. Este archivo no está enlazado a la
> compilación y no reemplaza ningún `.tex`.
>
> **Sobre la numeración:** las Secciones 3 (Marco normativo) y 4 (Análisis de
> impacto) se dejaron con su número intacto a propósito — doce referencias
> cruzadas del informe, tres a un subapartado concreto (3.4, 3.9, 4.4),
> dependen de esa numeración exacta (`CLAUDE.md`). Las cuatro secciones
> nuevas se insertaron después de la Sección 4 y antes de Metodología, que
> por eso se renumera de 5 a 8; Metodología no fija subapartados con número
> citado desde otra sección, así que ese corrimiento no rompe ninguna
> referencia cruzada existente.
>
> **Dos cosas que este documento señala y no resuelve por su cuenta,**
> porque son decisiones del equipo, no de redacción:
> 1. El informe (§1.3) describe Capstone I como validación sobre "conjuntos
>    de datos públicos de conteo de multitudes". El prototipo funcional que
>    se describe en la Sección 5 se probó sobre dos videos grabados por el
>    propio equipo en la universidad — no sobre datos públicos ni sobre el
>    Aeropuerto Jorge Chávez. Son tres evidencias distintas y ninguna
>    sustituye a las otras dos.
> 2. La arquitectura descrita en la Sección 6 (Diseño del Sistema) es la que
>    el prototipo ya implementa, **no** la "arquitectura definitiva" que
>    pide el punto B-01 de `PENDIENTES.md`, que sigue abierto.

---

<div align="center">

**Universidad ESAN**
**Facultad de Ingeniería**
**Carrera de Ingeniería de Inteligencia Artificial**

---

# Estimación de aglomeraciones de personas mediante visión computacional en el Aeropuerto Internacional Jorge Chávez

**Informe de Capstone I**
Cliente: Lima Airport Partners (LAP)

---

**Equipo de trabajo**

| Integrante | Frente |
|---|---|
| Angel Aguilar | Liderazgo e integración |
| Stephano Rivadeneyra | Ciencia de datos |
| José Ortega | Ingeniería de datos |
| Fabián Moreno Ugarte | Validación ética/legal y documentación |

Ciclo académico: *[VERIFICAR: ciclo según sílabo — pendiente A-10]*
Fecha de entrega: *[VERIFICAR: fecha según sílabo — pendiente A-10]*

Lima, Perú

</div>

---

## Resumen Ejecutivo

El proyecto **Estimación de aglomeraciones de personas mediante visión
computacional en el Aeropuerto Internacional Jorge Chávez** desarrolla, para
Lima Airport Partners (LAP), un sistema que estima la concentración de
personas por zona del terminal a partir de cámaras fijas, sin recurrir a
reconocimiento facial ni a datos biométricos que identifiquen a un pasajero
concreto. Esta condición no es una preferencia de diseño sino un límite
impuesto por la Ley 29733 de Protección de Datos Personales y su reglamento
vigente (D.S. 016-2024-JUS): un dato biométrico que por sí mismo identifica al
titular constituye dato sensible, y el proyecto se plantea evitar ese
tratamiento desde el diseño en lugar de mitigarlo después.

La Sección 2 (Antecedentes) revisa tres trabajos que marcan una progresión en
la línea de investigación de conteo de multitudes —CSRNet (mapas de
densidad), P2PNet (localización pura por puntos) y P2R (aprendizaje
semi-supervisado punto-a-región)— y concluye que la granularidad de la salida
es una decisión de cumplimiento normativo y no solo de producto: a igualdad
de utilidad operativa, el principio de proporcionalidad (art. 7, Ley 29733)
favorece la opción que menos datos trata. Esa decisión —qué arquitectura y qué
granularidad se adoptan— sigue abierta (`PENDIENTES.md`, punto B-01) al cierre
de esta versión.

Las Secciones 3 y 4 desarrollan, respectivamente, el marco normativo peruano
aplicable (Ley 29733, su reglamento, la Directiva de videovigilancia
01-2020-JUS/DGTAIPD, y el régimen de seguridad ciudadana del D.L. 1218 y la
Ley 30120) y el análisis de impacto del sistema sobre los derechos de las
personas observadas y sobre el entorno. Ambas secciones incorporan una
auditoría del prototipo de ingeniería ya construido, con hallazgos en ambos
sentidos: la fusión de identidad entre cámaras **no** usa reidentificación por
apariencia (hallazgo favorable, D-01), pero la base de datos del prototipo
persiste coordenadas individuales encadenadas a un identificador por persona,
lo que **no** satisface la medida de agregación por zona exigida (M-03,
hallazgo D-05) — el único hallazgo no conforme de todo el análisis que el
equipo puede cerrar por sí solo, sin depender de LAP.

En paralelo a la revisión de literatura, el frente de ingeniería construyó un
prototipo funcional (`proyecto_lap_prototipo/`), probado sobre dos cámaras
propias que registran la misma explanada de la universidad desde ángulos
distintos —no sobre material del Aeropuerto Jorge Chávez, que LAP todavía no
ha proporcionado (`PENDIENTES.md`, C-14)—. Las Secciones 5 a 8 de este
documento describen ese prototipo (requisitos, arquitectura, casos de uso) y
la planificación del proyecto; son evidencia de ingeniería complementaria a la
Sección 2, no la arquitectura definitiva que Metodología (Sección 9) debe
todavía cerrar por escrito.

Las Secciones 9 (Metodología), 10 (Resultados) y 11 (Conclusiones) siguen en
esqueleto, a cargo de otros integrantes del equipo; este documento no
inventa su contenido y reproduce fielmente su estado real.

---

## 1. Introducción

### 1.1 Contexto del problema

El Aeropuerto Internacional Jorge Chávez, operado por Lima Airport Partners
(LAP), concentra en determinadas franjas horarias y en puntos específicos del
terminal —filtros de seguridad, migraciones, mostradores de *check-in*, salas
de embarque— un volumen de pasajeros considerablemente mayor que el de otras
zonas del recinto en el mismo momento. Conocer dónde y cuándo se concentran
las personas es información operativa de valor para un operador aeroportuario:
permite, en principio, anticipar la apertura de mostradores adicionales,
redirigir el flujo de pasajeros o dimensionar al personal de atención con
mayor precisión que una revisión manual o periódica.

LAP cuenta ya con infraestructura de videovigilancia de circuito cerrado en el
terminal. Este proyecto explora si esa misma infraestructura puede
aprovecharse, mediante técnicas de visión computacional, para producir una
estimación automatizada de la concentración de personas por zona, sin que ello
suponga identificar, individualizar ni caracterizar biométricamente a los
pasajeros que aparecen en la imagen. Esta última condición no es una
preferencia de diseño sino un límite impuesto por la Ley 29733 de Protección
de Datos Personales y su reglamento vigente (D.S. 016-2024-JUS): un dato
biométrico que por sí mismo identifica al titular constituye dato sensible, y
el proyecto se plantea evitar ese tratamiento desde el diseño en lugar de
mitigarlo después. La Sección 3 desarrolla en detalle el marco normativo
aplicable, y la Sección 2 revisa la literatura técnica que hace posible, en
principio, estimar una aglomeración sin recurrir a identificación individual.

Conviene precisar el alcance de esta afirmación desde ya, para no
sobredimensionar el problema que el proyecto atiende. El equipo no cuenta, al
momento de escribir este informe, con evidencia documentada por LAP
—incidentes registrados de aglomeración, tiempos de espera medidos o quejas de
pasajeros— que cuantifique el problema en el propio terminal; esa evidencia se
ha solicitado al cliente y su ausencia se deja constancia expresa en
`PENDIENTES.md`. El proyecto parte, por tanto, de una necesidad operativa
plausible y compartida por la literatura de conteo de multitudes en espacios
de alto tránsito, y no de una cifra propia de incidentes en el Aeropuerto
Jorge Chávez.

### 1.2 Objetivos

**Objetivo general.** Desarrollar y evaluar un sistema de visión
computacional capaz de estimar la concentración de personas en distintas
zonas del Aeropuerto Internacional Jorge Chávez a partir de imágenes de
cámaras fijas, sin recurrir a reconocimiento facial ni a la extracción de
rasgos biométricos identificantes, y en condiciones de cumplimiento con el
marco normativo peruano de protección de datos personales.

**Objetivos específicos.**

1. Revisar el estado del arte en detección, localización y conteo de
   personas en escenas congestionadas, e identificar qué enfoque técnico
   resulta más adecuado para un entorno aeroportuario y para las
   restricciones de privacidad del proyecto (Sección 2).
2. Determinar el marco de cumplimiento normativo aplicable al tratamiento de
   imágenes de un espacio de uso público bajo gestión concesionada,
   incluyendo el análisis de impacto y los requisitos de privacidad desde el
   diseño que ese tratamiento exige (Secciones 3 y 4).
3. Diseñar e implementar el componente de detección y estimación, con la
   granularidad de salida —superficie de densidad, conteo agregado por zona
   o localización individual— que resulte de aplicar el principio de
   proporcionalidad (§3.4) y la síntesis de antecedentes (§2.4). Esta
   decisión se documentará en la Sección de Metodología cuando el frente
   técnico la cierre; hasta entonces queda registrada como abierta en
   `PENDIENTES.md` (B-01 y D-11).
4. Evaluar el desempeño del sistema mediante métricas cuantitativas y
   cualitativas, indicando en cada caso sobre qué conjunto de datos fue
   medido cada resultado —ninguna cifra obtenida sobre conjuntos públicos se
   presentará como desempeño esperable en el terminal sin la validación en
   sitio que la Sección 2.3 señala como condición previa.
5. Identificar los requisitos de validación adicionales que quedan fuera del
   alcance material de este Capstone —en particular el acceso a datos del
   propio terminal y la evaluación de sesgo demográfico— y dejarlos
   documentados como trabajo pendiente en lugar de darlos por resueltos
   (retomado en la Sección 11).

### 1.3 Alcance y limitaciones del proyecto

**Alcance funcional.** El proyecto cubre la estimación de la concentración de
personas por zona a partir de imágenes de cámaras fijas. Queda expresamente
fuera de su alcance cualquier forma de identificación, reidentificación o
caracterización individual de las personas detectadas: el sistema está
pensado para responder *cuántas personas hay, y dónde*, no *quién es cada
una*. La Sección 2.2 señala, sin embargo, que esta distinción es una cuestión
de política de persistencia y no solo de algoritmo: el mismo modelo que
localiza personas puede, si sus salidas se retienen y se asocian entre
cuadros, aproximarse a un seguimiento de trayectorias. Por eso la granularidad
de salida que finalmente se implemente es, como se indica en el objetivo
específico 3, una decisión que debe quedar documentada por escrito antes de
cerrar la Sección de Metodología.

**Zonas cubiertas.** Las zonas concretas del terminal sobre las que se
entrena y evalúa el sistema dependen de qué cámaras y qué material
audiovisual habilite LAP para el proyecto, dato que a la fecha de este
informe no ha sido confirmado por el cliente (`PENDIENTES.md`, C-09/C-14).
Donde este informe menciona zonas a título de ejemplo —filtros de seguridad,
mostradores de *check-in*, salas de embarque— lo hace como ilustración del
tipo de espacio al que el sistema podría aplicarse, no como una cobertura ya
acordada con el cliente.

**Fase del proyecto y limitación de dominio.** Esta primera entrega
corresponde a Capstone I: un desarrollo y validación conceptual del sistema
sobre conjuntos de datos públicos de conteo de multitudes, sin acceso todavía
a material propio del Aeropuerto Jorge Chávez. Esto impone la limitación más
importante del proyecto en esta etapa, y conviene enunciarla sin atenuarla
porque condiciona la lectura de todo lo que sigue: como documenta en detalle
la Sección 2.3, los propios autores de la literatura revisada reconocen una
brecha de dominio entre los conjuntos públicos de entrenamiento y un entorno
de despliegue nuevo, y señalan que el desempeño se degrada de forma marcada
cuando no media una etapa de adaptación de dominio. En consecuencia, ninguna
cifra de desempeño que se reporte en la Sección de Resultados debe leerse
como una predicción de exactitud para el Aeropuerto Jorge Chávez: es, en el
mejor de los casos, una cota de referencia sobre datos públicos, sujeta a
validarse en sitio antes de comunicarse a LAP como una expectativa de
desempeño (§3.9).

> *Nota de esta consolidación:* la Sección 5 describe, además, un prototipo
> de ingeniería probado sobre grabaciones propias del equipo (no sobre los
> conjuntos públicos a los que remite este apartado). Es una tercera
> evidencia, distinta de las dos que aquí se contrastan, y el informe todavía
> no la distingue por escrito en ningún punto — ver la nota editorial al
> inicio de este documento.

---

## 2. Antecedentes

El conteo de personas en escenas congestionadas es un problema con una línea
de investigación propia dentro de la visión computacional. Esta sección
revisa tres trabajos que marcan tres etapas sucesivas de esa línea —la
regresión de mapas de densidad, la detección puramente basada en puntos y el
aprendizaje semi-supervisado sobre puntos— y discute, para cada uno, qué
propone, por qué resulta pertinente para el caso del Aeropuerto Internacional
Jorge Chávez y qué limitación reconocen sus propios autores.

Se privilegia deliberadamente la limitación *declarada por los autores* sobre
la crítica externa: en un informe de cumplimiento, lo que un proveedor de
tecnología reconoce por escrito sobre su propio método es el insumo más
defendible para dimensionar el riesgo residual del sistema.

> **Criterio aplicado a las cifras de esta sección.** Solo se reproducen aquí
> las cifras que constan en el texto en prosa de cada artículo —resumen,
> introducción o discusión de resultados—. Las que figuraban únicamente en
> las tablas de resultados se omiten: la conversión de esos cuadros a texto
> plano mezcla filas y columnas, y una cifra mal atribuida a un conjunto de
> datos sería precisamente el tipo de afirmación no verificable que este
> informe debe evitar.

### 2.1 CSRNet: redes convolucionales dilatadas para escenas altamente congestionadas

**Qué propone.** Li, Zhang y Chen [Li_2018_CVPR] proponen CSRNet, una red
completamente convolucional compuesta por dos bloques: un *front-end* que
reutiliza las primeras diez capas convolucionales de VGG-16 para extracción
de características 2D, y un *back-end* de convoluciones dilatadas que amplía
el campo receptivo sin recurrir a capas de *pooling*. La motivación explícita
es prescindir de las arquitecturas multi-columna previas: los autores
muestran experimentalmente que las tres columnas de MCNN aprenden
características casi idénticas, de modo que la ramificación introduce
redundancia sin aportar diversidad de escala real. La salida no es un número
sino un mapa de densidad, entrenado con pérdida euclídea contra un mapa de
referencia generado difuminando cada anotación de cabeza con un núcleo
gaussiano geométricamente adaptativo.

Los autores enuncian sus resultados en términos comparativos: sobre
ShanghaiTech obtienen un 7% menos de MAE que CP-CNN en la Parte A y un 47,3%
menos en la Parte B, y sobre TRANCOS (conteo de vehículos) reportan un 15,4%
menos de MAE que el mejor método previo.

**Por qué aplica al caso LAP.** (1) La salida es un mapa de densidad, no una
identidad: ninguna etapa requiere rasgos faciales ni plantilla biométrica. (2)
La arquitectura es puramente convolucional y admite resoluciones variables,
lo que importa porque las cámaras de un terminal no comparten resolución,
altura ni ángulo. (3) La distribución espacial es informativa por sí misma:
saber que hay 300 personas en el hall de salidas es menos útil que saber que
200 están concentradas frente a tres mostradores.

**Limitación reconocida por los autores.** Sobre UCSD (escenas dispersas, 11
a 46 personas por imagen) los propios autores admiten superar a la mayoría de
métodos previos *excepto a MCNN en MAE*, y reconocen que la baja resolución de
los cuadros ($238\times158$ px) dificultó generar un mapa de densidad de
calidad. El régimen de baja densidad no es el terreno donde el método brilla,
y buena parte del día un terminal aéreo opera precisamente en baja densidad.
Una segunda limitación, más estructural, es que el mapa de densidad no
entrega posiciones individuales.

### 2.2 P2PNet: un marco puramente basado en puntos

**Qué propone.** Song et al. [Song_2021_ICCV] sostienen que localizar
individuos responde mejor a las demandas prácticas del análisis de multitudes
que simplemente contarlos. P2PNet predice directamente un conjunto de puntos
con sus coordenadas y confianzas, sin representación intermedia, resolviendo
la asignación de objetivos de aprendizaje con emparejamiento uno a uno vía
algoritmo húngaro. Aportan además una métrica, la *density Normalized
Average Precision* (nAP), diseñada para evaluar conjuntamente localización y
conteo.

En resultados, sobre ShanghaiTech Parte A reducen el MAE un 4,8% y el MSE un
12,9% respecto de ADSCNet; sobre UCF\_CC\_50 rebajan el MAE en 2,1 puntos; sobre
NWPU-Crowd, un 12,4% frente a DM-Count. Reportan un MAE de 85,32 sobre
UCF-QNRF, y en localización, nAP$_{0.5}$ cerca del 90% en la mayoría de
conjuntos.

**Por qué aplica al caso LAP.** La localización individual convierte una
cifra en una decisión operativa: un conjunto de puntos admite agregación por
zonas definidas por LAP sin reentrenar el modelo. Ahora bien, esta misma
capacidad eleva el perfil de riesgo: un punto con coordenadas no es un dato
biométrico, pero sí es un dato espacio-temporal referido a una persona física.
Si esos puntos se persisten y se encadenan en el tiempo, el sistema se
acerca a un seguimiento de trayectorias, finalidad distinta de estimar
aglomeraciones.

> **Riesgo a validar con el cliente.** La diferencia entre *estimar una
> aglomeración* y *seguir a una persona* no es una diferencia de algoritmo
> sino de política de persistencia. Con la misma salida de P2PNet, retener
> los puntos y asociarlos entre cuadros produce trayectorias individuales.
> Este límite debe fijarse por diseño y por contrato, no dejarse a la
> configuración.

**Limitación reconocida por los autores.** En UCF-QNRF admiten que su
precisión "no es tan competitiva" frente a ADSCNet. En NWPU-Crowd atribuyen su
desempeño inferior en MAE[S] a usar un único mapa de características de una
sola escala. Más relevante: la precisión es notablemente menor bajo el umbral
estricto nAP$_{0.05}$, efecto de las desviaciones de etiquetado — un límite
del suelo de verdad, no del modelo, que obliga a formular cualquier
compromiso de exactitud a nivel de zona agregada y no de posición individual.

### 2.3 P2R: pérdida punto-a-región para conteo semi-supervisado

**Qué propone.** Lin, Zhao y Chan [Lin_2025_CVPR] parten de una constatación
económica: anotar cientos o miles de puntos por imagen ha frenado la adopción
del enfoque por puntos. Integran los métodos por puntos en un marco
semi-supervisado maestro-estudiante, y al implementarlo detectan que la
confianza de una pseudo-etiqueta no se propaga bien a los píxeles de fondo
bajo el esquema punto-a-punto. Su solución, P2R, sustituye el emparejamiento
punto-a-punto por uno punto-a-región, con el efecto colateral de que el
algoritmo húngaro deja de ser necesario.

Entrenar con el 5% de los datos usando P2R supera al aprendizaje totalmente
supervisado con el 10%. Con ese 5% de etiquetas alcanzan un MAE de 93,7 y un
MSE de 155,2 sobre ShanghaiTech Parte A. Bajo supervisión completa, P2R supera
a P2PNet en los cuatro conjuntos evaluados. Sobre una imagen de $576\times960$
con 775 puntos anotados, la pérdida punto-a-punto requiere 0,4307 s frente a
0,0064 s de P2R —cerca de 68 veces más rápido—.

**Por qué aplica al caso LAP.** El principio de minimización exige tratar
solo los datos necesarios. Un método competitivo con el 5% de datos
etiquetados reduce en proporción similar el volumen de imágenes del terminal
que deben revisarse y anotarse por personas: menos exposición de imágenes
reales a anotadores, menos copias fuera del entorno controlado. La eficiencia
de etiquetado deja de ser una ventaja de costo y se convierte en un argumento
de cumplimiento. Además, sus experimentos de adaptación de dominio no
supervisada abordan de frente un problema real del proyecto: ningún conjunto
público contiene escenas de un terminal aéreo peruano.

**Limitación reconocida por los autores.** Documentan un caso de fallo por
desenfoque de movimiento de la multitud —la norma, no la excepción, en un
terminal aéreo—. Más importante: registran la brecha de dominio explícitamente
— transferir el modelo sin adaptación degrada el desempeño de forma marcada.

> **Consecuencia para el proyecto.** Que los propios autores adviertan esta
> brecha de dominio implica que las métricas publicadas sobre conjuntos
> públicos **no son extrapolables** al Aeropuerto Jorge Chávez. El frente
> ético-legal recomienda que ninguna promesa cuantitativa de desempeño
> figure en un entregable al cliente antes de una validación en sitio, aun
> cuando eso implique presentar el proyecto sin cifras atractivas.

### 2.4 Síntesis: cómo se articulan los tres trabajos

Los tres artículos forman una progresión en la que cada uno resuelve una
limitación del anterior y desplaza el problema hacia el siguiente. CSRNet
[Li_2018_CVPR] resuelve *cuántos* con una superficie de densidad de la que no
se puede extraer *dónde*. P2PNet [Song_2021_ICCV] resuelve *dónde* eliminando
la representación intermedia, pero paga ese avance con costo de anotación
creciente. P2R [Lin_2025_CVPR] resuelve el costo de anotación llevando el
enfoque a régimen semi-supervisado.

| Trabajo | Avance técnico | Desplazamiento del riesgo |
|---|---|---|
| CSRNet [Li_2018_CVPR] | Mapa de densidad sin representación individual | Perfil más bajo: la salida es agregada por construcción. El riesgo se concentra aguas arriba, en qué se hace con el video original. |
| P2PNet [Song_2021_ICCV] | Localización individual por puntos | El riesgo se traslada a la salida: coordenadas por persona, persistibles y encadenables en trayectorias. Exige control de persistencia. |
| P2R [Lin_2025_CVPR] | Desempeño competitivo con 5% de etiquetas | Reduce el riesgo del proceso de anotación, pero introduce dependencia de pseudo-etiquetas cuya calidad no es auditable caso por caso. |

De esta lectura conjunta se desprenden tres criterios que el frente
ético-legal traslada al frente técnico: (1) la granularidad de la salida es
una decisión de cumplimiento, no solo de producto; (2) la eficiencia de
etiquetado de P2R es un argumento de minimización aprovechable; (3) ninguna
cifra de la literatura es transferible al terminal sin validación local.

Esta síntesis queda deliberadamente abierta en un punto: la elección de
arquitectura del frente técnico no consta por escrito al cerrar esta versión
del informe, y por esa razón la auditoría de la Sección 3.9 se formula de
manera condicional sobre los tres enfoques en lugar de sobre uno.

---

## 3. Marco normativo aplicable

*(Sección sin renumerar — ver nota editorial. Contenido íntegro de
`secciones/03_marco_normativo.md`, responsable Fabián Moreno Ugarte.)*

Esta sección identifica el régimen jurídico que rige el tratamiento de
imágenes de personas mediante videovigilancia y visión computacional en un
terminal aeroportuario, y traduce cada obligación en un requisito verificable
sobre el sistema propuesto. Las zonas en que la norma admite más de una
lectura razonable se presentan como riesgos a validar y no como conclusiones:
el análisis lo elabora un equipo de estudiantes de ingeniería y no un
despacho legal, y la calificación jurídica definitiva corresponde al área
legal de Lima Airport Partners y, en su caso, a la Autoridad Nacional de
Protección de Datos Personales.

### 3.1 Marco normativo aplicable

En el nivel constitucional, el artículo 2 de la Constitución de 1993 reconoce
en su inciso 6 el derecho "a que los servicios informáticos, computarizados o
no, públicos o privados, no suministren informaciones que afecten la
intimidad personal y familiar", y en su inciso 7 el derecho "al honor y a la
buena reputación, a la intimidad personal y familiar así como a la voz y a la
imagen propias". De ambos se desprende el criterio que atraviesa esta
sección: captar la imagen de una persona en un espacio abierto al público no
es intrínsecamente ilícito, pero constituye una injerencia en un derecho
fundamental y debe superar un examen de proporcionalidad.

La norma central es la Ley 29733, Ley de Protección de Datos Personales, cuyo
artículo 1 declara que su objeto es garantizar el derecho fundamental
previsto en el artículo 2 numeral 6 de la Constitución. Su reglamento vigente
fue aprobado por el Decreto Supremo 016-2024-JUS, publicado el 30 de
noviembre de 2024 y en vigor desde el 30 de marzo de 2025, que derogó el D.S.
003-2013-JUS. La consecuencia práctica es que los procedimientos, cláusulas
informativas y registros que LAP tenga construidos bajo el reglamento
anterior no son automáticamente conformes con el nuevo y deben revisarse.
*[VERIFICAR: las tres fechas y la disposición derogatoria se contrastaron
contra fuentes secundarias concordantes, no contra el diario oficial El
Peruano. Un error aquí arrastra todo el análisis de régimen transitorio.]*

El régimen se especifica para videovigilancia en la Directiva de Tratamiento
de Datos Personales mediante Sistemas de Videovigilancia (Directiva
01-2020-JUS/DGTAIPD, Resolución Directoral 02-2020-JUS/DGTAIPD, 16 de enero de
2020). Sigue vigente: la entrada en vigor del D.S. 016-2024-JUS no la
desplazó. *[VERIFICAR: descartar una derogación parcial revisando las
disposiciones complementarias derogatorias del D.S. 016-2024-JUS.]*

A ese cuerpo se superpone un segundo régimen, de finalidad distinta, en
materia de seguridad ciudadana: el Decreto Legislativo 1218 y la Ley 30120,
Ley de Apoyo a la Seguridad Ciudadana con Cámaras de Videovigilancia Públicas
y Privadas, ambos reglamentados por el D.S. 007-2020-IN (24 de abril de 2020).
Su artículo 3 delimita el ámbito de aplicación incluyendo a quienes son
propietarios o administradores de "establecimientos comerciales abiertos al
público con un aforo de cincuenta (50) personas o más". Un terminal
aeroportuario supera ese umbral con holgura, de modo que la aplicabilidad de
este régimen al Aeropuerto Jorge Chávez deja de ser hipótesis remota. *[VERIFICAR:
denominación oficial completa y fecha de publicación del D.L. 1218 y de la
Ley 30120. El D.S. 007-2020-IN sí se contrastó contra El Peruano.]*

Queda así identificada la zona gris principal: un terminal concesionado a un
operador privado no encaja limpiamente ni en la categoría de área de dominio
público ni en la de recinto privado cerrado. Resolverla requeriría analizar
el contrato de concesión y la normativa aeronáutica, lo que excede el alcance
del Capstone; es el primer punto a elevar al área legal del cliente.

### 3.2 Naturaleza de los datos tratados

El sistema no trata un solo tipo de dato sino cuatro, con regímenes distintos.

El primero es el **fotograma**: contiene rostros identificables y constituye
dato personal (art. 2.4, Ley 29733: "toda información sobre una persona
natural que la identifica o la hace identificable a través de medios que
pueden ser razonablemente utilizados"). El criterio legal es el de
identificabilidad por medios razonables, no el de identificación efectiva.

El segundo es el **punto con coordenadas** que producen los métodos basados
en puntos [Song_2021_ICCV; Lin_2025_CVPR]: desligado del fotograma, no
identifica por sí solo.

El tercero es el **dato espacio-temporal**, que aparece en cuanto ese punto se
asocia a una marca de tiempo y a una zona. Aislado sigue sin identificar;
encadenado con otros del mismo individuo, reconstruye una trayectoria — con
poder identificante muy superior al de cualquiera de sus puntos por separado.
La diferencia entre el segundo y el tercer tipo de dato no es algorítmica sino
de política de persistencia.

El cuarto es el **dato biométrico**: el art. 2.5 define como sensibles los
"datos biométricos que por sí mismos pueden identificar al titular" (entre
otras categorías). La fórmula es restrictiva: no todo rasgo corporal medido
es dato sensible, sino el que por sí mismo permite identificar. Una plantilla
facial cumple esa condición; un mapa de densidad y un conjunto de coordenadas
de cabezas, no. De esta taxonomía se sigue un matiz que suele pasarse por
alto: que la salida del modelo no sea biométrica no significa que la entrada
no lo sea.

**Discrepancia terminológica.** El material del equipo describe como
"personas anonimizadas" el resultado de un procesamiento que asigna a cada
persona un identificador persistente con el que se reconstruyen trayectorias.
El art. 2.12 define la anonimización como procedimiento *irreversible*; el
art. 2.13 define la disociación en términos casi idénticos pero *reversible*.
Un identificador persistente que permite reagrupar apariciones de un mismo
individuo no impide la identificación de forma irreversible: es disociación
(la figura que el régimen europeo llama seudonimización), y el dato disociado
**sigue siendo dato personal** sujeto al régimen general.

La discrepancia no se limita al material de presentación. El módulo de
persistencia del prototipo describe lo que almacena como "solo posiciones,
zonas, timestamps y el id temporal no reversible", y su esquema define ese
identificador como clave primaria de una tabla de personas a la que se enlaza
el historial completo de posiciones. Un identificador así permite reagrupar
las apariciones de una misma persona y reconstruir su recorrido: el
procedimiento es reversible, y por tanto disociación (art. 2.13), no
anonimización (art. 2.12). Este informe no corrige la terminología del equipo
por su cuenta; deja registrada la discrepancia —ahora en sus dos soportes, la
presentación y el código— y la eleva como punto abierto.

### 3.3 Base de legitimación y finalidad declarada

El art. 5 enuncia el principio de consentimiento, y el art. 13.5 precisa que
debe ser "previo, informado, expreso e inequívoco". Ese estándar es
materialmente inalcanzable en un terminal: el pasajero no elige ser
observado, no puede negociar las condiciones y, en la práctica, tampoco puede
optar por un terminal sin cámaras.

La ley prevé la salida: el art. 14 enumera los supuestos en que no se
requiere consentimiento, y la Directiva (num. 6.3) reconoce como bases del
tratamiento el consentimiento, la autorización por ley o alguno de esos
supuestos — con más frecuencia el numeral 9, "salvaguardar intereses
legítimos del titular de datos personales". Qué base invoca LAP es
información que solo el cliente puede aportar, y sin ella el cartel del
Anexo A no puede completarse.

Sobre la finalidad, la norma no deja margen: el art. 6 exige una finalidad
"determinada, explícita y lícita", que no se extienda a otra "no establecida
de manera inequívoca... al momento de su recopilación"; el art. 28.4 lo
repite.

**Discrepancia.** El informe describe, entre las aplicaciones posibles del
seguimiento multicámara, la medición de la permanencia de personas en zonas
comerciales, vinculada a un interés comercial del cliente. Medir permanencia
comercial no es una variante de estimar aglomeraciones: es una finalidad
distinta, que requeriría su propia declaración, base de legitimación y deber
de información (arts. 6, 28.4). Este informe deja la cuestión planteada sin
resolverla, pero advierte que presentar ambas finalidades como una sola sería
precisamente el deslizamiento que el artículo 6 prohíbe.

### 3.4 Principio de proporcionalidad y granularidad de salida

Consagrado en el art. 7 ("todo tratamiento debe ser adecuado, relevante y no
excesivo a la finalidad") y reiterado en la Directiva (num. 6.4). Es el
argumento más sólido a favor del enfoque del proyecto.

La estimación automática de densidad es idónea porque detecta aglomeraciones
que la observación humana de decenas de monitores no advierte a tiempo. En
necesidad: si la finalidad es estimar aglomeraciones, el medio menos invasivo
es un sistema de conteos agregados sin identificar personas; uno con
reconocimiento facial sería más invasivo sin lograr más. La proporcionalidad
en sentido estricto exige ponderar beneficio contra injerencia, y esa
ponderación requiere evidencia sobre la magnitud real del problema que solo
LAP puede aportar — mientras no la aporte, el examen se sostiene sobre una
premisa no acreditada.

De este principio depende la granularidad de salida, la decisión de mayor
consecuencia normativa: el mapa de densidad (CSRNet) es la opción que menos
datos trata; la agregación por zona produce el mismo resultado operativo con
cualquier método; la localización individual (P2PNet, P2R) entrega más
información de la que la finalidad requiere, y su licitud depende de que esas
coordenadas no se persistan ni se encadenen — garantía de política, no de
arquitectura. A igualdad de utilidad operativa, la opción menos granular es la
que supera el examen de necesidad. La elección del frente técnico no consta
por escrito al cerrar esta versión.

### 3.5 Privacidad desde el diseño y por defecto

El D.S. 016-2024-JUS la establece como exigencia, no como buena práctica
opcional: privacidad *por diseño* (garantías incorporadas desde la
concepción) y *por defecto* (la configuración más protectora activada de
fábrica). *[VERIFICAR: artículo concreto del D.S. 016-2024-JUS que consagra
ambos principios.]*

El proyecto incorpora diez medidas: **M-01** procesamiento en el borde (el
fotograma no sale del perímetro); **M-02** no persistencia del fotograma;
**M-03** salida agregada por zona, sin coordenadas individuales persistidas;
**M-04** difuminado irreversible de rostros si algún fotograma debe
conservarse; **M-05** plazo de retención definido con purga automática;
**M-06** control de acceso por roles con auditoría; **M-07** cifrado en
tránsito y en reposo; **M-08** carteles informativos (Anexo A); **M-09**
documentación del linaje de datos; **M-10** supervisión humana (el sistema
alerta, no ejecuta acciones automáticas).

M-02 es la de mayor impacto sobre el perfil de riesgo y también la más
restrictiva para el equipo técnico, que sin fotogramas conservados no tiene
material propio para reentrenar. Cuál versión proponer a LAP (estricta, o
atenuada con retención corta y difuminado) queda abierto.

**Estas diez medidas son requisitos, no una descripción del sistema actual.
Al cerrar esta versión, M-03 no se cumple en el prototipo incorporado al
repositorio**, que persiste coordenadas individuales asociadas a un
identificador por persona; el contraste se desarrolla en 3.9. M-02, en
cambio, sí se respeta.

### 3.6 Plazos de retención y supresión

El principio de calidad (art. 8) ordena conservar los datos "solo por el
tiempo necesario"; el art. 28.7 obliga a suprimirlos cuando dejen de ser
necesarios. Para videovigilancia, la Directiva (num. 6.13 y 7.18) fija la
conservación de imágenes en un rango de 30 a 60 días como máximo.

**Tensión normativa.** El art. 17.2 del D.S. 007-2020-IN obliga a almacenar
imágenes por un plazo *mínimo* de 45 días calendario; su art. 17.1 impone
entregarlas a la PNP o al Ministerio Público en máximo 24 horas ante sospecha
de delito. El régimen de protección de datos empuja a conservar lo mínimo y
fija un techo de 60 días; el de seguridad ciudadana fija un piso de 45. Ambos
son compatibles solo dentro de una ventana estrecha, y únicamente porque
recaen sobre finalidades distintas.

La consecuencia de diseño: tratar el sistema de estimación de aglomeraciones
como un subsistema separado del CCTV de seguridad, con su propia finalidad,
base de legitimación y plazo de retención. Bajo M-02 y M-03, el subsistema de
conteo no almacena imágenes, de modo que la obligación del art. 17.2 recaería
sobre el CCTV preexistente de LAP y no sobre lo que el proyecto añade.

### 3.7 Derechos de los titulares e información al público

El Título III reconoce: derecho de información (art. 18, "en forma
detallada, sencilla, expresa, inequívoca y de manera previa"), acceso (art.
19), actualización/inclusión/rectificación/supresión (art. 20), impedir el
suministro (art. 21), oposición (art. 22), tutela (art. 24), indemnización
(art. 25).

El art. 23 consagra el derecho al tratamiento objetivo — a no verse sometido
a una decisión con efectos significativos sustentada únicamente en un
tratamiento automatizado. Es el fundamento de M-10: mientras el sistema se
limite a alertas agregadas que un operador humano interpreta, no se activa;
si sus salidas alimentaran una medida automática sobre un pasajero concreto,
sí lo haría.

El deber de información se cumple mediante señalética: la Directiva (num.
6.11) fija el contenido mínimo del cartel y una dimensión de 297×210 mm; el
Anexo A propone un modelo. Varios de sus campos —razón social, base de
legitimación, canal de atención, plazo de conservación— solo LAP puede
completarlos.

### 3.8 Encargados de tratamiento y flujos hacia terceros

El art. 2.6 define al encargado del banco de datos; cualquier proveedor que
trate datos por cuenta de LAP (etiquetado, MLOps, almacenamiento, inferencia)
queda sujeto al art. 30. El flujo transfronterizo (art. 2.8, art. 15) solo se
permite si el país destinatario mantiene niveles de protección adecuados. El
D.S. 016-2024-JUS contempla además un alcance extraterritorial. *[VERIFICAR:
artículo que fija ese alcance y sus criterios de conexión.]*

Tres consecuencias: si el entrenamiento o la inferencia se ejecutan en nube
fuera del Perú, hay flujo transfronterizo a analizar; usar un modelo
preentrenado descargado no constituye transferencia (no se exportan datos),
pero enviar fotogramas del terminal a una interfaz externa sí; y el servidor
externo de evaluación de NWPU-Crowd implica envío a un tercero fuera del Perú
—acotado en fase académica, pero no si se remitiera material del terminal.

**La decisión entre inferencia *on-premise* y en nube externa es, a juicio de
este frente, la de mayor impacto legal del proyecto.** No consta por escrito
al cerrar esta versión; M-01 la anticipa en el sentido más protector sin que
ello equivalga a que esté tomada.

### 3.9 Auditoría: ¿el sistema trata datos biométricos?

La auditoría se formula de manera condicional sobre los enfoques de la
Sección 2 porque la elección de arquitectura no consta todavía por escrito,
pero **sí consta en código**: el frente técnico incorporó al repositorio un
prototipo de detección, seguimiento y fusión entre cámaras.

Bajo CSRNet, ninguna etapa construye plantilla biométrica; la salida es
agregada por construcción. Bajo P2PNet o P2R, tampoco se construyen
plantillas faciales, pero la conformidad queda condicionada a la política de
persistencia. Bajo seguimiento multicámara con reidentificación por
apariencia, la calificación cambia de naturaleza: un vector de apariencia
construido para reconocer a un individuo en otra cámara es una característica
extraída del cuerpo cuyo propósito es individualizarlo, y en ninguna lectura
posible (dato sensible, o dato personal reconstruyendo trayectorias) el
resultado es neutro.

**Contraste contra lo que el prototipo implementa realmente:**

**Sobre reidentificación por apariencia, la preocupación no se confirma.** El
material de presentación contemplaba *embeddings* de apariencia, lo que
habría chocado con RNF-01. El prototipo no hace eso: la fusión entre cámaras
se resuelve como asociación espacio-temporal sobre un plano común, capa
obligatoria; solo ante ambigüedad interviene un descriptor de desempate
(histograma de color del torso + proporción alto/ancho), no biométrico, nunca
identificador único, no persistido. Va en la dirección que RNF-01 exige.
*[VERIFICAR: texto literal del RNF-01; no figura en el repositorio.]*

**Sobre lo que se persiste, aparece un hallazgo no conforme que no estaba
previsto.** El esquema de base de datos del prototipo almacena una tabla de
personas y una tabla de posiciones (identificador, cámara, coordenadas,
instante, zona) por cada detección, escrita en disco, no procesada en
memoria. **La medida M-03 no se cumple en la implementación actual.** M-02 sí
se respeta. El comentario del propio módulo de persistencia describe lo
almacenado como "el id temporal no reversible" — calificación que reproduce
la discrepancia de 3.2: es reversible por construcción (clave primaria de un
historial completo), y por tanto disociación, no anonimización.

**Cuatro hallazgos no conformes resultan del contraste:** (1) ausencia de
Evaluación de Impacto en Protección de Datos, exigible antes de tratamientos
de alto riesgo — el más grave formalmente, el más fácil de subsanar porque el
material sustantivo ya está en la Sección 4; (2) incumplimiento de M-03 —
**defecto de implementación, no ausencia de evidencia**, subsanable por el
propio equipo sin depender de terceros; (3) ausencia de validación de
exactitud en el dominio de destino; (4) ausencia de evaluación de sesgo
demográfico. Los dos últimos requieren acceso a material del terminal.

---

## 4. Análisis de impacto y privacidad desde el diseño

*(Sección sin renumerar — ver nota editorial. Contenido íntegro de
`secciones/04_analisis_impacto.md`, responsable Fabián Moreno Ugarte.)*

### 4.1 Metodología del análisis de impacto

Esta sección reproduce deliberadamente la estructura de una Evaluación de
Impacto en Protección de Datos: identificar el tratamiento, valorar su
necesidad y proporcionalidad, identificar riesgos para los titulares y
proponer mitigaciones. No es una analogía metodológica: el D.S. 016-2024-JUS
exige esa evaluación antes de tratamientos de alto riesgo, y la videovigilancia
masiva figura expresamente entre los supuestos que la activan.

Conviene descartar una tentación previsible: argumentar que, como la salida
es agregada y no hay reconocimiento facial, el sistema no alcanza el umbral de
alto riesgo. El supuesto que se activa es el de captación masiva, que existe
con independencia de lo que el modelo haga después.

Un criterio gobierna todo lo que sigue: se prefiere declarar un impacto como
no cuantificado antes que estimarlo sin base.

### 4.2 Sesgos del sistema

**Brecha de dominio.** La limitación mejor documentada y la más grave para
esta fase. Los autores de P2R [Lin_2025_CVPR] reconocen que el desempeño se
degrada de forma marcada sin adaptación de dominio, y documentan un modo de
fallo por sobreestimación severa. Esta primera entrega se desarrolla sobre
conjuntos públicos, sin acceso a material del Aeropuerto Jorge Chávez, de
modo que ninguna cifra reportada debe leerse como predicción de exactitud
para el terminal.

**Sesgo demográfico.** Ningún trabajo revisado reporta desempeño desagregado
por características demográficas — ausencia en la literatura, no omisión de
este informe. Factores identificables aunque no cuantificados: estatura
(subconteo de niños ocluidos), vestimenta y cubrimientos de cabeza (alteran la
señal de la región de cabeza), equipaje voluminoso y sillas de ruedas
(siluetas distintas), y composición demográfica de los conjuntos de origen
sin garantía de neutralidad.

**Sesgo de anotación.** El menos visible, el que los autores sí documentan.
P2PNet [Song_2021_ICCV] señala que nAP con umbral 0,05 cae por desviaciones de
etiquetado. CSRNet [Li_2018_CVPR] construye su referencia con un supuesto
sobre distancia-a-cámara/tamaño-de-cabeza que se sesga con perspectivas
oblicuas y cámaras de gran angular — habituales en un terminal.

El sistema no toma decisiones sobre personas individuales, pero si el
subconteo se concentra en un grupo, las zonas donde ese grupo se concentra
reciben sistemáticamente menos recursos: el daño es distributivo, no
individual, y real aunque indirecto. Recomendación: que la validación en
sitio incluya evaluación desagregada por franja de estatura y presencia de
equipaje voluminoso — condicional al acceso a material del terminal.

### 4.3 Sesgo de automatización y factor humano

Riesgo de sustitución progresiva del criterio humano por el del sistema: un
fallo en momento crítico produce un efecto peor que su ausencia, porque la
atención humana ya se retiró. Anclaje normativo: art. 23 (tratamiento
objetivo); M-10 responde a esa exigencia pero es insuficiente por sí sola —
un operador que aprueba mecánicamente reintroduce de hecho la decisión
automatizada.

La capacitación del personal debe tratarse como medida de mitigación: los
operadores necesitan conocer que el desempeño sobre datos públicos no predice
el desempeño en el terminal, que existe un modo de fallo por sobreestimación
severa, y que el régimen de baja densidad no es donde estos métodos rinden
mejor.

Sobre el efecto conductual de saberse observado, este informe no puede
afirmarlo como hecho acreditado por falta de literatura incorporada — se deja
en condicional.

### 4.4 Lectura ambiental del costo de cómputo

El equipo no ha medido el consumo energético, de modo que este apartado es
cualitativo y estructural. Tres decisiones ya adoptadas o previstas: reutilizar
modelos preentrenados (CSRNet parte de VGG-16 ya entrenada); la eficiencia de
etiquetado de P2R (reduce esfuerzo humano, no necesariamente cómputo, porque
el esquema maestro-estudiante mantiene dos modelos); y la eliminación del
algoritmo húngaro en P2R, que los autores cuantifican: 0,4307 s frente a
0,0064 s por imagen —68 veces más rápido—, aunque esa cifra mide una
operación por iteración, no el consumo total del ciclo.

A escala de vida útil, la inferencia continua supera previsiblemente al
entrenamiento. Dos decisiones convergen en reducirla: frecuencia de muestreo
baja (las aglomeraciones se forman en minutos) y procesamiento en el borde
(M-01, evita transmisión continua a la nube). Resultado más útil de esta
subsección: las decisiones que reducen exposición de datos personales
—muestrear menos, procesar localmente, no persistir imágenes, agregar la
salida— son las mismas que reducen cómputo, transmisión y almacenamiento.

Dos puntos abiertos: registrar las horas de GPU desde el inicio del
entrenamiento (no reconstruible a posteriori), y confirmar con LAP si existe
política de sostenibilidad institucional.

### 4.5 Riesgos residuales y decisiones pendientes

Síntesis en cuatro dimensiones: **ética** (alternativa menos invasiva que
biometría; riesgo de deslizamiento hacia identificación, mitigable con
declaración de finalidades excluidas y M-02/M-03); **social** (prevención de
incidentes y asignación de recursos basada en evidencia; riesgo de
distribución desigual de beneficio/carga y exceso de confianza); **económica**
(eficiencia operativa; riesgo del costo de reconstruir el sistema si se
detecta no conformidad después del despliegue); **ambiental** (huella menor
que alternativas de mayor granularidad; riesgo del consumo acumulado de
inferencia continua).

Tres conclusiones transversales: las decisiones de minimización operan en las
cuatro dimensiones a la vez; el riesgo dominante es de gobernanza y no de
tecnología (se previene con documentación y auditoría, no con mejor
ingeniería); y varios impactos permanecen sin cuantificar por falta de
información, declarado como tal.

El riesgo de deslizamiento de finalidad merece desarrollo propio: una vez
desplegada la infraestructura, el costo marginal de añadir reidentificación o
reconocimiento facial es bajo — decisión de configuración, no de rediseño. La
mitigación propuesta es una declaración de finalidades excluidas: el sistema
no realiza identificación de personas, no realiza seguimiento individual de
trayectorias, no realiza reconocimiento de emociones, no alimenta decisiones
automatizadas sobre pasajeros individuales, e incluye la exclusión del uso
laboral de los datos.

Los riesgos residuales son de tres clases: ausencias de evidencia subsanables
con acceso al terminal (validación de exactitud, sesgo demográfico);
decisiones del equipo abiertas (arquitectura y granularidad, localización del
procesamiento, plazo de retención, horas de GPU); y discrepancias entre
documentos del propio proyecto, registradas y no resueltas por este frente
(terminología de anonimización, permanencia en zona comercial como finalidad
distinta). La preocupación sobre reidentificación por *embeddings* **no se
confirmó**. **La medida M-03 no se cumple en la implementación actual — el
único hallazgo que el equipo puede cerrar por sí solo, sin depender de LAP,
y por eso debería encabezar la lista de acciones.**

---

## 5. Especificación de Requerimientos

Esta sección describe el prototipo tal como está implementado en
`proyecto_lap_prototipo/` (backend `live_server.py` + consola web
**AeroTrack**), no una versión aspiracional ni la arquitectura definitiva que
pide B-01. Es evidencia de ingeniería complementaria a la Sección 2, previa a
que Metodología (Sección 9) cierre la arquitectura que finalmente se adopte.

### 5.1 Casos de uso del sistema

**CU-01 — Configurar el plano y las cámaras.**
*Actor:* Operador. *Precondición:* servidor local en ejecución.
*Flujo:* el operador crea un plano en blanco o importa una imagen, PDF o DXF;
si es imagen o PDF, recorta la región útil y el sistema la reduce a un dibujo
esquemático de líneas por detección de bordes en vez de conservar la
fotografía completa; coloca cada cámara sobre el plano y define su alcance
orientativo (cono o rectángulo); declara qué cámaras son vecinas entre sí.
*Postcondición:* el plano queda disponible para calibración.

**CU-02 — Calibrar una cámara.**
*Precondición:* fuente de video válida.
*Flujo:* el operador marca un punto de referencia del suelo en el video y su
correspondencia en el plano, un mínimo de cuatro veces (seis a ocho
recomendadas); el sistema calcula la homografía y rechaza la calibración si
las correspondencias son geométricamente inconsistentes.
*Postcondición:* la cámara queda habilitada para proyectar posiciones al
plano compartido.

**CU-03 — Procesar una fuente y hacer seguimiento.**
*Flujo:* el operador elige un detector (HOG de referencia, P2PNet, o YOLO con
pesos locales que debe aportar él mismo) e inicia la sesión; el sistema
detecta personas por cuadro y asigna un identificador local estable dentro de
esa cámara mediante seguimiento por distancia euclidiana y asignación
húngara en dos etapas (adaptación de ByteTrack [Zhang_2022_ECCV] a puntos en
vez de cajas).
*Excepción documentada:* con P2PNet, la posición no se proyecta al plano — el
detector localiza cabezas, no pies, y esta integración no aproxima una a la
otra sin validar el error que eso introduciría —, de modo que ese modo solo
sirve para validar detección y seguimiento por cámara, no el plano completo.

**CU-04 — Asociar identidad entre cámaras.**
*Precondición:* al menos dos cámaras calibradas y vecinas; el operador
declaró explícitamente que verificó la sincronización de reloj entre
fuentes.
*Flujo:* ante una observación nueva, el sistema busca entre las personas
activas de una cámara vecina alguna cuya posición proyectada, ajustada por
velocidad si no hay solape temporal, quede dentro de un margen de distancia y
tiempo configurables; si hay un candidato inequívoco reutiliza su
identificador y lo marca "estimado"; si hay varios candidatos próximos,
desempata por un descriptor no biométrico de apariencia; si ninguno es
suficientemente inequívoco, lo marca "incierto" en vez de forzar una fusión.
*Nota de cumplimiento:* esta es la lógica que la auditoría de §3.9 revisó y
consideró alineada con RNF-01 (hallazgo D-01).

**CU-05 — Detectar y alertar aglomeraciones.**
El operador define, por zona o globalmente, un radio, una cantidad mínima de
personas y un tiempo de permanencia; el sistema marca una alerta cuando una
concentración cumple los tres criterios de forma sostenida.

**CU-06 — Visualizar el plano en vivo y el video por cámara.**
El operador ve el plano con nodos, trayectorias recientes y aglomeraciones
resaltadas, y puede alternar a ver el video real de una cámara con las cajas
y el identificador de cada persona superpuestos.

**CU-07 — Exportar reportes.**
El sistema exporta, en PDF, Excel, CSV o JSON, ocupación por zona, evolución
temporal y trayectorias de la sesión activa, señalando siempre si el origen
es una fuente real o la demostración sintética.

### 5.2 Requisitos funcionales y no funcionales

| ID | Requisito | Estado verificado en el prototipo |
|---|---|---|
| RF-01 | Configurar plano y cámaras, con recorte e importación como dibujo de líneas | Implementado |
| RF-02 | Calibrar por homografía con validación de consistencia geométrica | Implementado |
| RF-03 | Detectar y seguir personas con detector seleccionable (HOG, P2PNet, YOLO) | Implementado; YOLO requiere pesos locales no incluidos |
| RF-04 | Asociar identidad entre cámaras solo con sincronización declarada, con estado "incierta" cuando corresponda | Implementado (ver D-01) |
| RF-05 | Reglas de aglomeración configurables por radio, cantidad y permanencia | Implementado |
| RF-06 | Visualizar plano en vivo y video real por cámara con overlay de ID | Implementado |
| RF-07 | Exportar reportes en PDF/Excel/CSV/JSON | Implementado |
| RNF-01 | No derivar del video ningún rasgo que permita identificación biométrica o reidentificación individual persistente | **Parcialmente no conforme**: la fusión no usa biometría (D-01, favorable); la persistencia de posiciones individuales no satisface M-03 (D-05, no conforme) |
| RNF-02 | Servidor accesible solo desde 127.0.0.1, con token de sesión en escritura | Implementado |
| RNF-03 | No persistir imágenes de forma permanente | Cumplido (M-02) |
| RNF-04 | Declarar explícitamente cuándo el sistema opera en modo demostración sintética | Implementado |
| RNF-05 | Ninguna cifra de desempeño sobre datos públicos ni sobre grabaciones propias se presenta como desempeño esperado en el Aeropuerto Jorge Chávez sin validación en sitio | Ver §2.3-2.4, §4.5 |
| RNF-06 | Tiempo de inferencia compatible con operación práctica | **No verificado como cumplido**: P2PNet en CPU, sin GPU, procesó del orden de 3,5 s por cada 0,2 s de video de fuente en la prueba registrada |

---

## 6. Diseño del Sistema

**Nota de encaje:** esta sección describe la arquitectura *del prototipo*, no
la arquitectura definitiva que pide B-01. El responsable de Metodología (§9)
debe decidir si la adopta, la ajusta o documenta una distinta.

### 6.1 Arquitectura conceptual

Seis componentes, cada uno con responsabilidad única:

1. **Adquisición** — lectura de cada fuente de cámara (archivo, USB o RTSP).
2. **Detección** — un detector intercambiable (HOG, P2PNet o YOLO) produce
   posiciones en píxeles con confianza asociada; la elección es explícita del
   operador, no automática, porque ninguno de los tres es adecuado para
   todos los casos.
3. **Seguimiento mono-cámara** — adaptación de ByteTrack [Zhang_2022_ECCV] a
   puntos, con filtro de Kalman de velocidad constante y asignación húngara
   en dos etapas por confianza.
4. **Calibración y proyección** — homografía por cámara, validada por
   consistencia geométrica antes de aceptarse.
5. **Fusión entre cámaras** — asociación de identidad por proximidad
   espacio-temporal en el plano compartido, con descriptor de apariencia no
   biométrico como desempate de última instancia.
6. **Persistencia, analítica y presentación** — estado de sesión agregado en
   memoria y expuesto por la consola AeroTrack (configuración, plano en
   vivo, video por cámara, reportes).

### 6.2 Algoritmo — Fusión de identidad entre cámaras (núcleo de CU-04/RF-04)

```
Entrada: observación nueva (cámara, punto_plano, tiempo, color_torso),
         personas activas de cámaras vecinas, ventana_tiempo, radio_asociación
Salida: identificador_global, estado_asociación ("local"|"estimada"|"incierta")

candidatos <- [ ]
para cada persona activa P vista por una cámara vecina:
    si P fue vista fuera de la ventana_tiempo: continuar
    si la cámara actual y la de P se solapan en el mismo instante:
        distancia <- distancia_euclidiana(punto_plano, P.punto)
    si no:
        punto_esperado <- P.punto + P.velocidad * tiempo_transcurrido
        distancia <- distancia_euclidiana(punto_plano, punto_esperado)
    si distancia <= radio_asociación:
        candidatos.agregar(P, distancia, similitud_color(color_torso, P.color))

si candidatos está vacío:
    crear identificador_global nuevo
en otro caso si hay un candidato claramente mejor que el resto:
    reutilizar su identificador_global; estado <- "estimada"
en otro caso:
    estado <- "incierta"; crear identificador_global nuevo
```

Prioriza declarar incertidumbre sobre forzar una fusión — la misma lectura
que la auditoría de §3.9 hace de esta lógica frente a RNF-01.

### 6.3 Justificación del diseño

La separación entre "cuántas personas hay" (aglomeración, disponible incluso
sin calibración) y "quién es quién entre cámaras" (identidad, que exige
calibración y sincronización declarada) es consistente con §2.4: la
granularidad de la salida condiciona el examen de proporcionalidad, y el
diseño evita comprometerse con la granularidad más invasiva por defecto.
Excluir a P2PNet de la proyección al suelo (CU-03) va en la misma dirección:
prefiere no ocultar un error geométrico no cuantificado detrás de una cifra
de exactitud, en línea con la recomendación de §2.3.

---

## 7. Planificación y Gestión del Proyecto

### 7.1 Roles y responsabilidades

| Integrante | Frente | Responsabilidad en el informe |
|---|---|---|
| Angel Aguilar | Liderazgo e integración | Coordinación general; consolidación de secciones; co-responsable de ampliar Antecedentes; responsable de la integración `.md` → `.docx` |
| Stephano Rivadeneyra | Ciencia de datos | Metodología (§9, esqueleto); aportó referencias de seguimiento multicámara aún no citadas en el cuerpo; co-responsable de ampliar Antecedentes |
| José Ortega | Ingeniería de datos | Resultados (§10, esqueleto); verificación de licencias de datasets |
| Fabián Moreno Ugarte | Validación ética/legal y documentación | Antecedentes, Marco normativo, Análisis de impacto, Anexo A; mantenimiento del repositorio del informe |

Conclusiones (§11) figura como "a cargo de otro integrante" sin nombre
asignado en `README.md` — *[PENDIENTE: confirmar responsable]*.

### 7.2 Cronograma

*[PENDIENTE — no se completa con fechas de ejemplo.]* El ciclo académico y la
fecha de entrega de la portada están sin confirmar contra el sílabo del
curso (A-10). Un cronograma con fechas inventadas incurriría en el mismo
problema que el resto del informe evita deliberadamente.

### 7.3 Gestión de riesgos

| Riesgo | Evidencia | Mitigación propuesta |
|---|---|---|
| Tres evidencias distintas (datos públicos, grabaciones propias, datos del terminal) usadas para un mismo argumento sin distinguirse por escrito | §1.3 vs. §5 de este documento | Decidir con el equipo si se declara expresamente en el informe |
| M-03 no se cumple en el prototipo (persistencia de coordenadas individuales) | §3.5, §3.9 (D-05) | Agregar por zona antes de persistir, o fijar retención corta — corregible sin depender de LAP |
| Arquitectura definitiva sin cerrar (B-01), lo que mantiene condicional la auditoría de §3.9 | `PENDIENTES.md` B-01 | Cerrar la decisión por escrito, con la Sección 6 como insumo, no como decisión ya tomada |
| Rendimiento de P2PNet en CPU incompatible con operación casi en tiempo real | Medición registrada: ~3,5 s de cómputo por cada 0,2 s de video, sin GPU | Evaluar GPU dedicada, o ajustar la frecuencia de muestreo (§4.4) |
| Acceso a material del Aeropuerto Jorge Chávez sin confirmar | `PENDIENTES.md` C-14, A-11 | Cursar la solicitud formal a LAP |

---

## 8. Nota sobre el estado de las Secciones 9 a 11

Las tres secciones que siguen están **en esqueleto**, a cargo de otros
integrantes del equipo. Se reproducen a continuación exactamente como están
en `informe/secciones/`, sin completar su contenido por cuenta de esta
consolidación — inventarlo aquí sería precisamente el tipo de relleno que el
resto del informe evita.

## 9. Metodología

> **Sección en elaboración.** El contenido de esta sección está a cargo de
> otro integrante del equipo. El frente ético-legal la audita (§3.9). Dos
> decisiones que se documenten aquí condicionan directamente esa auditoría
> —la arquitectura elegida y el lugar donde se ejecuta la inferencia—, por lo
> que conviene que se fijen por escrito antes de cerrarla.

### 9.1 Arquitectura propuesta

Este apartado documentará la arquitectura del sistema de visión
computacional. La Sección 2.4 deja planteada la elección entre los tres
enfoques revisados y, sobre todo, la granularidad de la salida.

### 9.2 Datos y entrenamiento

Este apartado documentará los conjuntos de datos utilizados, la estrategia de
entrenamiento y la de adaptación de dominio. La verificación de licencias se
sigue en `CHECKLIST_CUMPLIMIENTO.md`, sección B.

### 9.3 Métricas de evaluación

Este apartado justificará las métricas seleccionadas — MAE, MSE, nAP u otras.
La Sección 2.2 señala una restricción a tener presente: los compromisos de
exactitud deben formularse a nivel de zona agregada y no de posición
individual.

## 10. Resultados

> **Sección en elaboración.** El contenido de esta sección está a cargo de
> otro integrante del equipo. Regla de redacción aplicable a todo lo que se
> incorpore: cada cifra debe indicar expresamente sobre qué datos fue
> medida (§2.3).

### 10.1 Resultados cuantitativos

Este apartado recogerá las tablas de error de conteo y de desempeño de
localización.

### 10.2 Análisis cualitativo

Este apartado recogerá casos de éxito y de fallo del modelo. Los casos de
fallo alimentan además la capacitación de operadores de §4.3.

## 11. Conclusiones y trabajo futuro

> **Sección en elaboración.** Los insumos ya disponibles son la síntesis de
> antecedentes (§2.4) y la síntesis del análisis de impacto (§4.5).

Este apartado recogerá las conclusiones del proyecto y las líneas de trabajo
futuro. Dos resultados de la auditoría de §3.9 deben reflejarse aquí sin
atenuarlos: la exactitud del sistema no está validada en el dominio de
destino y el desempeño desagregado por características demográficas no ha
sido evaluado. Ambos son subsanables dentro del proyecto, pero requieren
acceso a material del terminal.

---

## Referencias

*Citadas en el cuerpo del informe (Secciones 2, 3, 4):*

1. Li, Y., Zhang, X., Chen, D. (2018). *CSRNet: Dilated Convolutional Neural
   Networks for Understanding the Highly Congested Scenes*. CVPR, 1091–1100.
2. Song, Q., Wang, C., Jiang, Z., Wang, Y., Tai, Y., Wang, C., Li, J., Huang,
   F., Wu, Y. (2021). *Rethinking Counting and Localization in Crowds: A
   Purely Point-Based Framework*. ICCV, 3365–3374.
3. Lin, W., Zhao, C., Chan, A. B. (2025). *Point-to-Region Loss for
   Semi-Supervised Point-Based Crowd Counting*. CVPR, 29363–29373.

*En `referencias.bib` pero no citadas todavía en el cuerpo del informe*
(seguimiento multicámara, aportadas para ampliar Antecedentes — E-03/E-09 de
`PENDIENTES.md`; no se citan aquí hasta que el equipo decida incorporarlas):

- Zhang, Y., Sun, P., Jiang, Y., Yu, D., Weng, F., Yuan, Z., Luo, P., Liu, W.,
  Wang, X. (2022). *ByteTrack: Multi-Object Tracking by Associating Every
  Detection Box*. ECCV. *(Base del seguimiento mono-cámara del prototipo,
  Sección 6.1 — citada en Diseño del Sistema como referencia técnica, no
  como antecedente formal de la Sección 2.)*
- Gao, R., Wang, L. (2023). *MeMOTR: Long-Term Memory-Augmented Transformer
  for Multi-Object Tracking*. ICCV, 9901–9910.
- Liu, C., Lu, H., Cao, Z., Liu, T. (2023). *Point-Query Quadtree for Crowd
  Counting, Localization, and More*. ICCV, 1676–1685.
- Zhang, Y., Wang, T., Zhang, X. (2023). *MOTRv2: Bootstrapping End-to-End
  Multi-Object Tracking by Pretrained Object Detectors*. CVPR, 22056–22065.
- Qin, Z., Wang, L., Zhou, S., Fu, P., Hua, G., Tang, W. (2024). *Towards
  Generalizable Multi-Object Tracking*. CVPR, 18995–19004.
- Huang, H.-W. et al. (2023). *Enhancing Multi-Camera People Tracking With
  Anchor-Guided Clustering and Spatio-Temporal Consistency ID
  Re-Assignment*. CVPR Workshops, 5239–5249.
- Wang, Y. et al. (2025). *MCBLT: Multi-Camera Multi-Object 3D Tracking in
  Long Videos*. ICCV Workshops, 5304–5313.

*Normativa citada en prosa (no en `referencias.bib`, por regla del `README`
del informe — trazabilidad completa en `NOTAS_FUENTES.md`):* Constitución
Política del Perú (1993), art. 2; Ley 29733, Ley de Protección de Datos
Personales; D.S. 016-2024-JUS; D.S. 003-2013-JUS (derogado); Directiva
01-2020-JUS/DGTAIPD; D.L. 1218; Ley 30120; D.S. 007-2020-IN.

---

## Anexo A — Modelo de cartel informativo de videovigilancia

*(Contenido íntegro de `secciones/anexo_cartel.tex`, responsable Fabián
Moreno Ugarte.)*

### A.1 Propósito y estatus de este modelo

La Sección 3.7 estableció que el tratamiento de datos personales mediante
videovigilancia exige informar previamente a los titulares mediante carteles
visibles. Este anexo propone un modelo concreto para el sistema del proyecto.

> **Estatus de este modelo.** Se trata de una **propuesta de trabajo**, no de
> un formato aprobado. Está construido sobre los elementos informativos que
> la Directiva 01-2020-JUS/DGTAIPD exige, pero su redacción final debe ser
> revisada por el área legal de LAP antes de su colocación física. Este
> informe propone el conjunto de campos, no acredita que sea el exigible.

### A.2 Elementos que el modelo incorpora

| Elemento | Razón de su inclusión |
|---|---|
| Identidad del responsable | El titular debe saber ante quién ejercer sus derechos |
| Finalidad del tratamiento | Núcleo del deber de información y límite frente al deslizamiento de finalidad (§4.5) |
| Base de legitimación | Permite entender por qué no se pidió consentimiento |
| Plazo de conservación | Exigencia del principio de conservación limitada |
| Destinatarios | Incluye la eventual entrega a autoridades (§3.1) |
| Canal para ejercer derechos | Sin un canal indicado, el derecho es nominal |
| Declaración de lo que el sistema *no* hace | No exigido por la norma; decisión de este frente — es la traducción visible del compromiso contra el deslizamiento de finalidad |

### A.3 Modelo propuesto

> **ZONA VIDEOVIGILADA — SISTEMA DE ESTIMACIÓN DE AFORO**
> *Este sistema NO identifica personas*
>
> **Responsable:** Lima Airport Partners S.R.L. — *razón social registral
> completa, RUC y domicilio fiscal, a completar por LAP.*
>
> **Finalidad:** Estimar el número de personas presentes por zona, con el fin
> de prevenir aglomeraciones y gestionar el flujo de pasajeros en el
> terminal.
>
> **Base legal:** *Base de legitimación que LAP invoque, con su fundamento
> normativo exacto, a completar por su área legal.*
>
> **Conservación:** Las imágenes no se almacenan. El sistema conserva
> únicamente conteos agregados por zona, durante el plazo fijado en su
> política de retención — *plazo a definir con LAP (M-05).*
>
> **Destinatarios:** Personal autorizado de LAP. Las imágenes del sistema de
> seguridad podrán entregarse a las autoridades competentes cuando lo
> requieran conforme a ley.
>
> **Sus derechos:** Puede ejercer sus derechos de acceso, rectificación,
> cancelación y oposición escribiendo al canal de atención de LAP o
> acudiendo a su oficina de atención al usuario — *dirección de correo y
> ubicación de la oficina, a completar por LAP.*
>
> **Más información:** *Dirección web de la política de privacidad de LAP, a
> completar.*
>
> *Este sistema no realiza reconocimiento facial, no identifica a personas
> concretas, no realiza seguimiento individual de trayectorias y no adopta
> decisiones automatizadas sobre los pasajeros.*

### A.4 Criterios de colocación

1. **Anterioridad** — visible antes de ingresar a la zona videovigilada, no
   dentro de ella.
2. **Cobertura de todos los accesos** — cada acceso sin cartel es un punto de
   incumplimiento.
3. **Legibilidad** — tamaño y contraste suficientes para leerse a la
   distancia de aproximación real.
4. **Idiomas** — español e inglés como mínimo; idiomas adicionales según
   composición real del tráfico, dato a pedir a LAP.
5. **Accesibilidad** — altura y ubicación legibles desde una silla de ruedas.
   *[VERIFICAR: normativa peruana de accesibilidad aplicable, no contrastada.]*
6. **Registro de la colocación** — documentar fotográficamente cada cartel,
   con fecha y ubicación.

### A.5 Observación final sobre este anexo

Este cartel es el punto donde el análisis normativo se vuelve visible para el
pasajero. La frase "este sistema no identifica personas" solo es defendible
si las medidas M-02, M-03 y M-04 están efectivamente implementadas.

> **Advertencia.** Colocar un cartel que declare más de lo que el sistema
> cumple es peor que no colocarlo. La redacción final debe fijarse *después*
> de que la arquitectura esté congelada, y debe revisarse si la arquitectura
> cambia.
