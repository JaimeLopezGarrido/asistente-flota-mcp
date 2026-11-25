"""Tests del laboratorio de ingesta (L09). Los de chunking usan textos chicos; el último genera un PDF."""

import re

import pytest

from exploracion import chunking as ch
from scripts import generar_folleto

PAGINAS_CRUDAS = [
    (1, ["Portada"]),
    (2, ["Encabezado X", "Texto uno.", "Página 2 de 4"]),
    (3, ["Encabezado X", "Texto dos.", "Página 3 de 4"]),
    (4, ["Encabezado X", "Texto tres", "sigue acá.", "Página 4 de 4"]),
]
PAGINAS = [
    (2, "1. Intro hola."),
    (3, "Sigue intro. 2. Chile permiso notarial con 72 horas."),
    (4, "Fin del texto."),
]
TITULOS = ["1. Intro", "2. Chile"]


@pytest.fixture
def doc():
    return ch.construir_documento(PAGINAS, TITULOS, "prueba.pdf")


def test_por_caracteres_sin_solapamiento():
    assert ch.por_caracteres("abcdefghij", 4) == [(0, 4), (4, 8), (8, 10)]


def test_por_caracteres_con_solapamiento():
    assert ch.por_caracteres("abcdefghij", 4, 1) == [(0, 4), (3, 7), (6, 10)]


def test_solapamiento_igual_al_tamanio_falla():
    with pytest.raises(ValueError, match="solapamiento"):
        ch.por_caracteres("abc", 4, 4)


def test_oraciones_no_corta_despues_de_un_numero():
    texto = "El punto 5. Dice algo. Otra cosa! ¿Y esto? Final"
    partes = [texto[a:b].strip() for a, b in ch.oraciones(texto)]
    assert partes == ["El punto 5. Dice algo.", "Otra cosa!", "¿Y esto?", "Final"]


def test_agrupar_con_y_sin_solapamiento():
    partes = [(0, 10), (10, 20), (20, 30), (30, 40)]
    assert ch.agrupar(partes, 20) == [(0, 20), (20, 40)]
    assert ch.agrupar(partes, 20, 1) == [(0, 20), (10, 30), (20, 40)]


def test_una_oracion_mas_larga_que_el_tamanio_queda_entera():
    assert ch.agrupar([(0, 50), (50, 60)], 20) == [(0, 50), (50, 60)]


def test_agrupar_sin_oraciones():
    assert ch.agrupar([], 20) == []


def test_limpiar_saca_encabezado_y_pie():
    assert ch.limpiar_paginas(PAGINAS_CRUDAS) == [
        (1, "Portada"),
        (2, "Texto uno."),
        (3, "Texto dos."),
        (4, "Texto tres sigue acá."),
    ]


def test_documento_recuerda_pagina_y_seccion(doc):
    assert doc.pagina_en(0) == 2
    assert doc.pagina_en(doc.texto.index("Sigue")) == 3
    assert doc.pagina_en(doc.texto.index("Fin")) == 4
    assert doc.seccion_en(0) == "1. Intro"
    assert doc.seccion_en(doc.texto.index("permiso")) == "2. Chile"
    assert doc.seccion_en(doc.texto.index("Fin")) == "2. Chile"


def test_fragmentar_guarda_metadatos(doc):
    primero = ch.fragmentar(doc, ch.por_caracteres(doc.texto, 30), "fijo")[0]
    assert primero["id"] == "fijo-01"
    assert primero["fuente"] == "prueba.pdf"
    assert primero["paginas"] == [2, 3]
    assert primero["seccion"] == "1. Intro"
    assert primero["secciones"] == ["1. Intro", "2. Chile"]
    assert primero["caracteres"] == len(primero["texto"])


def test_secciones_no_mezcla_y_deja_el_dato_entero(doc):
    fragmentos = ch.fragmentar(doc, ch.estrategia_secciones(doc), "secciones")
    assert all(len(f["secciones"]) == 1 for f in fragmentos)
    assert ch.hecho_entero(fragmentos, ("permiso notarial", "72 horas"))
    chile = next(f for f in fragmentos if "permiso" in f["texto"])
    assert chile["seccion"] == "2. Chile"
    assert chile["paginas"] == [3, 4]


def test_oraciones_por_pagina_nunca_cruza_paginas(doc):
    cortes = ch.estrategia_oraciones_por_pagina(doc)
    fragmentos = ch.fragmentar(doc, cortes, "oraciones_por_pagina")
    assert fragmentos
    assert all(len(f["paginas"]) == 1 for f in fragmentos)


def test_hecho_partido_en_dos_fragmentos():
    hecho = ("permiso notarial", "72 horas")
    partidos = [{"texto": "Pedí el permiso notarial con"}, {"texto": "72 horas de anticipación."}]
    assert not ch.hecho_entero(partidos, hecho)
    assert ch.hecho_entero([{"texto": "Permiso notarial con 72 horas."}], hecho)


def test_pdf_sin_texto_avisa_que_hace_falta_ocr():
    with pytest.raises(ValueError, match="OCR"):
        ch.construir_documento([(1, ""), (2, "")], TITULOS, "escaneo.pdf")


def test_folleto_de_punta_a_punta(tmp_path):
    ruta = tmp_path / "folleto.pdf"
    paginas = generar_folleto.generar(ruta)
    assert paginas >= 6
    assert ch.metadatos_pdf(ruta)["paginas"] == paginas
    doc = ch.preparar(ruta)
    assert not re.search(r"Página \d+ de \d+", doc.texto)
    assert generar_folleto.ENCABEZADO not in doc.texto
    assert len(doc.secciones) >= 10
    fragmentos = ch.fragmentar(doc, ch.estrategia_secciones(doc), "secciones")
    assert ch.hecho_entero(fragmentos, ("permiso notarial", "72 horas"))
    con_permiso = [f for f in fragmentos if "permiso notarial" in f["texto"]]
    assert any(f["seccion"].startswith("5.") for f in con_permiso)
