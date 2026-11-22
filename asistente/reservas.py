"""Reservas pendientes de aprobación, guardadas en SQLite (datos FICTICIOS).

Escribir no es como leer: una reserva duplicada o que el cliente no pidió le cuesta al negocio.
Por eso reservar tiene dos pasos y las barandas están en código, no en el prompt:

1. preparar(): valida los datos, re-verifica que el auto esté libre y guarda un BORRADOR.
   No reserva nada: devuelve el resumen para que el cliente lo lea.
2. confirmar(): convierte un borrador vigente en una reserva PENDIENTE de aprobación.
   Es idempotente: el mismo borrador produce una sola reserva aunque la llamada se repita.

El id del borrador es una huella (hash) de los datos: mismo pedido, mismo id. Desde L07,
borradores y reservas viven en la base (asistente/base.py) y cada paso corre en una transacción:
verificar y escribir pasan juntos, aunque haya varios procesos. Que el cliente haya dicho que sí
lo controla el agente (asistente/agente.py), no esta clase.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from asistente import base as bd
from asistente.herramientas import ErrorHerramienta, cotizar

log = logging.getLogger(__name__)

VIGENCIA_BORRADOR_SEG = 30 * 60  # después de 30 minutos hay que volver a cotizar
FECHA = r'^\d{4}-\d{2}-\d{2}$'
# La reserva como la ve el agente, con el nombre del cliente (los bloqueos de la semilla no tienen cliente)
_RESERVA = (
    'SELECT r.id AS reserva_id, r.estado, r.auto_id, r.desde, r.hasta, c.nombre, r.total '
    'FROM reservas AS r JOIN clientes AS c ON c.id = r.cliente_id'
)


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
    """Borradores y reservas en la base. La transacción reemplaza al candado de L06."""

    def __init__(
        self,
        reloj: Callable[[], float] = time.time,
        hoy: Callable[[], date] = date.today,
        base: bd.BaseDeDatos | None = None,
    ):
        # time.time y no time.monotonic: el momento se guarda en la base y tiene que seguir valiendo
        # para otro proceso o después de un reinicio (monotonic no tiene una fecha de referencia fija)
        self._reloj = reloj
        self._hoy = hoy
        self._base = base

    @property
    def base(self) -> bd.BaseDeDatos:
        """La base propia o la del proceso (en los tests, una temporal)."""
        return self._base or bd.obtener()

    def preparar(self, argumentos: dict) -> dict:
        """Paso 1: valida, cotiza, re-verifica y guarda un borrador. No reserva nada."""
        try:
            datos = DatosReserva.model_validate(argumentos)
        except ValidationError as e:
            raise ErrorHerramienta(_mensaje_de_validacion(e)) from None
        # Lo que tarda o puede fallar va ANTES de la transacción: así la transacción es corta
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
        with self.base.transaccion() as con:
            ya_creada = con.execute(_RESERVA + ' WHERE r.borrador_id = ?', (borrador_id,)).fetchone()
            if ya_creada is not None:
                return {**dict(ya_creada), 'ya_existia': True}
            if not bd.auto_libre(con, datos.auto_id, datos.desde, datos.hasta):
                raise ErrorHerramienta(f'el auto {datos.auto_id} no está libre en esas fechas; ofrecé otro')
            anterior = con.execute('SELECT creado FROM borradores WHERE id = ?', (borrador_id,)).fetchone()
            nuevo = anterior is None or self._vencido(anterior['creado'])
            con.execute(
                'INSERT INTO borradores (id, datos, total, creado) VALUES (?, ?, ?, ?) '
                'ON CONFLICT (id) DO UPDATE SET total = excluded.total, creado = excluded.creado',
                (borrador_id, datos.model_dump_json(), cotizacion['total'], self._reloj()),
            )
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
        with self.base.transaccion() as con:
            ya_creada = con.execute(_RESERVA + ' WHERE r.borrador_id = ?', (borrador_id,)).fetchone()
            if ya_creada is not None:
                log.info('reserva de %s pedida otra vez: devuelvo la misma', borrador_id)
                return {**dict(ya_creada), 'ya_existia': True}
            borrador = con.execute(
                'SELECT datos, total, creado FROM borradores WHERE id = ?', (borrador_id,)
            ).fetchone()
            if borrador is None:
                raise ErrorHerramienta(
                    f'no existe el borrador {borrador_id!r}: llamá antes a preparar_reserva'
                )
            if self._vencido(borrador['creado']):
                raise ErrorHerramienta('el borrador venció: llamá otra vez a preparar_reserva')
            datos = DatosReserva.model_validate_json(borrador['datos'])
            if not bd.auto_libre(con, datos.auto_id, datos.desde, datos.hasta):
                raise ErrorHerramienta('otro cliente acaba de reservar ese auto: ofrecé otro')
            # Recién ahora se escribe: todo lo que podía fallar ya se verificó
            con.execute(
                'INSERT INTO clientes (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING', (datos.nombre,)
            )
            cliente = con.execute('SELECT id FROM clientes WHERE nombre = ?', (datos.nombre,)).fetchone()
            reserva_id = 'R-' + borrador_id.removeprefix('B-')
            con.execute(
                'INSERT INTO reservas (id, borrador_id, auto_id, cliente_id, desde, hasta, total, estado) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    reserva_id,
                    borrador_id,
                    datos.auto_id,
                    cliente['id'],
                    datos.desde,
                    datos.hasta,
                    borrador['total'],
                    'pendiente_de_aprobacion',
                ),
            )
            con.execute('DELETE FROM borradores WHERE id = ?', (borrador_id,))
            reserva = dict(con.execute(_RESERVA + ' WHERE r.id = ?', (reserva_id,)).fetchone())
        log.info('reserva %s creada, pendiente de aprobación', reserva_id)
        return {**reserva, 'ya_existia': False}

    def reservas(self) -> list[dict]:
        """Las reservas creadas en la demo (sin los días bloqueados de la semilla)."""
        with self.base.conexion() as con:
            filas = con.execute(_RESERVA + ' ORDER BY r.creada, r.id').fetchall()
        return [dict(fila) for fila in filas]

    def _vencido(self, creado: float) -> bool:
        return self._reloj() - creado > VIGENCIA_BORRADOR_SEG


REGISTRO = RegistroReservas()
