"""Embeddings a mano con numpy (L08): qué ficha de la rentadora se parece más a una pregunta.

Junta las 10 políticas y las 10 secciones del manual (20 fichas), las convierte en vectores y
busca con similitud coseno, sin base vectorial. Es exploración: el producto sigue usando rag/buscar.py.

Uso:
    python -m exploracion.embeddings                          # preguntas de ejemplo (Gemini)
    python -m exploracion.embeddings --pregunta "¿puedo ir con mi perro?"
    python -m exploracion.embeddings --trampas                # casos donde la similitud engaña
    python -m exploracion.embeddings --proveedor ollama       # modelo local (EmbeddingGemma)
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from numpy.typing import ArrayLike

from rag import embeddings as rag_embeddings

RAIZ = Path(__file__).resolve().parent.parent
POLITICAS = RAIZ / "datos" / "politicas.md"
MANUAL = RAIZ / "datos" / "manual" / "manual_rentadora.md"

# EmbeddingGemma rinde mejor si cada texto dice para qué es (formato de su ficha técnica)
PREFIJO_CONSULTA = "task: search result | query: "
PREFIJO_DOCUMENTO = "title: none | text: "

PREGUNTAS = [
    "¿Puedo llevar a mi perro en el auto?",
    "¿Qué hago si pincho una goma en la ruta?",
    "¿Cuánto tarda en volver la plata de la garantía?",
    "Quiero ir a Osorno, ¿qué papeles necesito?",
    "¿Cuál es la capital de Francia?",
]

# Parejas de frases: las cuatro primeras dicen cosas distintas; la quinta es una paráfrasis correcta
TRAMPAS = [
    ("Se puede fumar dentro del auto.", "No se puede fumar dentro del auto.", "negación"),
    ("El alquiler incluye 300 km por día.", "El alquiler incluye 500 km por día.", "otro número"),
    (
        "Cancelación sin cargo hasta 48 horas antes del retiro.",
        "Cancelación sin cargo hasta 48 horas después del retiro.",
        "antes o después",
    ),
    (
        "La garantía se deja con tarjeta de crédito.",
        "La garantía se deja con tarjeta de débito.",
        "un dato cambia la regla",
    ),
    (
        "¿Puedo llevar a mi perro?",
        "Se aceptan mascotas con jaula o funda protectora.",
        "paráfrasis correcta",
    ),
    ("¿Puedo llevar a mi perro?", "El perro de la oficina se llama Toto.", "misma palabra, otro tema"),
]


def leer_politicas(ruta: Path = POLITICAS) -> list[dict]:
    """Una ficha por política: {'id': 'P5', 'texto': 'Mascotas: ...'}."""
    fichas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        coincidencia = re.match(r"(P\d+)\. (.+)", linea.strip())
        if coincidencia:
            fichas.append({"id": coincidencia.group(1), "texto": coincidencia.group(2)})
    return fichas


def leer_manual(ruta: Path = MANUAL) -> list[dict]:
    """Una ficha por sección '## N. Título'. El corte fino en fragmentos es tema de L09."""
    fichas = []
    for bloque in ruta.read_text(encoding="utf-8").split("\n## ")[1:]:
        titulo, _, cuerpo = bloque.partition("\n")
        numero = titulo.split(".", 1)[0]
        fichas.append({"id": f"M{numero}", "texto": f"{titulo}: {' '.join(cuerpo.split())}"})
    return fichas


def normalizar(vectores: ArrayLike) -> np.ndarray:
    """Divide cada vector por su largo (norma L2): quedan todos de largo 1."""
    matriz = np.asarray(vectores, dtype=float)
    normas = np.linalg.norm(matriz, axis=-1, keepdims=True)
    if np.any(normas == 0):
        raise ValueError("hay un vector de ceros: no tiene dirección y no se puede comparar")
    return matriz / normas


def coseno(a: ArrayLike, b: ArrayLike) -> float:
    """Similitud coseno: 1 misma dirección, 0 nada que ver, -1 opuestos."""
    return float(normalizar(a) @ normalizar(b))


def mas_parecidos(consulta: ArrayLike, documentos: ArrayLike, k: int = 3) -> list[tuple[int, float]]:
    """Los k documentos más parecidos a la consulta: (posición, similitud), de mayor a menor."""
    similitudes = normalizar(documentos) @ normalizar(consulta)
    orden = np.argsort(-similitudes)[:k]
    return [(int(i), float(similitudes[i])) for i in orden]


def con_prefijo(textos: list[str], es_consulta: bool) -> list[str]:
    prefijo = PREFIJO_CONSULTA if es_consulta else PREFIJO_DOCUMENTO
    return [prefijo + texto for texto in textos]


def url_embed(base: str) -> str:
    """De la URL compatible con OpenAI (.../v1) a la ruta nativa de embeddings de Ollama."""
    return base.rstrip("/").removesuffix("/v1") + "/api/embed"


def modelo_ollama() -> str:
    return os.environ.get("OLLAMA_EMBEDDINGS_MODEL", "embeddinggemma")


def vectorizar_ollama(textos: list[str], es_consulta: bool, modelo: str, url: str) -> np.ndarray:
    """Pide los vectores a Ollama (local, sin clave). Una fila por texto."""
    cuerpo = {"model": modelo, "input": con_prefijo(textos, es_consulta)}
    pedido = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pedido, timeout=120) as respuesta:
        return np.array(json.loads(respuesta.read())["embeddings"], dtype=float)


def vectorizar(textos: list[str], es_consulta: bool, proveedor: str) -> np.ndarray:
    """Una fila por texto. Siempre el mismo proveedor y modelo para fichas y preguntas."""
    if proveedor == "ollama":
        url = url_embed(os.environ.get("OLLAMA_URL", "http://localhost:11434/v1"))
        return vectorizar_ollama(textos, es_consulta, modelo_ollama(), url)
    tarea = "RETRIEVAL_QUERY" if es_consulta else "RETRIEVAL_DOCUMENT"
    vectores = rag_embeddings.vectorizar(textos, tarea)  # la misma función que usa el producto
    if vectores is None:
        raise RuntimeError(
            "Gemini no devolvió embeddings: revisá GEMINI_API_KEY en .env, esperá un minuto "
            "si fue por cupo, o probá --proveedor ollama"
        )
    return np.array(vectores, dtype=float)


def nombre_modelo(proveedor: str) -> str:
    return modelo_ollama() if proveedor == "ollama" else rag_embeddings.MODELO


def recortar(texto: str, largo: int = 90) -> str:
    return texto if len(texto) <= largo else texto[: largo - 3] + "..."


def mostrar_busqueda(preguntas: list[str], proveedor: str, k: int) -> None:
    fichas = leer_politicas() + leer_manual()
    documentos = vectorizar([f["texto"] for f in fichas], es_consulta=False, proveedor=proveedor)
    consultas = vectorizar(preguntas, es_consulta=True, proveedor=proveedor)
    print(f"Modelo: {nombre_modelo(proveedor)} | {len(fichas)} fichas | {documentos.shape[1]} dimensiones")
    for pregunta, vector in zip(preguntas, consultas, strict=True):
        print(f"\n{pregunta}")
        for posicion, similitud in mas_parecidos(vector, documentos, k):
            ficha = fichas[posicion]
            print(f"  {similitud:.3f}  {ficha['id']:<4} {recortar(ficha['texto'])}")


def mostrar_trampas(proveedor: str) -> None:
    textos = [frase for a, b, _ in TRAMPAS for frase in (a, b)]
    vectores = vectorizar(textos, es_consulta=False, proveedor=proveedor)
    print(f"Modelo: {nombre_modelo(proveedor)}. Similitud coseno entre dos frases:\n")
    for n, (a, b, caso) in enumerate(TRAMPAS):
        similitud = coseno(vectores[2 * n], vectores[2 * n + 1])
        print(f"  {similitud:.3f}  [{caso}]\n         {a}\n         {b}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Embeddings y similitud coseno a mano")
    parser.add_argument("--pregunta", action="append", help="se puede repetir")
    parser.add_argument("--proveedor", choices=["gemini", "ollama"], default="gemini")
    parser.add_argument("--trampas", action="store_true", help="casos donde la similitud engaña")
    parser.add_argument("-k", type=int, default=3, help="cuántas fichas mostrar por pregunta")
    args = parser.parse_args()
    try:
        if args.trampas:
            mostrar_trampas(args.proveedor)
        else:
            mostrar_busqueda(args.pregunta or PREGUNTAS, args.proveedor, args.k)
    except urllib.error.URLError as e:
        print(
            f"No pude hablar con Ollama ({e}). ¿Está abierta la app y descargado el modelo? "
            f"Probá: ollama pull {modelo_ollama()}"
        )
    except RuntimeError as e:
        print(e)


if __name__ == "__main__":
    main()
