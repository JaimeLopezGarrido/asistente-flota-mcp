from asistente.esquema import Respuesta
from asistente.evaluacion import evaluar, normalizar


def _respuesta(**cambios) -> Respuesta:
    base = {
        "intencion": "politica",
        "respuesta": "Sí, se aceptan mascotas con un cargo de limpieza.",
        "datos_faltantes": [],
        "derivar_a_humano": False,
        "politicas_usadas": ["P5"],
    }
    return Respuesta(**(base | cambios))


def test_respuesta_correcta_no_tiene_fallas():
    esperado = {"intencion": "politica", "debe_contener": ["limpieza"], "debe_citar": ["P5"]}
    assert evaluar(_respuesta(), esperado) == []


def test_detecta_intencion_y_derivacion():
    fallas = evaluar(_respuesta(), {"intencion": "reclamo", "derivar_a_humano": True})
    assert len(fallas) == 2


def test_detecta_frases_prohibidas_sin_importar_tildes():
    fallas = evaluar(_respuesta(respuesta="Sí, podés sin problema"), {"no_debe_contener": ["si, podes"]})
    assert fallas == ["no debería decir 'si, podes'"]


def test_detecta_datos_faltantes_y_citas():
    fallas = evaluar(_respuesta(politicas_usadas=[]), {"min_datos_faltantes": 1, "debe_citar": ["P5"]})
    assert len(fallas) == 2


def test_normalizar():
    assert normalizar("Podés CANCELAR") == "podes cancelar"
