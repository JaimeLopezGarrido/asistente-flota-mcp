"""Evalúa una respuesta del asistente contra lo esperado en un caso de prueba."""

import json
import unicodedata
from pathlib import Path

from asistente.esquema import Respuesta

CASOS = Path(__file__).resolve().parent.parent / "tests" / "casos" / "casos.json"


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar sin falsos negativos."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def cargar_casos(ruta: Path = CASOS) -> list[dict]:
    return json.loads(ruta.read_text(encoding="utf-8"))


def evaluar(r: Respuesta, esperado: dict) -> list[str]:
    """Devuelve la lista de fallas; vacía si la respuesta cumple todo."""
    fallas = []
    if "intencion" in esperado and r.intencion != esperado["intencion"]:
        fallas.append(f"intención '{r.intencion}', se esperaba '{esperado['intencion']}'")
    if "derivar_a_humano" in esperado and r.derivar_a_humano != esperado["derivar_a_humano"]:
        fallas.append(f"derivar_a_humano={r.derivar_a_humano}, se esperaba {esperado['derivar_a_humano']}")
    texto = normalizar(r.respuesta)
    for frase in esperado.get("debe_contener", []):
        if normalizar(frase) not in texto:
            fallas.append(f"falta '{frase}' en la respuesta")
    for frase in esperado.get("no_debe_contener", []):
        if normalizar(frase) in texto:
            fallas.append(f"no debería decir '{frase}'")
    minimo = esperado.get("min_datos_faltantes", 0)
    if len(r.datos_faltantes) < minimo:
        fallas.append(f"pidió {len(r.datos_faltantes)} datos, se esperaban al menos {minimo}")
    for pid in esperado.get("debe_citar", []):
        if pid not in r.politicas_usadas:
            fallas.append(f"no citó la política {pid}")
    return fallas
