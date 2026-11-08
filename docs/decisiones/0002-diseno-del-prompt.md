# 0002. Diseño del system prompt y salida estructurada
Fecha: 2026-11-07 · Estado: aceptada

## Contexto
El asistente no puede inventar políticas ni disponibilidad, y el código necesita saber la intención del cliente y si hay que derivar a una persona.

## Decisión
- System prompt en `prompts/sistema.md`, separado del código, con secciones XML: rol, `<politicas>` arriba, `<reglas>` con el porqué, `<formato_salida>` y tres `<ejemplos>` que no repiten los casos de prueba.
- Políticas cortas con IDs (P1 a P10) en `datos/politicas.md`; el modelo cita las que usa en `politicas_usadas`.
- Salida con JSON schema generado desde Pydantic (`asistente/esquema.py`) y validada siempre; si no valida, se pasa al siguiente proveedor.
- El mensaje del cliente va envuelto en `<mensaje_cliente>` y se trata como dato.
- 10 casos difíciles en `tests/casos/casos.json`, corridos con `python -m scripts.correr_casos`.

## Alternativas consideradas
- Prompt dentro del código Python: más difícil de revisar y versionar.
- Pedir JSON solo con instrucciones: falla en una parte de los casos.
- Meter el manual completo: más caro y peor (context rot).

## Consecuencias
- Cada cambio de prompt es un PR revisable con el resultado de los casos antes y después.
- La disponibilidad y los precios reales quedan para L03 (herramientas).
