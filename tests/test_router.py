import json
from types import SimpleNamespace

import pytest

from asistente import router


class _ClienteFalso:
    """Imita al cliente de OpenAI: devuelve siempre el mismo contenido y guarda cada pedido."""

    def __init__(self, contenido: str):
        self.contenido = contenido
        self.pedidos: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.pedidos.append(kwargs)
        mensaje = SimpleNamespace(content=self.contenido)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


def _json(ruta: str, motivo: str = 'prueba') -> str:
    return json.dumps({'ruta': ruta, 'motivo': motivo})


def _usar(monkeypatch, **respuestas) -> dict:
    clientes = {nombre: _ClienteFalso(texto) for nombre, texto in respuestas.items()}

    def crear(nombre):
        if nombre not in clientes:
            raise RuntimeError('proveedor caído')
        return clientes[nombre], f'modelo-{nombre}'

    monkeypatch.setattr(router, 'crear_cliente', crear)
    return clientes


@pytest.mark.parametrize('ruta', router.RUTAS)
def test_devuelve_la_ruta_que_eligio_el_modelo(monkeypatch, ruta):
    _usar(monkeypatch, falso=_json(ruta))
    decision = router.clasificar('hola', proveedores=['falso'])
    assert decision.ruta == ruta
    assert decision.proveedor == 'falso'


def test_ruta_inventada_pasa_al_siguiente_proveedor(monkeypatch):
    _usar(monkeypatch, malo=_json('ventas'), bueno=_json('reclamo', 'cobro duplicado'))
    decision = router.clasificar('Me cobraron dos veces', proveedores=['malo', 'bueno'])
    assert (decision.ruta, decision.proveedor) == ('reclamo', 'bueno')
    assert decision.motivo == 'cobro duplicado'


def test_texto_que_no_es_json_cuenta_como_falla(monkeypatch):
    _usar(monkeypatch, charlatan='Creo que es una política', bueno=_json('politica'))
    assert router.clasificar('¿Aceptan perros?', proveedores=['charlatan', 'bueno']).ruta == 'politica'


def test_sin_proveedores_usa_la_ruta_por_defecto(monkeypatch):
    _usar(monkeypatch)
    decision = router.clasificar('hola', proveedores=['caido'])
    assert decision.ruta == router.RUTA_POR_DEFECTO == 'cotizacion'
    assert decision.proveedor == 'ninguno'


def test_pide_json_con_temperatura_cero_y_contexto(monkeypatch):
    clientes = _usar(monkeypatch, falso=_json('cotizacion'))
    router.clasificar('Del 10 al 14', ultimo_asistente='¿Para qué fechas?', proveedores=['falso'])
    pedido = clientes['falso'].pedidos[0]
    assert pedido['temperature'] == 0
    assert pedido['response_format'] == {'type': 'json_object'}
    assert pedido['messages'][0]['role'] == 'system'
    usuario = pedido['messages'][-1]['content']
    assert '<ultimo_mensaje_asistente>¿Para qué fechas?</ultimo_mensaje_asistente>' in usuario
    assert usuario.endswith('<mensaje_cliente>Del 10 al 14</mensaje_cliente>')


def test_usa_el_modelo_propio_del_router(monkeypatch):
    clientes = _usar(monkeypatch, groq=_json('politica'))
    monkeypatch.setenv('ROUTER_GROQ_MODEL', 'modelo-chico')
    router.clasificar('¿Hay que dejar garantía?', proveedores=['groq'])
    assert clientes['groq'].pedidos[0]['model'] == 'modelo-chico'


def test_las_instrucciones_nombran_todas_las_rutas():
    texto = router.cargar_instrucciones()
    for ruta in router.RUTAS:
        assert ruta in texto
