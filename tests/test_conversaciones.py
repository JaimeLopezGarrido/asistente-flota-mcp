"""Conversaciones guardadas en la base: se recuperan tal cual después de un reinicio."""

from api.sesiones import AlmacenDeSesiones
from asistente import base as bd

LLAMADA = {'id': 'call_1', 'type': 'function', 'function': {'name': 'buscar_disponibilidad', 'arguments': '{}'}}
HISTORIAL = [
    {'role': 'user', 'content': '¿Tienen SUV para el finde largo?'},
    {'role': 'assistant', 'content': None, 'tool_calls': [LLAMADA]},
    {'role': 'tool', 'tool_call_id': 'call_1', 'content': '{"cantidad": 2}'},
    {'role': 'assistant', 'content': 'Sí, tengo dos SUV libres.'},
]


def _almacen(base: bd.BaseDeDatos | None = None, max_sesiones: int = 5) -> AlmacenDeSesiones:
    return AlmacenDeSesiones(max_sesiones=max_sesiones, max_mensajes=10, max_historial=20, base=base)


def test_la_conversacion_sobrevive_a_un_reinicio(tmp_path):
    ruta = tmp_path / 'chat.db'
    _almacen(bd.BaseDeDatos(ruta)).guardar('sesion-ana-01', HISTORIAL)
    reiniciado = _almacen(bd.BaseDeDatos(ruta))
    assert reiniciado.historial('sesion-ana-01') == HISTORIAL
    assert reiniciado.cantidad() == 1


def test_el_contador_de_mensajes_tambien_persiste(tmp_path):
    ruta = tmp_path / 'chat.db'
    _almacen(bd.BaseDeDatos(ruta)).guardar('sesion-beto-1', HISTORIAL[:1])
    restantes = _almacen(bd.BaseDeDatos(ruta)).guardar('sesion-beto-1', HISTORIAL)
    assert restantes == 10 - 2


def test_borrar_una_conversacion_borra_sus_mensajes():
    almacen = _almacen(max_sesiones=1)
    almacen.guardar('sesion-vieja-1', HISTORIAL)
    almacen.guardar('sesion-nueva-1', HISTORIAL[:1])
    with bd.obtener().conexion() as con:
        sesiones = {fila['sesion_id'] for fila in con.execute('SELECT sesion_id FROM mensajes')}
    assert sesiones == {'sesion-nueva-1'}
