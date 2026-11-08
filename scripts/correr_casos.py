"""Corre los casos difíciles de tests/casos/ contra el asistente real y muestra el resultado.

Uso:
    python -m scripts.correr_casos
    python -m scripts.correr_casos --repeticiones 3
    python -m scripts.correr_casos --caso c03 --proveedores groq
"""

import argparse
import logging
import sys
from collections import Counter

from dotenv import load_dotenv

from asistente.evaluacion import cargar_casos, evaluar
from asistente.llm import SinProveedorError, responder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corre los casos de prueba contra el LLM")
    parser.add_argument("--repeticiones", type=int, default=1, help="veces que se corre cada caso")
    parser.add_argument("--caso", help="id de un solo caso, por ejemplo c03")
    parser.add_argument("--proveedores", help="orden de proveedores, por ejemplo groq,ollama")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    proveedores = args.proveedores.split(",") if args.proveedores else None
    casos = [c for c in cargar_casos() if args.caso in (None, c["id"])]

    total = ok = 0
    for caso in casos:
        intenciones = Counter()
        for i in range(1, args.repeticiones + 1):
            total += 1
            try:
                res = responder(caso["mensaje"], proveedores=proveedores)
            except SinProveedorError as e:
                print(f"{caso['id']} #{i} ERROR {e}")
                continue
            fallas = evaluar(res.respuesta, caso["esperado"])
            intenciones[res.respuesta.intencion] += 1
            ok += not fallas
            estado = "OK   " if not fallas else "FALLA"
            print(f"{caso['id']} #{i} {estado} {res.proveedor}/{res.modelo} {res.segundos:4.1f}s  "
                  f"{res.respuesta.respuesta[:80]!r}")
            for falla in fallas:
                print(f"         - {falla}")
        if len(intenciones) > 1:
            print(f"         ! variabilidad de intención: {dict(intenciones)}")

    print()
    print(f"Resultado: {ok}/{total} corridas OK" + (f" ({ok / total:.0%})" if total else ""))
    return 0 if total and ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
