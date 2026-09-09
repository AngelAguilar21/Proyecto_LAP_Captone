VII. METODOLOGÍA

A. Requisitos

El prototipo se desarrolló en Python 3.10 o superior (validado en 3.13), con un conjunto reducido de librerías, cada una con un rol específico: OpenCV para lectura de video y operaciones geométricas, NumPy para matrices y transformaciones, PyTorch y torchvision para ejecutar la red de detección, filterpy para el filtro de Kalman, lap para la asignación húngara (Jonker-Volgenant) entre detecciones y trayectorias, y matplotlib para la reproducción animada del historial de posiciones. El historial se guarda con sqlite3, de la biblioteca estándar, sin motor de base de datos externo.

Para detectar cabezas se integró el repositorio oficial de P2PNet [1] como submódulo de git, junto con el punto de control preentrenado que ese mismo repositorio distribuye (SHTechA); no se reentrenó el modelo. Todo corrió sobre CPU (no hubo GPU disponible en ningún momento del desarrollo), condición que se tuvo presente al planear los tiempos de ejecución, aunque no impidió completar el pipeline sobre los datos de prueba.

Para que los integrantes del equipo trabajaran sobre el mismo entorno sin pelear con versiones de librerías, se definió un Dockerfile y un docker-compose orientados solo a CPU. El control de versiones se llevó en git/GitHub, con P2PNet enlazado como submódulo al repositorio oficial de Tencent Youtu Research.

Como entrada se usaron dos videos .mp4 grabados con teléfonos móviles: aproximadamente 60 cuadros por segundo, 464×832 píxeles, unos 34 segundos cada uno. Ambos registran la misma explanada exterior de la universidad desde ángulos y alturas distintos.

La TABLA I resume estos requisitos junto con los funcionales y no funcionales que se derivaron de ellos durante el desarrollo.

TABLA I

REQUISITOS DEL PROYECTO

TABLA_REQUISITOS

Nota: RT = requisito técnico, RF = requisito funcional, RNF = requisito no funcional.

B. Restricciones que definieron el diseño

Dos restricciones, una legal y una empírica, condicionaron cada decisión posterior.

La Ley 29733 de Protección de Datos Personales [3] impide sustentar la identificación de personas en reconocimiento facial o en cualquier dato biométrico reversible. Por eso toda la arquitectura se apoya en posición y en descriptores no biométricos, como el color dominante de la ropa y la proporción alto/ancho, que solo desempatan casos ambiguos y nunca funcionan como identificador principal.

La segunda restricción no se anticipó: al revisar el material grabado quedó claro que las dos cámaras no cubren tramos distintos de un mismo recorrido, como se había planteado al inicio del proyecto, sino que observan la misma zona desde ángulos diferentes, con una porción de campo de visión compartida. Esto obligó a descartar un modelo de continuidad basado en el tiempo que tarda alguien en cruzar un tramo ciego caminando, y a reemplazarlo por uno de asociación espacial simultánea entre cámaras, que se describe en la subsección E.

C. Detección y seguimiento mono-cámara

P2PNet entrega, cuadro a cuadro, un conjunto de puntos con su confianza asociada en lugar de cajas delimitadoras completas. Esa salida se adaptó al esquema de ByteTrack [2], que separa las detecciones en dos grupos según su confianza y las asocia en dos etapas sucesivas a las trayectorias existentes; esto permite recuperar un identificador tras una oclusión breve sin depender únicamente de las detecciones de mayor calidad. Cada trayectoria se representa con un filtro de Kalman de velocidad constante, y la asociación entre trayectorias y detecciones en cada etapa se resuelve con el algoritmo húngaro de la librería lap.

La primera versión de este componente calculó el costo de asociación como superposición (IoU) entre una caja fija de 20 píxeles centrada en cada punto. Al probarla sobre los videos reales, un mismo peatón terminaba repartido en varias decenas de identificadores distintos en pocos segundos. Un diagnóstico cuadro a cuadro señaló la causa: en esta vista tan oblicua, dos cabezas pueden estar a 15-25 píxeles entre sí cuando la gente camina junta, y basta con que el detector falle una sola detección para que, al reaparecer 10 píxeles más allá, la superposición entre cajas de ese tamaño caiga por debajo del umbral. El resultado era un identificador nuevo cada vez. Cambiar la métrica de costo a distancia euclidiana en píxeles, con un umbral de 45 píxeles y conservando la misma asignación húngara, redujo la fragmentación de inmediato, verificado sobre la misma secuencia donde antes fallaba.

D. Calibración geométrica

Como ambas cámaras observan la escena desde ángulos oblicuos y alturas distintas, sus coordenadas de píxel no son comparables entre sí ni representan directamente una posición sobre el piso. Se calculó, por cámara, una homografía de píxel a un plano compartido con cv2.findHomography, usando las esquinas de las losetas del piso como puntos de referencia contados desde un mismo origen físico en ambas cámaras.

Calibrar con cuatro puntos agrupados cerca de ese origen pareció suficiente al principio: las homografías resultantes eran precisas justo ahí, pero extrapolaban a posiciones sin sentido físico (más de cien unidades de distancia) en cuanto alguien se alejaba de la zona calibrada. La corrección fue repartir seis a ocho puntos por toda el área de interés en lugar de agruparlos, verificada comparando, antes y después, el rango de coordenadas que cada cámara produce para toda su zona de piso visible.

E. Fusión de identidades entre cámaras

Al no existir un tramo ciego real entre las dos cámaras, la continuidad entre ellas se resuelve comparando, en el plano compartido, la posición de una detección nueva de una cámara contra las personas que la otra cámara ya sigue en ese mismo instante. Si la distancia entre ambas cae dentro de 1.5 unidades del plano compartido (unidades de loseta en esta calibración, no metros verificados) y el desfase de tiempo es menor a un segundo, se asume que es la misma persona y se reutiliza su identificador. Si hay más de un candidato dentro de ese margen —dos personas caminando cerca, por ejemplo— el desempate se hace con el descriptor no biométrico: histograma de color HSV del torso y proporción alto/ancho, obtenidos por sustracción de fondo, viable porque ambas cámaras son fijas.

F. Persistencia y visualización

Cada posición calculada se guarda en SQLite junto con su cámara de origen, marca de tiempo y zona del plano. Con ese historial se genera una animación sobre el plano compartido que permite comparar, cuadro por cuadro, la trayectoria reconstruida contra el video original.

G. Validación

La validación tuvo dos etapas. Primero, un conjunto de pruebas sintéticas, independientes de los videos y del modelo de detección, cubre los casos límite de la lógica de fusión y seguimiento: que una misma persona vista por ambas cámaras casi al mismo tiempo reciba un solo identificador; que dos detecciones lejanas, o separadas por demasiado tiempo, no se fusionen; que el desempate por descriptor elija al candidato correcto entre varios ambiguos; y que un identificador se mantenga estable ante una oclusión de un par de cuadros.

Segundo, el pipeline completo corrió sobre los dos videos reales, y el número de identificadores globales generados sirvió como señal indirecta de calidad en cada iteración. Con la asociación por IoU descrita en la subsección C, la primera ejecución generó 226 identificadores globales para un número de peatones reales muy inferior a esa cifra (no se llevó un conteo manual exacto, pero a simple vista sobre el video no llegaban a la decena en ningún momento). Cambiar a distancia euclidiana bajó la cifra a 47, ya con la calibración de cuatro puntos agrupados de la subsección D; ampliar únicamente el margen de fusión, sin tocar la calibración, apenas la movió a 45, lo que confirmó que el problema no estaba en ese margen sino en la homografía misma. Recalibrar con seis a ocho puntos repartidos, como se describe en la subsección D, la bajó a 38, y una revisión cuadro a cuadro confirmó que varios identificadores se mantenían estables entre 10 y 14 segundos seguidos, sin los saltos de coordenadas que se habían observado antes. Ese contraste entre el conteo de identificadores y lo observado en el video original fue, en la práctica, el criterio que permitió detectar y corregir tanto la fragmentación del seguimiento (subsección C) como la calibración deficiente (subsección D) antes de considerar el prototipo listo.

H. Limitaciones metodológicas

El prototipo no cuenta con un conteo manual de referencia sobre los mismos videos, de modo que la validación de la subsección G es cualitativa: confirma que el comportamiento es razonable, no cuantifica un margen de error de conteo. Tampoco se calibró la escala real de las losetas en metros (se calibró en unidades de loseta), así que las distancias y velocidades que el sistema reporta internamente no equivalen todavía a magnitudes físicas verificables; esto no afecta la lógica de fusión, que solo necesita que ambas cámaras compartan una misma unidad, pero sí limita cualquier lectura en metros por segundo hasta que se mida una loseta real. Finalmente, los dos videos de prueba registran a lo sumo un grupo pequeño de personas caminando; no hay evidencia todavía de cómo se comporta el sistema con la densidad de gente que tendría un aeropuerto real.

REFERENCIAS

[1] Q. Song et al., "Rethinking Counting and Localization in Crowds: A Purely Point-Based Framework," arXiv:2107.12746, 2021.
[2] Y. Zhang et al., "ByteTrack: Multi-Object Tracking by Associating Every Detection Box," arXiv:2110.06864, 2021.
[3] Congreso de la República del Perú, Ley N.º 29733, Ley de Protección de Datos Personales, 2011.
