# Informe Capstone I — Aglomeraciones LAP

Proyecto LaTeX del informe de Capstone I (Universidad ESAN, Ingeniería de IA).
Sistema de visión computacional para estimar aglomeraciones de personas en el
Aeropuerto Internacional Jorge Chávez, para Lima Airport Partners (LAP).

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

**El documento se edita en Overleaf.** Ahí escribe el equipo, ahí se resuelven
los conflictos de edición simultánea y de ahí sale el PDF que se entrega.

**Lo que hay en esta carpeta del repositorio es una copia de referencia**, no una
segunda línea de trabajo. Sirve para que el informe quede junto al resto del
proyecto, para poder consultarlo o compilarlo sin abrir Overleaf, y para dejar
constancia versionada de cada estado estable del documento.

### La sincronización es manual

No hay sincronización automática entre Overleaf y este repositorio, ni está
previsto montarla. La copia se actualiza **a mano, en cada versión estable** del
documento: cuando se cierra un avance que vale la pena dejar registrado, se
descarga de Overleaf y se sube aquí en un commit.

De ese funcionamiento se siguen dos consecuencias que conviene tener claras:

- **Entre una versión estable y la siguiente, esta copia está desactualizada.**
  Es lo esperado, no un fallo. Si necesitas el estado más reciente del
  documento, ábrelo en Overleaf.
- **No edites el `.tex` aquí para trabajar en el informe.** Un cambio hecho solo
  en el repositorio se pierde en la siguiente sincronización, porque la copia se
  sobrescribe desde Overleaf. Los cambios se hacen en Overleaf.

### Cómo se actualiza la copia

Responsable: el frente de validación ético-legal y documentación.

1. En Overleaf, **Menu → Download → Source** (descarga el proyecto en ZIP).
2. Sustituir en `informe/` los `.tex`, el `.bib` y los `.md` por los del ZIP.
3. Descargar también el PDF compilado y guardarlo como `informe/main.pdf`.
4. Compilar en local para comprobar que la copia está completa y sin errores.
5. Un commit describiendo qué versión es y qué avanzó respecto de la anterior.

Los auxiliares de LaTeX que traiga el ZIP no hace falta borrarlos a mano: el
`.gitignore` de esta carpeta los deja fuera.

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
    ├── main.tex                    preámbulo, portada, índice, \input de secciones
    ├── referencias.bib             copia LITERAL de papers/citas_oficiales.txt
    ├── main.pdf                    PDF compilado (se versiona: es el entregable)
    ├── .gitignore                  reglas de LaTeX, solo rigen dentro de informe/
    ├── .gitattributes              fija LF en los fuentes; solo rige aquí dentro
    ├── PENDIENTES.md               puntos abiertos, agrupados por quién los cierra
    ├── RESUMEN_ANTECEDENTES.md     los tres papers en prosa, sin LaTeX de por medio
    ├── NOTAS_FUENTES.md            trazabilidad de cada afirmación del informe
    ├── CHECKLIST_CUMPLIMIENTO.md   estado de cumplimiento
    ├── README.md                   este archivo
    ├── papers/                     PDFs fuente + citas_oficiales.txt (no versionado)
    └── secciones/
        ├── introduccion.tex        a cargo de otro integrante
        ├── antecedentes.tex        ← frente ético-legal
        ├── marco_etico_legal.tex   ← frente ético-legal
        ├── analisis_impacto.tex    ← frente ético-legal
        ├── metodologia.tex         a cargo de otro integrante
        ├── resultados.tex          a cargo de otro integrante
        ├── conclusiones.tex        a cargo de otro integrante
        └── anexo_cartel.tex        ← frente ético-legal (Anexo A)
```

Todos los comandos de compilación de este README se ejecutan **desde
`informe/`**, no desde la raíz del repositorio.

### Los cuatro archivos `.md` y para qué sirve cada uno

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

## Cómo compilar

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

En Overleaf no hay que hacer nada especial: **Recompile** basta. Comprobar en
**Menu** que el compilador es `pdfLaTeX`, que el documento principal es
`main.tex` y que la versión de TeX Live es 2025 o posterior (ver la nota sobre
`longtable`).

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

Si aparece ese error en Overleaf, hay dos salidas equivalentes:

- cambiar la versión de TeX Live del proyecto (**Menu → Compiler**) a una que
  traiga `longtable` ≤ v4.23 o ≥ v4.27; o
- pedir la versión estable antigua, cambiando en `main.tex`:
  ```latex
  \usepackage{longtable}[=v4.13]
  ```
  Funciona, pero deja el aviso `Command \LT@p@ftntext has changed`.

Hay un comentario con esta misma explicación junto a la línea correspondiente
del preámbulo.

---

## Trabajo en equipo

**Menu → Share** en Overleaf e invitar a los otros integrantes. Cada uno edita su
archivo en `secciones/`; al estar separados en archivos distintos, no hay
conflictos de edición simultánea.

Dos reglas que conviene leer antes de tocar nada:

1. **Los `\label{...}` no se borran.** Las secciones ético-legales referencian
   los de las demás. Si desaparecen, el documento compila con referencias `??`
   en lugar de números de sección.
2. **Nada de marcadores de relleno en el cuerpo.** El documento ya no lleva
   ninguno. Si algo falta o hay que decidirlo, va a `PENDIENTES.md`, no al
   `.tex`. La macro `\pendiente` se eliminó del preámbulo a propósito: si
   alguien la escribe, la compilación falla en el acto, y eso es deliberado.

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

Compila limpio: **0 errores, 0 avisos, 0 cajas overfull/underfull**, 43 páginas,
3 entradas de bibliografía resueltas por Biber.

El cuerpo del PDF no contiene marcadores de relleno ni texto en ámbar.

Verificado con MiKTeX 25.12 (LaTeX2e 2025-11-01, `longtable` v4.27, Biber 2.21)
en Windows 11.

Qué falta y en qué orden: ver `PENDIENTES.md` y `CHECKLIST_CUMPLIMIENTO.md`.
