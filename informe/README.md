# Informe Capstone I — Aglomeraciones LAP

Informe de Capstone I (Universidad ESAN, Ingeniería de IA). Sistema de visión
computacional para estimar aglomeraciones de personas en el Aeropuerto
Internacional Jorge Chávez, para Lima Airport Partners (LAP).

> ## ⚠ Cambio de herramienta — 11 de septiembre de 2026
>
> **El entregable es ahora `Informe_LAP_Aglomeraciones.docx`, no el PDF de
> LaTeX.** El equipo dejó de trabajar en Overleaf porque la compilación dejó de
> funcionar por el límite de la cuenta gratuita.
>
> En consecuencia:
>
> - **Las Secciones 3 y 4 se mantienen en Markdown**, en
>   `secciones/03_marco_normativo.md` y `secciones/04_analisis_impacto.md`.
>   Son la **fuente única** de esas dos secciones y convierten a Word sin pasar
>   por LaTeX.
> - Sus versiones `.tex` se archivaron en `secciones/_archivo/` y **no se
>   editan**. El porqué y lo que quedó sólo allí está en
>   `secciones/_archivo/README.md`.
> - **El `.tex` ya no es la fuente del informe.** `main.tex` sigue compilando
>   —sus `\input` apuntan al archivo— para que el PDF histórico siga siendo
>   reproducible, pero esa compilación es **legado**: no es lo que se entrega.
> - Las demás secciones (`introduccion`, `antecedentes`, `metodologia`,
>   `resultados`, `conclusiones`, `anexo_cartel`) siguen en `.tex` y **no se han
>   migrado**. Hoy conviven dos formatos; unificarlos está registrado como punto
>   abierto E-01/E-03 en `PENDIENTES.md`.

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

**Ya no se edita en Overleaf.** El repositorio dejó de ser una copia de
referencia y pasó a ser el sitio donde se trabaja.

| Qué | Dónde se edita | Quién |
|---|---|---|
| **Secciones 3 y 4** | `secciones/03_marco_normativo.md` y `secciones/04_analisis_impacto.md`, aquí en el repositorio | Frente ético-legal |
| **Informe que se entrega** | `Informe_LAP_Aglomeraciones.docx` | Ángel (integración) |
| Resto de secciones | `.tex` en `secciones/`, sin migrar | Sus responsables |

El flujo hoy es: las Secciones 3 y 4 se escriben en Markdown, se convierten a
Word y se integran en el `.docx` que mantiene Ángel. **El `.md` es la fuente;
lo que esté en el `.docx` es el resultado de la última integración.** Si ambos
difieren, manda el `.md` y hay que reintegrar.

> **Punto abierto.** No hay todavía un procedimiento acordado de integración
> `.md` → `.docx` ni constancia de qué versión del `.md` está incorporada al
> `.docx` en cada momento. Registrado en `PENDIENTES.md` (E-01, E-02).

### Qué NO hacer

- **No editar los `.tex` de `secciones/_archivo/`.** Están congelados. Cualquier
  cambio en las Secciones 3 o 4 va al `.md` correspondiente.
- **No reintroducir las Secciones 3 y 4 en el `.tex`.** Volvería a haber dos
  fuentes para lo mismo, que es justamente lo que este cambio elimina.
- **No editar a mano en el `.docx` el texto de las Secciones 3 o 4.** Ese cambio
  se pierde en la siguiente integración desde el `.md`.

---

## Qué contiene el repositorio

El informe vive en la subcarpeta `informe/` del repositorio del equipo. La raíz
del repositorio es del frente de ingeniería (`Dockerfile`, `requirements.txt`,
`Tareas equipo.md`) y **no se toca desde aquí**, incluido su `.gitignore`.

```
Proyecto_LAP_Captone/
├── Dockerfile                      raíz: frente de ingeniería
├── dockercompose.yml               raíz: frente de ingeniería
├── requirements.txt                raíz: frente de ingeniería
├── Tareas equipo.md                raíz: coordinación del equipo
├── .gitignore                      raíz: reglas de Python/Docker (NO tocar)
└── informe/                        ← todo lo de este README
    ├── Informe_LAP_Aglomeraciones.docx   ← EL ENTREGABLE (lo mantiene Ángel)
    ├── main.tex                    LEGADO: preámbulo, portada, \input de secciones
    ├── referencias.bib             copia LITERAL de papers/citas_oficiales.txt
    ├── main.pdf                    LEGADO: PDF compilado, ya no es el entregable
    ├── .gitignore                  reglas de LaTeX, solo rigen dentro de informe/
    ├── .gitattributes              fija LF en los fuentes; solo rige aquí dentro
    ├── PENDIENTES.md               puntos abiertos, agrupados por quién los cierra
    ├── RESUMEN_ANTECEDENTES.md     los tres papers en prosa, sin LaTeX de por medio
    ├── NOTAS_FUENTES.md            trazabilidad de cada afirmación del informe
    ├── CHECKLIST_CUMPLIMIENTO.md   estado de cumplimiento
    ├── README.md                   este archivo
    ├── papers/                     PDFs fuente + citas_oficiales.txt (no versionado)
    ├── fichas_antecedentes/        fichas de PET, MeMOTR, ByteTrack, P2PNet
    └── secciones/
        ├── 03_marco_normativo.md   ← FUENTE de la Sección 3 (frente ético-legal)
        ├── 04_analisis_impacto.md  ← FUENTE de la Sección 4 (frente ético-legal)
        ├── introduccion.tex        a cargo de otro integrante
        ├── antecedentes.tex        ← frente ético-legal
        ├── metodologia.tex         a cargo de otro integrante
        ├── resultados.tex          a cargo de otro integrante
        ├── conclusiones.tex        a cargo de otro integrante
        ├── anexo_cartel.tex        ← frente ético-legal (Anexo A)
        └── _archivo/               .tex retirados de las Secciones 3 y 4
            ├── README.md           por qué se archivaron y qué quedó solo aquí
            ├── marco_etico_legal.tex    CONGELADO — no editar
            └── analisis_impacto.tex     CONGELADO — no editar
```

Todos los comandos de compilación de este README se ejecutan **desde
`informe/`**, no desde la raíz del repositorio.

### Los cuatro archivos `.md` de seguimiento y para qué sirve cada uno

No confundirlos con los `.md` de `secciones/`, que son texto del informe. Estos
cuatro son de seguimiento y no se entregan al cliente.

| Archivo | Responde a la pregunta |
|---|---|
| `PENDIENTES.md` | ¿Qué falta, y quién puede cerrarlo? Agrupado en decisiones del frente ético-legal, decisiones del equipo e información que solo puede dar LAP. |
| `RESUMEN_ANTECEDENTES.md` | ¿Qué dicen los tres papers y por qué importan aquí? Redactado para leerse suelto, sin necesidad de abrir el informe. |
| `NOTAS_FUENTES.md` | ¿De dónde sale cada afirmación del informe y cuánto se puede confiar en ella hoy? |
| `CHECKLIST_CUMPLIMIENTO.md` | ¿En qué estado está cada requisito de cumplimiento? |

Codificación: **UTF-8 sin BOM**, saltos de línea **LF**. Los acentos van escritos
directamente (`á`, no `\'a`). El LF lo fija `.gitattributes` para los `.tex`,
`.md` y `.bib`, de modo que no depende de la configuración `core.autocrlf` de
cada máquina.

`papers/` no se versiona: son PDFs de terceros, pesan varios MB y no interviene
en la compilación. Las citas oficiales están en `referencias.bib` y la
trazabilidad, en `NOTAS_FUENTES.md`.

---

## Cómo compilar (legado)

> **Esta sección es legado.** El PDF ya no es el entregable y compilar no es
> parte del flujo de trabajo normal. Se conserva porque `main.tex` sigue
> compilando —sus `\input` de las Secciones 3 y 4 apuntan a
> `secciones/_archivo/`— y conviene que el PDF histórico siga siendo
> reproducible. **El PDF resultante no incluye las versiones vigentes de las
> Secciones 3 y 4**, que están en los `.md`.
>
> Overleaf ya no se usa: la compilación dejó de funcionar por el límite de la
> cuenta gratuita. Lo que sigue vale para compilar en local.

Requiere **pdfLaTeX + Biber**, ambos incluidos en MiKTeX y TeX Live.

```bash
latexmk -pdf main.tex     # hace las pasadas y llama a Biber solo
latexmk -C                # limpia los archivos auxiliares
```

Sin `latexmk`, la secuencia manual es:

```bash
pdflatex main
biber main
pdflatex main
pdflatex main
```

El documento principal es `main.tex` y requiere TeX Live 2025 o posterior (ver
la nota sobre `longtable`).

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

- usar una distribución de TeX que traiga `longtable` ≤ v4.23 o ≥ v4.27; o
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

1. **La numeración de las Secciones 3 y 4 es vinculante.** El informe las
   referencia doce veces, y tres de esas referencias apuntan a un subapartado
   concreto: «Sección 3.4» para el principio de proporcionalidad, «Sección 3.9»
   para la auditoría de dato biométrico y «Sección 4.4» para la lectura
   ambiental del costo de cómputo. **No renumerar** sin corregir las
   referencias que apuntan ahí.
2. **Nada de marcadores de relleno en el cuerpo.** Si algo falta o hay que
   decidirlo, va a `PENDIENTES.md`. La única excepción es `[VERIFICAR: ...]` en
   los `.md` de las Secciones 3 y 4, que marca una afirmación normativa cuyo
   respaldo documental exacto todavía no se ha contrastado: es deliberado y
   preferible a una cita inventada. Hoy quedan siete, todos sobre el articulado
   del D.S. 016-2024-JUS.
3. **Los `\label{...}` del `.tex` no se borran** mientras `main.tex` siga
   compilando. Si desaparecen, el documento compila con referencias `??`.

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

Bibliografía con `biblatex` + `biber`, estilo `numeric-comp`, `sorting=none`
(las referencias se numeran por orden de aparición).

### Macros y tipos de columna propios

| Macro | Uso |
|---|---|
| `\cajaaviso{título}{texto}` | Caja destacada para advertencias y riesgos a validar |

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
   `papers/citas_oficiales.txt`. Las normas legales **no** van en el `.bib`: se
   citan en el texto y se registran en `NOTAS_FUENTES.md`.

---

## Estado

**Secciones 3 y 4 (`.md`, vigentes).** Redactadas el 11/09/2026 con la
numeración 3.1–3.9 / 4.1–4.5 que exigen las referencias cruzadas. La Sección 3
cita contra **fuente primaria** la Ley 29733 (arts. 2, 5–8, 11, 13–15, 18–25,
28 y 30) y el D.S. 007-2020-IN (arts. 3, 17.1 y 17.2); la Directiva
01-2020-JUS/DGTAIPD y los incisos constitucionales están contrastados contra
reproducción íntegra de fuente secundaria. Quedan **siete `[VERIFICAR]`**, todos
sobre el articulado del D.S. 016-2024-JUS. Trazabilidad completa en
`NOTAS_FUENTES.md` §2.7.

**Compilación LaTeX (legado).** Verificada el 11/09/2026, después de mover las
Secciones 3 y 4 a `secciones/_archivo/` y repuntar los `\input` de `main.tex`:
compila con **0 errores**, 43 páginas y `main.pdf` byte a byte idéntico al
anterior (532.770 bytes). Se contrastó contra una compilación del estado
commiteado previo para descartar que el archivado introdujera regresiones, y no
la introdujo.

Una corrección sobre lo que este README afirmaba antes: la compilación **no está
libre de avisos**. Tanto antes como después del cambio, `hyperref` emite varios
avisos de *destination with the same identifier has been already used*
(8 en el estado previo, 6 ahora), y el estado previo producía además 5 cajas
overfull/underfull. No impiden la generación del PDF y son anteriores a este
cambio, pero conviene no repetir que la salida es limpia sin matizarlo.

Qué falta y en qué orden: ver `PENDIENTES.md` y `CHECKLIST_CUMPLIMIENTO.md`.
