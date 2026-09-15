# Cámaras, planos y revisión de resultados

## Flujo de trabajo

1. Inicia el sistema con `iniciar_sistema.ps1` y abre `http://127.0.0.1:5173/`.
2. En **Configuración → Proyecto y fuentes**, selecciona el espacio. El espacio de pruebas conserva las cámaras actuales; LAP ofrece niveles 1, 2, 3 y 4, con el 3 primero en la lista.
3. En **Cámaras**, agrega la fuente (archivo, ruta local o conexión autorizada), nombre y ubicación. **Obtener imagen** permite elegir un segundo del video sin ejecutar detección.
4. En **Zona útil de la imagen**, arrastra los vértices; pulsa cerca de un borde para insertar otro, o elimina el seleccionado. **Guardar cámara y zona** persiste la configuración. **Guardar progreso** también incluye los cambios del polígono. Esta máscara se aplica tanto a seguimiento como a conteo.
5. Para conteo, abre **Conteo y aglomeraciones**, selecciona la cámara, revisa sus zonas y umbrales y pulsa **Analizar video**. Los umbrales son configurables; no son una validación de aforo legal.
6. Para seguimiento, abre **Seguimiento → Pruebas de seguimiento → Comparar cámaras del espacio**. Selecciona las cámaras y pulsa **Analizar selección**. Sin asociación espacial, cada cámara conserva IDs independientes.
7. En **Videos y resultados**, selecciona uno o varios análisis. Los videos aparecen juntos y comparten reproducción, pausa, reinicio, saltos de 5 segundos, velocidad y barra temporal. En conteo, **Presencia acumulada** muestra las celdas de mayor presencia hasta el instante seleccionado.

## Imagen, cobertura y calibración son cosas diferentes

El archivo de una cámara es una matriz rectangular de píxeles; puede tener proporción panorámica, vertical o cuadrada. Una cámara ojo de pez puede mostrar una imagen circular dentro de ese rectángulo. El cono del plano representa una cobertura aproximada sobre el suelo, no la forma del archivo.

La zona útil excluye escaleras de otro nivel, espejos, pantallas y partes ajenas al análisis. Mover el cono no calibra la cámara. Para llevar posiciones del video al plano, marca al menos cuatro correspondencias distribuidas entre **el mismo suelo** en imagen y plano. Usa referencias adicionales para evaluar el error. El seguimiento proyecta el punto de apoyo de los pies; los puntos de cabeza del conteo no se convierten automáticamente en posiciones de suelo.

Las cámaras pueden compartir parte del suelo visible. Para asociar recorridos, configura referencias correctas, zonas útiles, cámaras vecinas y desfases de contenido, y activa **Asociar personas en el plano**. Dos videos que comienzan juntos o tienen el mismo nombre no prueban sincronización. Una asociación estimada puede equivocarse: no es identificación personal ni garantía de continuidad.

Las cámaras se asignan a un espacio/nivel. Las zonas de cada nivel se guardan por separado. El selector de nivel no traslada automáticamente las cámaras; cambiar su plano asociado borra referencias incompatibles. La cartografía LAP mantiene su escala de referencia: no se debe redimensionar mediante una distancia estimada del video.

## Pruebas C y D

Se añadieron **Cámara C** (cam1, vista hacia Plaza Vea) y **Cámara D** (cam2, vista hacia escaleras/McDonalds) desde `Downloads/videos LAP/prueba 2 camaras`. Se delimitaron zonas de suelo y se guardaron. Estos videos muestran un centro comercial, no el aeropuerto: se conservan en el espacio de pruebas, sin asignarles una ubicación ficticia en LAP ni declarar calibración o sincronización verificadas.

Para obtener recorridos combinados reales de esos videos falta identificar sus referencias comunes en un plano del lugar y verificar sus tiempos. El seguimiento individual y la comparación de resultados funcionan sin ese requisito. Las cámaras A y B conservan sus datos anteriores.

## Lectura correcta de las métricas

- **Personas en una muestra:** estimación en ese instante; no visitantes únicos del video.
- **Máximo simultáneo:** mayor conteo observado y el instante en que ocurrió.
- **Promedio:** ocupación media del periodo analizado.
- **Intervalos de concentración:** periodos que alcanzan el umbral durante la permanencia configurada.
- **Calor acumulado:** presencia integrada en el tiempo; el color es relativo. No sumar muestras para obtener personas únicas.
- **IDs de seguimiento:** trayectorias estimadas por sesión. Oclusiones y cambios de cámara pueden fragmentarlas; no sumar IDs locales de cámaras solapadas como visitantes únicos.

Sin fecha de grabación, los eventos se expresan en minutos/segundos del archivo. Solo introduce fecha/hora cuando se conozca.

## Procesamiento y reproducción

La inferencia usa CPU y procesa muestras; su velocidad depende de resolución, modelo y cantidad de cámaras. No se promete procesamiento de todas las cámaras del aeropuerto en tiempo real en una laptop. Los videos se procesan sin saltarse el tiempo de contenido configurado y luego se reproducen desde el archivo original a la velocidad del navegador, con observaciones guardadas. Los marcadores no equivalen a inferencia en cada fotograma: se ocultan cuando no hay una muestra suficientemente cercana.

En modo independiente, cada archivo termina por separado. La asociación sincronizada limita la sesión al periodo común. Durante una comparación entre análisis distintos, el reloj es relativo al inicio de cada archivo; no implica sincronización verificada.

Las fuentes en vivo requieren URL/protocolo, credenciales autorizadas y acceso a la red del LAP. Se admiten fuentes USB/IP/RTSP, pero esta versión no instala un grabador de streams: la revisión posterior completa requiere conservar un archivo de video. Una integración con el VMS/NVR del aeropuerto y capacidad de cómputo se dimensionan con LAP.

## Archivos y mantenimiento

- `dashboard/src/aero/CameraRegionEditor.tsx`: edición de la máscara compartida.
- `dashboard/src/aero/PlanSelector.tsx`, `VectorFloor.tsx`, `MapCanvas.tsx`: planos por nivel, vectores y edición espacial.
- `dashboard/src/aero/MultiCameraPanel.tsx`: selección de cámaras para una prueba.
- `dashboard/src/aero/ReplayWorkspace.tsx`: reproducción sincronizada y observaciones.
- `src/replay.py`: manifiestos, muestras y entrega del video con rangos HTTP para adelantar/retroceder.
- `data/replays/<sesión>/`: resultados locales. El manifiesto referencia el original; no duplica videos ni incluye audio en reproducción.
- `config/live.local.json`: configuración local de cámaras y espacios.

Los resultados de archivos conservan IDs anónimos de sesión para revisión. El estado activo se limpia al finalizar, pero **los resultados guardados no se borran automáticamente**. No se implementa reconocimiento facial. No muevas el video original mientras necesites reproducirlo; los endpoints públicos de resultados omiten su ruta local. El servidor del prototipo escucha solo en el equipo local.

## Validación realizada (14 de septiembre de 2026)

- 56 pruebas automáticas: máscaras, persistencia, planos separados, reproducción por rangos HTTP, recuperación de interrupciones y continuidad de archivos de distinta duración. La regresión de cámaras sin calibrar comprueba que un área del plano no descarte sus detecciones de imagen.
- Compilación de producción y comprobación TypeScript.
- Alta manual de C y D, edición de vértices, guardado y recuperación de sus zonas; colocación separada de los iconos en el esquema de pruebas. Esas posiciones son ilustrativas, no mediciones del centro comercial.
- Selección de niveles LAP 1–4, zoom del nivel 3 y regreso al espacio de pruebas conservando cámaras y zonas.
- Conteo C: 40 muestras, máximo estimado 15; conteo D: 37 muestras, máximo estimado 13. Son resultados del modelo y de las zonas configuradas, no conteos manualmente validados.
- Seguimiento final `a79ee98f`: C, 200 muestras hasta 39,8 s y máximo 12 observaciones; D, 182 muestras hasta 36,19 s y máximo 11. IDs locales y sin proyección inventada al suelo.
- Reproducción de originales con observaciones; pausa, reinicio y saltos temporales en ambas tomas. Los videos y resultados sobreviven al reinicio del servidor.

Las primeras ejecuciones de desarrollo que no contenían detecciones se apartaron del historial operativo en `data/replay-test-artifacts`. No se reemplazaron los videos originales ni los datos de A/B.
