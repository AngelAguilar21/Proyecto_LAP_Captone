# Informe Capstone I — Aglomeraciones LAP

Informe de Capstone I (Universidad ESAN, Ingeniería de IA). Sistema de visión
computacional para estimar aglomeraciones de personas en el Aeropuerto
Internacional Jorge Chávez, para Lima Airport Partners (LAP).

> ## El entregable es el PDF de LaTeX — 11 de septiembre de 2026 (tarde)
>
> **`main.pdf`, compilado desde `main.tex`, es el entregable.** El informe se
> consolidó en LaTeX y el PDF vuelve a contener el documento completo: 40
> páginas, 0 errores, sin citas ni referencias cruzadas sin resolver.
>
> Esto **revierte** el cambio de herramienta de la mañana del mismo día, que
> había declarado el PDF «legado» y puesto a `Informe_LAP_Aglomeraciones.docx`
> como entregable. Ese `.docx` sigue existiendo como copia de trabajo del frente
> de integración, pero **no se versiona** (está en `.gitignore`) y **no es el
> entregable**. Si este README contradijera a alguna versión anterior de sí
> mismo, manda esta.
>
> Overleaf no se recuperó y no se va a usar: la compilación dejó de funcionar
> por el límite de la cuenta gratuita. Se compila en local.

| Integrante | Frente |
|---|---|
| Angel Aguilar | Liderazgo e integración |
| Stephano Rivadeneyra | Ciencia de datos |
| José Ortega | Ingeniería de datos |
| Fabián Moreno Ugarte | Validación ética/legal y documentación |

Este repositorio lo mantiene el frente de validación ético-legal y
documentación.

---

## Dónde se edita el documento

El repositorio es el sitio donde se trabaja. No hay copia de referencia externa.

| Qué | Se edita en | Se genera | Quién |
|---|---|---|---|
| **Apartados 3.3.2-3.4 y Anexos B y C** | `secciones/03_marco_normativo.md`, `secciones/03_analisis_impacto.md`, `secciones/anexo_b_marco_normativo.md` y `secciones/anexo_c_analisis_impacto.md` | el `.tex` del mismo nombre, con `herramientas/md2tex.py` | Frente ético-legal |
| Resto de secciones y Anexo A | `secciones/*.tex`, directamente | — | Sus responsables |
| **Entregable** | no se edita: se compila | `main.pdf`, con `latexmk -pdf main.tex` | Frente ético-legal |

Hay, por tanto, **dos clases de sección** y conviene no confundirlas:

- **Secciones escritas en `.tex`.** Se editan en el `.tex` y ya está. Son todas
  salvo las de la línea siguiente, incluido el Anexo A.
- **Apartados 3.3.2, 3.3.3 y 3.4 y Anexos B y C, escritos en `.md`.** El `.md`
  es la **fuente**; el `.tex` es **producto derivado** y se regenera. Nunca se
  edita a mano.

> **Índice del modelo del curso (14/09/2026).** El informe sigue el índice del
> modelo NeuroSegment: 1 Resumen Ejecutivo, 2 Introducción, 3 Planteamiento del
> Problema y Análisis del Contexto, 4 Marco Teórico, 5 Especificación de
> Requerimientos, 6 Diseño del Sistema, 7 Planificación y Gestión, 8 Desarrollo
> y Entrenamiento del Modelo, 9 Resultados, 10 Conclusiones, 11 Referencias Bibliográficas y
> 12 Anexos. La Sección 3 se compone de `planteamiento_problema.tex` (3.1, 3.2 y
> 3.3.1), `03_marco_normativo` (3.3.2 Restricciones Éticas y 3.3.3 Restricciones
> Legales) y `03_analisis_impacto` (3.4). El marco normativo completo está en el
> **Anexo B** y el análisis de impacto completo en el **Anexo C**; los
> requisitos de privacidad M-01 a M-10 están en la Sección 5.2. Cada resumen y
> su anexo afirman lo mismo con distinto detalle: **un dato que se corrija en
> uno se corrige en el otro.** 3.3.3 no pasa de una página.

El motivo de la asimetría es que las Secciones 3 y 4 se habían pasado a Markdown
durante el episodio de Overleaf. Al volver a LaTeX no se rehízo el trabajo a
mano: se automatizó la conversión, que es reproducible y verificable palabra por
palabra. Unificar todo en un solo formato sigue abierto como **E-08** en
`PENDIENTES.md`.

### Cómo se regeneran los archivos escritos en `.md`

Desde `informe/`, después de tocar cualquiera de los cuatro `.md`:

```bash
py herramientas/md2tex.py secciones/03_marco_normativo.md       secciones/03_marco_normativo.tex       normativo
py herramientas/md2tex.py secciones/03_analisis_impacto.md      secciones/03_analisis_impacto.tex      impacto
py herramientas/md2tex.py secciones/anexo_b_marco_normativo.md  secciones/anexo_b_marco_normativo.tex  B
py herramientas/md2tex.py secciones/anexo_c_analisis_impacto.md secciones/anexo_c_analisis_impacto.tex C
py herramientas/verificar_fidelidad.py secciones/03_marco_normativo.md       secciones/03_marco_normativo.tex
py herramientas/verificar_fidelidad.py secciones/03_analisis_impacto.md      secciones/03_analisis_impacto.tex
py herramientas/verificar_fidelidad.py secciones/anexo_b_marco_normativo.md  secciones/anexo_b_marco_normativo.tex
py herramientas/verificar_fidelidad.py secciones/anexo_c_analisis_impacto.md secciones/anexo_c_analisis_impacto.tex
latexmk -pdf main.tex
```

- El tercer argumento de `md2tex.py` (`normativo`, `impacto`, `B` o `C`) fija
  el nivel de los encabezados y la tabla de `\label`. Esos `\label` sostienen las referencias cruzadas del resto del
  informe.
- `md2tex.py` **no reescribe prosa**: solo traduce marcado. Una ejecución limpia
  no imprime ningún `AVISO`; si imprime alguno, hay una construcción Markdown no
  prevista que hay que revisar a mano.
- `verificar_fidelidad.py` compara la prosa del `.md` con la del `.tex` palabra
  por palabra. La salida esperada es `IDENTICO` en los cuatro archivos.
- **El texto del informe no cita archivos del repositorio** (`PENDIENTES.md`,
  `CHECKLIST_CUMPLIMIENTO.md`, `NOTAS_FUENTES.md`, rutas) **ni códigos internos**
  (A-10, C-07...). Lo que falta se escribe como reserva en prosa: qué dato falta
  y de quién depende. Esos nombres solo pueden ir en comentarios o dentro de
  `[VERIFICAR: ...]`, que no se imprime.

### Qué NO hacer

- **No editar `secciones/03_marco_normativo.tex`,
  `secciones/03_analisis_impacto.tex`, `secciones/anexo_b_marco_normativo.tex`
  ni `secciones/anexo_c_analisis_impacto.tex`.**
  Son generados. Cualquier edición a mano
  se pierde en la siguiente conversión, y sin dejar rastro. El cambio va al
  `.md`.
- **No reintroducir `secciones/_archivo/`.** La carpeta (con
  `marco_etico_legal.tex`, `analisis_impacto.tex` y su `README.md`) se borró del
  repositorio en el commit `4646d7a` y solo queda en el historial de git. Nada de
  ahí se recupera sin revisarlo antes contra los `.md`, porque el texto divergió.
- **No editar el texto del informe en el `.docx`.** No es el entregable ni está
  versionado. Lo que cambie ahí no llega al PDF.
- **No tocar los `\label{...}`** de ninguna sección: el documento compilaría con
  referencias `??`.
- **No añadir `\pendiente{...}{...}`.** La macro se eliminó de `main.tex` a
  propósito y no se dejó como no-op: si alguien la escribe, la compilación
  falla. Es la salvaguarda que impide que un marcador de relleno reaparezca en
  el PDF. Lo que falte va a `PENDIENTES.md`.

---

## Qué contiene el repositorio

El informe vive en la subcarpeta `informe/` del repositorio del equipo. La raíz
del repositorio es del frente de ingeniería (`Dockerfile`, `requirements.txt`,
`Tareas equipo.md`) y **no se toca desde aquí**, salvo su `.gitignore` cuando
hay que ignorar un artefacto del informe que vive en la raíz (es el caso de
`informe.zip`).

```
Proyecto_LAP_Captone/
├── README.md                       raíz: README del proyecto
├── CLAUDE.md                       raíz: reglas para el asistente de código
├── Dockerfile                      raíz: frente de ingeniería
├── dockercompose.yml               raíz: frente de ingeniería
├── requirements.txt                raíz: frente de ingeniería
├── .gitmodules                     raíz: submódulo P2PNet del prototipo
├── configs/  docs/  reports/  scripts/  src/   raíz: frente de ingeniería
├── proyecto_lap_prototipo/         raíz: prototipo (frente de ingeniería)
├── Tareas equipo.md                raíz: coordinación del equipo
├── .gitignore                      raíz: Python, datos, prototipo, .env, .claude/ + informe.zip
├── informe.zip                     IGNORADO: empaquetado puntual, no fuente
└── informe/                        ← todo lo de este README
    ├── main.tex                    preámbulo, portada y \input de secciones
    ├── main.pdf                    ← EL ENTREGABLE (compilado, versionado)
    ├── referencias.bib             copia LITERAL de papers/citas_oficiales.txt
    ├── .gitignore                  reglas de LaTeX; solo rigen dentro de informe/
    ├── .gitattributes              fija LF en los fuentes; solo rige aquí dentro
    ├── Informe_LAP_Aglomeraciones.docx   IGNORADO: copia de trabajo de Ángel
    ├── INFORME_COMPLETO_ANGEL.md    consolidación en Markdown del frente de integración
    ├── PENDIENTES.md               puntos abiertos, agrupados por quién los cierra
    ├── RESUMEN_ANTECEDENTES.md     los tres papers en prosa, sin LaTeX de por medio
    ├── RESUMEN_4_ANTECEDENTES_TRACKING.md   resumen de los cuatro antecedentes de tracking
    ├── NOTAS_FUENTES.md            trazabilidad de cada afirmación del informe
    ├── CHECKLIST_CUMPLIMIENTO.md   estado de cumplimiento
    ├── README.md                   este archivo
    ├── imagenes/
    │   └── logo-esan.png           logo de la carátula
    ├── herramientas/
    │   ├── md2tex.py               conversor .md -> .tex (3.3.2-3.4, Anexos B y C)
    │   └── verificar_fidelidad.py  comprueba la conversión palabra por palabra
    ├── papers/                     IGNORADO: PDFs fuente + citas_oficiales.txt
    ├── fichas_antecedentes/        fichas A2, B1-B3, C1-C4
    └── secciones/
        ├── resumen_ejecutivo.tex       1   esqueleto
        ├── introduccion.tex            2   otro integrante
        ├── planteamiento_problema.tex  3.1-3.3.1 (texto movido de la Introducción)
        ├── 03_marco_normativo.md       3.3.2-3.3.3 ← FUENTE (frente ético-legal)
        ├── 03_marco_normativo.tex         GENERADO — no editar
        ├── 03_analisis_impacto.md      3.4 ← FUENTE (frente ético-legal)
        ├── 03_analisis_impacto.tex        GENERADO — no editar
        ├── antecedentes.tex            4   Marco Teórico ← frente ético-legal
        ├── requerimientos.tex          5   (5.2 del frente ético-legal)
        ├── diseno_sistema.tex          6   esqueleto, otro integrante
        ├── planificacion.tex           7   esqueleto
        ├── desarrollo_modelo.tex       8   esqueleto, otro integrante
        ├── resultados.tex              9   esqueleto, otro integrante
        ├── conclusiones.tex            10  esqueleto, otro integrante
        ├── anexo_cartel.tex            A ← frente ético-legal
        ├── anexo_b_marco_normativo.md  B ← FUENTE (frente ético-legal)
        ├── anexo_b_marco_normativo.tex    GENERADO — no editar
        ├── anexo_c_analisis_impacto.md C ← FUENTE (frente ético-legal)
        └── anexo_c_analisis_impacto.tex   GENERADO — no editar
```

Todos los comandos de este README se ejecutan **desde `informe/`**, no desde la
raíz del repositorio.

### Lo que está ignorado, y por qué importa saberlo

Tres cosas de esta carpeta no viajan en el repositorio. La primera tiene una
consecuencia que ya ha causado un problema real:

| Ignorado | Dónde se declara | Por qué |
|---|---|---|
| `papers/` | `informe/.gitignore` | PDFs de terceros: pesan varios MB, no nos corresponde redistribuirlos y no intervienen en la compilación |
| `Informe_LAP_Aglomeraciones.docx` | `informe/.gitignore` | Binario de 2 MB que Git no puede fusionar y que cambia en cada guardado. No es el entregable |
| `informe.zip` | `.gitignore` de la raíz | Empaquetado puntual de 14 MB con los PDF dentro. Es un artefacto, no fuente |

> **`papers/citas_oficiales.txt` solo existe en local.** Al estar `papers/`
> ignorado, ese archivo **no está en el repositorio**: quien clone ve
> `referencias.bib` pero no la copia oficial de la que procede. Eso es
> exactamente lo que ocurrió el 08/09/2026, cuando se añadieron cuatro entradas
> al `.bib` sin poder contrastarlas contra `citas_oficiales.txt`, y es la causa
> registrada de **E-09** en `PENDIENTES.md`. Si necesitas el archivo, pídelo al
> frente ético-legal; no intentes reconstruirlo desde el `.bib`.

Codificación: **UTF-8 sin BOM**, saltos de línea **LF**. Los acentos van escritos
directamente (`á`, no `\'a`). El LF lo fija `.gitattributes` para los `.tex`,
`.md`, `.bib` y `.py`, de modo que no depende de la configuración
`core.autocrlf` de cada máquina.

---

## Cómo compilar

Requiere **pdfLaTeX + Biber**, ambos incluidos en MiKTeX y TeX Live. El
documento principal es `main.tex` y requiere TeX Live 2025 o posterior (ver la
nota sobre `longtable`).

```bash
latexmk -pdf main.tex     # hace las pasadas y llama a Biber solo
latexmk -C                # limpia los auxiliares (y también main.pdf)
```

Sin `latexmk`, la secuencia manual es:

```bash
pdflatex main
biber main
pdflatex main
pdflatex main
```

Si has tocado uno de los `.md`, **antes hay que regenerar su `.tex`**: ver
«Cómo se regeneran los archivos escritos en `.md`» más arriba. Compilar sin
regenerar produce un PDF con la versión anterior de esa sección, sin avisar.

### Notas para Windows / MiKTeX

- `latexmk` es un script de Perl y MiKTeX **no incluye** un intérprete de Perl.
  Si aparece `MiKTeX could not find the script engine 'perl'`, basta con añadir
  al `PATH` el Perl que trae Git para Windows:

  ```powershell
  $env:PATH = "C:\Program Files\Git\usr\bin;$env:PATH"
  ```

  La alternativa es ejecutar la secuencia manual de cuatro comandos.
- Conviene dejar activada la instalación automática de paquetes:

  ```powershell
  initexmf --set-config-value "[MPM]AutoInstall=1"
  ```

### Nota sobre `longtable`

Las versiones **v4.24 a v4.26** de `longtable` (octubre–diciembre de 2025)
tienen una regresión: al partir entre páginas una tabla con columnas de tipo
`p{}`, pdfTeX emite

```
Infinite glue shrinkage found in box being split
```

y devuelve un código de salida distinto de cero, aunque igualmente genere el
PDF. **No depende de este documento:** se reproduce con un `longtable` mínimo de
una sola columna `p{}` que cruce un salto de página. Está corregido desde
**v4.27 (2026-01-28)**, que es la versión con la que se verificó este proyecto.

Si aparece ese error, hay dos salidas equivalentes:

- usar una distribución de TeX que traiga `longtable` <= v4.23 o >= v4.27; o
- pedir la versión estable antigua, cambiando en `main.tex`:
  ```latex
  \usepackage{longtable}[=v4.13]
  ```
  Funciona, pero deja el aviso `Command \LT@p@ftntext has changed`.

Hay un comentario con esta misma explicación junto a la línea correspondiente
del preámbulo.

---

## Trabajo en equipo

Cada integrante edita su propio archivo en `secciones/`; al estar separados, no
hay conflictos de edición. El control de versiones es git, no Overleaf.

Tres reglas que conviene leer antes de tocar nada:

1. **La numeración del índice del modelo es vinculante.** Más de veinte `\ref`
   del resto del informe apuntan a 3.3.3 (marco, proporcionalidad, auditoría,
   licencias), 3.4 y 3.4.2-3.4.4, y a 5.2 (requisitos de privacidad). Además,
   varios `.md` remiten **escribiendo el número a mano** («Sección 5», «Sección
   3.4», «Sección 4», «Anexo B», «apartado B.9»), y los Anexos B y C remiten a
   sus propios apartados del mismo modo. **No renumerar** sin corregir todo eso.
2. **Nada de marcadores de relleno en el cuerpo.** Si algo falta o hay que
   decidirlo, va a `PENDIENTES.md`. Hay dos excepciones, ambas deliberadas y
   preferibles a inventar un dato:
   - `[VERIFICAR: ...]` en los `.md` y en la Sección 3, que marca una
     afirmación normativa cuyo respaldo documental exacto todavía no se ha
     contrastado.
   - `[VERIFICAR: ...]` en el **ciclo académico y la fecha de entrega de la
     portada** de `main.tex`. Los dos valores deben salir del sílabo del curso;
     hasta entonces el hueco se ve, que es mejor que una portada afirmando un
     ciclo o una fecha que nadie ha confirmado. Es el pendiente **A-10**.
3. **Los `\label{...}` no se borran.** Si desaparecen, el documento compila con
   referencias `??`.

Cualquier cambio de arquitectura, de conjunto de datos o de política de
retención debe comunicarse al frente ético-legal: la auditoría de conformidad
del marco ético-legal se apoya en esas decisiones y cambia con ellas.

---

## Convenciones del documento

### Paquetes

Todo el preámbulo usa paquetes de distribución estándar. **No se usan
`tcolorbox` ni `mdframed`**.

**Formato (14/09/2026, pedido del frente de Liderazgo e Integración).** Times
New Roman a 12 pt (`newtxtext` + `newtxmath`); todo en negro (`hyperref` con
`hidelinks`, sin colores en títulos, tablas ni cartel); sangría de primera línea
de 1,25 cm en todos los párrafos (`indentfirst`) y sin espacio entre ellos (ya
no se carga `parskip`); sin recuadros sombreados; tablas en blanco y negro con
`booktabs`; carátula sin filetes decorativos; **ninguna raya (—) en el
cuerpo**, sustituidas por comas, paréntesis o punto y seguido. Quien añada
texto debe respetarlo: en particular, no reintroducir rayas ni colores.

Bibliografía con `biblatex` + `biber`, estilo `ieee`, `sorting=none`
(las referencias se numeran por orden de aparición).

### Macros y tipos de columna propios

| Macro | Uso |
|---|---|
| `\cajaaviso{título}{texto}` | Desde el 14/09/2026 ya **no** es una caja: imprime `texto` como párrafo corrido y descarta `título`. Ya no la usa ninguna sección; se conserva por compatibilidad. No usarla en texto nuevo |
| `\verificar{texto}` | Marcador `[VERIFICAR]` oculto: no imprime nada y deja rastro en el log |
| `\campoportada{marcador}{formato}{dato}` | Variante de portada: imprime el campo entero solo si `dato` no está vacío; si falta, no imprime nada |

| Tipo de columna | Equivale a |
|---|---|
| `L{ancho}` | `p{ancho}` alineada a la izquierda |
| `Y` | columna `X` de `tabularx` alineada a la izquierda |

Se usan en lugar de `p{}` y `X` porque, a esos anchos, el texto justificado
produce líneas muy sueltas (avisos `Underfull \hbox`).

---

## Reglas de redacción del frente ético-legal

Cuatro criterios se aplicaron de forma consistente y conviene mantenerlos:

1. **No se inventa nada.** Ningún artículo, numeral, fecha ni cifra se escribió
   de memoria como dato firme. Donde no hay certeza, el texto lo dice
   expresamente y queda registro en `NOTAS_FUENTES.md`.
2. **Ninguna cifra de la literatura se reproduce si no consta en la prosa del
   artículo.** Las que solo figuraban en tablas de resultados se retiraron: la
   conversión de esos cuadros a texto plano mezcla filas y columnas. Donde la
   comparación importa, se citan las magnitudes relativas que los propios
   autores enuncian.
3. **No se afirman conclusiones jurídicas categóricas.** Las zonas de
   interpretación se redactan como riesgos a validar con el cliente, en
   condicional.
4. **`referencias.bib` es intocable.** Es una copia literal de
   `papers/citas_oficiales.txt`, entrada por entrada. Las normas legales **no**
   van en el `.bib`: se citan en el texto y se registran en `NOTAS_FUENTES.md`.
   Si hay que añadir un paper, primero se pega su BibTeX oficial en
   `citas_oficiales.txt` —el bloque que publica la propia página del artículo— y
   solo después se copia al `.bib`. Nunca al revés.

---

## Estado

**Compilación.** Verificada el 14/09/2026 desde limpio (`latexmk -C` y después
`latexmk -pdf main.tex`), tras los cambios de formato pedidos por el frente de
Liderazgo e Integración y la reestructuración al índice del modelo del curso:
**0 errores, 41 páginas**, `main.pdf` de unos 530 KB,
**ninguna cita sin resolver y ninguna referencia cruzada sin resolver**.

La salida **no está libre de avisos**, y conviene no decir que lo está. Quedan
dos cosas, las dos cosméticas y ninguna impide generar el PDF:

- **1 aviso de `hyperref`** (*destination with the same identifier
  (name{page.1}) has been already used, duplicate ignored*). Viene del cambio
  de numeración romana a árabe entre el material preliminar y el cuerpo, no de
  ninguna sección concreta.
- **3 avisos de Biber** por entradas cuyo campo `month` es un nombre de mes en
  texto (`Li_2018_CVPR`, `Song_2021_ICCV`, `Lin_2025_CVPR`). Vienen del BibTeX
  oficial de la CVF, que se copia sin retocar por la regla 4.

Qué cambió respecto del estado del 13/09/2026 (40 páginas, 646.341 bytes):

- El paso a 12 pt con sangría alarga el texto; la compresión de la Sección 3 y
  la retirada de la nota de la página iii lo acortan. El saldo son 44 páginas,
  de las cuales 12 son el Anexo B.
- La reestructuración al índice del modelo del curso (cinco secciones nuevas en
  esqueleto y el Anexo C con el análisis de impacto completo) llevó el total a
  46. Bajó a 41 al quitar el salto de página forzado entre las Secciones 1 a 11
  (dejaba páginas casi vacías tras cada esqueleto; solo los Anexos abren página
  nueva), y la tabla de la síntesis del Marco Teórico pasó a `longtable` para
  poder partirse entre páginas.
- `\verificar` abre con `\unskip`: un marcador escrito entre dos espacios
  imprimía un espacio doble en el PDF.
- La caja `Overfull \hbox` que causaba `Directiva 01-2020-JUS/DGTAIPD` en la
  Sección 3 ya no aparece en el log.

**Sección 3 y Anexos B y C.** El apartado 3.3.3 (385 palabras impresas) y
3.3.2 resumen el Anexo B (unas 6.000); el apartado 3.4 (unas 740) resume el
Anexo C (unas 3.400). El Anexo B es donde se cita el articulado: contra **fuente
primaria** la Ley 29733 (arts. 2, 5-8, 11, 13-15, 18-25, 28 y 30) y el D.S.
007-2020-IN (arts. 3, 17.1 y 17.2); la Directiva 01-2020-JUS/DGTAIPD y los
incisos constitucionales están contrastados contra reproducción íntegra de
fuente secundaria. Trazabilidad completa en `NOTAS_FUENTES.md` §2.7, cuyos
«§3.x» corresponden hoy a B.x.

Quedan **12 `[VERIFICAR]`** según el recuento del log de compilación
(14/09/2026): **2 en la portada** (ciclo académico y fecha de entrega, A-10),
**4 en 3.1 y 3.2** (datos del terminal que dependen de LAP), **2 en 3.3.3**,
**1 en 5.2** y **3 en el Anexo B**. Los de 3.3.3, 5.2 y el Anexo B son tres
reservas, cada una marcada en el resumen y en el anexo porque en los dos se
afirma el dato: la fecha de entrada en vigor del D.S. 016-2024-JUS, la
denominación del D.L. 1218 y la Ley 30120 (3.3.3 y B), y el texto literal del
RNF-01 (5.2 y B). Desde
el 14/09/2026 esas tres reservas **se leen en el PDF**, redactadas en prosa en
el párrafo que afirma cada dato; el marcador sigue oculto. El apartado 3.4 y el
Anexo C no tienen ninguno. Lista autoritativa en `PENDIENTES.md` §a.3.

**Resto del informe.** Introducción, Sección 3, Marco Teórico, 5.2 y Anexo A
están redactados; Resumen Ejecutivo, 5.1, Diseño del Sistema, Planificación,
Desarrollo del Modelo, Resultados y Conclusiones siguen en **esqueleto**, con la
frase común «Esta sección se completará en la versión final del informe.» El detalle, con qué falta en cada una y de quién depende, está en
`PENDIENTES.md` §(f).

Qué falta y en qué orden: ver `PENDIENTES.md` y `CHECKLIST_CUMPLIMIENTO.md`.
