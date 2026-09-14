# -*- coding: utf-8 -*-
r"""Conversor md -> tex de las partes del informe LAP escritas en Markdown.

Los .md de secciones/ son la FUENTE; los .tex que main.tex incluye se
generan con este script y NO se editan a mano.

    cd informe
    py herramientas/md2tex.py secciones/03_marco_normativo.md        secciones/03_marco_normativo.tex        normativo
    py herramientas/md2tex.py secciones/03_analisis_impacto.md       secciones/03_analisis_impacto.tex       impacto
    py herramientas/md2tex.py secciones/anexo_b_marco_normativo.md   secciones/anexo_b_marco_normativo.tex   B
    py herramientas/md2tex.py secciones/anexo_c_analisis_impacto.md  secciones/anexo_c_analisis_impacto.tex  C
    py herramientas/verificar_fidelidad.py <md> <tex>   (para cada par)
    latexmk -pdf main.tex

El tercer argumento selecciona el nivel de los encabezados y la tabla de
\label. Esos \label sostienen las referencias cruzadas del resto del
informe; si se tocan, el documento compila con referencias ??.

verificar_fidelidad.py compara la prosa del .md con la del .tex palabra
por palabra; la salida esperada es IDENTICO.

No reescribe prosa: solo traduce marcado. Cualquier construccion Markdown
no prevista se deja registrada en STDERR para revisarla a mano; una
ejecucion limpia no imprime ningun AVISO.
"""
import re, sys, io, textwrap

SPECIALS = {'&': r'\&', '%': r'\%', '#': r'\#', '$': r'\$', '_': r'\_'}

def esc(t):
    # ~ y ^ no aparecen en las fuentes; se avisa si aparecieran.
    for ch in ['~', '^', chr(92)]:
        if ch in t:
            print('AVISO: caracter %r sin escapar en: %s' % (ch, t[:70]), file=sys.stderr)
    out = []
    for ch in t:
        out.append(SPECIALS.get(ch, ch))
    return ''.join(out)

# Claves bibliograficas: [Clave] o [Clave1; Clave2]
KEY = r'[A-Z][A-Za-z]+_\d{4}_[A-Z]+'
CITE = re.compile(r'\[(' + KEY + r'(?:\s*;\s*' + KEY + r')*)\]')

def convert_inline(t):
    """Devuelve LaTeX. Protege citas/codigo/VERIFICAR antes de escapar."""
    slots = []
    def stash(tex):
        slots.append(tex)
        return '\x00%d\x00' % (len(slots) - 1)

    # 1. [VERIFICAR: ...] -> \verificar{...}
    # La macro esta definida en main.tex y NO imprime nada en el PDF. El
    # texto del marcador se conserva integro aqui y en el .md de origen; la
    # lista autoritativa esta en PENDIENTES.md. Antes se emitia
    # \textit{[VERIFICAR: ...]}, que si se imprimia.
    def verificar(m):
        return stash(r'\verificar{' + convert_inline(m.group(1)) + '}')
    t = re.sub(r'\[VERIFICAR:\s*(.+?)\]', verificar, t, flags=re.S)

    # 2. codigo `x` -> \texttt{x} (con _ partible para no desbordar la caja)
    t = re.sub(r'`([^`]+)`',
               lambda m: stash(r'\texttt{' + esc(m.group(1)).replace(r'\_', r'\_\allowbreak ') + '}'),
               t)

    # 3. citas [Clave; Clave] -> \cite{Clave,Clave}
    t = CITE.sub(lambda m: stash(r'\cite{' + ','.join(k.strip() for k in m.group(1).split(';')) + '}'), t)

    # 4. negrita y cursiva
    t = re.sub(r'\*\*(.+?)\*\*', lambda m: stash(r'\textbf{' + convert_inline(m.group(1)) + '}'), t, flags=re.S)
    t = re.sub(r'(?<![\*\w])\*([^*\n]+?)\*(?!\*)', lambda m: stash(r'\emph{' + convert_inline(m.group(1)) + '}'), t)

    if '[' in t and ']' in t:
        print('AVISO: corchete sin convertir: %s' % t[:90], file=sys.stderr)

    t = esc(t)
    return re.sub(r'\x00(\d+)\x00', lambda m: slots[int(m.group(1))], t)

# Niveles de LaTeX. Cada archivo fija con OFFSET a que nivel corresponde "#":
#   offset 0 -> "#" section, "##" subsection, "###" subsubsection
#   offset 1 -> "#" subsection, "##" subsubsection (anexos: todos los
#               anexos cuelgan de la seccion 12, "Anexos")
LEVELS = ['section', 'subsection', 'subsubsection']
HEADING = re.compile(r'^(#{1,3})\s+((?:\d+|[A-Z])(?:\.\d+)*)\.?\s+(.*)$')

def convert(md, labels, header, offset):
    out = [header]
    body = re.sub(r'^<!--.*?-->\s*', '', md, flags=re.S)
    for raw in body.split('\n\n'):
        block = raw.strip()
        if not block:
            continue
        # "## 3.4 Titulo", "### 3.3.2 Titulo", "# B. Titulo", "## B.1 Titulo".
        # El numero no se escribe: lo pone LaTeX. Solo sirve para buscar los
        # \label y para dejar un comentario de orientacion en el .tex.
        m = HEADING.match(block)
        if m and '\n' not in block:
            depth = len(m.group(1)) - 1 + offset
            num, title = m.group(2), m.group(3)
            out.append('')
            out.append('%% ---- %s ----' % num)
            out.append('\\%s{%s}' % (LEVELS[depth], convert_inline(title)))
            out.extend(r'\label{%s}' % l for l in labels.get(num, []))
            continue
        if block.startswith('#'):
            print('AVISO: encabezado no reconocido: %s' % block[:70], file=sys.stderr)
        if re.match(r'^\s*[-*+]\s', block) or re.match(r'^\s*\d+\.\s', block):
            print('AVISO: lista sin convertir: %s' % block[:70], file=sys.stderr)
        out.append('')
        # Se ajusta a 72 columnas como el resto de los .tex del repo.
        # En LaTeX un salto de linea equivale a un espacio, de modo que
        # cortar en los espacios no altera el resultado compuesto.
        out.append(textwrap.fill(convert_inline(block), width=72,
                                 break_long_words=False,
                                 break_on_hyphens=False))
    return '\n'.join(out) + '\n'

def cabecera(titulo, fuente, notas):
    lineas = ['=' * 69, '  ' + titulo, '  Responsable: Fabian Moreno Ugarte', '',
              '  GENERADO desde %s, que es su FUENTE.' % fuente,
              '  No editar aqui: editar el .md y reconvertir.', ''] + ['  ' + n for n in notas] + ['=' * 69]
    return ''.join('%' + l + '\n' for l in lineas)

if __name__ == '__main__':
    src, dst, which = sys.argv[1], sys.argv[2], sys.argv[3]
    # Reestructuracion al indice del modelo del curso (2026-09-14). Los \label
    # de las antiguas Secciones 3 y 4 viven ahora en la Seccion 3:
    #   3.3.3 Restricciones legales  <- sec:marco, sec:directiva, sec:dl1218,
    #         sec:proporcionalidad, sec:auditoria, sec:licencias
    #   3.4   Analisis               <- sec:analisis, sec:eipd, sec:sintesis-impacto
    #   3.4.2 etico / 3.4.3 social / 3.4.4 ambiental
    #         <- sec:impacto-etico / sec:impacto-social / sec:impacto-ambiental
    # sec:privacidad-diseno ya no es generado: esta en secciones/requerimientos.tex.
    CONF = {
        'normativo': (0, {
            '3.3.3': ['sec:marco', 'sec:directiva', 'sec:dl1218',
                      'sec:proporcionalidad', 'sec:auditoria', 'sec:licencias'],
        }, cabecera('SECCION 3 -- RESTRICCIONES ETICAS Y LEGALES (3.3.2 y 3.3.3)',
                    'secciones/03_marco_normativo.md',
                    ['Resumen: el desarrollo completo esta en el Anexo B.',
                     'La restriccion legal (3.3.3) no debe pasar de una pagina.'])),
        'impacto': (0, {
            '3.4': ['sec:analisis', 'sec:eipd', 'sec:sintesis-impacto'],
            '3.4.2': ['sec:impacto-etico'],
            '3.4.3': ['sec:impacto-social'],
            '3.4.4': ['sec:impacto-ambiental'],
        }, cabecera('SECCION 3.4 -- ANALISIS TECNICO, ETICO, SOCIAL, AMBIENTAL',
                    'secciones/03_analisis_impacto.md',
                    ['Resumen: el desarrollo completo esta en el Anexo C.'])),
        'B': (1, {'B': ['anx:marco']},
              cabecera('ANEXO B -- MARCO NORMATIVO: DESARROLLO COMPLETO',
                       'secciones/anexo_b_marco_normativo.md',
                       ['Las remisiones internas (B.2, B.9...) van escritas en el .md.'])),
        'C': (1, {'C': ['anx:impacto']},
              cabecera('ANEXO C -- ANALISIS DE IMPACTO: DESARROLLO COMPLETO',
                       'secciones/anexo_c_analisis_impacto.md',
                       ['Las remisiones a B.x y C.x van escritas en el .md.'])),
    }
    offset, labels, header = CONF[which]
    md = io.open(src, encoding='utf-8').read()
    tex = convert(md, labels, header, offset)
    io.open(dst, 'w', encoding='utf-8', newline='\n').write(tex)
    print('escrito %s (%d bytes)' % (dst, len(tex.encode('utf-8'))))
