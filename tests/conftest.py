"""Cada test usa su propia base SQLite en una carpeta temporal: nunca toca datos/rentadora.db."""

import pytest

from asistente import base as bd


@pytest.fixture(autouse=True)
def base_temporal(tmp_path, monkeypatch) -> bd.BaseDeDatos:
    """autouse: se aplica sola a todos los tests, sin pedirla como argumento."""
    nueva = bd.BaseDeDatos(tmp_path / 'prueba.db')
    monkeypatch.setattr(bd, '_actual', nueva)
    return nueva
