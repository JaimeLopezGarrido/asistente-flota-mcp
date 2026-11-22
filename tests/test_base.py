"""La base SQLite: migraciones, semilla, restricciones y transacciones (sin internet)."""

import sqlite3

import pytest

from asistente import base as bd


def _contar(base: bd.BaseDeDatos, tabla: str) -> int:
    with base.conexion() as con:
        return con.execute(f'SELECT COUNT(*) FROM {tabla}').fetchone()[0]


def test_crea_el_esquema_y_carga_la_semilla(tmp_path):
    base = bd.BaseDeDatos(tmp_path / 'nueva.db')
    assert base.version() == len(bd.MIGRACIONES)
    assert _contar(base, 'autos') == 8
    assert _contar(base, 'reservas') == 5  # los días ocupados que trae datos/flota.json


def test_abrirla_otra_vez_no_duplica_nada(tmp_path):
    ruta = tmp_path / 'misma.db'
    bd.BaseDeDatos(ruta)
    otra_vez = bd.BaseDeDatos(ruta)
    assert _contar(otra_vez, 'autos') == 8
    assert _contar(otra_vez, 'reservas') == 5


def test_migra_una_base_vieja_sin_perder_datos(tmp_path):
    ruta = tmp_path / 'vieja.db'
    base = bd.BaseDeDatos(ruta)
    with base.transaccion() as con:  # la dejamos como si solo tuviera la migración 1
        con.execute('DROP INDEX reservas_por_auto')
        con.execute('PRAGMA user_version = 1')
    reabierta = bd.BaseDeDatos(ruta)
    assert reabierta.version() == len(bd.MIGRACIONES)
    with reabierta.conexion() as con:
        consulta = 'SELECT name FROM sqlite_master WHERE type = ?'
        indices = {fila['name'] for fila in con.execute(consulta, ('index',))}
    assert 'reservas_por_auto' in indices
    assert _contar(reabierta, 'autos') == 8


def test_la_transaccion_es_todo_o_nada(base_temporal):
    with pytest.raises(RuntimeError), base_temporal.transaccion() as con:
        con.execute('INSERT INTO clientes (nombre) VALUES (?)', ('Lucía Prueba',))
        raise RuntimeError('se cortó a la mitad')
    assert _contar(base_temporal, 'clientes') == 0


@pytest.mark.parametrize(
    ('auto_id', 'desde', 'hasta', 'estado'),
    [
        ('A99', '2026-12-10', '2026-12-12', 'bloqueo'),  # clave foránea: ese auto no existe
        ('A01', '2026-12-12', '2026-12-10', 'bloqueo'),  # CHECK: devolución antes del retiro
        ('A01', '2026-12-10', '2026-12-12', 'reservadisima'),  # CHECK: estado que no existe
    ],
)
def test_la_base_rechaza_datos_que_rompen_las_reglas(base_temporal, auto_id, desde, hasta, estado):
    with pytest.raises(sqlite3.IntegrityError), base_temporal.transaccion() as con:
        con.execute(
            'INSERT INTO reservas (id, auto_id, desde, hasta, estado) VALUES (?, ?, ?, ?, ?)',
            ('X-1', auto_id, desde, hasta, estado),
        )


def test_auto_libre_respeta_el_dia_de_devolucion(base_temporal):
    with base_temporal.conexion() as con:  # A01 está ocupado del 20 al 27 de diciembre
        assert bd.auto_libre(con, 'A01', '2026-12-27', '2026-12-30') is True
        assert bd.auto_libre(con, 'A01', '2026-12-26', '2026-12-28') is False


def test_ruta_por_defecto(monkeypatch):
    monkeypatch.delenv('DB_RUTA', raising=False)
    monkeypatch.delenv('VERCEL', raising=False)
    assert bd.ruta_por_defecto().endswith('rentadora.db')
    monkeypatch.setenv('VERCEL', '1')
    assert bd.ruta_por_defecto() == '/tmp/rentadora.db'
    monkeypatch.setenv('DB_RUTA', '/tmp/otra.db')
    assert bd.ruta_por_defecto() == '/tmp/otra.db'
