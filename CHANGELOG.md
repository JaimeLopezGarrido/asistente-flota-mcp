# Cambios

## 0.10.0 · 2026-11-22

- Laboratorio de embeddings (L08, exploracion/embeddings.py): 20 fichas de políticas y manual, similitud coseno a mano con numpy, casos trampa y modelo local opcional (EmbeddingGemma en Ollama).
- 16 tests sin red y ADR 0011 (modelo de embeddings y límites de la similitud).

## 0.9.0 · 2026-11-21

- Persistencia en SQLite (L07, asistente/base.py): autos, clientes, reservas, borradores y conversaciones, con migraciones numeradas (PRAGMA user_version), claves foráneas, CHECK y transacciones BEGIN IMMEDIATE.
- Las herramientas leen la disponibilidad de la base: una reserva hecha en el chat ya no aparece como libre.
- Las conversaciones de la API sobreviven a un reinicio. Ruta configurable con DB_RUTA.
- scripts/ver_base.py, una base temporal por test (tests/conftest.py) y ADR 0009.

## 0.8.0 · 2026-11-20

- Reservas en dos pasos (asistente/reservas.py): preparar_reserva valida con Pydantic estricto, re-verifica disponibilidad y devuelve un borrador con vigencia; crear_reserva lo convierte en reserva pendiente de aprobación de forma idempotente.
- Puerta de escritura en el agente: confirmación explícita del cliente, una escritura por turno y nunca en el mismo pedido del borrador.
- Lecturas de un turno en paralelo con timeout; los bugs de herramientas vuelven como error al modelo.
- Los logs ya no guardan los argumentos de las herramientas.
- 32 tests nuevos y ADR 0009.

## 0.7.0 · 2026-11-15

- RAG sobre un manual del cliente en PDF (ficticio, 11 páginas): ingesta con pypdf, fragmentos por página, embeddings de Gemini y búsqueda híbrida con BM25 (rag/).
- Herramienta buscar_manual para el agente; la ruta de políticas también consulta el manual.
- Citas obligatorias [pág. N] con el campo paginas_manual en la salida estructurada; la API devuelve las fuentes.
- Segundo modelo de Groq como respaldo (otro cupo de tokens por minuto).
- Interfaz web del chat (web/index.html) servida en / por la API, con ruta, herramientas y fuentes de cada respuesta.
- Demo pública en Vercel: https://asistente-rentadora-demo.vercel.app (historial del navegador para serverless, IP real para el límite por minuto).
- ADR 0007 (RAG) y 0008 (demo en Vercel).

## 0.6.0 · 2026-11-14

- API web con FastAPI (api/): POST /chat con historial por sesión, límites por sesión y por minuto, errores 422, 429 y 503 y CORS configurable; GET /salud y documentación en /docs.
- asistente/atencion.py informa el proveedor y las herramientas usadas.
- tests/test_api.py con el TestClient de FastAPI y proveedores falsos.
- ADR 0006 y entrada E1 en docs/portfolio.md.

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
