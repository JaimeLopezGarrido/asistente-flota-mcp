"""Conversaciones guardadas en SQLite y límite de uso por visitante.

Las conversaciones viven en la base (asistente/base.py): sobreviven a un reinicio del servidor y las
ven todos los procesos que usan el mismo archivo. El límite por minuto queda en memoria a propósito:
es un contador de vida corta y perderlo al reiniciar no le cuesta nada a nadie.
"""

import json
import sqlite3
import threading
import time
from collections import deque
from collections.abc import Callable

from asistente import base as bd

VENTANA_SEGUNDOS = 60


class LimiteAlcanzadoError(Exception):
    """El visitante superó un límite. El mensaje se le puede mostrar tal cual."""

    def __init__(self, motivo: str, reintentar_en: int | None = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.reintentar_en = reintentar_en


def _siguiente_uso(con: sqlite3.Connection) -> int:
    """Contador que solo sube: la conversación con el número más bajo es la que hace más que no se usa."""
    return con.execute('SELECT COALESCE(MAX(uso), 0) + 1 FROM conversaciones').fetchone()[0]


class AlmacenDeSesiones:
    """Historial por sesión, con tope de mensajes por sesión y de sesiones en total."""

    def __init__(
        self,
        max_sesiones: int,
        max_mensajes: int,
        max_historial: int,
        base: bd.BaseDeDatos | None = None,
    ):
        self.max_sesiones = max_sesiones
        self.max_mensajes = max_mensajes
        self.max_historial = max_historial
        self._base = base

    @property
    def base(self) -> bd.BaseDeDatos:
        """La base propia o la del proceso (en los tests, una temporal)."""
        return self._base or bd.obtener()

    def historial(self, sesion_id: str) -> list[dict]:
        """Copia del historial ([] si la sesión es nueva). Lanza LimiteAlcanzadoError si se agotó."""
        with self.base.transaccion() as con:
            fila = con.execute(
                'SELECT mensajes_usados FROM conversaciones WHERE sesion_id = ?', (sesion_id,)
            ).fetchone()
            if fila is None:
                return []
            if fila['mensajes_usados'] >= self.max_mensajes:
                raise LimiteAlcanzadoError(
                    f'Esta conversación llegó al máximo de {self.max_mensajes} mensajes. Empezá una nueva.'
                )
            uso = _siguiente_uso(con)
            con.execute('UPDATE conversaciones SET uso = ? WHERE sesion_id = ?', (uso, sesion_id))
            filas = con.execute(
                'SELECT contenido FROM mensajes WHERE sesion_id = ? ORDER BY orden', (sesion_id,)
            ).fetchall()
        return [json.loads(f['contenido']) for f in filas]

    def guardar(self, sesion_id: str, historial: list[dict]) -> int:
        """Guarda el historial nuevo (recortado) y devuelve cuántos mensajes le quedan a la sesión."""
        recorte = historial[-self.max_historial:]
        while recorte and recorte[0].get('role') != 'user':
            recorte = recorte[1:]
        filas = [
            (sesion_id, orden, mensaje['role'], json.dumps(mensaje, ensure_ascii=False))
            for orden, mensaje in enumerate(recorte)
        ]
        with self.base.transaccion() as con:
            con.execute(
                'INSERT INTO conversaciones (sesion_id, mensajes_usados, uso) VALUES (?, 1, ?) '
                'ON CONFLICT (sesion_id) DO UPDATE SET '
                'mensajes_usados = mensajes_usados + 1, uso = excluded.uso',
                (sesion_id, _siguiente_uso(con)),
            )
            con.execute('DELETE FROM mensajes WHERE sesion_id = ?', (sesion_id,))
            con.executemany(
                'INSERT INTO mensajes (sesion_id, orden, rol, contenido) VALUES (?, ?, ?, ?)', filas
            )
            usados = con.execute(
                'SELECT mensajes_usados FROM conversaciones WHERE sesion_id = ?', (sesion_id,)
            ).fetchone()[0]
            # Más sesiones que el tope: se borran las que hace más que no se usan (y sus mensajes, en cascada)
            con.execute(
                'DELETE FROM conversaciones WHERE sesion_id IN '
                '(SELECT sesion_id FROM conversaciones ORDER BY uso DESC LIMIT -1 OFFSET ?)',
                (self.max_sesiones,),
            )
        return max(self.max_mensajes - usados, 0)

    def cantidad(self) -> int:
        with self.base.conexion() as con:
            return con.execute('SELECT COUNT(*) FROM conversaciones').fetchone()[0]


class LimitadorPorMinuto:
    """Ventana deslizante: cada visitante puede hacer `maximo` pedidos cada 60 segundos."""

    def __init__(self, maximo: int, reloj: Callable[[], float] = time.monotonic):
        self.maximo = maximo
        self._reloj = reloj
        self._pedidos: dict[str, deque[float]] = {}
        self._candado = threading.Lock()

    def registrar(self, visitante: str) -> None:
        """Cuenta un pedido del visitante, o lanza LimiteAlcanzadoError si ya llegó al máximo."""
        ahora = self._reloj()
        with self._candado:
            pedidos = self._pedidos.setdefault(visitante, deque())
            while pedidos and ahora - pedidos[0] >= VENTANA_SEGUNDOS:
                pedidos.popleft()
            if len(pedidos) >= self.maximo:
                espera = int(VENTANA_SEGUNDOS - (ahora - pedidos[0])) + 1
                raise LimiteAlcanzadoError(
                    'Demasiados mensajes seguidos. Esperá un minuto y probá de nuevo.', reintentar_en=espera
                )
            pedidos.append(ahora)
