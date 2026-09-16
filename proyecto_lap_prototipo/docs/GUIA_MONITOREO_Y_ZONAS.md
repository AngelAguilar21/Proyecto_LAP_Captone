# Zonas, calibración y lectura del monitoreo

## Configurar una cámara

1. En **Configuración → Mapa y cámaras**, añade la cámara, asigna su nivel y selecciona su video o fuente.
2. Obtén la **imagen inicial**. Edita la **zona útil** para excluir reflejos, otros pisos y áreas ajenas. Esa máscara se usa tanto en seguimiento como en conteo especializado.
3. Puedes añadir zonas de imagen para medir sectores de esa toma. Los puntos se arrastran; un clic cerca de un borde añade un punto. Selecciona un punto para quitarlo o usa Deshacer edición.
4. Define los umbrales de ocupación. El conteo especializado es un complemento configurable; su estimación no se suma al conteo del detector.
5. Si la cámara permite observar ambos lados de una puerta, añade opcionalmente un **acceso de un local**. Dibuja la línea de paso y ajusta las áreas interior/exterior. Asocia el acceso con un local del mismo nivel en el mapa. La cámara conserva sus otras funciones.
6. Guarda la configuración. Coloca la cámara en el plano y establece las referencias del suelo para proyectar posiciones.

## Referencias del suelo y homografía

Cada referencia relaciona un punto del suelo en el video con el mismo punto físico en el mapa. Usa esquinas de baldosas u otras referencias fijas distribuidas por la zona visible. No uses cabezas ni esquinas arbitrarias del encuadre.

La homografía transforma coordenadas de la imagen en coordenadas del plano del suelo. Requiere al menos cuatro correspondencias. Se comprueba que los datos sean finitos, no estén repetidos ni casi alineados, que la matriz sea válida, que el error de ajuste no sea excesivo y que no atraviese una singularidad dentro del área de referencias.

Con cinco o más referencias se calcula además el error dejando fuera un punto cada vez. El punto excluido se proyecta usando los demás y se compara con su posición marcada. Si un subconjunto es degenerado, no se utiliza para esa comprobación. Cuatro puntos pueden ajustar exactamente aun estando mal ubicados: un error casi cero no demuestra precisión real.

Arrastra las referencias tanto en la imagen como en el mapa para corregirlas. Selecciona un punto del mapa o usa la lista para eliminarlo. Finaliza con **Validar y guardar referencias**. Valida también puntos físicos que no hayas usado y recorridos conocidos; la perspectiva fuera del área de referencias y los desniveles pueden producir errores.

## Zonas de interés del plano

En **Configuración → Zonas del plano**, dibuja polígonos o rectángulos y asigna un nombre y uso (comercio, cola, sala, pasillo, etc.). Con **Mover**, toca la zona para mostrar sus vértices: arrástralos, añade un punto entre dos existentes o elimina un punto seleccionado. El polígono debe conservar al menos tres vértices y no cruzarse.

Las sugerencias agrupan celdas contiguas con presencia del último monitoreo disponible de ese nivel. Son propuestas editables, no decisiones automáticas ni zonas comerciales confirmadas. Revisa sus límites y guarda la zona. Los umbrales se definen en **Alertas del plano**.

La relación con las cámaras es espacial: una posición calibrada dentro de la zona aporta a su ocupación. Una zona sin cobertura o sin proyecciones válidas no demuestra ausencia de personas. Cámaras superpuestas pueden observar a una misma persona; la asociación entre cámaras es estimada, no identidad verificada.

## Dónde consultar resultados

- **Vista general:** mapa sincronizado, cámaras, reproducción y resumen ejecutivo por zonas. El ranking usa el promedio observado; el gráfico muestra su evolución. Pulsa un máximo para ir al instante correspondiente.
- **Videos y resultados:** historial y comparación entre análisis. La línea de tiempo se expresa desde el inicio de la grabación; la fecha del análisis no es necesariamente la fecha de captura.
- **Reportes:** exportación y consulta de datos disponibles. Los sectores automáticos de presencia se pueden ubicar en el mapa y no equivalen a locales configurados.
- **Capas del mapa → Conteos y accesos por cámara:** activa los detalles que se ocultan inicialmente para mantener el plano despejado. Los accesos asociados aparecen en el local con entradas/salidas y el detalle al pasar el cursor.

YOLO detecta personas; ByteTrack enlaza detecciones e IDs a lo largo de una cámara. P2PNet estima puntos de cabezas y conteo en imágenes densas. La homografía del suelo proyecta el apoyo de las personas detectadas, no las cabezas de P2PNet. El conteo especializado se presenta asociado a la cámara, sin inventar coordenadas de personas en el suelo.

## Alertas

Una alerta requiere superar la cantidad y duración configuradas. Los avisos de concentración son visuales y silenciosos; se pueden cerrar y desaparecen tras 12 segundos. La condición sigue visible en sus indicadores y los episodios registrados en los resultados. Las confirmaciones desaparecen a los 6 segundos. Los errores requieren cierre manual y no impiden consultar el resto de la página.

Una presencia acumulada alta indica más tiempo observado en un sector, no necesariamente una aglomeración simultánea ni visitantes únicos. Usa el umbral y la duración de una zona para evaluar una concentración.

## Revisión de grabaciones

Visualización controla el video y las capas iniciales del mapa:
- Personas y recorridos: detecciones en imagen y trayectorias proyectadas con calibración.
- Presencia acumulada: intensidad del tiempo de presencia; no representa visitantes únicos.
- Estimación de multitudes: puntos estimados en imagen y conteo junto a la cámara. No se proyectan cabezas al suelo.

Las capas individuales del mapa siguen disponibles en Capas. La explicación de los modelos está en Acerca de las visualizaciones.

Eventos de concentración permite saltar al instante de confirmación de una alerta. Vista general muestra un aviso de evento grabado, cerrable y con duración máxima de 12 segundos. Al retroceder antes del evento puede aparecer otra vez. Videos y resultados muestra el listado sin avisos emergentes.

Cambiar de sección conserva la selección, el mapa y el instante; la reproducción se pausa al salir. Actualizar resultados permite consultar análisis nuevos. Vista general contiene el resumen por zonas; Reportes reúne exportaciones.
