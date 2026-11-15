"""Configuración de la API web, leída de variables de entorno (ver .env.example)."""

import os
from dataclasses import dataclass, field

ORIGENES_LOCALES = ['http://localhost:5500', 'http://127.0.0.1:5500']


def _lista(valor: str) -> list[str]:
    """'a, b,,c' -> ['a', 'b', 'c']"""
    return [parte.strip() for parte in valor.split(',') if parte.strip()]


def _entero(nombre: str, por_defecto: int) -> int:
    """Entero positivo de una variable de entorno; si está vacía, el valor por defecto."""
    valor = os.environ.get(nombre, '').strip()
    if not valor:
        return por_defecto
    try:
        numero = int(valor)
    except ValueError as e:
        raise ValueError(f'{nombre} tiene que ser un número entero y vale {valor!r}') from e
    if numero < 1:
        raise ValueError(f'{nombre} tiene que ser mayor que 0 y vale {numero}')
    return numero


@dataclass(frozen=True)
class Ajustes:
    origenes_cors: list[str] = field(default_factory=lambda: list(ORIGENES_LOCALES))
    max_mensajes_por_sesion: int = 20
    max_pedidos_por_minuto: int = 10
    max_sesiones: int = 500
    max_historial: int = 20

    @classmethod
    def desde_entorno(cls) -> 'Ajustes':
        """Ajustes a partir del entorno; lo que no esté definido usa el valor por defecto."""
        base = cls()
        origenes = os.environ.get('ORIGENES_CORS')
        return cls(
            origenes_cors=_lista(origenes) if origenes is not None else base.origenes_cors,
            max_mensajes_por_sesion=_entero('MAX_MENSAJES_POR_SESION', base.max_mensajes_por_sesion),
            max_pedidos_por_minuto=_entero('MAX_PEDIDOS_POR_MINUTO', base.max_pedidos_por_minuto),
            max_sesiones=_entero('MAX_SESIONES', base.max_sesiones),
            max_historial=_entero('MAX_HISTORIAL', base.max_historial),
        )
