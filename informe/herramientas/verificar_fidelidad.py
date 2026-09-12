# -*- coding: utf-8 -*-
"""Compara la prosa del .md contra la del .tex generado, palabra a palabra."""
import re, sys, io, difflib

B = chr(92)          # backslash
RB = re.escape(B)  # un backslash literal, listo para usar en regex

def norm_md(t):
    t = re.sub(r'^<!--.*?-->\s*', '', t, flags=re.S)
    t = re.sub(r'^#+\s*\d+(\.\d+)?\.?\s*', '', t, flags=re.M)
    t = t.replace('**', '').replace('*', '').replace('`', '')
    t = re.sub(r'\[([A-Z][A-Za-z]+_\d{4}_[A-Z]+(?:\s*;\s*[A-Z][A-Za-z]+_\d{4}_[A-Z]+)*)\]',
               lambda m: ' '.join(k.strip() for k in m.group(1).split(';')), t)
    return t

def norm_tex(t):
    t = re.sub(r'(?m)^%.*$', '', t)
    t = re.sub(RB + r'(?:sub)?section\{', '', t)
    t = re.sub(RB + r'label\{[^}]*\}', '', t)
    t = re.sub(RB + r'cite\{([^}]*)\}', lambda m: m.group(1).replace(',', ' '), t)
    t = re.sub(RB + r'(?:textbf|emph|textit|texttt)\{', '', t)
    t = t.replace(B + 'allowbreak', ' ')
    for ch in '&%#$_':
        t = t.replace(B + ch, ch)
    return t

def words(t):
    t = t.replace('{', ' ').replace('}', ' ')
    return re.findall(r"[\w\u00c0-\u024f'\u2019-]+", t, flags=re.U)

a = words(norm_md(io.open(sys.argv[1], encoding='utf-8').read()))
b = words(norm_tex(io.open(sys.argv[2], encoding='utf-8').read()))
print('%s -> %s' % (sys.argv[1], sys.argv[2]))
print('   md=%d palabras   tex=%d palabras' % (len(a), len(b)))
if a == b:
    print('   IDENTICO: la prosa coincide palabra por palabra.')
else:
    print('   DIFERENCIAS (- solo en md, + solo en tex):')
    n = 0
    for line in difflib.unified_diff(a, b, lineterm='', n=1):
        if line[:1] in '+-' and line[:3] not in ('+++', '---'):
            print('     ' + line)
            n += 1
            if n > 40:
                print('     ... truncado'); break
