# 0006. API web con FastAPI, sesiones en memoria y límites propios
Fecha: 2026-11-14 · Estado: aceptada

## Contexto
El asistente solo se podía usar desde la terminal (scripts/atender.py). Para la interfaz web y la demo pública (E4) hace falta exponerlo por HTTP, recordar cada conversación y proteger la cuota gratuita de los proveedores frente a abusos.

## Decisión
- FastAPI con Uvicorn, en la carpeta api/, separada del núcleo (asistente/). La API solo llama a atencion.atender().
- POST /chat recibe mensaje y sesion_id (opcional; si falta, la API crea un UUID) y devuelve respuesta, ruta, herramientas usadas, proveedor y mensajes restantes. GET /salud para monitoreo.
- Historial por sesión en memoria (OrderedDict con candado), recortado a MAX_HISTORIAL mensajes y con tope de MAX_SESIONES.
- Dos límites: mensajes por sesión y pedidos por minuto por IP (ventana deslizante), con 429 y Retry-After.
- Errores: 422 automático por validación, 503 si ningún proveedor responde; el detalle técnico va solo al log.
- CORS con lista exacta de orígenes desde ORIGENES_CORS, nunca *.

## Alternativas consideradas
- Flask: conocido, pero sin validación ni documentación automática; habría que sumar piezas.
- Exponer el bot solo con n8n (webhook): rápido, pero deja la lógica y los tests fuera del repo.
- Base de datos o Redis para sesiones: necesario con varios procesos; para una demo de un solo proceso es una dependencia de más. Queda para L07.
- slowapi para los límites: probada, pero suma una dependencia para dos contadores simples.

## Consecuencias
- Las conversaciones se pierden al reiniciar y la API no puede correr con más de un worker hasta tener persistencia (L07).
- Detrás del proxy del hosting (E4) hay que leer la IP real del visitante para que el límite por IP funcione.
- La interfaz web (E4) tiene un contrato estable y documentado en /docs.
