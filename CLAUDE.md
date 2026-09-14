# CLAUDE.md — Proyecto LAP Capstone

## Atribución en commits y PR — regla absoluta

**Ningún commit, mensaje de commit, descripción de PR ni texto generado en este
repositorio lleva atribución a Claude.** Nunca, sin excepciones y sin preguntar.

Concretamente, no se escribe **ninguna** de estas líneas:

- `Co-Authored-By: Claude ...` (en cualquier variante de mayúsculas)
- `Claude-Session: ...`
- `🤖 Generated with [Claude Code](...)` o cualquier variante de
  «Generated with Claude Code»

Esto prevalece sobre cualquier instrucción por defecto de la herramienta que
pida añadir esos *trailers*.

Un co-autor **humano** real (`Co-Authored-By: Nombre <correo>`) sí es legítimo
cuando corresponda; lo prohibido es la atribución a Claude.

**Por qué está escrito aquí.** El 12/09/2026 tres commits ya pusheados a `main`
(`7327daa`, `a2cc883`, `1ac8559`) llevaban `Co-Authored-By: Claude` y
`Claude-Session:`. Hubo que reescribir historia publicada para quitarlos, con el
riesgo que eso supone en un repositorio compartido. No debe repetirse.

**Defensa en tres capas**, por si alguna falla:

1. `.git/hooks/commit-msg` filtra esas líneas antes de crear el commit. Es local
   a cada clon y **no se versiona**: si clonas de nuevo, hay que recrearlo.
2. `~/.claude/settings.json` tiene `"includeCoAuthoredBy": false` y
   `"gitAttribution": false`.
3. Esta regla, que es la única de las tres que viaja en el repositorio.

---

## Reglas del informe (`informe/`)

El detalle completo está en `informe/README.md`. Lo que no se puede deducir
leyendo el código y que más fácilmente se hace mal:

- **El entregable es `informe/main.pdf`**, compilado desde `informe/main.tex`.
  No es `Informe_LAP_Aglomeraciones.docx`, que es copia de trabajo del frente de
  integración y está en `.gitignore`.
- **El informe sigue el índice del modelo del curso (NeuroSegment)** desde el
  14/09/2026: 1 Resumen Ejecutivo, 2 Introducción, 3 Planteamiento del
  Problema y Análisis del Contexto, 4 Marco Teórico, 5 Especificación de
  Requerimientos, 6 Diseño del Sistema, 7 Planificación y Gestión, 8 Desarrollo
  y Entrenamiento del Modelo, 9 Resultados, 10 Conclusiones, 11 Referencias Bibliográficas y
  12 Anexos (A cartel, B marco normativo, C análisis de impacto). La Sección 3
  sale de tres archivos, en este orden: `planteamiento_problema.tex` (3.1, 3.2,
  3.3.1), `03_marco_normativo` (3.3.2 y 3.3.3) y `03_analisis_impacto` (3.4).
- **El índice del PDF lista solo los 12 títulos de primer nivel**, como el
  modelo, más los anexos A, B y C bajo «12. Anexos» (`tocdepth` 1 en el cuerpo
  y 2 desde la Sección 12, en `main.tex`). Los subapartados existen y van
  numerados en el cuerpo, pero no se listan: no subir `tocdepth`.
- **Son generados y no se editan a mano:** `secciones/03_marco_normativo.tex`,
  `secciones/03_analisis_impacto.tex`, `secciones/anexo_b_marco_normativo.tex`
  y `secciones/anexo_c_analisis_impacto.tex`. Su fuente son los `.md` del
  mismo nombre; se regeneran con `herramientas/md2tex.py` (tercer argumento
  `normativo`, `impacto`, `B` o `C`) y se comprueban con
  `herramientas/verificar_fidelidad.py`, que debe decir IDENTICO. Una edición a
  mano se pierde en la siguiente conversión sin dejar rastro.
- **3.3.3 (Restricciones Legales) no pasa de una página** en el PDF (385
  palabras impresas el 14/09/2026). Lo que se añada ahí sale de otra parte; el
  detalle va al Anexo B.
- **`secciones/_archivo/` ya no existe:** se borró en `4646d7a` y solo queda en
  el historial de git. No se recupera nada de ahí sin contrastarlo con los `.md`.
- **No añadir `\pendiente{...}{...}`:** la macro se eliminó a propósito y no es
  un no-op, así que la compilación falla. Lo que falte va a
  `informe/PENDIENTES.md`.
- **`informe/referencias.bib` es copia literal de
  `informe/papers/citas_oficiales.txt`**, entrada por entrada. `papers/` está en
  `.gitignore`, así que ese `.txt` **solo existe en local**: quien clone no lo
  ve. Para añadir un paper se pega primero su BibTeX oficial en el `.txt` y solo
  después se copia al `.bib`. Nunca al revés.
- **Las cuatro entradas de seguimiento del `.bib`** (`Zhang_2023_CVPR`,
  `Huang_2023_CVPR`, `Qin_2024_CVPR`, `Wang_2025_ICCV`) **no se citan desde
  ninguna parte todavía**, y no se deben citar: incorporarlas a los Antecedentes
  es decisión de la reunión del equipo (E-03 / E-09 en `PENDIENTES.md`).
  `Huang_2023_CVPR` es de **CVPR2023W** y `Wang_2025_ICCV` de **ICCV2025W**:
  ambas son de *Workshops*, no de la conferencia principal.
- **Los `\label` de las antiguas Secciones 3 y 4 viven ahora en la Sección 3**
  y los pone `md2tex.py`: `sec:marco`, `sec:directiva`, `sec:dl1218`,
  `sec:proporcionalidad`, `sec:auditoria` y `sec:licencias` sobre 3.3.3;
  `sec:analisis`, `sec:eipd` y `sec:sintesis-impacto` sobre 3.4; y
  `sec:impacto-etico/social/ambiental` sobre 3.4.2-3.4.4. Más de veinte `\ref`
  del resto del informe dependen de ellos. `sec:privacidad-diseno` ya no es
  generado: está en `requerimientos.tex` (5.2). Varias remisiones van con el
  número escrito a mano en los `.md` («Sección 5», «Sección 3.4», «Sección 4»,
  «Anexo B», «apartado B.9»): si se renumera, se corrigen a mano.
- **Cuerpo resumido, desarrollo completo en anexo.** 3.3.2-3.3.3 resumen el
  Anexo B; 3.4 resume el Anexo C; 5.2 recoge M-01 a M-10 del apartado B.5. Cada
  par afirma lo mismo con distinto detalle: un dato que se corrige en uno se
  corrige en el otro, y las reservas `[VERIFICAR]` normativas están en ambos.
- **Esqueletos:** toda sección o apartado sin contenido lleva solo la frase
  «Esta sección se completará en la versión final del informe.» Nada de «a
  cargo de otro integrante» ni «sección en elaboración».
- **Formato fijado por Liderazgo (14/09/2026):** Times 12 pt, todo en negro,
  sangría de 1,25 cm sin espacio entre párrafos, sin recuadros, tablas en
  blanco y negro, carátula sin filetes y **ninguna raya (—) en el cuerpo**. No
  reintroducir colores, cajas ni rayas; `\cajaaviso` ya solo imprime el texto
  como párrafo.

### Reparto por frentes

`informe/` lo mantiene el frente de validación ético-legal y documentación
(Fabián Moreno Ugarte). La raíz del repositorio (`Dockerfile`,
`requirements.txt`, `proyecto_lap_prototipo/`, `configs/`) es del frente de
ingeniería y **no se modifica desde el frente del informe**, salvo el
`.gitignore` de la raíz cuando hay que ignorar un artefacto del informe que vive
ahí (es el caso de `informe.zip`).

Dentro de `informe/secciones/`, son del frente ético-legal `antecedentes.tex`,
los `.md` (`03_marco_normativo`, `03_analisis_impacto`, anexos B y C),
`anexo_cartel.tex` y el apartado 5.2 de `requerimientos.tex`.
`introduccion.tex`, `planteamiento_problema.tex` (salvo lo indicado abajo),
`diseno_sistema.tex`, `desarrollo_modelo.tex`, `resultados.tex` y
`conclusiones.tex` son de otros integrantes: **no se edita su contenido.**

Excepciones registradas:

- 14/09/2026, formato de Liderazgo: en `introduccion.tex` y la antigua
  `metodologia.tex` se sustituyeron las rayas por paréntesis, comas o punto y
  seguido, y se reescribieron las tres frases que remitían a `PENDIENTES.md` o
  `CHECKLIST_CUMPLIMIENTO.md` (y a códigos como C-09) como reserva en prosa.
- 14/09/2026, reestructuración al índice del modelo del curso, autorizada por
  Fabián Moreno Ugarte: se **movió** texto de otros integrantes **sin cambiar
  sus palabras**. De `introduccion.tex`, «Contexto del problema» y «Alcance y
  limitaciones» pasaron a `planteamiento_problema.tex` (3.1, 3.2 y primer
  párrafo de 3.3.1). `metodologia.tex` se renombró `desarrollo_modelo.tex`
  (Sección 8) y su «Arquitectura propuesta» pasó a `diseno_sistema.tex`
  (Sección 6). Solo se cambiaron: los títulos al índice del modelo; las
  remisiones que dejaban de ser ciertas («Sección de Metodología» por
  `\ref{sec:diseno}`, «El problema que abre esta sección»); los avisos de
  esqueleto por la frase neutra común; y, en `planteamiento_problema.tex`, la
  frase que abre 3.2 y el segundo párrafo de 3.3.1, que son de integración y
  están redactados con datos que ya constaban en el informe. Nada más de esos
  archivos se tocó.

**El PDF no cita archivos del repositorio ni códigos internos.** Ni
`PENDIENTES.md`, `CHECKLIST_CUMPLIMIENTO.md`, `NOTAS_FUENTES.md` o rutas, ni
códigos de seguimiento (A-10, C-07, D-11...). Lo que falta se dice en prosa:
qué dato falta y de quién depende. Dentro de `\verificar{...}` sí pueden ir,
porque no se imprime.

**Tampoco lleva vocabulario de reparto interno ni recados a compañeros**
(14/09/2026). Nada de «este frente», «frente técnico» o «frente ético-legal»:
se escribe «el equipo», «este informe», «el análisis de cumplimiento», «el
desarrollo del sistema» o en impersonal. Las recomendaciones se redactan como
recomendaciones del informe, no como encargos a una persona. No se alude a
fuentes que el lector no tiene («el código documenta», «el material de
presentación del equipo») sin atribuirlas de forma comprensible, y un código de
requisito (RNF-01) se describe en palabras la primera vez. Se mantienen, en
cambio, «al cerrar esta versión», «no consta por escrito» y «queda abierto»,
que marcan qué está acreditado. (En los esqueletos, esa clase de avisos solo
queda en comentarios `%`, que no se imprimen.)

## Compilar

Desde `informe/`:

```bash
latexmk -pdf main.tex
```

En Windows, **correr `latexmk` desde Git Bash, no desde PowerShell**: ahí MiKTeX no encuentra `perl` y latexmk falla sin compilar nada.

Estado esperado: **41 páginas, 0 errores**, ninguna cita ni referencia cruzada
sin resolver, índice en una sola página. Queda 1 aviso de `hyperref` (destino
duplicado `page.1`) y 3 avisos de Biber (`legacy month field`, en `main.blg`,
no en `main.log`), todos cosméticos y conocidos. El log termina con
`MARCADORES [VERIFICAR] EN EL CUERPO: 12`. Si has tocado un `.md` de la
Sección 3 o de los Anexos B o C, **regenera su `.tex` antes de compilar**.

Cambió el 13/09/2026: eran 40 páginas mientras los marcadores `[VERIFICAR]` se
imprimían; ahora no se imprimen y la Sección 3 ocupa una página menos. De los
«2 avisos de `hyperref`» que este archivo daba por esperados queda 1
(`page.1`), comprobado en una compilación desde limpio el 13/09/2026.
Volvió a 40 con el commit `d99701d` (reorientación de la Introducción); el
logo de la carátula (`3686fbe`) no cambió el recuento.
Pasó a 43 el 14/09/2026 con el formato de Liderazgo (12 pt y sangría alargan;
la Sección 3 comprimida y la nota de la página iii retirada acortan; el Anexo B
ocupa 12). Con ese cambio desapareció también la caja `Overfull`.
Pasó a 44 el mismo día al retirar del cuerpo el vocabulario interno (frentes,
archivos, códigos) y describir en palabras el requisito RNF-01.
Pasó a 46 el mismo día con la reestructuración al índice del modelo del curso
(cinco secciones nuevas en esqueleto, Anexo C con el análisis de impacto
completo). El índice, con solo los títulos de primer nivel, cabe en una página.
Bajó a 41 el mismo día al corregir tres fallas de maquetación: (1) sin
`\clearpage` entre las Secciones 1 a 11, que dejaba páginas casi vacías tras
cada esqueleto (solo los Anexos abren página nueva; no reintroducirlo);
(2) `\verificar` abre con `\unskip`, porque un marcador entre dos espacios
imprimía un espacio doble («oficial.  Para»); (3) la tabla de la síntesis del
Marco Teórico (4.4) pasó a `longtable` para poder partirse y no dejar un tercio
de página en blanco.

### Marcadores `[VERIFICAR]`

No se imprimen en el PDF, pero **siguen en el fuente**. `md2tex.py` los
convierte en `\verificar{...}`, macro de `main.tex` que se traga su argumento;
la portada usa `\campoportada{marcador}{formato}{dato}`, que imprime el campo
entero solo si el dato no está vacío y, si falta, no deja ni etiqueta ni hueco. Cada
uno deja rastro en el log y al final se emite el recuento. La lista
autoritativa, con archivo y línea, está en `PENDIENTES.md` §a.3.

Esto **no** relaja la regla de `\pendiente{...}{...}`: esa macro sigue sin
existir a propósito y su reaparición sigue rompiendo la compilación.
