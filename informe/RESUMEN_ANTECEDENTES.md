# Resumen de antecedentes

**Proyecto:** Estimación de aglomeraciones de personas mediante visión computacional en el Aeropuerto Internacional Jorge Chávez
**Cliente:** Lima Airport Partners (LAP)
**Capstone I — Universidad ESAN, Ingeniería de Inteligencia Artificial**

Este documento resume los tres artículos que sirven de antecedente al proyecto.
Para cada uno se indica qué propone, por qué resulta pertinente para el caso de
LAP y qué limitación reconocen sus propios autores.

Una advertencia sobre las cifras que aparecen aquí. Solo se reproducen las que
constan en el texto en prosa de cada artículo —resumen, introducción o
discusión de resultados—. Las que figuraban únicamente en las tablas de
resultados se omitieron: la conversión de esos cuadros a texto plano mezcla
filas y columnas, y una cifra mal atribuida a un conjunto de datos sería
exactamente el tipo de afirmación no verificable que este proyecto debe evitar.
Donde la comparación importa, se citan las magnitudes relativas que los propios
autores enuncian, que además es la forma en que ellos presentan sus
contribuciones.

---

## 1. CSRNet

**Título:** *CSRNet: Dilated Convolutional Neural Networks for Understanding the Highly Congested Scenes*
**Autores:** Yuhong Li, Xiaofan Zhang, Deming Chen
**Conferencia:** IEEE Conference on Computer Vision and Pattern Recognition (CVPR)
**Año:** 2018

### Qué propone

CSRNet es una red completamente convolucional para el análisis de escenas
congestionadas, construida en dos bloques. El primero, el *front-end*,
reutiliza las diez primeras capas convolucionales de VGG-16 para extraer
características de la imagen. El segundo, el *back-end*, emplea convoluciones
dilatadas, que amplían el campo receptivo de la red sin recurrir a capas de
reducción de resolución.

La motivación del diseño es explícita y polémica frente a lo que se hacía
entonces: los autores muestran que las tres columnas de MCNN —la arquitectura
multi-columna dominante hasta ese momento— aprenden características casi
idénticas, de modo que la ramificación añade redundancia y tiempo de
entrenamiento sin aportar la diversidad de escala que prometía.

La salida del modelo no es un número sino un mapa de densidad: una superficie
continua que indica cuánta concentración de personas hay en cada punto de la
imagen. El conteo se obtiene integrando esa superficie. El entrenamiento
compara ese mapa contra uno de referencia, generado difuminando cada cabeza
anotada con un núcleo gaussiano adaptado a la geometría de la escena.

En términos comparativos, los autores reportan un 7 % menos de error absoluto
medio que CP-CNN sobre la parte A del conjunto ShanghaiTech y un 47,3 % menos
sobre la parte B. Extienden además el método al conteo de vehículos, donde
reportan un 15,4 % menos de error que el mejor método previo.

### Por qué aplica al caso LAP

Tres propiedades del diseño son directamente relevantes para el terminal.

La primera, y la más importante desde el punto de vista del cumplimiento
normativo: **la salida es un mapa de densidad, no una identidad**. Ninguna
etapa del proceso extrae rasgos faciales ni construye una plantilla biométrica.
Es el principal insumo técnico para sostener que el tratamiento no recae sobre
datos biométricos, aunque esa conclusión depende también de qué se almacene
antes de que la imagen llegue al modelo.

La segunda es operativa: al ser puramente convolucional, la red admite
imágenes de resoluciones distintas. Las cámaras de un terminal no comparten
resolución, altura ni ángulo, y el método no obliga a reescalarlo todo a un
formato único.

La tercera es que la distribución espacial informa por sí misma. Los autores
ilustran el punto con imágenes que contienen el mismo número de personas pero
repartidas de maneras radicalmente distintas. Para LAP, saber que hay
trescientas personas en el hall de salidas es mucho menos útil que saber que
doscientas de ellas están concentradas frente a tres mostradores.

### Limitación reconocida por los autores

La limitación más explícita aparece en la evaluación sobre UCSD, un conjunto de
escenas relativamente dispersas —entre 11 y 46 personas por imagen—. Los
propios autores indican que superan a la mayoría de métodos previos **excepto a
MCNN en la categoría de error absoluto medio**. Reconocen además que la baja
resolución de esos cuadros dificulta generar un mapa de densidad de calidad
después de las sucesivas operaciones de reducción, hasta el punto de que fue
necesario ampliarlos por interpolación.

La consecuencia para el proyecto es incómoda y conviene enunciarla: el régimen
de baja densidad no es el terreno donde el método brilla, y buena parte del día
un terminal aéreo opera precisamente en baja densidad. El método está
optimizado para el escenario que menos ocurre.

Hay una segunda limitación, más estructural: el mapa de densidad no entrega
posiciones individuales. Los autores la asumen como parte del paradigma. El
trabajo siguiente la convierte en su crítica central.

---

## 2. P2PNet

**Título:** *Rethinking Counting and Localization in Crowds: A Purely Point-Based Framework*
**Autores:** Qingyu Song, Changan Wang, Zhengkai Jiang, Yabiao Wang, Ying Tai, Chengjie Wang, Jilin Li, Feiyue Huang, Yang Wu
**Conferencia:** IEEE/CVF International Conference on Computer Vision (ICCV)
**Año:** 2021

### Qué propone

Los autores parten de una tesis: localizar a los individuos responde mejor a
las demandas prácticas del análisis de multitudes que limitarse a contarlos.
Sostienen que los métodos basados en representaciones intermedias —mapas de
densidad o cajas delimitadoras generadas artificialmente— son contraintuitivos
y propensos a error.

Su propuesta, P2PNet, predice directamente un conjunto de puntos con sus
coordenadas y su confianza, sin pasar por ninguna representación intermedia.
La pieza crítica del método no es la arquitectura sino la forma de asignar los
objetivos de aprendizaje: los autores establecen que tanto el caso en que
varias predicciones se emparejan con una misma persona anotada como el caso
inverso confunden al modelo durante el entrenamiento y producen conteos sobre-
o subestimados. Lo resuelven con un emparejamiento uno a uno mediante el
algoritmo húngaro.

El trabajo aporta además una métrica propia, la *density Normalized Average
Precision*, que evalúa conjuntamente localización y conteo, diseñada para no
ignorar la variación de densidad entre escenas ni dejar sin penalización las
predicciones duplicadas.

Los autores describen sus resultados de conteo en términos relativos: sobre la
parte A de ShanghaiTech reducen el error absoluto medio un 4,8 % y el
cuadrático medio un 12,9 % respecto del segundo mejor método; sobre la parte B,
un 2,3 % en error absoluto; sobre NWPU-Crowd, un 12,4 % frente al método más
cercano. En localización señalan que su precisión se sitúa cerca del 90 % en la
mayoría de conjuntos bajo el umbral principal de la métrica, y reportan un
F1 / precisión / exhaustividad de 71,2 % / 72,9 % / 69,5 % bajo la métrica de
NWPU-Crowd.

### Por qué aplica al caso LAP

La localización individual es lo que convierte una cifra en una decisión
operativa. Un conteo agregado por cámara no permite decidir dónde abrir un
mostrador adicional ni hacia dónde redirigir el flujo; un conjunto de puntos
sí, porque admite agregarse por zonas definidas por LAP —colas de facturación,
filtro de seguridad, migraciones— sin necesidad de reentrenar el modelo.

Ahora bien, esa misma capacidad eleva el perfil de riesgo del sistema. Un punto
con coordenadas no es un dato biométrico, pero sí es un dato espacio-temporal
referido a una persona física presente en un lugar y un momento determinados.
Si esos puntos se guardan y se encadenan en el tiempo, el sistema se acerca al
seguimiento de trayectorias, que es una finalidad distinta de la estimación de
aglomeraciones y que requeriría su propia base de legitimación.

La diferencia entre estimar una aglomeración y seguir a una persona no es, por
tanto, una diferencia de algoritmo: es una diferencia de política de
persistencia. Con la misma salida de P2PNet, retener los puntos y asociarlos
entre cuadros produce trayectorias individuales. Ese límite debe fijarse por
diseño y por contrato, no dejarse a la configuración: una vez que el sistema
está en producción, permitir la persistencia es un cambio de parámetro,
mientras que prohibirla obliga a volver sobre el diseño.

### Limitación reconocida por los autores

Los autores reconocen tres limitaciones de manera explícita.

Primero, admiten que sobre UCF-QNRF su precisión «no es tan competitiva» frente
a ADSCNet, aunque sea superior en todos los demás conjuntos.

Segundo, atribuyen su desempeño inferior en una de las métricas de NWPU-Crowd a
que sus predicciones se basan en un único mapa de características de una sola
escala, elegido por simplicidad; señalan que incorporar fusión multiescala
sería una mejora natural.

Tercero, y es lo más relevante para el caso de LAP, observan que la precisión
cae de forma notable bajo el umbral de localización más estricto, y explican
que a esa exigencia empiezan a hacerse aparentes los efectos de las
desviaciones del etiquetado.

Esta última observación no es un límite del modelo sino **del suelo de verdad**:
por debajo de cierta escala, la propia anotación humana es ruidosa. La
consecuencia práctica es directa. Cualquier compromiso de exactitud que el
equipo ofrezca a LAP debe formularse a nivel de zona agregada y no a nivel de
posición individual, porque a nivel individual la referencia contra la cual se
mediría no es confiable.

---

## 3. P2R

**Título:** *Point-to-Region Loss for Semi-Supervised Point-Based Crowd Counting*
**Autores:** Wei Lin, Chenyang Zhao, Antoni B. Chan
**Conferencia:** IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)
**Año:** 2025

### Qué propone

El punto de partida es económico. Entrenar un contador basado en puntos exige
anotar cientos o miles de puntos por imagen, y ese costo ha frenado la adopción
del enfoque. Los autores integran entonces los métodos basados en puntos en un
esquema semi-supervisado de pseudo-etiquetado, en el que un modelo maestro
genera etiquetas para imágenes sin anotar y un modelo estudiante aprende de
ellas.

Al implementarlo detectan un problema concreto: la confianza asociada a una
pseudo-etiqueta no logra propagarse a los píxeles del fondo bajo el esquema
punto-a-punto. Para diagnosticarlo diseñan un mapa de activación específico por
punto y observan que los píxeles vecinos de cada píxel de primer plano quedan
sobreactivados, de modo que el decodificador acaba interpretándolos como
personas distintas.

La solución es sustituir el emparejamiento punto-a-punto por uno
punto-a-región: en lugar de detectar un punto por peatón, se segmenta una
región local, de forma que todos los píxeles de esa región comparten la
confianza del pseudo-punto correspondiente. Como efecto colateral, el algoritmo
húngaro deja de ser necesario. Los autores miden esa ganancia: sobre una imagen
de 576 × 960 píxeles con 775 puntos anotados, el cálculo de la pérdida
punto-a-punto requiere 0,4307 segundos frente a 0,0064 segundos del suyo, cerca
de 68 veces más rápido.

Los experimentos se realizan sobre cuatro conjuntos —ShanghaiTech A y B,
UCF-QNRF y JHU-Crowd++— bajo protocolos del 5 %, 10 % y 40 % de datos
etiquetados. La afirmación central es que entrenar con el 5 % de los datos
usando este método supera al aprendizaje totalmente supervisado con el 10 %, y
resulta equivalente a otros métodos semi-supervisados que emplean ese mismo
10 %. Como referencia del punto de partida, el modelo entrenado únicamente con
ese 5 % de datos etiquetados alcanza un error absoluto medio de 93,7 y un error
cuadrático medio de 155,2 sobre la parte A de ShanghaiTech. Bajo supervisión
completa, el método supera a P2PNet en los cuatro conjuntos.

### Por qué aplica al caso LAP

Es, de los tres, el trabajo con la implicancia legal más favorable, y conviene
ser explícito sobre por qué.

El principio de minimización exige tratar solo los datos necesarios para la
finalidad perseguida. Un método que alcanza desempeño competitivo con el 5 % de
los datos etiquetados permite reducir en proporción similar el volumen de
imágenes del terminal que deben ser revisadas y anotadas por personas. Menos
imágenes anotadas significa menos exposición de imágenes de pasajeros reales a
anotadores humanos, menos copias del material fuera del entorno controlado y
una superficie de brecha considerablemente menor.

Dicho de otro modo: la eficiencia de etiquetado deja de ser una ventaja de
costo y se convierte en un argumento de cumplimiento normativo. Es un argumento
que conviene documentar como tal en el análisis de riesgo, y no solo como un
ahorro.

Además, los experimentos de adaptación de dominio del artículo abordan de
frente el problema que este proyecto tendrá que resolver: ningún conjunto
público de conteo de multitudes contiene escenas de un terminal aéreo peruano.

### Limitación reconocida por los autores

Los autores documentan un caso de fallo atribuido al desenfoque producido por
el movimiento de la multitud, y lo presentan como tal dentro de su comparación
visual de predicciones. El método tiene, por tanto, un modo de fallo reconocido
y ligado a una condición —multitud en movimiento— que en un terminal aéreo es
la norma y no la excepción.

Más importante aún, los propios autores registran la brecha de dominio. Al
transferir el modelo entre conjuntos sin adaptación de dominio, el desempeño se
degrada de forma marcada, y son ellos quienes señalan que ese pobre resultado
subraya la distancia entre los datos de origen y los de destino; cuando se
incorporan al entrenamiento datos no etiquetados del dominio de destino, los
errores se reducen de forma significativa.

La consecuencia para el proyecto es la más importante de todo este resumen: si
los propios autores advierten una brecha de dominio de esta naturaleza,
entonces **las métricas publicadas sobre conjuntos públicos no son
extrapolables al Aeropuerto Jorge Chávez**. Presentar a LAP una cifra de
exactitud tomada de la literatura, sin validación en el terminal, sería una
afirmación sin respaldo. El frente ético-legal recomienda que ninguna promesa
cuantitativa de desempeño figure en un entregable al cliente antes de una
validación en sitio, aun cuando eso implique presentar el proyecto sin cifras
atractivas.

---

## Cómo se articulan los tres trabajos

Los tres artículos no son alternativas entre las cuales elegir: forman una
progresión en la que cada uno resuelve una limitación del anterior y, al
hacerlo, desplaza el problema hacia el siguiente. CSRNet resuelve el problema
de *cuántos* con una arquitectura simple y entrenable de extremo a extremo,
pero entrega una superficie de densidad de la que no puede extraerse dónde está
cada persona. P2PNet resuelve el problema de *dónde*, eliminando la
representación intermedia y prediciendo puntos directamente, pero paga ese
avance con un costo de anotación que crece con la densidad de la escena. P2R
resuelve el problema del *costo de anotación*, llevando el enfoque por puntos
al régimen semi-supervisado, y de paso elimina el algoritmo húngaro que P2PNet
había introducido. Ahora bien, vista desde el frente ético-legal esa progresión
tiene una lectura distinta y en parte inversa: cada paso adelante en capacidad
técnica es también un paso hacia un perfil de riesgo distinto. CSRNet tiene el
perfil más bajo, porque su salida es agregada por construcción y el riesgo se
concentra aguas arriba, en qué se hace con el video original. P2PNet traslada
el riesgo a la salida del modelo —coordenadas por persona, que pueden
persistirse y encadenarse en trayectorias— y exige, por tanto, un control
explícito de persistencia. P2R reduce el riesgo del proceso de anotación,
porque expone menos imágenes reales a anotadores humanos, pero introduce una
dependencia de pseudo-etiquetas cuya calidad no es auditable caso por caso. De
esa lectura conjunta se desprenden los tres criterios que este frente traslada
al frente técnico: que la granularidad de la salida es una decisión de
cumplimiento y no solo de producto, y que conviene preferir la mínima que
resuelva el problema aunque el modelo sea capaz de más; que la eficiencia de
etiquetado es aprovechable como argumento de minimización y debe documentarse
así; y que ninguna cifra de la literatura es transferible al terminal sin
validación local, cosa que la evidencia del tercer artículo demuestra por sí
sola.
