"""Genera datos/manual/manual_rentadora.pdf a partir del texto en manual_rentadora.md.

Una sección por página, así cada fragmento del RAG puede citar su página. Usa Chrome en modo
headless para imprimir el HTML a PDF (no hace falta instalar nada más).

Uso:
    python -m scripts.generar_manual
"""

import html
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / 'datos' / 'manual' / 'manual_rentadora.md'
SALIDA = RAIZ / 'datos' / 'manual' / 'manual_rentadora.pdf'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

ESTILO = """
@page { size: A4; margin: 22mm 20mm; }
body { font: 12pt/1.55 Helvetica, Arial, sans-serif; color: #1a1916; }
h1 { font-size: 20pt; margin: 0 0 6mm; }
h2 { font-size: 15pt; margin: 0 0 4mm; }
p { margin: 0 0 3mm; }
.aviso { color: #6b665c; font-size: 10pt; }
section { page-break-after: always; }
section:last-child { page-break-after: auto; }
"""


def a_html(texto: str) -> str:
    """Markdown mínimo: '# ' título, '## ' una sección por página, el resto párrafos."""
    secciones, actual, titulo = [], [], ''
    for linea in texto.splitlines():
        if linea.startswith('# '):
            titulo = linea[2:]
        elif linea.startswith('## '):
            if actual:
                secciones.append(actual)
            actual = [f'<h2>{html.escape(linea[3:])}</h2>']
        elif linea.strip():
            actual.append(f'<p>{html.escape(linea.strip())}</p>')
    secciones.append(actual)
    secciones[0] = [f'<h1>{html.escape(titulo)}</h1>', '<p class="aviso">Documento ficticio para la demo.</p>',
                    *secciones[0]]
    cuerpo = ''.join(f'<section>{"".join(s)}</section>' for s in secciones)
    return f'<!doctype html><html lang="es"><meta charset="utf-8"><style>{ESTILO}</style><body>{cuerpo}</body></html>'


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        pagina = Path(tmp) / 'manual.html'
        pagina.write_text(a_html(FUENTE.read_text(encoding='utf-8')), encoding='utf-8')
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                        f'--print-to-pdf={SALIDA}', pagina.as_uri()], check=True, capture_output=True)
    print(f'Manual generado: {SALIDA.relative_to(RAIZ)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
