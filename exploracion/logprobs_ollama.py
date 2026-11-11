"""Opcional: pide a Ollama (modelo local) las probabilidades reales de cada token generado.

Uso: python -m exploracion.logprobs_ollama --temperatura 0.7
Necesita la app de Ollama abierta y un modelo descargado (OLLAMA_MODEL en .env).
"""

import argparse
import json
import math
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

PREGUNTA = "Completá con una sola palabra: el país vecino al que se cruza en auto desde Bariloche es"


def url_chat_nativa(base: str) -> str:
    """Pasa de la URL compatible con OpenAI (.../v1) a la API nativa de Ollama, que sí da logprobs."""
    return base.rstrip("/").removesuffix("/v1") + "/api/chat"


def a_probabilidad(logprob: float) -> float:
    """Un logprob es el logaritmo natural de la probabilidad: exp lo deshace."""
    return math.exp(logprob)


def resumir(respuesta: dict, maximo: int = 10) -> list[str]:
    """Una línea por token generado: el elegido y sus alternativas, con probabilidad."""
    lineas = []
    for paso in (respuesta.get("logprobs") or [])[:maximo]:
        elegido = f"{paso['token']!r} {a_probabilidad(paso['logprob']):.0%}"
        alternativas = ", ".join(
            f"{alt['token']!r} {a_probabilidad(alt['logprob']):.0%}" for alt in paso.get("top_logprobs", [])
        )
        lineas.append(f"{elegido:<24} | alternativas: {alternativas}")
    return lineas


def pedir(pregunta: str, modelo: str, url: str, temperatura: float, top: int = 5) -> dict:
    cuerpo = {
        "model": modelo,
        "messages": [{"role": "user", "content": pregunta}],
        "stream": False,
        "logprobs": True,
        "top_logprobs": top,
        "options": {"temperature": temperatura, "num_predict": 15},
    }
    pedido = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pedido, timeout=180) as r:
        return json.loads(r.read())


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Logprobs reales con Ollama")
    parser.add_argument("--pregunta", default=PREGUNTA)
    parser.add_argument("--temperatura", type=float, default=0.7)
    args = parser.parse_args()
    modelo = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
    url = url_chat_nativa(os.environ.get("OLLAMA_URL", "http://localhost:11434/v1"))
    try:
        respuesta = pedir(args.pregunta, modelo, url, args.temperatura)
    except urllib.error.URLError as e:
        print(f"No pude hablar con Ollama en {url}: {e}. ¿Está abierta la app y descargado {modelo}?")
        return
    lineas = resumir(respuesta)
    if not lineas:
        print("La respuesta no trae logprobs: actualizá Ollama (https://ollama.com/download) o probá otro modelo.")
        return
    print(f"Modelo {modelo}, temperatura {args.temperatura}")
    print("Respuesta:", respuesta.get("message", {}).get("content", ""))
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
