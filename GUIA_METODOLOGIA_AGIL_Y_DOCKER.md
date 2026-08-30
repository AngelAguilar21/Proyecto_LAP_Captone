# Guía de trabajo en equipo — Proyecto LAP

Esta guía cubre tres cosas: (1) la metodología ágil para organizar tareas y ver el estado de cada quien, (2) si conviene o no usar Docker y cómo configurarlo paso a paso, y (3) cómo funciona la automatización de actas y recordatorios.

---

## 1. Metodología ágil: Kanban semanal en GitHub Projects

No usaremos Scrum con sprints de 2 semanas porque solo nos vemos una vez por semana (miércoles). En su lugar, cada semana de clase es un "ciclo": se cierran tareas de la semana anterior y se abren las nuevas, coordinado con el acta.

### 1.1 Configurar el tablero (una sola vez, ~10 minutos)

1. En el repositorio de GitHub, ir a la pestaña **Projects** → **New project** → elegir la plantilla **Board**.
2. Crear estas columnas (renombrando las que vienen por defecto):
   - **Backlog** — ideas o tareas futuras, aún no asignadas a una semana.
   - **Por hacer (esta semana)** — lo que se acordó en el acta de la última reunión.
   - **En progreso** — alguien ya está trabajando en ello.
   - **En revisión** — el trabajo está listo y espera que otro integrante lo revise (código, documento, etc.).
   - **Hecho** — cumple la Definition of Done (ver 1.4).
3. Crear las etiquetas (**Labels**, en la pestaña Issues) por rol, una por integrante/función, con un color distinto:
   - `líder-integración` (Ángel)
   - `ciencia-de-datos` (Stephano)
   - `ingeniería-de-datos` (José)
   - `ética-documentación` (Fabián)
   - Etiquetas adicionales de tipo: `investigación`, `código`, `docs`, `bug`.
4. Crear un **Milestone** por semana de clase (`Semana 1 - 26/08`, `Semana 2 - 02/09`, etc.), con fecha de vencimiento = la siguiente clase. Esto reemplaza tener que buscar la fecha límite en el acta cada vez.

### 1.2 Crear una tarea (Issue)

Cada tarea del acta se convierte en un Issue de GitHub (ya dejé la plantilla lista en `.github/ISSUE_TEMPLATE/tarea.md`, dentro de este mismo paquete de archivos). Al crear un Issue nuevo, GitHub la ofrecerá automáticamente. Debe llevar:
- Responsable (**Assignee**).
- Etiqueta de rol + tipo (**Labels**).
- Milestone de la semana correspondiente.
- Checklist de subtareas si la tarea es grande (usar `- [ ] subtarea` en la descripción).

Luego se arrastra la tarjeta a la columna que corresponda según el avance.

### 1.3 Ritual semanal (reemplaza los "daily standups")

Como solo se reúnen una vez por semana, el inicio de cada clase (antes de entrar al tema técnico) cumple la función de standup:
1. Cada integrante mueve sus propias tarjetas al estado real (no lo hace el líder por ellos).
2. Cada uno dice en 1 minuto: qué avanzó, qué le falta, y si tiene algún bloqueo.
3. El líder (tú) cierra los Issues de "Hecho" que ya fueron validados y abre los nuevos Issues de la semana según lo que se acuerde en la reunión, moviéndolos a "Por hacer".

### 1.4 Definition of Done (cuándo una tarea pasa a "Hecho")

Para evitar discusiones de "¿esto ya está o no?", una tarea solo pasa a Hecho si:
- Es código: está subido a una rama y al menos otro integrante lo revisó (aunque sea informalmente, no hace falta un Pull Request formal todavía).
- Es investigación/documentación: el documento está en la carpeta correspondiente del repo o del Drive, y fue mencionado en el acta de esa semana.
- Es una entrega para el docente: está subida a la carpeta que él habilitó.

---

## 2. ¿Necesitamos Docker? Sí, recomendado — pero en su versión simple

**Veredicto:** no es 100% obligatorio para que el proyecto funcione, pero si van a compartir código de visión por computadora (OpenCV, PyTorch) entre computadoras distintas (Windows, Mac, Linux), es la causa más común de "en mi máquina sí corre" y vale la pena invertir los 20-30 minutos de configuración inicial para ahorrarse ese dolor de cabeza más adelante.

Lo que **no** recomiendo todavía es una configuración con GPU dentro de Docker (nvidia-docker, versiones de CUDA, etc.) — eso es bastante más complejo y para un proyecto de curso probablemente van a entrenar/probar modelos pesados en Google Colab o Kaggle (que ya traen GPU lista) y usar Docker solo para el código de CPU: preprocesamiento, pruebas del pipeline, y todo lo que no requiera entrenamiento pesado.

### 2.1 Paso a paso para configurar Docker (una vez, lo hace quien tenga el repo)

1. Instalar Docker Desktop (Windows/Mac) o Docker Engine (Linux) — <https://docs.docker.com/get-docker/>. Cada integrante lo instala una sola vez en su computadora.
2. Copiar los tres archivos que dejé en este paquete a la raíz del repositorio: `Dockerfile`, `docker-compose.yml`, `requirements.txt`. Ya vienen con las librerías básicas de CV (OpenCV, PyTorch CPU, Ultralytics/YOLO, numpy, matplotlib).
3. Desde la raíz del repo, construir la imagen (solo la primera vez, o cuando cambien las dependencias):
   ```bash
   docker compose build
   ```
4. Levantar el entorno:
   ```bash
   docker compose up -d
   ```
5. Entrar al contenedor para trabajar dentro de él (es como abrir una terminal que ya tiene todo instalado):
   ```bash
   docker compose exec app bash
   ```
6. Cada integrante edita el código normalmente en su editor (VS Code, etc.) en su propia carpeta del repo — el `docker-compose.yml` ya monta esa carpeta dentro del contenedor (`volumes`), así que los cambios se ven al instante sin tener que reconstruir la imagen. Solo hay que reconstruir (`docker compose build`) si alguien agrega una librería nueva a `requirements.txt`.
7. Para bajar el entorno al terminar: `docker compose down`.

### 2.2 Cuándo SÍ conviene reconstruir la imagen

Cada vez que alguien agregue una línea nueva a `requirements.txt` (una librería nueva), debe avisar en el chat del equipo y todos corren `docker compose build` de nuevo antes de seguir trabajando. Esto evita el error clásico de "a mí me funciona porque tengo instalada una versión distinta de OpenCV".

---

## 3. Automatización: actas y recordatorios

### 3.1 Resumen de reunión (bajo demanda, no automático)

Como acordamos, esto no corre solo en segundo plano — el flujo es:
1. Grabas la reunión (o subes el audio/transcripción a la carpeta de Drive del proyecto, como ya hicimos con la primera).
2. Me avisas en el chat que hay una transcripción nueva.
3. Genero el borrador del acta siguiendo la misma plantilla ya usada, más un resumen ejecutivo corto que puedas reenviar rápido al grupo del equipo.

No hace falta ninguna configuración adicional para esto — simplemente avísame cuando toque.

### 3.2 Recordatorios automáticos por correo

Acordamos que tú envías el primer mensaje (la explicación de este nuevo sistema al equipo) y, de ahí en adelante, yo me encargo de mandar los recordatorios semanales por correo.

Para armar esto todavía necesito dos cosas tuyas:
1. **El correo de Stephano, José y Fabián** (para poder escribirles directamente).
2. **Confirmar el día/hora del recordatorio** — mi sugerencia es el martes en la noche, la víspera de cada clase del miércoles, para que lleguen frescos con su tarea a la reunión.

Ojo con una limitación honesta: no tengo acceso directo al tablero de GitHub Projects (no hay un conector de GitHub disponible en esta sesión), así que no puedo "leer" automáticamente qué tarjeta está atrasada. Lo que sí puedo hacer, y que resuelve el mismo problema en la práctica: guardo la tabla de tareas de cada acta (responsable, tarea, fecha límite) en el Proyecto de Claude compartido, y cada semana el recordatorio automático se arma leyendo esa tabla — o sea, en cuanto generamos el acta de la semana, ya queda la fuente de verdad lista para que el recordatorio la use. Si más adelante quieres que también lea el estado real del tablero de GitHub, se podría conectar ese conector desde la configuración de Cowork y lo integro.

En cuanto me pases los correos, dejo programado el envío automático.
