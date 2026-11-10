"""Chat por terminal con el agente (usa las claves de .env).

Uso:
    python -m scripts.chat
    python -m scripts.chat --proveedores groq
    python -m scripts.chat --una '¿Hay camionetas del 10 al 14 de diciembre?'
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

from asistente.agente import ResultadoAgente, conversar
from asistente.llm import SinProveedorError


def mostrar(res: ResultadoAgente) -> None:
    for llamada in res.llamadas:
        nombre, argumentos = llamada['herramienta'], llamada['argumentos']
        estado = 'ERROR' if 'error' in llamada['resultado'] else 'ok'
        print(f'   [herramienta] {nombre}({argumentos}) -> {estado}')
    print(f'Asistente ({res.proveedor}, {res.vueltas} vueltas, {res.segundos:.1f} s): {res.texto}')
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Chat con el agente de la rentadora')
    parser.add_argument('--proveedores', help='orden de proveedores, por ejemplo groq,gemini')
    parser.add_argument('--una', help='manda un solo mensaje y termina')
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')
    proveedores = args.proveedores.split(',') if args.proveedores else None

    if args.una:
        try:
            mostrar(conversar(args.una, proveedores=proveedores))
        except SinProveedorError as e:
            print(f'ERROR {e}')
            return 1
        return 0

    print('Chat con el asistente de la rentadora. Escribí salir para terminar.')
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
            res = conversar(mensaje, historial=historial, proveedores=proveedores)
        except SinProveedorError as e:
            print(f'ERROR {e}')
            continue
        historial = res.historial
        mostrar(res)
    return 0


if __name__ == '__main__':
    sys.exit(main())
