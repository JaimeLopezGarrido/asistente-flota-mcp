"""Búsqueda híbrida en el manual: embeddings (significado) + BM25 (palabras exactas).

Si Gemini no responde, sigue solo con palabras: la búsqueda nunca se cae por un proveedor.
Uso para inspeccionar resultados:
    python -m rag.buscar "¿qué hago si pincho una goma?"
"""

import json
import logging
import math
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

from rag.embeddings import vectorizar
from rag.texto import palabras

INDICE = Path(__file__).resolve().parent.parent / 'datos' / 'manual' / 'indice.json'
PESO_SENTIDO = 0.6
MINIMO_SENTIDO = 0.62  # por debajo, el fragmento no habla de lo que se pregunta
MINIMO_PALABRAS = 0.35

log = logging.getLogger(__name__)


@lru_cache
def cargar(ruta: Path = INDICE) -> dict:
    indice = json.loads(ruta.read_text(encoding='utf-8'))
    docs = [palabras(f'{f["seccion"]} {f["texto"]}') for f in indice['fragmentos']]
    indice['_docs'] = docs
    indice['_df'] = Counter(p for d in docs for p in set(d))
    indice['_largo_medio'] = sum(map(len, docs)) / max(len(docs), 1)
    return indice


def _bm25(consulta: list[str], indice: dict, k1: float = 1.4, b: float = 0.75) -> list[float]:
    n = len(indice['_docs'])
    puntajes = []
    for doc in indice['_docs']:
        frec, total = Counter(doc), 0.0
        for p in set(consulta):
            if p not in frec:
                continue
            idf = math.log(1 + (n - indice['_df'][p] + 0.5) / (indice['_df'][p] + 0.5))
            tf = frec[p] * (k1 + 1) / (frec[p] + k1 * (1 - b + b * len(doc) / indice['_largo_medio']))
            total += idf * tf
        puntajes.append(total)
    return puntajes


def _coseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


def buscar(pregunta: str, k: int = 3, indice: dict | None = None) -> list[dict]:
    """Los k fragmentos más relevantes, con página y puntaje. [] si no hay evidencia suficiente."""
    indice = indice or cargar()
    fragmentos = indice['fragmentos']
    lexico = _bm25(palabras(pregunta), indice)
    tope = max(lexico) or 1.0
    lexico = [x / tope for x in lexico]

    sentido = None
    if indice.get('modelo') and all('vector' in f for f in fragmentos):
        vector = vectorizar([pregunta], 'RETRIEVAL_QUERY')
        if vector:
            sentido = [_coseno(vector[0], f['vector']) for f in fragmentos]

    resultados = []
    for i, f in enumerate(fragmentos):
        if sentido is not None:
            if sentido[i] < MINIMO_SENTIDO and lexico[i] < MINIMO_PALABRAS:
                continue
            puntaje = PESO_SENTIDO * sentido[i] + (1 - PESO_SENTIDO) * lexico[i]
        else:
            if lexico[i] < MINIMO_PALABRAS or max(_bm25(palabras(pregunta), indice)) == 0:
                continue
            puntaje = lexico[i]
        resultados.append({'pagina': f['pagina'], 'seccion': f['seccion'], 'texto': f['texto'],
                           'puntaje': round(puntaje, 3), 'modo': 'hibrido' if sentido is not None else 'palabras'})
    resultados.sort(key=lambda r: r['puntaje'], reverse=True)
    return resultados[:k]


if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv()
    for r in buscar(' '.join(sys.argv[1:]) or '¿qué hago si pincho una goma?'):
        print(f'[pág. {r["pagina"]}] {r["puntaje"]} ({r["modo"]}) {r["seccion"]}: {r["texto"][:140]}…')
