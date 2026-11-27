"""Base vectorial local (L10): los fragmentos del manual en Qdrant, con filtros por metadatos.

Qdrant corre adentro de este mismo proceso (modo local, sin servidor) y guarda en datos/vectorial/.
El mismo código sirve contra un servidor de Qdrant o Qdrant Cloud: solo cambia cómo se crea el cliente.
La demo pública sigue usando rag/buscar.py; esto se conecta al agente en L11.

Uso (las preguntas, siempre entre comillas):
    python -m rag.vectorial --indexar                  # carga datos/manual/indice.json
    python -m rag.vectorial '¿puedo cruzar a Chile?'   # top-k con página, sección y puntaje
    python -m rag.vectorial --secciones                # las secciones que se pueden filtrar
    python -m rag.vectorial 'mascotas' --k 5 --seccion '10. Preguntas frecuentes'
    python -m rag.vectorial --como-fragmento ID        # vecinos de un fragmento (sin red)
"""

import argparse
import json
import logging
import math
import sys
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from rag.embeddings import MODELO, vectorizar

RAIZ = Path(__file__).resolve().parent.parent
INDICE = RAIZ / 'datos' / 'manual' / 'indice.json'
CARPETA = RAIZ / 'datos' / 'vectorial'
COLECCION = 'manual'

log = logging.getLogger(__name__)


def abrir(carpeta: Path | None = CARPETA) -> QdrantClient:
    """Qdrant en modo local: guardado en una carpeta, o solo en memoria si carpeta es None (tests)."""
    if carpeta is None:
        return QdrantClient(':memory:')
    carpeta.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(carpeta))


def indexar(cliente: QdrantClient, indice: dict, coleccion: str = COLECCION) -> int:
    """Borra y vuelve a crear la colección con todos los fragmentos. Devuelve cuántos puntos quedaron."""
    fragmentos = indice['fragmentos']
    if not indice.get('modelo') or not fragmentos or not all('vector' in f for f in fragmentos):
        raise ValueError('el índice no tiene embeddings: corré python -m rag.ingesta con GEMINI_API_KEY')
    dimension = len(fragmentos[0]['vector'])
    if cliente.collection_exists(coleccion):
        cliente.delete_collection(coleccion)
    cliente.create_collection(
        coleccion,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )
    puntos = [
        models.PointStruct(
            id=numero,
            vector=f['vector'],
            payload={
                'fragmento': f['id'],
                'pagina': f['pagina'],
                'seccion': f['seccion'],
                'texto': f['texto'],
                'fuente': indice['fuente'],
                'modelo': indice['modelo'],
            },
        )
        for numero, f in enumerate(fragmentos)
    ]
    cliente.upsert(coleccion, points=puntos)
    total = cliente.count(coleccion).count
    log.info('%d puntos en la colección %s', total, coleccion)
    return total


def filtro(seccion: str | None = None, paginas: list[int] | None = None) -> models.Filter | None:
    """Condiciones sobre el payload: sección exacta y/o alguna de las páginas. None = sin filtro."""
    condiciones = []
    if seccion:
        condiciones.append(models.FieldCondition(key='seccion', match=models.MatchValue(value=seccion)))
    if paginas:
        condiciones.append(models.FieldCondition(key='pagina', match=models.MatchAny(any=paginas)))
    return models.Filter(must=condiciones) if condiciones else None


def buscar(
    cliente: QdrantClient,
    vector: list[float],
    k: int = 3,
    seccion: str | None = None,
    paginas: list[int] | None = None,
    minimo: float | None = None,
    coleccion: str = COLECCION,
) -> list[dict]:
    """Los k puntos más parecidos que cumplen el filtro, con su payload y su puntaje (coseno)."""
    respuesta = cliente.query_points(
        coleccion,
        query=vector,
        limit=k,
        query_filter=filtro(seccion, paginas),
        score_threshold=minimo,
        with_payload=True,
    )
    return [{**(p.payload or {}), 'puntaje': round(p.score, 3)} for p in respuesta.points]


def vector_de_fragmento(
    cliente: QdrantClient, fragmento: str, coleccion: str = COLECCION
) -> list[float] | None:
    """El vector guardado de un fragmento (por su id, el que se ve entre paréntesis), o None."""
    condicion = models.FieldCondition(key='fragmento', match=models.MatchValue(value=fragmento))
    puntos, _ = cliente.scroll(
        coleccion, scroll_filter=models.Filter(must=[condicion]), limit=1, with_vectors=True
    )
    if not puntos or not isinstance(puntos[0].vector, list):
        return None
    return [float(x) for x in puntos[0].vector]


def _coseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=True))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


def exactos(indice: dict, vector: list[float], k: int) -> list[str]:
    """Los ids de los k fragmentos más parecidos, calculados a mano contra todos (fuerza bruta)."""
    orden = sorted(indice['fragmentos'], key=lambda f: _coseno(vector, f['vector']), reverse=True)
    return [f['id'] for f in orden[:k]]


def secciones(indice: dict) -> dict[str, int]:
    """Cuántos fragmentos tiene cada sección, en el orden del manual."""
    cuenta: dict[str, int] = {}
    for f in indice['fragmentos']:
        cuenta[f['seccion']] = cuenta.get(f['seccion'], 0) + 1
    return cuenta


def mostrar(resultados: list[dict]) -> None:
    if not resultados:
        print('  (nada: ningún fragmento pasa el filtro o el umbral)')
    for n, r in enumerate(resultados, start=1):
        seccion = r['seccion'] or '(sin sección)'
        pagina, puntaje, fragmento = r['pagina'], r['puntaje'], r['fragmento']
        print(f'{n}. [pág. {pagina}] {puntaje:.3f}  {seccion}  ({fragmento})')
        print(textwrap.indent(textwrap.fill(r['texto'][:300], 92), '     '))


def consultar(cliente: QdrantClient, indice: dict, args: argparse.Namespace) -> int:
    if args.indexar or not cliente.collection_exists(COLECCION):
        total = indexar(cliente, indice)
        print(f'{total} fragmentos indexados en datos/vectorial/ (colección {COLECCION})')
        if not args.pregunta and not args.como_fragmento:
            return 0
    if args.como_fragmento:
        vector = vector_de_fragmento(cliente, args.como_fragmento)
        if vector is None:
            print(f'No existe el fragmento {args.como_fragmento}: copiá un id de los resultados.')
            return 1
        consulta = f'vecinos de {args.como_fragmento}'
    else:
        modelo_indice = indice['modelo']
        if modelo_indice != MODELO:
            print(f'El índice se hizo con {modelo_indice} y la pregunta usaría {MODELO}: reindexá.')
            return 1
        consulta = ' '.join(args.pregunta) or '¿qué hago si pincho una goma?'
        vectores = vectorizar([consulta], 'RETRIEVAL_QUERY')
        if not vectores:
            print('No pude vectorizar la pregunta: revisá GEMINI_API_KEY en .env o usá --como-fragmento.')
            return 1
        vector = vectores[0]

    resultados = buscar(cliente, vector, args.k, args.seccion, args.pagina, args.minimo)
    print(f'Top-{args.k} para: {consulta}')
    mostrar(resultados)
    if args.comparar:
        if args.seccion or args.pagina:
            print('--comparar funciona sin filtros: sacá --seccion y --pagina.')
        else:
            a_mano = exactos(indice, vector, args.k)[: len(resultados)]
            de_qdrant = [r['fragmento'] for r in resultados]
            veredicto = 'coinciden' if a_mano == de_qdrant else f'NO coinciden (a mano: {a_mano})'
            print(f'Búsqueda exacta a mano vs Qdrant: {veredicto}')
    return 0


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')
    parser = argparse.ArgumentParser(description='Base vectorial local del manual (Qdrant)')
    parser.add_argument('pregunta', nargs='*', help='la pregunta del cliente, entre comillas')
    parser.add_argument('--indexar', action='store_true', help='borrar y volver a cargar indice.json')
    parser.add_argument('--k', type=int, default=3, help='cuántos fragmentos traer (top-k)')
    parser.add_argument('--seccion', help='filtrar por sección exacta (ver --secciones)')
    parser.add_argument('--pagina', type=int, action='append', help='filtrar por página (repetible)')
    parser.add_argument('--minimo', type=float, help='puntaje mínimo para mostrar un fragmento')
    parser.add_argument('--como-fragmento', metavar='ID', help='buscar con el vector de un fragmento')
    parser.add_argument('--comparar', action='store_true', help='comparar con la búsqueda exacta a mano')
    parser.add_argument('--secciones', action='store_true', help='listar las secciones para --seccion')
    args = parser.parse_args()

    indice = json.loads(INDICE.read_text(encoding='utf-8'))
    if args.secciones:
        for nombre, cantidad in secciones(indice).items():
            etiqueta = nombre or '(sin sección)'
            print(f'{cantidad:>3} fragmentos  {etiqueta}')
        return 0
    cliente = abrir()
    try:
        return consultar(cliente, indice, args)
    finally:
        cliente.close()


if __name__ == '__main__':
    sys.exit(main())
