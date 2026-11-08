from typing import get_args

from asistente.esquema import Intencion
from asistente.evaluacion import cargar_casos

CLAVES = {
    "intencion",
    "derivar_a_humano",
    "debe_contener",
    "no_debe_contener",
    "min_datos_faltantes",
    "debe_citar",
}


def test_hay_diez_casos_con_id_unico():
    casos = cargar_casos()
    assert len(casos) == 10
    assert len({c["id"] for c in casos}) == 10


def test_los_casos_estan_bien_formados():
    for caso in cargar_casos():
        assert caso["mensaje"].strip()
        assert set(caso["esperado"]) <= CLAVES, caso["id"]
        if "intencion" in caso["esperado"]:
            assert caso["esperado"]["intencion"] in get_args(Intencion)
