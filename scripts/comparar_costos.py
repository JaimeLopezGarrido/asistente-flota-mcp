"""Estima tokens de entrada por mensaje: mandar todo al agente contra usar el router.

Es una estimación: cuenta con tiktoken los tokens de los prompts fijos y supone cuántas
llamadas hace cada camino. No llama a ninguna API.

Uso:
    python -m scripts.comparar_costos
"""

import json
import sys
from collections.abc import Callable

import tiktoken

from asistente.agente import cargar_instrucciones as instrucciones_agente
from asistente.herramientas import HERRAMIENTAS
from asistente.prompt import cargar_sistema
from asistente.router import cargar_instrucciones as instrucciones_router

# Mezcla ficticia de mensajes de un día: ruta -> porcentaje
MEZCLA = {'politica': 40, 'cotizacion': 35, 'reclamo': 15, 'fuera_de_alcance': 10}
# Llamadas que hace el agente solo, por ruta (a ojo, mirando scripts.chat)
VUELTAS_AGENTE = {'politica': 2, 'cotizacion': 3, 'reclamo': 1, 'fuera_de_alcance': 1}
MENSAJE_TIPICO = 40  # tokens de un mensaje de cliente promedio
EXTRA_POR_VUELTA = 150  # tokens que suma cada ida y vuelta de herramienta (pedido + resultado)


def prefijos(contar: Callable[[str], int]) -> dict[str, int]:
    """Tokens de la parte fija que se manda en cada llamada de cada camino."""
    menu = json.dumps(HERRAMIENTAS, ensure_ascii=False)
    return {
        'agente': contar(instrucciones_agente()) + contar(menu),
        'politicas': contar(cargar_sistema()),
        'router': contar(instrucciones_router()),
    }


def tokens_agente(prefijo: int, vueltas: int) -> int:
    """Cada vuelta reenvía el prefijo, el mensaje y lo acumulado en las vueltas anteriores."""
    return sum(prefijo + MENSAJE_TIPICO + EXTRA_POR_VUELTA * i for i in range(vueltas))


def estimar(p: dict[str, int]) -> dict[str, dict[str, int]]:
    """Tokens de entrada y llamadas por mensaje, para cada ruta y cada diseño."""
    filas = {}
    for ruta, pct in MEZCLA.items():
        vueltas = VUELTAS_AGENTE[ruta]
        solo = tokens_agente(p['agente'], vueltas)
        con = p['router'] + MENSAJE_TIPICO
        llamadas = 1
        if ruta == 'politica':
            con += p['politicas'] + MENSAJE_TIPICO
            llamadas += 1
        elif ruta == 'cotizacion':
            con += solo
            llamadas += vueltas
        filas[ruta] = {
            'pct': pct,
            'solo_agente': solo,
            'con_router': con,
            'llamadas_solo': vueltas,
            'llamadas_router': llamadas,
        }
    return filas


def promedio(filas: dict[str, dict[str, int]], columna: str) -> float:
    """Promedio ponderado por el porcentaje de cada ruta."""
    return sum(fila['pct'] * fila[columna] for fila in filas.values()) / 100


def main() -> int:
    codificador = tiktoken.get_encoding('o200k_base')

    def contar(texto: str) -> int:
        return len(codificador.encode(texto))

    p = prefijos(contar)
    filas = estimar(p)
    print('Prefijos fijos (tokens):', ', '.join(f'{nombre} {n}' for nombre, n in p.items()))
    print()
    print('ruta                 %  solo agente   con router   llamadas')
    for ruta, fila in filas.items():
        pct, solo, con = fila['pct'], fila['solo_agente'], fila['con_router']
        ls, lr = fila['llamadas_solo'], fila['llamadas_router']
        print(f'{ruta:<18}{pct:>4}%{solo:>13}{con:>13}{ls:>8} -> {lr}')
    solo, con = promedio(filas, 'solo_agente'), promedio(filas, 'con_router')
    ls, lr = promedio(filas, 'llamadas_solo'), promedio(filas, 'llamadas_router')
    print()
    print(f'Promedio por mensaje: {solo:.0f} tokens solo agente, {con:.0f} con router')
    print(f'Diferencia: {100 * (solo - con) / solo:.0f}% menos tokens de entrada con router')
    print(f'Llamadas promedio por mensaje: {ls:.2f} solo agente, {lr:.2f} con router')
    return 0


if __name__ == '__main__':
    sys.exit(main())
