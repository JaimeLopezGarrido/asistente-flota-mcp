"""Sesiones de conversación en memoria y límites de uso por visitante.

En memoria quiere decir que se pierden al reiniciar el servidor y que no se comparten entre procesos:
alcanza para una demo con un solo proceso. La persistencia en base de datos llega en L07.
"""

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field

VENTANA_SEGUNDOS = 60


class LimiteAlcanzadoError(Exception):
    """El visitante superó un límite. El mensaje se le puede mostrar tal cual."""

    def __init__(self, motivo: str, reintentar_en: int | None = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.reintentar_en = reintentar_en


@dataclass
class Sesion:
    historial: list[dict] = field(default_factory=list)
    mensajes: int = 0


class AlmacenDeSesiones:
    """Historial por sesión, con tope de mensajes por sesión y de sesiones en total."""

    def __init__(self, max_sesiones: int, max_mensajes: int, max_historial: int):
        self.max_sesiones = max_sesiones
        self.max_mensajes = max_mensajes
        self.max_historial = max_historial
        self._sesiones: OrderedDict[str, Sesion] = OrderedDict()
        self._candado = threading.Lock()

    def historial(self, sesion_id: str) -> list[dict]:
        """Copia del historial ([] si la sesión es nueva). Lanza LimiteAlcanzadoError si se agotó."""
        with self._candado:
            sesion = self._sesiones.get(sesion_id)
            if sesion is None:
                return []
            if sesion.mensajes >= self.max_mensajes:
                raise LimiteAlcanzadoError(
                    f'Esta conversación llegó al máximo de {self.max_mensajes} mensajes. Empezá una nueva.'
                )
            self._sesiones.move_to_end(sesion_id)
            return list(sesion.historial)

    def guardar(self, sesion_id: str, historial: list[dict]) -> int:
        """Guarda el historial nuevo (recortado) y devuelve cuántos mensajes le quedan a la sesión."""
        recorte = historial[-self.max_historial:]
        while recorte and recorte[0].get('role') != 'user':
            recorte = recorte[1:]
        with self._candado:
            sesion = self._sesiones.setdefault(sesion_id, Sesion())
            sesion.historial = recorte
            sesion.mensajes += 1
            self._sesiones.move_to_end(sesion_id)
            while len(self._sesiones) > self.max_sesiones:
                self._sesiones.popitem(last=False)  # la que hace más tiempo no se usa
            return max(self.max_mensajes - sesion.mensajes, 0)

    def cantidad(self) -> int:
        with self._candado:
            return len(self._sesiones)


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
