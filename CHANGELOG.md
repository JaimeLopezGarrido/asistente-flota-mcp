# Cambios

## 0.4.0 · 2026-11-10

- exploracion/: tokenización (tiktoken), temperatura, top-p y muestreo (numpy) y logprobs con Ollama, con tests.
- ADR 0004: conocimiento con herramientas y RAG, sin fine-tuning.
- README: sección de exploración y roadmap actualizado.

## 0.3.0 · 2026-11-08

- Flota ficticia en datos/flota.json y herramientas buscar_disponibilidad, cotizar y consultar_politica, con tests.
- Agente con loop de tool use (formato compatible con OpenAI), límite de vueltas y fallback Gemini, Groq y Ollama.
- Chat por terminal (scripts/chat.py) y demo de streaming (scripts/streaming.py).
- ADR 0003 (tool use).

## 0.2.0 · 2026-11-07

- System prompt con etiquetas XML, reglas con el porqué, few-shot y políticas ficticias numeradas.
- Salida estructurada con JSON schema (Pydantic) y fallback Gemini → Groq → Ollama.
- 10 casos difíciles y `scripts/correr_casos.py` para medir calidad y variabilidad.
- ADR 0001 (modelo) y 0002 (prompt).

## 0.1.0 · 2026-11-07

- Esqueleto del proyecto.
