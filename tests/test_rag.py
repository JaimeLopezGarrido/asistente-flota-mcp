import json

from asistente import atencion, herramientas
from rag import buscar as rag_buscar
from rag.ingesta import INDICE, fragmentar, seccion_de

PAGINAS = [
    (1, ('6. Qué hacer si... Pinchadura: estacioná en un lugar seguro y cambiá la rueda. La reparación de la '
        'cubierta corre por cuenta del cliente.')),
    (2, '8. Daños, seguro y franquicia Todos los autos tienen seguro con una franquicia de $ 900.000.'),
]


def _preparar(indice: dict) -> dict:
    from collections import Counter

    docs = [rag_buscar.palabras(f'{f["seccion"]} {f["texto"]}') for f in indice['fragmentos']]
    return indice | {'_docs': docs, '_df': Counter(p for d in docs for p in set(d)),
                     '_largo_medio': sum(map(len, docs)) / len(docs)}


def test_fragmentar_conserva_pagina_y_seccion():
    fragmentos = fragmentar(PAGINAS, tamanio=60)
    assert {f['pagina'] for f in fragmentos} == {1, 2}
    assert all(f['id'].startswith(f'p{f["pagina"]}-') for f in fragmentos)
    assert seccion_de(PAGINAS[0][1], ['6. Qué hacer si...', '8. Daños, seguro y franquicia']) == '6. Qué hacer si...'
    assert seccion_de('Portada sin título', ['6. Qué hacer si...']) == ''


def test_busqueda_por_palabras_encuentra_la_pagina_correcta():
    resultados = rag_buscar.buscar('franquicia del seguro', indice=_preparar({'modelo': None, 'fragmentos': fragmentar(PAGINAS)}))
    assert resultados and resultados[0]['pagina'] == 2
    assert resultados[0]['modo'] == 'palabras'


def test_sin_evidencia_no_devuelve_nada():
    indice = _preparar({'modelo': None, 'fragmentos': fragmentar(PAGINAS)})
    assert rag_buscar.buscar('receta de empanadas tucumanas', indice=indice) == []


def test_el_indice_del_repo_tiene_paginas_y_vectores():
    indice = json.loads(INDICE.read_text(encoding='utf-8'))
    assert len(indice['fragmentos']) >= 10
    assert all(f['pagina'] >= 1 and f['texto'] for f in indice['fragmentos'])


def test_herramienta_buscar_manual_avisa_si_no_hay_fragmentos(monkeypatch):
    monkeypatch.setattr(rag_buscar, 'buscar', lambda consulta: [])
    assert herramientas.buscar_manual('algo raro')['fragmentos'] == []


def test_herramienta_buscar_manual_devuelve_paginas(monkeypatch):
    monkeypatch.setattr(rag_buscar, 'buscar', lambda consulta: [{'pagina': 7, 'seccion': '6. Qué hacer si', 'texto': 'x'}])
    assert herramientas.buscar_manual('pinchadura')['fragmentos'][0]['pagina'] == 7


def test_fuentes_citadas_solo_las_paginas_que_aparecen():
    fragmentos = [{'pagina': 7, 'seccion': 'a', 'texto': 'uno'}, {'pagina': 9, 'seccion': 'b', 'texto': 'dos'}]
    fuentes = atencion.fuentes_citadas('Cambiá la rueda [pág. 7].', fragmentos)
    assert [f['pagina'] for f in fuentes] == [7]
    assert atencion.fuentes_citadas('Sin citas.', fragmentos) == []
