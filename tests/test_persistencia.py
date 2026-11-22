"""Reservas en la base: sobreviven a un reinicio y las herramientas ven lo que se reservó."""

from datetime import date

from asistente import base as bd
from asistente import herramientas as h
from asistente.reservas import RegistroReservas

HOY = date(2026, 11, 20)
PEDIDO = {'auto_id': 'A02', 'desde': '2026-12-10', 'hasta': '2026-12-14', 'nombre': 'Ana Pérez'}


def _libres(desde: str, hasta: str) -> set[str]:
    return {a['id'] for a in h.buscar_disponibilidad(desde, hasta)['autos_libres']}


def test_las_herramientas_ven_lo_que_se_reservo():
    registro = RegistroReservas(hoy=lambda: HOY)
    assert 'A02' in _libres('2026-12-11', '2026-12-13')
    registro.confirmar(registro.preparar(PEDIDO)['borrador_id'])
    assert 'A02' not in _libres('2026-12-11', '2026-12-13')
    assert h.cotizar('A02', '2026-12-11', '2026-12-13')['disponible'] is False
    assert 'A02' in _libres('2026-12-14', '2026-12-16')  # se puede retirar el día que Ana devuelve


def test_la_reserva_sobrevive_a_un_reinicio(tmp_path):
    ruta = tmp_path / 'rentadora.db'
    antes = RegistroReservas(hoy=lambda: HOY, base=bd.BaseDeDatos(ruta))
    borrador_id = antes.preparar(PEDIDO)['borrador_id']
    reserva = antes.confirmar(borrador_id)
    despues = RegistroReservas(hoy=lambda: HOY, base=bd.BaseDeDatos(ruta))  # como si se reiniciara
    assert [r['reserva_id'] for r in despues.reservas()] == [reserva['reserva_id']]
    assert despues.confirmar(borrador_id)['ya_existia'] is True


def test_el_borrador_sobrevive_a_un_reinicio(tmp_path):
    ruta = tmp_path / 'rentadora.db'
    primera = RegistroReservas(hoy=lambda: HOY, base=bd.BaseDeDatos(ruta))
    borrador_id = primera.preparar(PEDIDO)['borrador_id']
    segunda = RegistroReservas(hoy=lambda: HOY, base=bd.BaseDeDatos(ruta))
    reserva = segunda.confirmar(borrador_id)
    assert reserva['estado'] == 'pendiente_de_aprobacion'
    assert reserva['nombre'] == 'Ana Pérez'
    assert reserva['total'] == h.cotizar('A02', '2026-12-10', '2026-12-14')['total']


def test_el_mismo_cliente_no_se_duplica_y_no_quedan_borradores():
    registro = RegistroReservas(hoy=lambda: HOY)
    registro.confirmar(registro.preparar(PEDIDO)['borrador_id'])
    registro.confirmar(registro.preparar({**PEDIDO, 'auto_id': 'A04'})['borrador_id'])
    with bd.obtener().conexion() as con:
        assert con.execute('SELECT COUNT(*) FROM clientes').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM borradores').fetchone()[0] == 0
