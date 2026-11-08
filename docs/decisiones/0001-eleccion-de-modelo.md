# 0001. Elección de modelo y fallback
Fecha: 2026-11-07 · Estado: aceptada

## Contexto
El asistente responde consultas de una rentadora (políticas, tarifas, disponibilidad). Volumen de demo bajo y presupuesto cero hasta tener un cliente que pague.

## Decisión
1. Principal: Gemini Flash por API (free tier de Google AI Studio), con JSON schema.
2. Fallback 1: Groq con openai/gpt-oss-20b (free tier, rápido y con `strict: true` en salidas estructuradas).
3. Fallback 2: Ollama local con Gemma 4 e4b (entra en una Mac de 16 GB; no depende de red ni de cuota).

El orden se configura con `PROVEEDORES` en `.env`.

## Alternativas consideradas
- Claude Haiku 5.5: mejor seguimiento de instrucciones y costo bajo, pero pago. Candidato cuando haya cliente.
- Modelos locales de 27B o más: no entran en 16 GB.

## Consecuencias
- Los free tiers tienen límites por minuto: en corridas largas se activa el fallback, y es esperable.
- Los free tiers no son aptos para datos reales de clientes.
- Pendiente: benchmark formal de calidad y latencia entre los tres proveedores con `scripts/correr_casos.py`.
