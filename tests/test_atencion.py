from types import SimpleNamespace

import pytest

from asistente import atencion
from asistente.esquema import Respuesta
from asistente.llm import SinProveedorError
from asistente.router import Decision


class _Espia:
    """Reemplaza una función: guarda cada llamada y devuelve (o lanza) lo que le digas."""

    def __init__(self, devolver=None, error: Exception | None = None):
        self.devolver = devolver
        self.error = error
        self.llamadas: list[tuple] = []

    def __call__(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.devolver


def _politica(intencion: str, texto: str = 'Sí, con jaula o funda (P5).') -> SimpleNamespace:
    respuesta = Respuesta(
        intencion=intencion,
        respuesta=texto,
        datos_faltantes=[],
        derivar_a_humano=False,
        politicas_usadas=['P5'],
    )
    return SimpleNamespace(respuesta=respuesta)


def _preparar(monkeypatch, ruta, proveedor='falso', politicas=None, agente=None) -> dict:
    agente_falso = SimpleNamespace(texto='Hay 2 SUV libres.', vueltas=3, historial=[{'role': 'x'}])
    espias = {
        'router': _Espia(Decision(ruta, 'prueba', proveedor)),
        'politicas': politicas or _Espia(_politica('politica')),
        'agente': agente or _Espia(agente_falso),
    }
    monkeypatch.setattr(atencion.router, 'clasificar', espias['router'])
    monkeypatch.setattr(atencion.llm, 'responder', espias['politicas'])
    monkeypatch.setattr(atencion.agente, 'conversar', espias['agente'])
    return espias


def test_reclamo_responde_fijo_y_deriva_sin_mas_llamadas(monkeypatch):
    espias = _preparar(monkeypatch, 'reclamo')
    res = atencion.atender('Me cobraron dos veces la garantía')
    assert res.texto == atencion.RESPUESTA_RECLAMO
    assert res.derivar_a_humano is True
    assert res.llamadas_llm == 1
    assert espias['politicas'].llamadas == []
    assert espias['agente'].llamadas == []


def test_fuera_de_alcance_responde_fijo(monkeypatch):
    _preparar(monkeypatch, 'fuera_de_alcance')
    res = atencion.atender('¿Me recomendás un restaurante?')
    assert res.texto == atencion.RESPUESTA_FUERA
    assert res.derivar_a_humano is False


def test_politica_usa_una_sola_llamada_sin_agente(monkeypatch):
    espias = _preparar(monkeypatch, 'politica')
    res = atencion.atender('¿Puedo llevar a mi perro?')
    assert res.texto == 'Sí, con jaula o funda (P5).'
    assert res.llamadas_llm == 2
    assert len(espias['politicas'].llamadas) == 1
    assert espias['agente'].llamadas == []


def test_si_el_camino_de_politicas_detecta_fechas_pasa_al_agente(monkeypatch):
    espias = _preparar(monkeypatch, 'politica', politicas=_Espia(_politica('disponibilidad')))
    res = atencion.atender('¿Aceptan perros? Lo necesito del 10 al 14')
    assert res.texto == 'Hay 2 SUV libres.'
    assert res.llamadas_llm == 1 + 1 + 3
    assert len(espias['agente'].llamadas) == 1


def test_politica_sin_proveedor_pasa_al_agente(monkeypatch):
    _preparar(monkeypatch, 'politica', politicas=_Espia(error=SinProveedorError('nadie')))
    res = atencion.atender('¿Cuánto es la garantía?')
    assert res.texto == 'Hay 2 SUV libres.'
    assert res.llamadas_llm == 1 + 3


def test_cotizacion_va_al_agente_con_el_historial_y_el_contexto(monkeypatch):
    espias = _preparar(monkeypatch, 'cotizacion')
    previo = [{'role': 'user', 'content': 'hola'}, {'role': 'assistant', 'content': '¿Para qué fechas?'}]
    res = atencion.atender('Del 10 al 14 de diciembre', historial=previo)
    assert res.historial == [{'role': 'x'}]
    _, kwargs = espias['agente'].llamadas[0]
    assert kwargs['historial'] == previo
    argumentos_router, _ = espias['router'].llamadas[0]
    assert argumentos_router[1] == '¿Para qué fechas?'


def test_los_caminos_sin_agente_guardan_el_historial(monkeypatch):
    _preparar(monkeypatch, 'fuera_de_alcance')
    res = atencion.atender('¿Qué tal el clima?')
    assert [m['role'] for m in res.historial] == ['user', 'assistant']
    assert res.historial[0]['content'] == '<mensaje_cliente>¿Qué tal el clima?</mensaje_cliente>'


def test_router_sin_proveedor_no_cuenta_su_llamada(monkeypatch):
    _preparar(monkeypatch, 'cotizacion', proveedor='ninguno')
    assert atencion.atender('hola').llamadas_llm == 3


def test_si_el_agente_falla_el_error_sube(monkeypatch):
    _preparar(monkeypatch, 'cotizacion', agente=_Espia(error=SinProveedorError('nadie')))
    with pytest.raises(SinProveedorError):
        atencion.atender('¿Hay camionetas?')
