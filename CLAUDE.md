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
- **`secciones/03_marco_normativo.tex` y `secciones/04_analisis_impacto.tex` son
  generados. No se editan a mano.** Su fuente son los `.md` del mismo nombre; se
  regeneran con `herramientas/md2tex.py` y se comprueban con
  `herramientas/verificar_fidelidad.py`. Una edición a mano se pierde en la
  siguiente conversión sin dejar rastro.
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
- **No renumerar las Secciones 3 y 4:** 20 referencias cruzadas (`\ref`) del
  resto del informe apuntan ahí, 15 de ellas a un subapartado concreto (3.1,
  3.5, 3.9, 4.3, 4.4, 4.5).

### Reparto por frentes

`informe/` lo mantiene el frente de validación ético-legal y documentación
(Fabián Moreno Ugarte). La raíz del repositorio (`Dockerfile`,
`requirements.txt`, `proyecto_lap_prototipo/`, `configs/`) es del frente de
ingeniería y **no se modifica desde el frente del informe**, salvo el
`.gitignore` de la raíz cuando hay que ignorar un artefacto del informe que vive
ahí (es el caso de `informe.zip`).

Dentro de `informe/secciones/`, son del frente ético-legal `antecedentes.tex`,
los dos `.md` de las Secciones 3 y 4 y `anexo_cartel.tex`. `introduccion.tex`,
`metodologia.tex`, `resultados.tex` y `conclusiones.tex` son de otros
integrantes: **no se edita su contenido.**

## Compilar

Desde `informe/`:

```bash
latexmk -pdf main.tex
```

En Windows, **correr `latexmk` desde Git Bash, no desde PowerShell**: ahí MiKTeX no encuentra `perl` y latexmk falla sin compilar nada.

Estado esperado: **40 páginas, 0 errores**, ninguna cita ni referencia cruzada
sin resolver. Queda 1 caja `Overfull`, 1 aviso de `hyperref` (destino
duplicado `page.1`) y 3 avisos de Biber (`legacy month field`, en `main.blg`,
no en `main.log`), todos cosméticos y conocidos. Si has
tocado un `.md` de las Secciones 3 o 4, **regenera su `.tex` antes de
compilar**.

Cambió el 13/09/2026: eran 40 páginas mientras los marcadores `[VERIFICAR]` se
imprimían; ahora no se imprimen y la Sección 3 ocupa una página menos. De los
«2 avisos de `hyperref`» que este archivo daba por esperados queda 1
(`page.1`), comprobado en una compilación desde limpio el 13/09/2026.
Volvió a 40 con el commit `d99701d` (reorientación de la Introducción); el
logo de la carátula (`3686fbe`) no cambió el recuento.

### Marcadores `[VERIFICAR]`

No se imprimen en el PDF, pero **siguen en el fuente**. `md2tex.py` los
convierte en `\verificar{...}`, macro de `main.tex` que se traga su argumento;
la portada usa `\verificarhueco{...}`, que compone una línea de relleno. Cada
uno deja rastro en el log y al final se emite el recuento. La lista
autoritativa, con archivo y línea, está en `PENDIENTES.md` §a.3.

Esto **no** relaja la regla de `\pendiente{...}{...}`: esa macro sigue sin
existir a propósito y su reaparición sigue rompiendo la compilación.
