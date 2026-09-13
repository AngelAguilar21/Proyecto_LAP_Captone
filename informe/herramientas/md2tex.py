# -*- coding: utf-8 -*-
r"""Conversor md -> tex para las Secciones 3 y 4 del informe LAP.

Los .md de secciones/ son la FUENTE de las Secciones 3 y 4. Los .tex que
main.tex incluye se generan con este script y NO se editan a mano: si hay
que cambiar algo, se cambia el .md y se vuelve a convertir.

    cd informe
    py herramientas/md2tex.py secciones/03_marco_normativo.md secciones/03_marco_normativo.tex 3
    py herramientas/md2tex.py secciones/04_analisis_impacto.md secciones/04_analisis_impacto.tex 4
    py herramientas/verificar_fidelidad.py secciones/03_marco_normativo.md secciones/03_marco_normativo.tex
    py herramientas/verificar_fidelidad.py secciones/04_analisis_impacto.md secciones/04_analisis_impacto.tex
    latexmk -pdf main.tex

El tercer argumento (3 o 4) selecciona la tabla de \label. Esos
\label reproducen los anclajes de la version archivada en
secciones/_archivo/ para que las referencias cruzadas del resto del
informe sigan resolviendo; si se tocan, el documento compila con
referencias ??.

verificar_fidelidad.py compara la prosa del .md con la del .tex palabra
por palabra: es la comprobacion de que la conversion no perdio ni altero
texto. La unica diferencia esperada es el \allowbreak de
CHECKLIST_CUMPLIMIENTO.md en la Seccion 4.

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

def convert(md, labels, header):
    out = [header]
    body = re.sub(r'^<!--.*?-->\s*', '', md, flags=re.S)
    for raw in body.split('\n\n'):
        block = raw.strip()
        if not block:
            continue
        m = re.match(r'^#\s+\d+\.\s+(.*)$', block)
        if m:
            out.append(r'\section{%s}' % convert_inline(m.group(1)))
            out.extend(r'\label{%s}' % l for l in labels.get('SEC', []))
            continue
        m = re.match(r'^##\s+(\d+\.\d+)\s+(.*)$', block)
        if m:
            num, title = m.group(1), m.group(2)
            out.append('')
            out.append('%% ---- %s ----' % num)
            out.append(r'\subsection{%s}' % convert_inline(title))
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

if __name__ == '__main__':
    src, dst, which = sys.argv[1], sys.argv[2], sys.argv[3]
    LABELS = {
        '3': {
            'SEC': ['sec:marco'],
            '3.1': ['sec:directiva', 'sec:dl1218'],
            '3.5': ['sec:privacidad-diseno'],
            '3.9': ['sec:auditoria', 'sec:licencias'],
        },
        '4': {
            'SEC': ['sec:analisis'],
            '4.1': ['sec:eipd'],
            '4.3': ['sec:impacto-social'],
            '4.4': ['sec:impacto-ambiental'],
            '4.5': ['sec:sintesis-impacto', 'sec:impacto-etico'],
        },
    }[which]
    HEADERS = {
        '3': ('%=====================================================================\n'
              '%  SECCION 3 -- MARCO NORMATIVO APLICABLE\n'
              '%  Responsable: Fabian Moreno Ugarte\n'
              '%\n'
              '%  GENERADO desde secciones/03_marco_normativo.md, que sigue siendo la\n'
              '%  FUENTE de esta seccion. No editar aqui: editar el .md y reconvertir.\n'
              '%\n'
              '%  Los marcadores label reproducen los anclajes de la version archivada para que\n'
              '%  las doce referencias cruzadas del resto del informe sigan\n'
              '%  resolviendo. La numeracion 3.1-3.9 es vinculante.\n'
              '%=====================================================================\n'),
        '4': ('%=====================================================================\n'
              '%  SECCION 4 -- ANALISIS DE IMPACTO Y PRIVACIDAD DESDE EL DISENO\n'
              '%  Responsable: Fabian Moreno Ugarte\n'
              '%\n'
              '%  GENERADO desde secciones/04_analisis_impacto.md, que sigue siendo la\n'
              '%  FUENTE de esta seccion. No editar aqui: editar el .md y reconvertir.\n'
              '%\n'
              '%  Los marcadores label reproducen los anclajes de la version archivada. La\n'
              '%  numeracion 4.1-4.5 es vinculante.\n'
              '%=====================================================================\n'),
    }[which]
    md = io.open(src, encoding='utf-8').read()
    tex = convert(md, LABELS, HEADERS)
    io.open(dst, 'w', encoding='utf-8', newline='\n').write(tex)
    print('escrito %s (%d bytes)' % (dst, len(tex.encode('utf-8'))))
