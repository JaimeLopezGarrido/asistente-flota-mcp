# 0008. Demo pública en Vercel, con interfaz servida por la misma API
Fecha: 2026-11-15 · Estado: aceptada

## Contexto
El asistente tenía que quedar online para el portfolio, gratis, sin depender de la Mac y sin que un visitante pueda vaciar la cuota de los proveedores.

## Decisión
- Vercel (plan gratuito) con el runtime de Python: `index.py` expone la app de FastAPI y `vercel.json` la enruta. `.vercelignore` excluye `.env`, tests y `pyproject.toml` (si está, Vercel lo usa en lugar de `requirements.txt`).
- La interfaz (`web/index.html`) la sirve la misma API en `/`: mismo origen, sin CORS, y se embebe en el portfolio con un iframe.
- Serverless: cada pedido puede caer en una instancia nueva, así que el navegador guarda el historial y lo manda; la API lo usa solo si no conoce la sesión, valida roles y envuelve los mensajes del usuario como datos.
- Límites: 8 pedidos por minuto por IP (leída de X-Forwarded-For) y 20 mensajes por conversación.
- Proveedores: Groq (gpt-oss-20b), Groq (gpt-oss-120b, otro cupo de tokens por minuto) y Gemini, en ese orden. Las claves son variables de entorno de Vercel, nunca en el repo.

## Alternativas consideradas
- Hugging Face Spaces o Render: requerían cuenta nueva; Vercel ya estaba configurado (lo usa la demo de Proper).
- Interfaz en otro hosting llamando a la API: suma CORS y otro deploy.
- Sesiones en Redis o en una base: lo correcto con más tráfico; para la demo alcanza el historial del navegador (persistencia real en L07).

## Consecuencias
- Si los tres proveedores gratuitos se saturan a la vez, la demo responde 503 con un mensaje claro. El paso siguiente es sumar Claude Haiku como respaldo pago con tope de gasto.
- Publicar una versión nueva: `npx vercel deploy --prod` desde la raíz del repo.
