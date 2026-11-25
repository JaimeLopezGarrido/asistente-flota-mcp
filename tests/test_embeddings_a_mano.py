"""Tests de la exploración de embeddings (L08). No usan red: vectores chicos hechos a mano."""

import json

import numpy as np
import pytest

from exploracion import embeddings as emb


def test_normalizar_deja_largo_uno():
    matriz = emb.normalizar([[3.0, 4.0], [0.0, 2.0]])
    assert np.linalg.norm(matriz, axis=1).tolist() == pytest.approx([1.0, 1.0])
    assert matriz[0].tolist() == pytest.approx([0.6, 0.8])


def test_vector_de_ceros_falla():
    with pytest.raises(ValueError, match="ceros"):
        emb.normalizar([0.0, 0.0])


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [([1, 1], [3, 3], 1.0), ([1, 0], [0, 5], 0.0), ([1, 2], [-1, -2], -1.0)],
)
def test_coseno_casos_basicos(a, b, esperado):
    assert emb.coseno(a, b) == pytest.approx(esperado)


def test_ejemplo_del_gimnasio_de_la_teoria():
    q = [0.9, 0.1, 0.2]
    assert emb.coseno(q, [0.8, 0.2, 0.1]) == pytest.approx(0.987, abs=0.001)
    assert emb.coseno(q, [0.1, 0.9, 0.3]) == pytest.approx(0.271, abs=0.001)


def test_mas_parecidos_ordena_y_respeta_k():
    documentos = [[1.0, 0.0], [0.0, 1.0], [10.0, 10.0]]
    resultado = emb.mas_parecidos([1.0, 0.2], documentos, k=2)
    assert [posicion for posicion, _ in resultado] == [0, 2]
    assert resultado[0][1] > resultado[1][1]


def test_el_largo_del_vector_no_cambia_el_resultado():
    documentos = [[1.0, 0.0], [0.0, 1.0]]
    corto = emb.mas_parecidos([1.0, 0.2], documentos, k=2)
    largo = emb.mas_parecidos([100.0, 20.0], documentos, k=2)
    assert [p for p, _ in corto] == [p for p, _ in largo]
    assert [s for _, s in corto] == pytest.approx([s for _, s in largo])


def test_leer_politicas():
    fichas = emb.leer_politicas()
    assert [f["id"] for f in fichas] == [f"P{n}" for n in range(1, 11)]
    assert fichas[4]["texto"].startswith("Mascotas")


def test_leer_manual():
    fichas = emb.leer_manual()
    assert len(fichas) == 10
    assert fichas[0]["id"] == "M1"
    assert "Chile" in fichas[4]["texto"]
    assert all("\n" not in f["texto"] for f in fichas)


def test_prefijos_de_embeddinggemma():
    assert emb.con_prefijo(["hola"], es_consulta=True) == ["task: search result | query: hola"]
    assert emb.con_prefijo(["hola"], es_consulta=False) == ["title: none | text: hola"]


@pytest.mark.parametrize(
    "base", ["http://localhost:11434/v1", "http://localhost:11434/v1/", "http://localhost:11434"]
)
def test_url_embed(base):
    assert emb.url_embed(base) == "http://localhost:11434/api/embed"


class RespuestaFalsa:
    """Imita lo que devuelve urlopen: se usa con 'with' y tiene read()."""

    def __init__(self, datos: dict):
        self.datos = datos

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.datos).encode("utf-8")


def test_vectorizar_ollama_manda_prefijos_y_devuelve_matriz(monkeypatch):
    enviados = []

    def urlopen_falso(pedido, timeout):
        assert timeout > 0
        enviados.append(json.loads(pedido.data))
        return RespuestaFalsa({"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    monkeypatch.setattr(emb.urllib.request, "urlopen", urlopen_falso)
    matriz = emb.vectorizar_ollama(
        ["a", "b"], es_consulta=False, modelo="embeddinggemma", url="http://x/api/embed"
    )
    assert matriz.shape == (2, 2)
    assert enviados[0]["model"] == "embeddinggemma"
    assert enviados[0]["input"] == ["title: none | text: a", "title: none | text: b"]


def test_gemini_sin_clave_da_un_error_claro(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        emb.vectorizar(["hola"], es_consulta=True, proveedor="gemini")
