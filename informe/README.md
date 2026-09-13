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
| **Secciones 3 y 4** | `secciones/03_marco_normativo.md` y `secciones/04_analisis_impacto.md` | el `.tex` del mismo nombre, con `herramientas/md2tex.py` | Frente ético-legal |
| Secciones 1, 2, 5, 6, 7 y Anexo A | `secciones/*.tex`, directamente | — | Sus responsables |
| **Entregable** | no se edita: se compila | `main.pdf`, con `latexmk -pdf main.tex` | Frente ético-legal |

Hay, por tanto, **dos clases de sección** y conviene no confundirlas:

- **Secciones escritas en `.tex`.** Se editan en el `.tex` y ya está. Son la
  Introducción, Antecedentes, Metodología, Resultados, Conclusiones y el
  Anexo A.
- **Secciones 3 y 4, escritas en `.md`.** El `.md` es la **fuente**; el `.tex`
  es **producto derivado** y se regenera. Nunca se edita a mano.

El motivo de la asimetría es que las Secciones 3 y 4 se habían pasado a Markdown
durante el episodio de Overleaf. Al volver a LaTeX no se rehízo el trabajo a
mano: se automatizó la conversión, que es reproducible y verificable palabra por
palabra. Unificar todo en un solo formato sigue abierto como **E-08** en
`PENDIENTES.md`.

### Cómo se regeneran las Secciones 3 y 4

Desde `informe/`, después de tocar cualquiera de los dos `.md`:

```bash
py herramientas/md2tex.py secciones/03_marco_normativo.md secciones/03_marco_normativo.tex 3
py herramientas/md2tex.py secciones/04_analisis_impacto.md  secciones/04_analisis_impacto.tex  4
py herramientas/verificar_fidelidad.py secciones/03_marco_normativo.md secciones/03_marco_normativo.tex
py herramientas/verificar_fidelidad.py secciones/04_analisis_impacto.md  secciones/04_analisis_impacto.tex
latexmk -pdf main.tex
```

- El tercer argumento de `md2tex.py` (`3` o `4`) selecciona la tabla de
  `\label`. Esos `\label` reproducen los anclajes de la versión archivada para
  que las referencias cruzadas del resto del informe sigan resolviendo.
- `md2tex.py` **no reescribe prosa**: solo traduce marcado. Una ejecución limpia
  no imprime ningún `AVISO`; si imprime alguno, hay una construcción Markdown no
  prevista que hay que revisar a mano.
- `verificar_fidelidad.py` compara la prosa del `.md` con la del `.tex` palabra
  por palabra. La única diferencia esperada es un `\allowbreak` tipográfico en la
  Sección 4.

### Qué NO hacer

- **No editar `secciones/03_marco_normativo.tex` ni
  `secciones/04_analisis_impacto.tex`.** Son generados. Cualquier edición a mano
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
    │   ├── md2tex.py               conversor .md -> .tex de las Secciones 3 y 4
    │   └── verificar_fidelidad.py  comprueba la conversión palabra por palabra
    ├── papers/                     IGNORADO: PDFs fuente + citas_oficiales.txt
    ├── fichas_antecedentes/        fichas A2, B1-B3, C1-C4
    └── secciones/
        ├── introduccion.tex        a cargo de otro integrante
        ├── antecedentes.tex        ← frente ético-legal
        ├── 03_marco_normativo.md   ← FUENTE de la Sección 3 (frente ético-legal)
        ├── 03_marco_normativo.tex     GENERADO — no editar
        ├── 04_analisis_impacto.md  ← FUENTE de la Sección 4 (frente ético-legal)
        ├── 04_analisis_impacto.tex    GENERADO — no editar
        ├── metodologia.tex         a cargo de otro integrante
        ├── resultados.tex          a cargo de otro integrante
        ├── conclusiones.tex        a cargo de otro integrante
        └── anexo_cartel.tex        ← frente ético-legal (Anexo A)
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

Si has tocado un `.md` de las Secciones 3 o 4, **antes hay que regenerar su
`.tex`**: ver «Cómo se regeneran las Secciones 3 y 4» más arriba. Compilar sin
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

1. **La numeración de las Secciones 3 y 4 es vinculante.** El resto del
   informe las referencia **20 veces** con `\ref`, y **15** de esas referencias
   apuntan a un subapartado concreto: 3.1, 3.5, 3.9 (la auditoría de dato
   biométrico y las licencias), 4.3, 4.4 (la lectura ambiental del costo de
   cómputo) y 4.5. **No renumerar** sin corregir las referencias que apuntan
   ahí.
2. **Nada de marcadores de relleno en el cuerpo.** Si algo falta o hay que
   decidirlo, va a `PENDIENTES.md`. Hay dos excepciones, ambas deliberadas y
   preferibles a inventar un dato:
   - `[VERIFICAR: ...]` en los `.md` de las Secciones 3 y 4, que marca una
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
`tcolorbox` ni `mdframed`**: las cajas de aviso están construidas con
`\fcolorbox` + `minipage`, para que el proyecto compile en cualquier
distribución sin instalar nada.

Bibliografía con `biblatex` + `biber`, estilo `ieee`, `sorting=none`
(las referencias se numeran por orden de aparición).

### Macros y tipos de columna propios

| Macro | Uso |
|---|---|
| `\cajaaviso{título}{texto}` | Caja destacada para advertencias y riesgos a validar |
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

**Compilación.** Verificada el 13/09/2026 desde limpio (`latexmk -C` y después
`latexmk -pdf main.tex`): **0 errores, 40 páginas**, `main.pdf` de 646.341
bytes, **ninguna cita sin resolver y ninguna referencia cruzada sin resolver**.

La salida **no está libre de avisos**, y conviene no decir que lo está. Quedan
tres cosas, las tres cosméticas y ninguna impide generar el PDF:

- **1 aviso de `hyperref`** (*destination with the same identifier
  (name{page.1}) has been already used, duplicate ignored*). Viene del cambio
  de numeración romana a árabe entre el material preliminar y el cuerpo, no de
  ninguna sección concreta.
- **1 caja `Overfull \hbox`** (3,2 pt) en `secciones/03_marco_normativo.tex`,
  por la cadena `Directiva 01-2020-JUS/DGTAIPD`, que no admite guionado.
- **3 avisos de Biber** por entradas cuyo campo `month` es un nombre de mes en
  texto (`Li_2018_CVPR`, `Song_2021_ICCV`, `Lin_2025_CVPR`). Vienen del BibTeX
  oficial de la CVF, que se copia sin retocar por la regla 4.

Dos correcciones sobre lo que este README afirmaba antes:

- Decía «43 páginas» y «532.770 bytes». Eran los del PDF anterior a la
  consolidación; hoy son 40 páginas y 646.341 bytes. El salto de tamaño lo
  explica el logo de la carátula (`3686fbe`): el PDF anterior, también de 40
  páginas, pesaba 432.226 bytes.
- Decía «8 en el estado previo, 6 ahora» avisos de `hyperref` y «5 cajas
  overfull/underfull». Hoy son **1** y **1** respectivamente.

**Secciones 3 y 4.** Vigentes, con la numeración 3.1-3.9 / 4.1-4.5 que exigen
las referencias cruzadas. La Sección 3 (5.461 palabras) cita contra **fuente
primaria** la Ley 29733 (arts. 2, 5-8, 11, 13-15, 18-25, 28 y 30) y el D.S.
007-2020-IN (arts. 3, 17.1 y 17.2); la Directiva 01-2020-JUS/DGTAIPD y los
incisos constitucionales están contrastados contra reproducción íntegra de
fuente secundaria. Trazabilidad completa en `NOTAS_FUENTES.md` §2.7.

Quedan **17 `[VERIFICAR]`** en total, según el recuento del log de compilación
(13/09/2026): **7 en la portada**, **4 en la Introducción** y **6 en la
Sección 3**; la Sección 4 no tiene ninguno. Los 7 de la portada son el apellido
materno de tres integrantes, los cuatro códigos de alumno, y el ciclo académico
y la fecha de entrega (A-10): ninguno es normativo. Los 4 de la Introducción
son datos del terminal que dependen de LAP (C-07, C-08, aforo y zonas/cámaras).
Esto corrige la cuenta anterior de este README, «seis en el cuerpo y dos en la
portada», que no incluía la Introducción ni los huecos de los integrantes.

De los 6 de la Sección 3, corrige a su vez lo que este README decía antes
—«siete, todos sobre el articulado del D.S. 016-2024-JUS»—: son seis (el séptimo
era el ejemplo del comentario de cabecera del `.md`) y **solo dos** versan sobre
el articulado del D.S. 016-2024-JUS. Los otros cuatro son sobre las fechas y la disposición
derogatoria del propio D.S., la vigencia de la Directiva 01-2020-JUS/DGTAIPD, la
denominación del D.L. 1218 y la Ley 30120, y el texto literal del RNF-01.

**Resto del informe.** Introducción, Antecedentes y Anexo A están redactados;
Metodología, Resultados y Conclusiones siguen en **esqueleto** y son de otros
integrantes. El detalle, con qué falta en cada una y de quién depende, está en
`PENDIENTES.md` §(f).

Qué falta y en qué orden: ver `PENDIENTES.md` y `CHECKLIST_CUMPLIMIENTO.md`.
