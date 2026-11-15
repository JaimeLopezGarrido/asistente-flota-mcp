"""Atención con router: primero se clasifica el mensaje y después se elige el camino.

politica         -> una sola llamada con las políticas en el prompt (asistente/llm.py)
cotizacion       -> el agente con herramientas (asistente/agente.py)
reclamo          -> respuesta fija y derivación a una persona, sin más llamadas
fuera_de_alcance -> respuesta fija, sin más llamadas
"""

import logging
import re
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
    proveedor: str = 'ninguno'  # quién escribió la respuesta ('ninguno' = respuesta fija)
    herramientas: list[str] = field(default_factory=list)  # las que usó el agente, en orden
    fuentes: list[dict] = field(default_factory=list)  # fragmentos del manual citados: pagina, seccion, extracto


def fuentes_citadas(texto: str, fragmentos: list[dict]) -> list[dict]:
    """Los fragmentos cuya página aparece citada en la respuesta como [pág. N], sin repetir páginas."""
    citadas = {int(n) for n in re.findall(r'p[áa]g\.?\s*(\d+)', texto, flags=re.IGNORECASE)}
    salida, vistas = [], set()
    for f in fragmentos:
        if f['pagina'] in citadas and f['pagina'] not in vistas:
            vistas.add(f['pagina'])
            salida.append({'pagina': f['pagina'], 'seccion': f.get('seccion', ''), 'extracto': f['texto'][:280]})
    return salida


def _buscar_en_manual(mensaje: str) -> list[dict]:
    """El RAG nunca tumba la atención: si algo falla, se responde sin manual."""
    try:
        from rag.buscar import buscar

        return buscar(mensaje)
    except Exception as e:  # noqa: BLE001 (índice ausente o error inesperado: seguimos sin manual)
        log.warning('no pude buscar en el manual: %s', e)
        return []


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
    proveedor: str = 'ninguno',
) -> Atencion:
    """Respuesta de un camino sin agente, con el historial actualizado."""
    nuevo = [
        *previos,
        {'role': 'user', 'content': envolver_mensaje(mensaje)},
        {'role': 'assistant', 'content': texto},
    ]
    return Atencion(texto, decision.ruta, decision.motivo, llamadas, derivar, nuevo, proveedor)


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
        fragmentos = _buscar_en_manual(mensaje)
        try:
            resultado = llm.responder(mensaje, proveedores, manual=fragmentos)
        except SinProveedorError as e:
            log.warning('camino de políticas sin proveedor (%s); paso al agente', e)
        else:
            llamadas += 1
            respuesta = resultado.respuesta
            if respuesta.intencion not in INTENCIONES_DEL_AGENTE:
                cierre = _cerrar(
                    mensaje,
                    previos,
                    decision,
                    respuesta.respuesta,
                    llamadas,
                    respuesta.derivar_a_humano,
                    resultado.proveedor,
                )
                paginas = set(respuesta.paginas_manual) & {f['pagina'] for f in fragmentos}
                if paginas and not re.search(r'p[áa]g\.', cierre.texto, flags=re.IGNORECASE):
                    # El modelo usó el manual pero no citó en el texto: agregamos la cita nosotros
                    cita = ', '.join(str(p) for p in sorted(paginas))
                    cierre.texto = f'{cierre.texto} [pág. {cita}]'
                    cierre.historial[-1]['content'] = cierre.texto
                cierre.fuentes = fuentes_citadas(cierre.texto, fragmentos)
                return cierre
            log.info('el camino de políticas detectó %s; paso al agente', respuesta.intencion)

    res = agente.conversar(mensaje, historial=previos, proveedores=proveedores)
    herramientas = [llamada['herramienta'] for llamada in res.llamadas]
    del_manual = [
        f
        for llamada in res.llamadas
        if llamada['herramienta'] == 'buscar_manual'
        for f in (llamada.get('resultado') or {}).get('fragmentos', [])
    ]
    return Atencion(
        res.texto,
        decision.ruta,
        decision.motivo,
        llamadas + res.vueltas,
        False,
        res.historial,
        res.proveedor,
        herramientas,
        fuentes_citadas(res.texto, del_manual),
    )
