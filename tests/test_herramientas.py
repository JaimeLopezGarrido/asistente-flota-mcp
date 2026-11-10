import inspect
import json

import pytest

from asistente import herramientas as h


def _ids(resultado: dict) -> set[str]:
    return {a['id'] for a in resultado['autos_libres']}


def test_disponibilidad_excluye_autos_reservados():
    r = h.buscar_disponibilidad('2026-12-21', '2026-12-24')
    assert r['dias'] == 3
    assert _ids(r) == {'A02', 'A04', 'A06', 'A07', 'A08'}


def test_se_puede_retirar_el_dia_que_otro_devuelve():
    r = h.buscar_disponibilidad('2026-12-27', '2027-01-02', categoria='economico')
    assert _ids(r) == {'A01', 'A02', 'A08'}


def test_filtra_por_categoria_y_cruce_a_chile():
    r = h.buscar_disponibilidad('2027-01-03', '2027-01-06', categoria='camioneta', cruce_chile=True)
    assert _ids(r) == {'A05'}


def test_suv_sin_permiso_no_aparece_si_pide_chile():
    r = h.buscar_disponibilidad('2027-03-01', '2027-03-05', categoria='suv', cruce_chile=True)
    assert _ids(r) == {'A03'}


@pytest.mark.parametrize(
    ('desde', 'hasta'),
    [
        ('2026-12-24', '2026-12-21'),
        ('24/12/2026', '2026-12-28'),
        ('2026-12-01', '2027-01-15'),
        ('2026-12-10', '2026-12-10'),
    ],
)
def test_rechaza_fechas_invalidas(desde, hasta):
    with pytest.raises(h.ErrorHerramienta):
        h.buscar_disponibilidad(desde, hasta)


def test_rechaza_categoria_y_booleano_invalidos():
    with pytest.raises(h.ErrorHerramienta):
        h.buscar_disponibilidad('2026-12-10', '2026-12-12', categoria='deportivo')
    with pytest.raises(h.ErrorHerramienta):
        h.buscar_disponibilidad('2026-12-10', '2026-12-12', cruce_chile='false')


def test_cotiza_con_temporada_alta_y_mascota():
    r = h.cotizar('A01', '2026-12-10', '2026-12-17', mascota=True)
    assert r['dias'] == 7
    assert r['dias_temporada_alta'] == 2  # 15 y 16 de diciembre
    assert r['alquiler'] == 45000 * 7 + 45000 * 30 * 2 // 100  # 342.000
    assert r['extras'] == {'mascota': 40000}
    assert r['total'] == 382000
    assert r['km_incluidos'] == 2100
    assert r['disponible'] is True
    assert r['politicas'] == ['P2', 'P3', 'P5']


def test_cotiza_y_avisa_si_no_esta_disponible():
    r = h.cotizar('A03', '2026-12-20', '2026-12-23')
    assert r['disponible'] is False
    assert r['total'] == 304200


def test_cotizar_errores():
    with pytest.raises(h.ErrorHerramienta):
        h.cotizar('Z99', '2026-12-10', '2026-12-12')
    with pytest.raises(h.ErrorHerramienta):
        h.cotizar('A04', '2026-12-10', '2026-12-12', cruce_chile=True)
    with pytest.raises(h.ErrorHerramienta):
        h.cotizar('A01', '2026-12-10', '2026-12-12', mascota='sí')


def test_consultar_politica():
    assert '72' in h.consultar_politica('P6')['texto']
    with pytest.raises(h.ErrorHerramienta):
        h.consultar_politica('P99')


def test_ejecutar_nunca_lanza_y_devuelve_json():
    assert 'error' in json.loads(h.ejecutar('volar', {}))
    assert 'argumentos inválidos' in json.loads(h.ejecutar('cotizar', {'auto': 'A01'}))['error']
    pedido = {'auto_id': 'Z9', 'desde': '2026-12-10', 'hasta': '2026-12-12'}
    assert 'no existe el auto' in json.loads(h.ejecutar('cotizar', pedido))['error']
    assert '21' in json.loads(h.ejecutar('consultar_politica', {'politica_id': 'P1'}))['texto']


def test_cada_herramienta_coincide_con_su_funcion():
    assert {x['function']['name'] for x in h.HERRAMIENTAS} == set(h.FUNCIONES)
    for herramienta in h.HERRAMIENTAS:
        definicion = herramienta['function']
        parametros = inspect.signature(h.FUNCIONES[definicion['name']]).parameters
        assert set(definicion['parameters']['properties']) == set(parametros), definicion['name']
        obligatorios = {n for n, p in parametros.items() if p.default is inspect.Parameter.empty}
        assert set(definicion['parameters']['required']) == obligatorios, definicion['name']


def test_formato_anthropic():
    for tool in h.a_formato_anthropic():
        assert set(tool) == {'name', 'description', 'input_schema'}
        assert tool['input_schema']['type'] == 'object'


def test_flota_ficticia_bien_formada():
    autos = h.cargar_flota()['autos']
    assert len({a['id'] for a in autos}) == len(autos)
    for auto in autos:
        assert auto['categoria'] in h.CATEGORIAS
        for reserva in auto['reservas']:
            assert reserva['desde'] < reserva['hasta']
