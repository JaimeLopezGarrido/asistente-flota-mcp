"""Llamada al LLM con salida estructurada y fallback entre proveedores."""

import logging
import os
import time
from dataclasses import dataclass

from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import ValidationError

from asistente.esquema import Respuesta
from asistente.prompt import cargar_sistema, envolver_mensaje

log = logging.getLogger(__name__)
ESQUEMA = Respuesta.model_json_schema()


class SinProveedorError(RuntimeError):
    """Ningún proveedor devolvió una respuesta válida."""


@dataclass
class Resultado:
    respuesta: Respuesta
    proveedor: str
    modelo: str
    segundos: float


def _clave(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return valor


def _gemini(sistema: str, mensaje: str) -> tuple[str, str]:
    modelo = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    cliente = genai.Client(api_key=_clave("GEMINI_API_KEY"))
    r = cliente.models.generate_content(
        model=modelo,
        contents=mensaje,
        config=types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",
            response_json_schema=ESQUEMA,
        ),
    )
    return modelo, r.text or ""


def _openai_compatible(base_url: str, clave: str, modelo: str, sistema: str, mensaje: str) -> str:
    cliente = OpenAI(base_url=base_url, api_key=clave, timeout=60, max_retries=1)
    r = cliente.chat.completions.create(
        model=modelo,
        temperature=0.2,
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": mensaje}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "respuesta", "strict": True, "schema": ESQUEMA},
        },
    )
    return r.choices[0].message.content or ""


def _groq(sistema: str, mensaje: str) -> tuple[str, str]:
    modelo = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    clave = _clave("GROQ_API_KEY")
    return modelo, _openai_compatible("https://api.groq.com/openai/v1", clave, modelo, sistema, mensaje)


def _ollama(sistema: str, mensaje: str) -> tuple[str, str]:
    modelo = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1")
    return modelo, _openai_compatible(base, "ollama", modelo, sistema, mensaje)


PROVEEDORES = {"gemini": _gemini, "groq": _groq, "ollama": _ollama}


def responder(mensaje: str, proveedores: list[str] | None = None) -> Resultado:
    """Responde un mensaje probando los proveedores en orden hasta obtener JSON válido."""
    orden = proveedores or os.environ.get("PROVEEDORES", "gemini,groq,ollama").split(",")
    sistema = cargar_sistema()
    entrada = envolver_mensaje(mensaje)
    errores = []
    for nombre in (n.strip() for n in orden):
        llamar = PROVEEDORES.get(nombre)
        if llamar is None:
            log.warning("Proveedor desconocido: %s", nombre)
            continue
        inicio = time.perf_counter()
        try:
            modelo, texto = llamar(sistema, entrada)
            respuesta = Respuesta.model_validate_json(texto)
        except ValidationError as e:
            log.warning("%s devolvió una salida que no cumple el esquema: %s", nombre, e.errors()[:2])
            errores.append(f"{nombre}: esquema inválido")
            continue
        except Exception as e:  # noqa: BLE001 (a propósito: red, cuota o clave faltante -> siguiente)
            log.warning("%s falló: %s", nombre, e)
            errores.append(f"{nombre}: {type(e).__name__}")
            continue
        return Resultado(respuesta, nombre, modelo, time.perf_counter() - inicio)
    raise SinProveedorError("Ningún proveedor respondió: " + "; ".join(errores))
