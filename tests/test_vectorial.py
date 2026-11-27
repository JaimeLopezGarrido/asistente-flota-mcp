"""Base vectorial local (L10): Qdrant en memoria con vectores de juguete, sin red."""

import json

import pytest

from rag import vectorial

INDICE = {
    'fuente': 'manual_prueba.pdf',
    'modelo': 'modelo-de-prueba',
    'fragmentos': [
        {'id': 'p2-0', 'pagina': 2, 'seccion': '5. Cruce a Chile',
         'texto': 'Permiso notarial con 72 horas de anticipación.', 'vector': [1.0, 0.0, 0.0]},
        {'id': 'p2-1', 'pagina': 2, 'seccion': '5. Cruce a Chile',
         'texto': 'Seguro obligatorio para circular en Chile.', 'vector': [0.9, 0.1, 0.0]},
        {'id': 'p3-2', 'pagina': 3, 'seccion': '6. Qué hacer si...',
         'texto': 'Pinchadura: llamá al auxilio.', 'vector': [0.0, 1.0, 0.0]},
        {'id': 'p4-3', 'pagina': 4, 'seccion': '10. Preguntas frecuentes',
         'texto': 'Mascotas: siempre en jaula.', 'vector': [0.0, 0.0, 1.0]},
    ],
}


@pytest.fixture
def cliente():
    nuevo = vectorial.abrir(None)
    vectorial.indexar(nuevo, INDICE)
    yield nuevo
    nuevo.close()


def ids(resultados: list[dict]) -> list[str]:
    return [r['fragmento'] for r in resultados]


def test_indexa_todos_los_fragmentos(cliente):
    assert cliente.count(vectorial.COLECCION).count == 4


def test_reindexar_no_duplica(cliente):
    assert vectorial.indexar(cliente, INDICE) == 4


def test_top_k_ordenado_y_con_metadatos(cliente):
    resultados = vectorial.buscar(cliente, [1.0, 0.0, 0.0], k=2)
    assert ids(resultados) == ['p2-0', 'p2-1']
    assert resultados[0]['puntaje'] >= resultados[1]['puntaje']
    assert resultados[0]['pagina'] == 2
    assert resultados[0]['fuente'] == 'manual_prueba.pdf'


def test_filtro_por_seccion(cliente):
    resultados = vectorial.buscar(cliente, [1.0, 0.0, 0.0], k=3, seccion='10. Preguntas frecuentes')
    assert ids(resultados) == ['p4-3']


def test_filtro_por_paginas(cliente):
    resultados = vectorial.buscar(cliente, [0.0, 1.0, 0.0], k=5, paginas=[3, 4])
    assert {r['pagina'] for r in resultados} == {3, 4}


def test_umbral_descarta_lo_lejano(cliente):
    resultados = vectorial.buscar(cliente, [0.0, 1.0, 0.0], k=4, minimo=0.5)
    assert ids(resultados) == ['p3-2']


def test_un_fragmento_se_encuentra_a_si_mismo_primero(cliente):
    vector = vectorial.vector_de_fragmento(cliente, 'p2-0')
    assert vector is not None
    resultados = vectorial.buscar(cliente, vector, k=2)
    assert ids(resultados) == ['p2-0', 'p2-1']
    assert resultados[0]['puntaje'] == pytest.approx(1.0, abs=1e-3)


def test_fragmento_inexistente(cliente):
    assert vectorial.vector_de_fragmento(cliente, 'no-existe') is None


def test_coincide_con_la_busqueda_exacta(cliente):
    consulta = [0.2, 0.9, 0.5]
    assert ids(vectorial.buscar(cliente, consulta, k=4)) == vectorial.exactos(INDICE, consulta, k=4)


def test_indice_sin_embeddings_falla_claro():
    nuevo = vectorial.abrir(None)
    with pytest.raises(ValueError, match='embeddings'):
        vectorial.indexar(nuevo, {**INDICE, 'modelo': None})
    nuevo.close()


def test_el_indice_real_tiene_vectores_de_una_sola_medida():
    indice = json.loads(vectorial.INDICE.read_text(encoding='utf-8'))
    assert all('vector' in f for f in indice['fragmentos'])
    assert {len(f['vector']) for f in indice['fragmentos']} == {indice['dimensiones']}
