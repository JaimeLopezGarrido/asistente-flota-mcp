# 0009. Reservas en dos pasos, con puerta de escritura en código e idempotencia
Fecha: 2026-11-20 · Estado: aceptada

## Contexto
El asistente pasa de solo leer (disponibilidad, cotización, políticas, manual) a escribir: dejar una reserva pendiente de aprobación. Una escritura duplicada o no pedida le cuesta al negocio. Además, el agente reintenta todo el loop con otro proveedor si el primero falla, así que una misma escritura puede llegar dos veces.

## Decisión
- Dos herramientas: preparar_reserva (valida con Pydantic estricto, re-verifica disponibilidad y devuelve un borrador con vigencia de 30 minutos) y crear_reserva (convierte el borrador en reserva pendiente de aprobación).
- El id del borrador es un hash de los datos: el sí del cliente queda atado a esos datos exactos y funciona como clave de idempotencia. Repetir crear_reserva devuelve la misma reserva con ya_existia true.
- Puerta de escritura en asistente/agente.py: una escritura por turno, nunca en el mismo pedido en que se creó el borrador y solo si el último mensaje real del cliente es una confirmación clara. Ante la duda, no se escribe.
- Las lecturas de un turno corren en paralelo con timeout de 15 s; un bug de una herramienta vuelve al modelo como error y no dispara el fallback de proveedor.
- Solo se pide nombre y apellido; los logs no guardan argumentos.

## Alternativas consideradas
- Confirmación solo en el prompt: más simple, pero depende de que el modelo la cumpla.
- Una sola herramienta reservar con un campo confirmado true: el modelo puede ponerlo solo.
- Botón de confirmación en la web con un evento estructurado: es lo mejor para un producto real; queda para una iteración de la interfaz.
- Clave de idempotencia generada por el cliente (UUID): estándar en pagos, pero el modelo no la genera de forma confiable.

## Consecuencias
- Las reservas viven en memoria: en la demo serverless de Vercel un borrador puede perderse entre pedidos si cae en otra instancia; el modelo vuelve a prepararlo. La persistencia real llega en L07 (SQLite).
- La regla de confirmación por texto es conservadora: un “sí, pero…” obliga a preguntar de nuevo.
- Groq con gpt-oss no pide herramientas en paralelo; el paralelo rinde con Gemini.
