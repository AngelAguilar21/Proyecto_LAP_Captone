# Guía de uso de AeroTrack

Inicia el sistema con `iniciar_sistema.cmd` (o `iniciar_sistema.ps1`) y abre http://127.0.0.1:8765/?view=overview.
Cómo funciona por dentro: `docs/ARQUITECTURA.md`.

## 1. Crear el proyecto

En **Proyectos → Nuevo proyecto** escribe un nombre único y pulsa **Crear y configurar**. Solo el rol operador configura
plano y cámaras; el administrador crea proyectos y ajusta alertas. Con una sesión activa no se puede editar: finalízala antes.

## 2. Configurar (Configuración → Espacio completo)

1. **Proyecto**: nombre del espacio, terminal y nivel, y tipo de fuente (**Videos grabados** o **Cámaras en vivo**).
2. **Plano**: elige un nivel del LAP, importa una imagen o PDF, o dibújalo con puntos y líneas.
3. **Conexión**: añade cada cámara con su archivo, ruta o URL (USB, RTSP, IP) y pulsa **Probar esta fuente**.
4. **Zona útil**: con **Obtener imagen**, arrastra los vértices para dejar solo el suelo real (fuera espejos, pantallas,
   vidrios y otros pisos). Lo que queda fuera se dibuja en gris en el video: YOLO lo ve, pero no cuenta. Aquí también puedes
   añadir **accesos de locales**: una línea sobre el umbral de la puerta, con áreas interior y exterior.
5. **Homografía y cámaras relacionadas**
   - **A · Puntos del suelo** (opcional): marca un punto del suelo en el video y luego el mismo punto en el plano. Al menos 4;
     mejor 6 a 8 repartidos por donde camina la gente. Usa esquinas de baldosas, bases de columnas o cruces visibles; nunca
     cabezas ni objetos elevados. Si otra cámara ve el mismo suelo, reutiliza sus puntos (aparecen como círculos punteados).
     **Validar homografía** muestra el error de cada punto y la huella de la imagen en el plano.
   - **B · La misma persona en dos cámaras** (necesario con 2 o más cámaras): elige dos cámaras, mueve cada video al instante
     en que se ve a la misma persona y marca sus **pies** en ambas. Con **4 parejas** las cámaras quedan **relacionadas**: el
     monitoreo podrá reconocer a una persona cuando pase de una a otra. Las mismas parejas miden el desfase de tiempo entre
     los videos (se corrige solo) y, si las dos cámaras tienen puntos del suelo, si sus homografías concuerdan. Repite con
     cada par de cámaras que se vean o se sucedan. Abajo se listan las cámaras relacionadas del proyecto.
6. **Contexto comercial**: indica si hay negocios y registra sus medidas. Define la alerta general: cuántas personas
   próximas y durante cuántos segundos.
7. **Revisión**: cuando todo esté «Preparado», **Guardar y abrir monitoreo**.

## 3. Monitorear (Vista general)

- **Procesar niveles**: analiza las cámaras activas de todos los niveles o solo las del nivel visible.
- **Asociar recorridos**: une a las personas entre cámaras relacionadas. Necesita las cámaras sincronizadas (paso 5B).
- **Recorte en grupos**: en grupos, aprovecha la parte visible de cada persona en vez de descartar la vista.
- **Rendimiento**: Automático elige según el número de cámaras; Preciso analiza cada 0,2 s, Equilibrado 0,4 s, Rápido 0,6 s.
  En CPU, con varias cámaras, el análisis va más lento que el video.

Una persona recién vista lleva un ID provisional (`T…`) hasta confirmarse; los provisionales se dibujan pero no cuentan. Al
terminar, la grabación queda con IDs finales `P00001`..`P0000N`.

## 4. Revisar (Videos y resultados, Reportes)

En **Videos y resultados** eliges análisis y nivel; los videos comparten reproducción, pausa, saltos de 5 s y velocidad.
La capa del video muestra **personas y recorridos** o **presencia acumulada**. **Reportes** exporta CSV, XLSX y PDF:
sectores con más presencia (S1, S2… con «Ubicar»), eventos de accesos, ocupación y trayectorias.

## 5. Cómo leer las métricas

- **Personas en una muestra**: observaciones en ese instante, no visitantes únicos.
- **Máximo** e instante: mayor ocupación observada. **Promedio**: presencia media del periodo.
- **Aglomeración**: un grupo supera la cantidad de personas durante el tiempo configurados. Los avisos son visuales y se
  cierran solos; los episodios quedan en los resultados.
- **Presencia acumulada**: dónde permanecieron más tiempo; no son personas simultáneas.
- **Entradas y salidas**: cruces de una línea de acceso confirmados en ambas áreas. Aparecer dentro del local no cuenta.
- Cámaras que se solapan pueden ver a la misma persona: no sumes IDs locales de varias cámaras como visitantes únicos.

## 6. Cuándo volver a configurar

- Cambiaste la zona útil, la fuente o los accesos: vuelve a procesar (lo descartado antes no se recupera).
- Cambiaste los puntos del suelo: la Vista general reproyecta las posiciones; no hace falta reprocesar.
- La cámara cambió de zoom u orientación: recalibra sus puntos del suelo.
- El panel avisa que la misma persona queda lejos entre dos cámaras: sus puntos del suelo no concuerdan; recalibra usando
  los mismos puntos del plano en ambas.

## Fuentes en vivo y cartografía

Las fuentes en vivo requieren URL, credenciales autorizadas y acceso a la red; no se archiva su video. Para marcar a la misma
persona en dos cámaras hacen falta videos grabados; con cámaras en vivo se declara en la revisión que comparten la hora. Los
cuatro niveles del LAP son datos vectoriales locales (`dashboard/public/maps/lap/`), con atribución a Living Map/LAP; para
un producto con LAP corresponde obtener su cartografía autorizada.
