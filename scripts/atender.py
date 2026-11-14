"""Chat por terminal con router de intención: muestra qué camino eligió cada mensaje.

Uso:
    python -m scripts.atender
    python -m scripts.atender --detalle
    python -m scripts.atender --una 'Me cobraron dos veces la garantía'
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

from asistente.atencion import Atencion, atender
from asistente.llm import SinProveedorError


def mostrar(res: Atencion) -> None:
    aviso = ' -> derivar a una persona' if res.derivar_a_humano else ''
    print(f'   [router] {res.ruta}: {res.motivo}{aviso}')
    print(f'Asistente ({res.llamadas_llm} llamadas al modelo): {res.texto}')
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Chat con router de intención de la rentadora')
    parser.add_argument('--proveedores', help='orden de proveedores, por ejemplo groq,gemini')
    parser.add_argument('--una', help='manda un solo mensaje y termina')
    parser.add_argument('--detalle', action='store_true', help='muestra los logs del router')
    args = parser.parse_args(argv)

    load_dotenv()
    nivel = logging.INFO if args.detalle else logging.WARNING
    logging.basicConfig(level=nivel, format='%(levelname)s %(name)s: %(message)s')
    proveedores = args.proveedores.split(',') if args.proveedores else None

    if args.una:
        try:
            mostrar(atender(args.una, proveedores=proveedores))
        except SinProveedorError as e:
            print(f'ERROR {e}')
            return 1
        return 0

    print('Chat con router. Escribí salir para terminar.')
    print()
    historial: list[dict] = []
    while True:
        try:
            mensaje = input('Vos: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if mensaje.lower() in {'salir', 'chau', 'exit'}:
            break
        if not mensaje:
            continue
        try:
            res = atender(mensaje, historial=historial, proveedores=proveedores)
        except SinProveedorError as e:
            print(f'ERROR {e}')
            continue
        historial = res.historial
        mostrar(res)
    return 0


if __name__ == '__main__':
    sys.exit(main())
