"""Puerta de escritura, idempotencia, paralelo y timeouts del agente (sin internet: clientes falsos)."""

import json
import threading
import time
from datetime import date
from types import SimpleNamespace

import pytest

from asistente import agente, herramientas, reservas

PEDIDO = {'auto_id': 'A02', 'desde': '2026-12-10', 'hasta': '2026-12-14', 'nombre': 'Ana Pérez'}


class _Llamada:
    """Imita un tool_call del SDK de OpenAI."""

    def __init__(self, id_: str, nombre: str, argumentos: dict):
        self.id = id_
        self.function = SimpleNamespace(name=nombre, arguments=json.dumps(argumentos))

    def model_dump(self, **_opciones) -> dict:
        funcion = {'name': self.function.name, 'arguments': self.function.arguments}
        return {'id': self.id, 'type': 'function', 'function': funcion}


def _pide(*llamadas: tuple[str, dict]) -> SimpleNamespace:
    """Un turno del modelo que pide una o varias herramientas a la vez."""
    pedidos = [_Llamada(f'call_{i}', nombre, args) for i, (nombre, args) in enumerate(llamadas, start=1)]
    return SimpleNamespace(content=None, tool_calls=pedidos)


def _dice(texto: str) -> SimpleNamespace:
    return SimpleNamespace(content=texto, tool_calls=None)


def _crear(borrador_id: str) -> tuple[str, dict]:
    return ('crear_reserva', {'borrador_id': borrador_id})


def _politica(politica_id: str) -> tuple[str, dict]:
    return ('consultar_politica', {'politica_id': politica_id})


class _ClienteFalso:
    """Responde según el guion; sin guion, falla como un proveedor caído."""

    def __init__(self, guion: list):
        self.guion = list(guion)
        self.pedidos = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.pedidos.append(list(kwargs['messages']))
        return SimpleNamespace(choices=[SimpleNamespace(message=self.guion.pop(0))])


def _usar(monkeypatch, **guiones) -> dict:
    clientes = {nombre: _ClienteFalso(guion) for nombre, guion in guiones.items()}
    monkeypatch.setattr(agente, 'crear_cliente', lambda nombre: (clientes[nombre], f'modelo-{nombre}'))
    return clientes


@pytest.fixture
def registro(monkeypatch) -> reservas.RegistroReservas:
    """Un registro de reservas vacío para cada test, con hoy fijo."""
    nuevo = reservas.RegistroReservas(hoy=lambda: date(2026, 11, 20))
    monkeypatch.setattr(reservas, 'REGISTRO', nuevo)
    return nuevo


@pytest.mark.parametrize(
    ('mensaje', 'esperado'),
    [
        ('Sí, confirmo', True),
        ('si', True),
        ('Dale, reservalo', True),
        ('Confirmo la reserva', True),
        ('No, esperá', False),
        ('Sí, pero cambiemos la fecha', False),
        ('Cuánto sale con mascota?', False),
    ],
)
def test_cliente_confirmo(mensaje, esperado):
    assert agente.cliente_confirmo(mensaje) is esperado


def test_sin_confirmacion_no_escribe_aunque_el_modelo_lo_pida(monkeypatch, registro):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    _usar(monkeypatch, falso=[_pide(_crear(borrador_id)), _dice('Cuando quieras, confirmás.')])
    res = agente.conversar('No, esperá que lo consulto', proveedores=['falso'])
    assert 'no confirmó' in res.llamadas[0]['resultado']['error']
    assert registro.reservas() == []


def test_no_escribe_en_el_mismo_pedido_en_que_se_creo_el_borrador(monkeypatch, registro):
    otro_registro = reservas.RegistroReservas(hoy=lambda: date(2026, 11, 20))
    borrador_id = otro_registro.preparar(PEDIDO)['borrador_id']  # el id solo depende de los datos
    guion = [_pide(('preparar_reserva', PEDIDO)), _pide(_crear(borrador_id)), _dice('Confirmás?')]
    _usar(monkeypatch, falso=guion)
    mensaje = 'Sí, reservame el A02 del 10 al 14 de diciembre, soy Ana Pérez'
    res = agente.conversar(mensaje, proveedores=['falso'])
    assert res.llamadas[0]['resultado']['borrador_id'] == borrador_id
    assert 'todavía no vio' in res.llamadas[1]['resultado']['error']
    assert registro.reservas() == []


def test_con_confirmacion_crea_la_reserva_pendiente(monkeypatch, registro):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    guion = [_pide(_crear(borrador_id)), _dice('Listo, quedó pendiente de aprobación.')]
    _usar(monkeypatch, falso=guion)
    res = agente.conversar('Sí, confirmo', proveedores=['falso'])
    assert res.llamadas[0]['resultado']['estado'] == 'pendiente_de_aprobacion'
    assert len(registro.reservas()) == 1


def test_una_sola_escritura_por_turno(monkeypatch, registro):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    guion = [_pide(_crear(borrador_id), _crear(borrador_id)), _dice('Listo.')]
    _usar(monkeypatch, falso=guion)
    res = agente.conversar('Sí, confirmo', proveedores=['falso'])
    assert res.llamadas[0]['resultado']['ya_existia'] is False
    assert 'una sola escritura' in res.llamadas[1]['resultado']['error']
    assert len(registro.reservas()) == 1


def test_si_el_proveedor_cae_despues_de_escribir_el_reintento_no_duplica(monkeypatch, registro):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    # 'cae' escribe y se queda sin guion (falla); conversar pasa a 'bueno', que repite la escritura
    cae = [_pide(_crear(borrador_id))]
    bueno = [_pide(_crear(borrador_id)), _dice('Listo, quedó pendiente.')]
    _usar(monkeypatch, cae=cae, bueno=bueno)
    res = agente.conversar('Sí, confirmo', proveedores=['cae', 'bueno'])
    assert res.proveedor == 'bueno'
    assert res.llamadas[0]['resultado']['ya_existia'] is True
    assert len(registro.reservas()) == 1


def test_las_lecturas_de_un_turno_corren_en_paralelo(monkeypatch):
    barrera = threading.Barrier(2, timeout=2)

    def politica_que_espera(politica_id: str) -> dict:
        barrera.wait()  # si corrieran de a una, la primera esperaría sola y fallaría
        return {'id': politica_id, 'texto': 'ok'}

    monkeypatch.setitem(herramientas.FUNCIONES, 'consultar_politica', politica_que_espera)
    guion = [_pide(_politica('P5'), _politica('P6')), _dice('Sí a las dos (P5, P6).')]
    clientes = _usar(monkeypatch, falso=guion)
    res = agente.conversar('Puedo ir a Chile con mi perro?', proveedores=['falso'])
    assert [ll['resultado']['id'] for ll in res.llamadas] == ['P5', 'P6']
    segundo = clientes['falso'].pedidos[1]
    assert [m['tool_call_id'] for m in segundo[-2:]] == ['call_1', 'call_2']


def test_una_herramienta_colgada_vuelve_como_error(monkeypatch):
    def politica_colgada(politica_id: str) -> dict:
        time.sleep(1)
        return {'id': politica_id}

    monkeypatch.setattr(agente, 'TIMEOUT_HERRAMIENTA', 0.05)
    monkeypatch.setitem(herramientas.FUNCIONES, 'consultar_politica', politica_colgada)
    _usar(monkeypatch, falso=[_pide(_politica('P1')), _dice('Ahora no lo puedo ver.')])
    res = agente.conversar('Qué necesito para alquilar?', proveedores=['falso'])
    assert res.llamadas[0]['resultado']['reintentable'] is True


def test_un_bug_en_una_herramienta_no_tumba_la_conversacion(monkeypatch):
    def politica_rota(politica_id: str) -> dict:
        raise KeyError(politica_id)

    monkeypatch.setitem(herramientas.FUNCIONES, 'consultar_politica', politica_rota)
    _usar(monkeypatch, falso=[_pide(_politica('P1')), _dice('Lo ve una persona del equipo.')])
    res = agente.conversar('Qué necesito para alquilar?', proveedores=['falso'])
    assert res.proveedor == 'falso'
    assert 'falla interna' in res.llamadas[0]['resultado']['error']
