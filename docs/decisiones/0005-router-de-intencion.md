# 0005. Router de intención antes del agente
Fecha: 2026-11-11 · Estado: aceptada

## Contexto
Hasta la versión 0.4.0 todos los mensajes iban al agente con herramientas (L03). El agente manda en cada llamada su system prompt y el menú de herramientas, y suele dar 2 o 3 vueltas, aunque la pregunta sea una política fija o un reclamo que igual termina en una persona.

## Decisión
Antes del agente, un router (asistente/router.py) clasifica el mensaje en cuatro rutas con una llamada corta, temperatura 0 y salida JSON validada con Pydantic. Recibe el último mensaje del asistente como contexto.
- politica: una sola llamada con las políticas en el prompt (asistente/llm.py). Si esa llamada detecta disponibilidad, tarifa o reserva, o no hay proveedor, pasa al agente.
- cotizacion: el agente con herramientas.
- reclamo: respuesta fija y derivación a una persona, sin más llamadas.
- fuera_de_alcance: respuesta fija.
Si ningún proveedor clasifica, la ruta por defecto es cotizacion (el camino más capaz).

## Alternativas consideradas
- Mandar todo al agente: más simple, pero paga prefijo y vueltas en mensajes que no lo necesitan.
- Reglas por palabras clave: gratis y rápidas, pero fallan con mensajes mezclados o mal escritos. Quedan como opción para casos críticos.
- Un framework de agentes: suma dependencias sin necesidad para cuatro rutas.

## Consecuencias
- Según scripts/comparar_costos.py, menos tokens de entrada por mensaje en promedio; las cotizaciones cuestan un poco más porque suman la clasificación.
- Una llamada más de espera en las cotizaciones. Se puede bajar con un modelo chico para el router (ROUTER_*_MODEL).
- El router puede equivocarse: cada camino mantiene sus defensas y el de políticas tiene una compuerta hacia el agente. Medir su precisión queda para el bloque de evals.
