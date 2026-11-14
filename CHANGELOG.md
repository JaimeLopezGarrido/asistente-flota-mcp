# Cambios

## 0.5.0 · 2026-11-11

- Router de intención (asistente/router.py): cuatro rutas, temperatura 0, JSON validado, contexto del último mensaje y ruta por defecto.
- Atención por caminos (asistente/atencion.py): políticas en una llamada, agente para cotizar, reclamos y fuera de alcance sin llamadas extra.
- scripts/atender.py y scripts/comparar_costos.py, con tests del router, de los caminos y de la estimación.
- ADR 0005 y docs/portfolio.md con la bitácora de L02 a L05.

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
