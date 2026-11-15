from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.config import Ajustes
from api.main import crear_app
from api.sesiones import AlmacenDeSesiones, LimitadorPorMinuto, LimiteAlcanzadoError
from asistente import atencion
from asistente.llm import SinProveedorError
from asistente.router import Decision

ORIGEN_DEMO = 'https://demo.ejemplo.com'
RESPUESTA = 'Hay 2 SUV libres del 10 al 14.'


class _AgenteFalso:
    """Reemplaza agente.conversar: no llama a ningún proveedor y guarda el historial que recibió."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.historiales: list[list[dict]] = []

    def __call__(self, mensaje, historial=None, proveedores=None):
        previos = list(historial or [])
        self.historiales.append(previos)
        if self.error is not None:
            raise self.error
        nuevo = [*previos, {'role': 'user', 'content': mensaje}, {'role': 'assistant', 'content': RESPUESTA}]
        return SimpleNamespace(
            texto=RESPUESTA,
            proveedor='falso',
            vueltas=2,
            llamadas=[{'herramienta': 'buscar_disponibilidad'}, {'herramienta': 'cotizar'}],
            historial=nuevo,
        )


def _clasificar_falso(*args, **kwargs) -> Decision:
    return Decision('cotizacion', 'pide fechas', 'falso')


@pytest.fixture
def agente(monkeypatch) -> _AgenteFalso:
    falso = _AgenteFalso()
    monkeypatch.setattr(atencion.router, 'clasificar', _clasificar_falso)
    monkeypatch.setattr(atencion.agente, 'conversar', falso)
    return falso


def _cliente(**cambios) -> TestClient:
    return TestClient(crear_app(Ajustes(origenes_cors=[ORIGEN_DEMO], **cambios)))


def _chat(cliente: TestClient, mensaje: str, sesion_id: str | None = None):
    cuerpo = {'mensaje': mensaje}
    if sesion_id:
        cuerpo['sesion_id'] = sesion_id
    return cliente.post('/chat', json=cuerpo)


def test_salud_responde_ok():
    r = _cliente().get('/salud')
    assert r.status_code == 200
    assert r.json()['estado'] == 'ok'


def test_chat_devuelve_ruta_herramientas_y_proveedor(agente):
    r = _chat(_cliente(), '¿Tienen SUV del 10 al 14?', 'sesion-prueba-1')
    assert r.status_code == 200
    datos = r.json()
    assert datos['respuesta'] == RESPUESTA
    assert datos['ruta'] == 'cotizacion'
    assert datos['herramientas'] == ['buscar_disponibilidad', 'cotizar']
    assert datos['proveedor'] == 'falso'
    assert datos['llamadas_llm'] == 1 + 2
    assert datos['sesion_id'] == 'sesion-prueba-1'


def test_sin_sesion_la_api_crea_una(agente):
    datos = _chat(_cliente(), 'hola').json()
    assert len(datos['sesion_id']) == 32


def test_el_historial_se_guarda_por_sesion(agente):
    cliente = _cliente()
    _chat(cliente, 'Quiero una camioneta', 'sesion-ana-01')
    _chat(cliente, 'Del 10 al 14 de diciembre', 'sesion-ana-01')
    _chat(cliente, 'Hola', 'sesion-beto-01')
    assert agente.historiales[0] == []
    assert [m['role'] for m in agente.historiales[1]] == ['user', 'assistant']
    assert agente.historiales[2] == []


@pytest.mark.parametrize(
    'cuerpo',
    [
        {'mensaje': '   '},
        {'mensaje': 'x' * 1001},
        {'mensaje': 'hola', 'sesion_id': 'corto'},
        {'mensaje': 'hola', 'sesion_id': 'tiene espacios y ñ'},
        {'mensaje': 'hola', 'admin': True},
    ],
)
def test_pedidos_invalidos_dan_422_sin_llamar_al_agente(agente, cuerpo):
    r = _cliente().post('/chat', json=cuerpo)
    assert r.status_code == 422
    assert agente.historiales == []


def test_limite_de_mensajes_por_sesion(agente):
    cliente = _cliente(max_mensajes_por_sesion=2)
    assert _chat(cliente, 'uno', 'sesion-larga-1').json()['mensajes_restantes'] == 1
    assert _chat(cliente, 'dos', 'sesion-larga-1').json()['mensajes_restantes'] == 0
    r = _chat(cliente, 'tres', 'sesion-larga-1')
    assert r.status_code == 429
    assert 'máximo de 2 mensajes' in r.json()['detail']
    assert _chat(cliente, 'otra conversación', 'sesion-nueva-1').status_code == 200


def test_limite_por_minuto_devuelve_429_con_retry_after(agente):
    cliente = _cliente(max_pedidos_por_minuto=3)
    codigos = [_chat(cliente, f'mensaje {i}').status_code for i in range(4)]
    assert codigos == [200, 200, 200, 429]
    r = _chat(cliente, 'uno más')
    assert int(r.headers['retry-after']) > 0


def test_sin_proveedor_da_503_sin_filtrar_detalles(monkeypatch):
    monkeypatch.setattr(atencion.router, 'clasificar', _clasificar_falso)
    monkeypatch.setattr(atencion.agente, 'conversar', _AgenteFalso(error=SinProveedorError('groq: 429')))
    cliente = _cliente()
    r = _chat(cliente, '¿Hay autos?', 'sesion-caida-1')
    assert r.status_code == 503
    assert 'groq' not in r.json()['detail']
    assert cliente.get('/salud').json()['sesiones_activas'] == 0


def test_cors_acepta_el_origen_configurado():
    r = _cliente().options(
        '/chat',
        headers={
            'Origin': ORIGEN_DEMO,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type',
        },
    )
    assert r.status_code == 200
    assert r.headers['access-control-allow-origin'] == ORIGEN_DEMO


def test_cors_rechaza_otros_origenes():
    r = _cliente().options(
        '/chat',
        headers={'Origin': 'https://otra-web.com', 'Access-Control-Request-Method': 'POST'},
    )
    assert r.status_code == 400
    assert 'access-control-allow-origin' not in r.headers


def test_limitador_libera_despues_de_un_minuto():
    ahora = [0.0]
    limitador = LimitadorPorMinuto(2, reloj=lambda: ahora[0])
    limitador.registrar('190.1.2.3')
    limitador.registrar('190.1.2.3')
    with pytest.raises(LimiteAlcanzadoError):
        limitador.registrar('190.1.2.3')
    limitador.registrar('200.4.5.6')  # otro visitante no se ve afectado
    ahora[0] = 61.0
    limitador.registrar('190.1.2.3')


def test_el_almacen_recorta_el_historial_y_borra_la_sesion_mas_vieja():
    almacen = AlmacenDeSesiones(max_sesiones=2, max_mensajes=10, max_historial=3)
    largo = [{'role': rol, 'content': str(i)} for i, rol in enumerate(['user', 'assistant'] * 3)]
    almacen.guardar('a', largo)
    assert [m['role'] for m in almacen.historial('a')] == ['user', 'assistant']
    almacen.guardar('b', [])
    almacen.guardar('c', [])
    assert almacen.cantidad() == 2
    assert almacen.historial('a') == []
