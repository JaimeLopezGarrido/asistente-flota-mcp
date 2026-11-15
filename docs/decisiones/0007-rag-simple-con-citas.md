# 0007. RAG simple con búsqueda híbrida y citas de página
Fecha: 2026-11-15 · Estado: aceptada

## Contexto
Las políticas P1 a P10 no alcanzan para responder lo que pregunta un cliente real (qué hacer si pincho, multas, franquicia, devolución). Esa información vive en un manual del cliente (PDF ficticio de 11 páginas) y cambia más seguido que el código.

## Decisión
- Ingesta (`rag/ingesta.py`): PDF -> texto por página (pypdf) -> fragmentos de ~420 caracteres sin mezclar páginas, con una oración de solapamiento y el título de la sección adelante -> embeddings de Gemini (`gemini-embedding-001`, 768 dimensiones) -> `datos/manual/indice.json`, versionado.
- Búsqueda híbrida (`rag/buscar.py`): 60 % similitud de embeddings + 40 % BM25 (palabras). Umbral calibrado con preguntas dentro y fuera del manual (relevantes >= 0,72; ajenas <= 0,57; corte en 0,62): sin evidencia devuelve [] y el asistente dice que no lo encuentra.
- Si Gemini no responde, la búsqueda sigue solo por palabras: el RAG nunca tumba la atención.
- Dos usos: la ruta de políticas recibe los fragmentos en el prompt, y el agente tiene la herramienta `buscar_manual`.
- Citas obligatorias: la salida estructurada tiene `paginas_manual`; el código arma las fuentes desde ahí y agrega `[pág. N]` si el modelo no lo escribió. La API devuelve las fuentes y la interfaz las muestra.

## Alternativas consideradas
- Base vectorial (Chroma, pgvector): innecesaria para 21 fragmentos; un JSON se carga en milisegundos y no suma infraestructura. Se revisa en L10.
- Solo embeddings: falla si Gemini está caído (pasó el 10/11). Solo palabras: no entiende "pincho una goma" ↔ "pinchadura".
- Fine-tuning: el manual cambia; ver ADR 0004.
- Confiar en que el modelo cite: en la prueba real, 2 de 4 respuestas no citaban. Por eso la cita se exige en el esquema.

## Consecuencias
- Cambiar el manual es editar `manual_rentadora.md`, regenerar el PDF y correr `python -m rag.ingesta`.
- La calidad depende del umbral: se evalúa con un set de preguntas en L13.
