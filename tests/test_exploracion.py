import math

import numpy as np
import pytest

from exploracion.logprobs_ollama import resumir, url_chat_nativa
from exploracion.probabilidades import LOGITS, entropia, muestrear, softmax, top_p


@pytest.mark.parametrize("t", [0, 0.2, 0.7, 1.0, 1.5, 5.0])
def test_probabilidades_suman_uno(t):
    assert softmax(LOGITS, t).sum() == pytest.approx(1.0)


def test_temperatura_baja_concentra_y_alta_aplana():
    assert softmax(LOGITS, 0.2)[0] > softmax(LOGITS, 1.0)[0] > softmax(LOGITS, 1.5)[0]
    assert entropia(softmax(LOGITS, 0.2)) < entropia(softmax(LOGITS, 1.0)) < entropia(softmax(LOGITS, 1.5))


def test_valores_de_la_teoria():
    assert softmax(LOGITS, 1.0)[0] == pytest.approx(0.418, abs=0.001)
    assert softmax(LOGITS, 0.2)[0] == pytest.approx(0.814, abs=0.001)


def test_temperatura_cero_es_greedy():
    assert softmax(LOGITS, 0).tolist() == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert entropia(softmax(LOGITS, 0)) == 0.0


def test_temperatura_negativa_falla():
    with pytest.raises(ValueError):
        softmax(LOGITS, -1)


def test_logits_enormes_no_rompen():
    p = softmax([1000.0, 999.0], 1.0)
    assert not np.isnan(p).any()
    assert p[0] == pytest.approx(0.731, abs=0.001)


def test_top_p_corta_donde_dice_la_teoria():
    assert top_p(softmax(LOGITS, 1.0), 0.9).tolist() == [0, 1, 2, 3]
    assert top_p(softmax(LOGITS, 0.2), 0.9).tolist() == [0, 1]


def test_muestreo_con_semilla_es_repetible():
    probs = softmax(LOGITS, 1.0)
    assert muestrear(probs, 50, semilla=7).tolist() == muestrear(probs, 50, semilla=7).tolist()


@pytest.mark.parametrize(
    "base", ["http://localhost:11434/v1", "http://localhost:11434/v1/", "http://localhost:11434"]
)
def test_url_chat_nativa(base):
    assert url_chat_nativa(base) == "http://localhost:11434/api/chat"


def test_resumir_con_respuesta_falsa():
    falsa = {
        "logprobs": [
            {
                "token": " Chile",
                "logprob": math.log(0.9),
                "top_logprobs": [
                    {"token": " Chile", "logprob": math.log(0.9)},
                    {"token": " Uruguay", "logprob": math.log(0.05)},
                ],
            }
        ]
    }
    lineas = resumir(falsa)
    assert len(lineas) == 1
    assert "' Chile' 90%" in lineas[0]
    assert "' Uruguay' 5%" in lineas[0]


def test_resumir_sin_logprobs_devuelve_lista_vacia():
    assert resumir({"message": {"content": "Chile"}}) == []
