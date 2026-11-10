# 0003. Tool use con formato compatible con OpenAI
Fecha: 2026-11-08 · Estado: aceptada

## Contexto
El asistente tiene que responder disponibilidad y precios reales sin inventar. Los datos cambian todos los días y no conviene meterlos en el prompt.

## Decisión
- Tres herramientas de solo lectura en `asistente/herramientas.py`: `buscar_disponibilidad`, `cotizar` y `consultar_politica`, sobre `datos/flota.json` (ficticia).
- Los precios los calcula el código (`cotizar`), nunca el modelo.
- Los errores de datos vuelven al modelo como un objeto con `error`, para que corrija o pregunte; `ejecutar()` nunca lanza.
- Loop en `asistente/agente.py` con el formato de chat compatible con OpenAI (Gemini, Groq y Ollama con el mismo código), límite de 6 vueltas y fallback de proveedores.
- El historial entre turnos guarda solo texto: la disponibilidad se vuelve a consultar en cada turno.

## Alternativas consideradas
- SDK propio de cada proveedor: tres loops distintos para mantener.
- Claude (Messages API) con prompt caching: mejor seguimiento de instrucciones, pero pago. `a_formato_anthropic()` deja lista la migración.
- Meter la flota en el prompt: se desactualiza y crece con la flota.

## Consecuencias
- El agente responde texto, sin JSON schema: Groq no combina salidas estructuradas con tool use. El clasificador de L02 sigue en `asistente/llm.py`.
- Las herramientas de escritura (reservar) quedan para más adelante, con confirmación del cliente.
- Pendiente: casos de prueba del agente que verifiquen que llama a la herramienta correcta.
