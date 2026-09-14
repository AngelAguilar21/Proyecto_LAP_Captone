<!--
=====================================================================
 SECCION 3 -- RESTRICCIONES ETICAS (3.3.2) Y LEGALES (3.3.3)
 Responsable: Fabian Moreno Ugarte (Validacion etica/legal y documentacion)

 14/09/2026, reestructuracion al indice del modelo del curso: lo que era
 la Seccion 3 (Marco normativo) queda en el cuerpo reducido a estos dos
 apartados. El desarrollo completo esta, sin recortes, en el Anexo B
 (secciones/anexo_b_marco_normativo.md), y los requisitos de privacidad
 M-01 a M-10 en la Seccion 5 (secciones/requerimientos.tex).

 LIMITE: 3.3.3 (restricciones legales) no pasa de UNA PAGINA en el PDF.
 Si se anade algo, se quita otra cosa; el detalle va al Anexo B.

 Esta version no afirma nada que no conste en el Anexo B: si se corrige
 un dato, se corrige en los dos archivos.

 REGLAS DE REDACCION APLICADAS EN ESTE ARCHIVO
 - Ninguna cita normativa se escribio de memoria (NOTAS_FUENTES.md, sec. 2).
 - Lo que no pudo contrastarse va marcado [VERIFICAR: ...] y, ademas, con
   la reserva escrita en prosa en el mismo parrafo.
 - Referencias bibliograficas con las claves de referencias.bib.
 - Las remisiones a "Seccion 5" y "Anexo B" van escritas a mano.
=====================================================================
-->

### 3.3.2 Restricciones Éticas

El sistema debe responder cuántas personas hay y dónde, nunca quién es cada una, y de esa condición se siguen tres restricciones. La primera es no identificar ni individualizar a los pasajeros: ninguna etapa debe extraer rasgos faciales ni construir plantillas biométricas, y la granularidad de salida debe ser la mínima que resuelva el problema, porque la diferencia entre estimar una aglomeración y seguir a una persona no depende del algoritmo sino de si las salidas se persisten y se encadenan. La segunda es no deslizarse hacia otras finalidades: una vez instalada la infraestructura, añadir reidentificación o reconocimiento facial es una decisión de configuración, de modo que el proyecto incorpora una declaración expresa de finalidades excluidas. La tercera es no prometer exactitud sin validación: ninguna cifra obtenida sobre conjuntos públicos debe presentarse a LAP como desempeño esperable en el terminal.

### 3.3.3 Restricciones Legales

El tratamiento de imágenes de personas en el terminal está sujeto a la Ley 29733, de Protección de Datos Personales, y a su reglamento, el D.S. 016-2024-JUS, cuya entrada en vigor se habría producido el 30 de marzo de 2025, fecha pendiente de contrastar contra la fuente oficial. [VERIFICAR: únicamente la fecha de entrada en vigor, el 30 de marzo de 2025, que es el dato que fija el régimen transitorio. La expedición, la publicación y la disposición derogatoria sí se contrastaron contra la separata de *El Peruano* del 30 de noviembre de 2024.] Para videovigilancia rige además la Directiva 01-2020-JUS/DGTAIPD. Se superpone el régimen de seguridad ciudadana del D.L. 1218 y la Ley 30120, cuya denominación oficial también falta confirmar, reglamentados por el D.S. 007-2020-IN, que alcanza a los establecimientos comerciales abiertos al público con aforo de cincuenta personas o más. [VERIFICAR: denominación oficial completa y fecha de publicación del D.L. 1218 y de la Ley 30120. El D.S. 007-2020-IN sí se contrastó contra el texto publicado en *El Peruano*.] Cómo encaja un terminal concesionado en ambos regímenes debe validarlo el área legal de LAP.

De ese marco se derivan cinco restricciones de diseño. El consentimiento no es viable en un terminal, de modo que la licitud depende de un supuesto del artículo 14 que solo LAP puede invocar y de superar el examen de proporcionalidad del artículo 7: a igual utilidad, la salida agregada por zona prevalece sobre la localización individual. La finalidad declarada no puede extenderse (artículo 6), y medir permanencias en zonas comerciales exigiría una base propia. La Directiva fija para las imágenes una conservación máxima de treinta a sesenta días y el D.S. 007-2020-IN exige conservar las de seguridad al menos cuarenta y cinco, lo que obliga a separar el subsistema de conteo del CCTV. El deber de información exige carteles como el del Anexo A. Y ejecutar la inferencia fuera del Perú crearía un flujo transfronterizo (artículo 15), por lo que se prefiere el procesamiento local. La privacidad desde el diseño, exigible por el principio de responsabilidad proactiva, se concreta en los requisitos de la Sección 5.

Contrastado con el prototipo del equipo, ningún enfoque revisado construye plantillas biométricas, pero el prototipo persiste trayectorias individuales. Resultan cuatro hallazgos no conformes: falta la Evaluación de Impacto en Protección de Datos, exigible antes de tratamientos de alto riesgo como la videovigilancia masiva; no se cumple el requisito de salida agregada, defecto que el equipo puede corregir; y faltan la validación de exactitud en el terminal y la evaluación de sesgo demográfico, que requieren acceso a material de LAP. Siguen pendientes la política de retención, la localización del procesamiento y la trazabilidad de licencias de los conjuntos de datos. El desarrollo completo figura en el Anexo B.
