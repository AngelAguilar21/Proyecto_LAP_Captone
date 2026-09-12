# secciones/_archivo/ — versiones LaTeX retiradas

Contiene las versiones en LaTeX de las Secciones 3 y 4, retiradas de uso el
**11 de septiembre de 2026**.

| Archivo | Era | Sustituido por |
|---|---|---|
| `marco_etico_legal.tex` | Sección 3 — «Marco ético y legal aplicable» (6.471 palabras) | `secciones/03_marco_normativo.md` |
| `analisis_impacto.tex` | Sección 4 — «Análisis de impacto» (3.144 palabras) | `secciones/04_analisis_impacto.md` |

## Por qué se archivaron

El equipo dejó de trabajar en Overleaf: la compilación dejó de funcionar por el
límite de la cuenta gratuita. El informe que se entrega es ahora
`Informe_LAP_Aglomeraciones.docx`, y las Secciones 3 y 4 se mantienen en
Markdown, que convierte a Word sin pasar por LaTeX.

Al reescribirlas se siguió la numeración **3.1–3.9 / 4.1–4.5** que exigen las
doce referencias cruzadas del informe —«Sección 3.4» para proporcionalidad,
«Sección 3.9» para la auditoría de dato biométrico, «Sección 4.4» para la
lectura ambiental—, que no coincide con el reparto de temas de estos `.tex`.

## Qué NO se perdió al migrar

Los `.md` se construyeron sobre este texto, no en lugar de él. Se conservan
íntegros el examen de proporcionalidad, las medidas M-01…M-10, la auditoría
condicional sobre los tres enfoques, el análisis de sesgo y la lectura
ambiental. La migración además **añadió** citas contrastadas contra fuente
primaria (Ley 29733 y D.S. 007-2020-IN) que estos `.tex` sólo describían en
términos generales.

## Qué sí se quedó aquí

Contenido que no entraba en el esquema pedido para las nuevas secciones y que
**no está en los `.md`**. Si alguna vez hace falta, se recupera de aquí:

- La referencia comparada completa: RGPD art. 35, Reglamento (UE) 2024/1689
  (AI Act), ISO/IEC 27001 e ISO/IEC 42001.
- El desarrollo de la notificación de brechas con los requisitos técnicos
  derivados **R-01, R-02 y R-03**.
- El apartado sobre el Oficial de Datos Personales y su cronograma escalonado.
- El apartado de licencias de los conjuntos de datos públicos, con la regla
  propuesta para el servidor de evaluación de NWPU-Crowd.
- Los impactos **social y económico** de la Sección 4, con el reparto de
  beneficios y cargas por actor y el costo del incumplimiento.

## Reglas

- **No se editan.** Son un registro congelado. Cualquier cambio en las
  Secciones 3 o 4 se hace en `secciones/03_marco_normativo.md` o
  `secciones/04_analisis_impacto.md`.
- `main.tex` sigue apuntando a estos dos archivos con `\input` para que el PDF
  histórico continúe siendo reproducible. Esa compilación es **legado**: no es
  el entregable.
