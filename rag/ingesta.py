"""Ingesta del manual: PDF -> texto por página -> fragmentos con metadatos -> embeddings -> índice.

Uso (una vez, o cuando cambie el manual):
    python -m rag.ingesta
Genera datos/manual/indice.json, que se versiona en el repo para que la API no tenga que procesar el PDF.
"""

import json
import logging
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from rag.embeddings import DIMENSIONES, MODELO, vectorizar

RAIZ = Path(__file__).resolve().parent.parent
PDF = RAIZ / 'datos' / 'manual' / 'manual_rentadora.pdf'
INDICE = RAIZ / 'datos' / 'manual' / 'indice.json'
TAMANIO = 420  # caracteres por fragmento, aproximado

log = logging.getLogger(__name__)


def leer_paginas(ruta: Path = PDF) -> list[tuple[int, str]]:
    """Devuelve [(número de página, texto)] con los saltos de línea del PDF unidos."""
    from pypdf import PdfReader

    paginas = []
    for numero, pagina in enumerate(PdfReader(ruta).pages, start=1):
        texto = re.sub(r'\s+', ' ', pagina.extract_text() or '').strip()
        if texto:
            paginas.append((numero, texto))
    return paginas


FUENTE = RAIZ / 'datos' / 'manual' / 'manual_rentadora.md'


def titulos(ruta: Path = FUENTE) -> list[str]:
    """Los títulos de sección ('5. Cruce a Chile') tomados de la fuente del manual."""
    return [linea[3:].strip() for linea in ruta.read_text(encoding='utf-8').splitlines() if linea.startswith('## ')]


def seccion_de(texto: str, lista: list[str] | None = None) -> str:
    """El título de la sección que aparece en la página, o '' si no hay ninguno (por ejemplo, la portada)."""
    for titulo in lista if lista is not None else titulos():
        if titulo in texto[:200]:
            return titulo
    return ''


def fragmentar(paginas: list[tuple[int, str]], tamanio: int = TAMANIO) -> list[dict]:
    """Corta cada página en fragmentos de oraciones completas, sin mezclar páginas.

    Cada fragmento lleva la sección de su página adelante (contexto para la búsqueda) y una oración
    de solapamiento con el anterior, para no perder ideas que quedan justo en el corte.
    """
    fragmentos = []
    lista = titulos()
    for numero, texto in paginas:
        seccion = seccion_de(texto, lista)
        oraciones = re.split(r'(?<=[.!?])\s+', texto)
        actual: list[str] = []
        for oracion in oraciones:
            if actual and len(' '.join(actual)) + len(oracion) > tamanio:
                fragmentos.append({'pagina': numero, 'seccion': seccion, 'texto': ' '.join(actual)})
                actual = actual[-1:]
            actual.append(oracion)
        if actual:
            fragmentos.append({'pagina': numero, 'seccion': seccion, 'texto': ' '.join(actual)})
    for i, f in enumerate(fragmentos):
        f['id'] = f'p{f["pagina"]}-{i}'
    return fragmentos


def construir(ruta: Path = PDF) -> dict:
    fragmentos = fragmentar(leer_paginas(ruta))
    vectores = vectorizar([f'{f["seccion"]}. {f["texto"]}' for f in fragmentos], 'RETRIEVAL_DOCUMENT')
    if vectores:
        for f, v in zip(fragmentos, vectores, strict=True):
            f['vector'] = [round(x, 5) for x in v]
    return {'fuente': ruta.name, 'modelo': MODELO if vectores else None, 'dimensiones': DIMENSIONES,
            'fragmentos': fragmentos}


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    indice = construir()
    INDICE.write_text(json.dumps(indice, ensure_ascii=False), encoding='utf-8')
    con = 'con embeddings' if indice['modelo'] else 'SIN embeddings (solo palabras)'
    print(f'{len(indice["fragmentos"])} fragmentos de {indice["fuente"]} {con} -> {INDICE.relative_to(RAIZ)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
