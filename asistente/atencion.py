"""Atención con router: primero se clasifica el mensaje y después se elige el camino.

politica         -> una sola llamada con las políticas en el prompt (asistente/llm.py)
cotizacion       -> el agente con herramientas (asistente/agente.py)
reclamo          -> respuesta fija y derivación a una persona, sin más llamadas
fuera_de_alcance -> respuesta fija, sin más llamadas
"""

import logging
from dataclasses import dataclass, field

from asistente import agente, llm, router
from asistente.llm import SinProveedorError
from asistente.prompt import envolver_mensaje
from asistente.router import Decision

log = logging.getLogger(__name__)

RESPUESTA_RECLAMO = (
    'Lamento mucho lo que pasó. Para resolverlo bien lo tiene que ver una persona del equipo: '
    'ya dejé tu mensaje marcado como reclamo y te van a escribir por este mismo chat.'
)
RESPUESTA_FUERA = (
    'Solo puedo ayudarte con el alquiler de autos: disponibilidad, precios y políticas '
    '(requisitos, garantía, kilometraje, Chile, mascotas, pagos y cancelación). ¿En qué te ayudo?'
)
# Si el camino de políticas detecta una de estas intenciones, el router se equivocó: pasa al agente
INTENCIONES_DEL_AGENTE = {'disponibilidad', 'tarifa', 'reserva'}


@dataclass
class Atencion:
    texto: str
    ruta: str
    motivo: str
    llamadas_llm: int
    derivar_a_humano: bool
    historial: list[dict] = field(default_factory=list)


def _ultimo_asistente(historial: list[dict]) -> str | None:
    for mensaje in reversed(historial):
        if mensaje.get('role') == 'assistant' and mensaje.get('content'):
            return mensaje['content']
    return None


def _cerrar(
    mensaje: str,
    previos: list[dict],
    decision: Decision,
    texto: str,
    llamadas: int,
    derivar: bool,
) -> Atencion:
    """Respuesta de un camino sin agente, con el historial actualizado."""
    nuevo = [
        *previos,
        {'role': 'user', 'content': envolver_mensaje(mensaje)},
        {'role': 'assistant', 'content': texto},
    ]
    return Atencion(texto, decision.ruta, decision.motivo, llamadas, derivar, nuevo)


def atender(
    mensaje: str,
    historial: list[dict] | None = None,
    proveedores: list[str] | None = None,
) -> Atencion:
    """Clasifica el mensaje y lo resuelve por el camino más simple que alcanza."""
    previos = list(historial or [])
    decision = router.clasificar(mensaje, _ultimo_asistente(previos), proveedores)
    llamadas = 0 if decision.proveedor == 'ninguno' else 1

    if decision.ruta == 'reclamo':
        return _cerrar(mensaje, previos, decision, RESPUESTA_RECLAMO, llamadas, derivar=True)
    if decision.ruta == 'fuera_de_alcance':
        return _cerrar(mensaje, previos, decision, RESPUESTA_FUERA, llamadas, derivar=False)
    if decision.ruta == 'politica':
        try:
            resultado = llm.responder(mensaje, proveedores)
        except SinProveedorError as e:
            log.warning('camino de políticas sin proveedor (%s); paso al agente', e)
        else:
            llamadas += 1
            respuesta = resultado.respuesta
            if respuesta.intencion not in INTENCIONES_DEL_AGENTE:
                return _cerrar(
                    mensaje, previos, decision, respuesta.respuesta, llamadas, respuesta.derivar_a_humano
                )
            log.info('el camino de políticas detectó %s; paso al agente', respuesta.intencion)

    res = agente.conversar(mensaje, historial=previos, proveedores=proveedores)
    return Atencion(res.texto, decision.ruta, decision.motivo, llamadas + res.vueltas, False, res.historial)
