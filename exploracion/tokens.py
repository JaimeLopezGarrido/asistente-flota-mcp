"""Muestra cómo un tokenizador parte textos de la rentadora en tokens.

Uso: python -m exploracion.tokens            (frases de ejemplo)
     python -m exploracion.tokens --texto "lo que quieras"
"""

import argparse

import tiktoken

TEXTOS = [
    "Hola, ¿tienen una SUV libre del 20 al 23 de diciembre?",
    "Hi, do you have an SUV available from December 20 to 23?",
    "San Carlos de Bariloche",
    "$ 70.000 por día",
    "2026-12-15",
    "¿Puedo llevar a mi perro? 🐶🚗",
]


def tokenizar(texto: str, codificacion: str = "o200k_base") -> tuple[list[int], list[str]]:
    """Devuelve los IDs de los tokens y el pedazo de texto que representa cada uno."""
    enc = tiktoken.get_encoding(codificacion)
    ids = enc.encode(texto)
    piezas = [enc.decode([i]) for i in ids]
    return ids, piezas


def mostrar(texto: str) -> None:
    ids, piezas = tokenizar(texto)
    print(f"\n{texto!r}")
    print(f"  {len(texto)} caracteres -> {len(ids)} tokens ({len(texto) / len(ids):.1f} caracteres por token)")
    print("  piezas:", " | ".join(repr(p) for p in piezas))
    print("  IDs:   ", ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ver cómo se tokeniza un texto")
    parser.add_argument("--texto", help="texto propio para tokenizar")
    args = parser.parse_args()
    for texto in [args.texto] if args.texto else TEXTOS:
        mostrar(texto)


if __name__ == "__main__":
    main()
