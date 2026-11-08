from datetime import date

from asistente.prompt import cargar_sistema, envolver_mensaje


def test_inyecta_fecha_y_politicas():
    sistema = cargar_sistema(date(2026, 11, 7))
    assert "2026-11-07" in sistema
    assert "P6." in sistema
    assert "{{" not in sistema


def test_tiene_las_secciones_xml():
    sistema = cargar_sistema()
    for etiqueta in ("<politicas>", "<reglas>", "<formato_salida>", "<ejemplos>"):
        assert etiqueta in sistema


def test_envuelve_el_mensaje_del_cliente():
    assert envolver_mensaje("  hola ") == "<mensaje_cliente>hola</mensaje_cliente>"
