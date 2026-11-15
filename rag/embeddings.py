"""Embeddings con Gemini (gratis con GEMINI_API_KEY). Si no hay clave o falla, devuelve None."""

import logging
import os

log = logging.getLogger(__name__)

MODELO = os.environ.get('EMBEDDINGS_MODEL', 'gemini-embedding-001')
DIMENSIONES = 768


def vectorizar(textos: list[str], tarea: str) -> list[list[float]] | None:
    """tarea: 'RETRIEVAL_DOCUMENT' para el manual y 'RETRIEVAL_QUERY' para la pregunta."""
    clave = os.environ.get('GEMINI_API_KEY', '').strip()
    if not clave or not textos:
        return None
    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=clave, http_options=types.HttpOptions(timeout=15000))
        r = cliente.models.embed_content(
            model=MODELO,
            contents=textos,
            config=types.EmbedContentConfig(task_type=tarea, output_dimensionality=DIMENSIONES),
        )
        return [list(e.values) for e in r.embeddings]
    except Exception as e:  # noqa: BLE001 (red, cuota o clave: la búsqueda sigue solo con palabras)
        log.warning('embeddings no disponibles (%s); uso solo búsqueda por palabras', e)
        return None
