"""Arma el system prompt a partir de la plantilla y las políticas."""

from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "prompts" / "sistema.md"
POLITICAS = RAIZ / "datos" / "politicas.md"


def cargar_sistema(fecha: date | None = None) -> str:
    """Devuelve el system prompt con la fecha y las políticas inyectadas."""
    texto = PLANTILLA.read_text(encoding="utf-8")
    texto = texto.replace("{{FECHA}}", (fecha or date.today()).isoformat())
    texto = texto.replace("{{POLITICAS}}", POLITICAS.read_text(encoding="utf-8").strip())
    if "{{" in texto:
        raise ValueError("La plantilla del system prompt tiene marcadores sin reemplazar")
    return texto


def envolver_mensaje(mensaje: str) -> str:
    """Marca el mensaje del cliente como dato, no como instrucción."""
    return f"<mensaje_cliente>{mensaje.strip()}</mensaje_cliente>"
