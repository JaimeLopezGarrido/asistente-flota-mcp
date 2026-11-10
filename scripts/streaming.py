"""Demo de streaming: muestra la respuesta a medida que el modelo la genera (sin herramientas).

Uso:
    python -m scripts.streaming
    python -m scripts.streaming --proveedor gemini 'Tu pregunta'
"""

import argparse
import sys
import time

from dotenv import load_dotenv

from asistente.agente import crear_cliente

PREGUNTA = 'En 5 oraciones: ¿por qué conviene alquilar una 4x4 para ir al cerro Catedral en julio?'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Demo de streaming')
    parser.add_argument('pregunta', nargs='?', default=PREGUNTA)
    parser.add_argument('--proveedor', default='groq', help='gemini, groq u ollama')
    args = parser.parse_args(argv)
    load_dotenv()

    cliente, modelo = crear_cliente(args.proveedor)
    inicio = time.perf_counter()
    primer_texto = None
    stream = cliente.chat.completions.create(
        model=modelo, messages=[{'role': 'user', 'content': args.pregunta}], stream=True
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        pedazo = chunk.choices[0].delta.content or ''
        if pedazo and primer_texto is None:
            primer_texto = time.perf_counter() - inicio
        print(pedazo, end='', flush=True)
    total = time.perf_counter() - inicio
    print()
    print(f'Primer texto a los {primer_texto or 0:.2f} s · respuesta completa a los {total:.2f} s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
