"""Reservas en dos pasos: validación, idempotencia, vigencia y concurrencia (sin internet)."""

from datetime import date
from threading import Thread

import pytest

from asistente import herramientas as h
from asistente.reservas import VIGENCIA_BORRADOR_SEG, RegistroReservas

HOY = date(2026, 11, 20)
PEDIDO = {'auto_id': 'A02', 'desde': '2026-12-10', 'hasta': '2026-12-14', 'nombre': 'Ana Pérez'}


class Reloj:
    """Reloj falso: el test decide cuánto tiempo pasó."""

    def __init__(self):
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def registro(reloj) -> RegistroReservas:
    return RegistroReservas(reloj=reloj, hoy=lambda: HOY)


def test_preparar_devuelve_el_total_del_sistema_y_no_reserva(registro):
    borrador = registro.preparar(PEDIDO)
    assert borrador['borrador_id'].startswith('B-')
    assert borrador['nuevo'] is True
    assert borrador['total'] == h.cotizar('A02', '2026-12-10', '2026-12-14')['total']
    assert 'confirma' in borrador['siguiente_paso']
    assert registro.reservas() == []


def test_mismo_pedido_mismo_borrador(registro):
    primero = registro.preparar(PEDIDO)
    segundo = registro.preparar(dict(PEDIDO))
    assert primero['borrador_id'] == segundo['borrador_id']
    assert segundo['nuevo'] is False
    con_mascota = registro.preparar({**PEDIDO, 'mascota': True})
    assert con_mascota['borrador_id'] != primero['borrador_id']


def test_confirmar_dos_veces_crea_una_sola_reserva(registro):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    primera = registro.confirmar(borrador_id)
    segunda = registro.confirmar(borrador_id)
    assert primera['ya_existia'] is False
    assert segunda['ya_existia'] is True
    assert primera['reserva_id'] == segunda['reserva_id']
    assert primera['estado'] == 'pendiente_de_aprobacion'
    assert len(registro.reservas()) == 1


def test_diez_confirmaciones_simultaneas_crean_una_reserva(registro):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    hilos = [Thread(target=registro.confirmar, args=(borrador_id,)) for _ in range(10)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert len(registro.reservas()) == 1


def test_borrador_vencido(registro, reloj):
    borrador_id = registro.preparar(PEDIDO)['borrador_id']
    reloj.ahora += VIGENCIA_BORRADOR_SEG + 1
    with pytest.raises(h.ErrorHerramienta, match='venció'):
        registro.confirmar(borrador_id)


def test_borrador_inexistente(registro):
    with pytest.raises(h.ErrorHerramienta, match='preparar_reserva'):
        registro.confirmar('B-INVENTADO')


@pytest.mark.parametrize(
    ('cambio', 'campo'),
    [
        ({'auto_id': 'Z1'}, 'auto_id'),
        ({'nombre': 'A'}, 'nombre'),
        ({'nombre': 'Ana 1155550000'}, 'nombre'),
        ({'mascota': 'sí'}, 'mascota'),
        ({'desde': '10/12/2026'}, 'desde'),
        ({'telefono': '1155550000'}, 'telefono'),
    ],
)
def test_rechaza_datos_invalidos_diciendo_que_campo(registro, cambio, campo):
    with pytest.raises(h.ErrorHerramienta, match=campo):
        registro.preparar({**PEDIDO, **cambio})


def test_rechaza_una_fecha_que_ya_paso(registro):
    with pytest.raises(h.ErrorHerramienta, match='ya pasó'):
        registro.preparar({**PEDIDO, 'desde': '2026-11-01', 'hasta': '2026-11-05'})


def test_rechaza_un_auto_ocupado_en_la_flota(registro):
    ocupado = {**PEDIDO, 'auto_id': 'A03', 'desde': '2026-12-20', 'hasta': '2026-12-23'}
    with pytest.raises(h.ErrorHerramienta, match='no está libre'):
        registro.preparar(ocupado)


def test_dos_clientes_mismo_auto_gana_el_primero(registro):
    ana = registro.preparar(PEDIDO)['borrador_id']
    beto = registro.preparar({**PEDIDO, 'nombre': 'Beto Gómez'})['borrador_id']
    registro.confirmar(ana)
    with pytest.raises(h.ErrorHerramienta, match='otro cliente'):
        registro.confirmar(beto)
    with pytest.raises(h.ErrorHerramienta, match='no está libre'):
        registro.preparar({**PEDIDO, 'nombre': 'Caro Díaz'})


def test_las_herramientas_de_reserva_estan_registradas():
    assert {'preparar_reserva', 'crear_reserva'} <= set(h.FUNCIONES)
    assert h.HERRAMIENTAS_DE_ESCRITURA == {'crear_reserva'}


def test_crear_reserva_rechaza_un_id_inventado():
    with pytest.raises(h.ErrorHerramienta, match='preparar_reserva'):
        h.crear_reserva('R-123')
