"""Reservas pendientes de aprobación, en memoria (datos FICTICIOS; en L07 pasan a una base de datos).

Escribir no es como leer: una reserva duplicada o que el cliente no pidió le cuesta al negocio.
Por eso reservar tiene dos pasos y las barandas están en código, no en el prompt:

1. preparar(): valida los datos, re-verifica que el auto esté libre y guarda un BORRADOR.
   No reserva nada: devuelve el resumen para que el cliente lo lea.
2. confirmar(): convierte un borrador vigente en una reserva PENDIENTE de aprobación.
   Es idempotente: el mismo borrador produce una sola reserva aunque la llamada se repita.

El id del borrador es una huella (hash) de los datos: mismo pedido, mismo id. Así el sí del
cliente queda atado a esos datos exactos. Que el cliente haya dicho que sí lo controla el
agente (asistente/agente.py), no esta clase.
"""

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from asistente.herramientas import ErrorHerramienta, cotizar

log = logging.getLogger(__name__)

VIGENCIA_BORRADOR_SEG = 30 * 60  # después de 30 minutos hay que volver a cotizar
FECHA = r'^\d{4}-\d{2}-\d{2}$'


class DatosReserva(BaseModel):
    """Los argumentos que manda el modelo. Se validan ANTES de tocar nada."""

    model_config = ConfigDict(extra='forbid', strict=True)

    auto_id: str = Field(pattern=r'^A\d{2}$')
    desde: str = Field(pattern=FECHA)
    hasta: str = Field(pattern=FECHA)
    # Solo nombre y apellido: es una demo pública y no guardamos teléfonos, mails ni documentos
    nombre: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' ]+$")
    retiro_aeropuerto: bool = False
    mascota: bool = False
    cruce_chile: bool = False


@dataclass
class Borrador:
    datos: DatosReserva
    total: int
    creado: float


def _mensaje_de_validacion(error: ValidationError) -> str:
    """Traduce los errores de Pydantic a una frase que el modelo pueda usar para corregir."""
    partes = []
    for detalle in error.errors():
        campo = '.'.join(str(p) for p in detalle['loc']) or 'datos'
        partes.append(f'{campo}: {detalle["msg"]}')
    return 'datos inválidos (' + '; '.join(partes) + '). Pedile al cliente el dato correcto.'


def _id_de_borrador(datos: DatosReserva) -> str:
    """Mismo pedido -> mismo id: preparar dos veces lo mismo no crea dos borradores distintos."""
    huella = hashlib.sha256(datos.model_dump_json().encode()).hexdigest()
    return 'B-' + huella[:8].upper()


class RegistroReservas:
    """Borradores y reservas en memoria. El candado evita que dos pedidos simultáneos se pisen."""

    def __init__(
        self,
        reloj: Callable[[], float] = time.monotonic,
        hoy: Callable[[], date] = date.today,
    ):
        self._reloj = reloj
        self._hoy = hoy
        self._candado = threading.Lock()
        self._borradores: dict[str, Borrador] = {}
        self._reservas: dict[str, dict] = {}  # clave: borrador_id (la clave de idempotencia)

    def preparar(self, argumentos: dict) -> dict:
        """Paso 1: valida, cotiza, re-verifica y guarda un borrador. No reserva nada."""
        try:
            datos = DatosReserva.model_validate(argumentos)
        except ValidationError as e:
            raise ErrorHerramienta(_mensaje_de_validacion(e)) from None
        cotizacion = cotizar(
            datos.auto_id,
            datos.desde,
            datos.hasta,
            retiro_aeropuerto=datos.retiro_aeropuerto,
            mascota=datos.mascota,
            cruce_chile=datos.cruce_chile,
        )
        if date.fromisoformat(datos.desde) < self._hoy():
            raise ErrorHerramienta('la fecha de retiro ya pasó: pedile al cliente fechas nuevas')
        borrador_id = _id_de_borrador(datos)
        with self._candado:
            if borrador_id in self._reservas:
                return {**self._reservas[borrador_id], 'ya_existia': True}
            if not cotizacion['disponible'] or self._ocupado(datos):
                raise ErrorHerramienta(f'el auto {datos.auto_id} no está libre en esas fechas; ofrecé otro')
            anterior = self._borradores.get(borrador_id)
            nuevo = anterior is None or self._vencido(anterior)
            self._borradores[borrador_id] = Borrador(datos, cotizacion['total'], self._reloj())
        log.info('borrador %s preparado (%s, %d días)', borrador_id, datos.auto_id, cotizacion['dias'])
        return {
            'borrador_id': borrador_id,
            'nuevo': nuevo,
            'auto': f'{cotizacion["modelo"]} ({datos.auto_id})',
            'desde': datos.desde,
            'hasta': datos.hasta,
            'dias': cotizacion['dias'],
            'extras': cotizacion['extras'],
            'total': cotizacion['total'],
            'moneda': cotizacion['moneda'],
            'siguiente_paso': (
                'Mostrale al cliente este resumen con el borrador_id y preguntale si confirma. '
                'No llames a crear_reserva hasta que responda que sí.'
            ),
        }

    def confirmar(self, borrador_id: str) -> dict:
        """Paso 2: borrador vigente -> reserva pendiente de aprobación. Idempotente."""
        with self._candado:
            if borrador_id in self._reservas:
                log.info('reserva %s pedida otra vez: devuelvo la misma', borrador_id)
                return {**self._reservas[borrador_id], 'ya_existia': True}
            borrador = self._borradores.get(borrador_id)
            if borrador is None:
                raise ErrorHerramienta(
                    f'no existe el borrador {borrador_id!r}: llamá antes a preparar_reserva'
                )
            if self._vencido(borrador):
                del self._borradores[borrador_id]
                raise ErrorHerramienta('el borrador venció: llamá otra vez a preparar_reserva')
            if self._ocupado(borrador.datos):
                raise ErrorHerramienta('otro cliente acaba de reservar ese auto: ofrecé otro')
            datos = borrador.datos
            reserva = {
                'reserva_id': 'R-' + borrador_id.removeprefix('B-'),
                'estado': 'pendiente_de_aprobacion',
                'auto_id': datos.auto_id,
                'desde': datos.desde,
                'hasta': datos.hasta,
                'nombre': datos.nombre,
                'total': borrador.total,
            }
            self._reservas[borrador_id] = reserva
            del self._borradores[borrador_id]
        log.info('reserva %s creada, pendiente de aprobación', reserva['reserva_id'])
        return {**reserva, 'ya_existia': False}

    def reservas(self) -> list[dict]:
        """Copia de las reservas creadas (para los tests y, en L07, para guardarlas)."""
        with self._candado:
            return [dict(r) for r in self._reservas.values()]

    def _vencido(self, borrador: Borrador) -> bool:
        return self._reloj() - borrador.creado > VIGENCIA_BORRADOR_SEG

    def _ocupado(self, datos: DatosReserva) -> bool:
        """True si choca con una reserva ya creada en esta demo (las de flota.json las mira cotizar)."""
        return any(
            r['auto_id'] == datos.auto_id and datos.desde < r['hasta'] and r['desde'] < datos.hasta
            for r in self._reservas.values()
        )


REGISTRO = RegistroReservas()
