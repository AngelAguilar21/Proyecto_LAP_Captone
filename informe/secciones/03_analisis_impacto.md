<!--
=====================================================================
 SECCION 3.4 -- ANALISIS TECNICO, ETICO, SOCIAL, AMBIENTAL
 Responsable: Fabian Moreno Ugarte (Validacion etica/legal y documentacion)

 14/09/2026, reestructuracion al indice del modelo del curso: resume la
 antigua Seccion 4 (Analisis de impacto y privacidad desde el diseno),
 cuyo desarrollo completo esta, sin recortes, en el Anexo C
 (secciones/anexo_c_analisis_impacto.md). Esta version no afirma nada que
 no conste alli: si se corrige un dato, se corrige en los dos archivos.

 Correspondencia con el Anexo C:
   3.4 (introduccion) <- C.1        3.4.3 social    <- C.2, C.3, C.5
   3.4.1 tecnico      <- C.2        3.4.4 ambiental <- C.4
   3.4.2 etico        <- C.5

 REGLAS DE REDACCION APLICADAS EN ESTE ARCHIVO
 - Ninguna cifra de la literatura se reproduce si no consta en la prosa
   del articulo de origen (NOTAS_FUENTES.md, seccion 1).
 - Se prefiere declarar un impacto como no cuantificado antes que
   estimarlo sin base.
 - Las remisiones a "Seccion 5" y "Anexo C" van escritas a mano.
=====================================================================
-->

## 3.4 Análisis Técnico, Ético, Social, Ambiental

Este análisis sigue la estructura de una Evaluación de Impacto en Protección de Datos: identificar el tratamiento, valorar su necesidad y proporcionalidad, identificar los riesgos para los titulares y proponer medidas de mitigación. Esa evaluación es exigible antes de iniciar un tratamiento basado en la captación masiva y continua de imágenes, con independencia de que el modelo produzca conteos agregados, de modo que este apartado es su contenido sustantivo. Se prefiere declarar un impacto como no cuantificado antes que estimarlo sin base. El desarrollo completo figura en el Anexo C.

### 3.4.1 Análisis Técnico

El riesgo técnico dominante es la brecha de dominio. Los autores de P2R [Lin_2025_CVPR] reconocen que el desempeño de los métodos de conteo se degrada de forma marcada cuando el entorno de despliegue difiere del de entrenamiento, y documentan un modo de fallo que produce sobreestimación severa del conteo. Ninguna cifra obtenida sobre datos públicos predice, por tanto, la exactitud en el terminal. A ello se suman el sesgo de anotación, pues la métrica de localización más exigente de P2PNet [Song_2021_ICCV] cae por efecto de las desviaciones de etiquetado, y el sesgo demográfico, que ninguno de los trabajos revisados evalúa de forma desagregada: la estatura, los cubrimientos de cabeza, el equipaje voluminoso o las sillas de ruedas pueden inducir desempeño desigual en una población tan heterogénea como la de un aeropuerto internacional. Se recomienda que la validación en sitio incluya una evaluación desagregada, al menos por franja de estatura y por presencia de equipaje voluminoso.

### 3.4.2 Análisis Ético

El sistema ofrece una alternativa menos invasiva que la identificación biométrica para la misma finalidad, pero su riesgo principal no es técnico sino de gobernanza: el deslizamiento de finalidad. Una vez desplegada la infraestructura, incorporar reidentificación para medir tiempos de permanencia, o reconocimiento facial para detectar personas de interés, es una decisión de configuración y de presupuesto, no un rediseño. La mitigación que se propone es documental y contractual: una declaración de finalidades excluidas conforme a la cual el sistema no identifica personas, no realiza seguimiento individual de trayectorias, no reconoce emociones y no alimenta decisiones automatizadas sobre pasajeros individuales, reforzada por los requisitos de no persistencia y salida agregada de la Sección 5. Una lista de lo que el sistema no hace es más difícil de erosionar silenciosamente que una lista de lo que sí hace.

### 3.4.3 Análisis Social

El beneficio social es la prevención de incidentes por aglomeración y una asignación de recursos basada en evidencia. Frente a él se identifican tres riesgos. Si el subconteo se concentra en un grupo, las zonas donde ese grupo se concentra reciben sistemáticamente menos personal y menos apertura de mostradores: el daño no es individual sino distributivo. El segundo es el sesgo de automatización: si el personal llega a confiar en el tablero más que en su propia observación, un fallo en un momento crítico produce un efecto peor que la ausencia del sistema, y un operador que aprueba mecánicamente sus alertas reintroduce de hecho la decisión automatizada que la supervisión humana pretende evitar. Por eso se recomienda tratar la capacitación de los operadores en los modos de fallo del modelo como medida de mitigación y no como accesorio de implantación. El tercero es el uso laboral no declarado: si los conteos por zona se cruzan con los turnos del personal, el sistema se convierte en una herramienta de evaluación de desempeño, y esa exclusión debe figurar expresamente en la declaración de finalidades.

### 3.4.4 Análisis Ambiental

El equipo no ha medido el consumo energético del entrenamiento ni de la inferencia, de modo que este análisis es cualitativo. La reutilización de modelos preentrenados evita entrenar desde cero, y la pérdida de P2R prescinde del algoritmo húngaro: sobre una imagen de 576 × 960 píxeles con 775 puntos anotados, su cálculo es cerca de sesenta y ocho veces más rápido que el de la pérdida punto a punto [Lin_2025_CVPR], aunque esa cifra mide una operación por iteración y no el consumo total. A lo largo de la vida útil, la inferencia continua pesará previsiblemente más que el entrenamiento, y las decisiones que la reducen (muestrear un fotograma cada varios segundos, procesar en el borde, no persistir imágenes y agregar la salida) son las mismas que reducen la exposición de datos personales. Se recomienda registrar las horas de GPU desde el primer entrenamiento, porque ese dato no es reconstruible a posteriori, y reutilizar la infraestructura de CCTV existente, que es además la opción económicamente decisiva.
