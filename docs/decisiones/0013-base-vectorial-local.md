# 0013. Base vectorial local con Qdrant
Fecha: 2026-11-25 · Estado: aceptada

## Contexto
El manual está en datos/manual/indice.json (21 fragmentos con vectores de Gemini de 768 dimensiones) y rag/buscar.py los recorre todos en cada pregunta. Funciona con 21 fragmentos, pero no tiene filtros por metadatos, hay que reescribir el archivo entero para cambiar un fragmento y no escala a los documentos de un cliente real (miles a millones de fragmentos).

## Decisión
Sumar una base vectorial: Qdrant en modo local (qdrant-client, sin servidor), en rag/vectorial.py. Una colección manual con distancia coseno; un punto por fragmento con payload (id del fragmento, página, sección, texto, fuente y modelo). Búsqueda con top-k, umbral y filtros por sección y página. La carpeta datos/vectorial/ no se versiona: se regenera desde indice.json, que sigue siendo la fuente de verdad. El comando se niega a buscar si el modelo del índice no es el de la consulta.

La demo pública no cambia: Vercel tiene disco efímero y la búsqueda actual es híbrida. qdrant-client queda en requirements-dev.txt. Cómo se conecta al agente se decide en L11.

## Alternativas consideradas
- Seguir solo con JSON y fuerza bruta: alcanza hoy, pero no enseña ni resuelve filtros ni actualizaciones.
- sqlite-vec: encaja con la base SQLite de L07, pero todavía no llegó a la versión 1 y depende de poder cargar extensiones en el Python de cada máquina.
- Chroma: API simple, pero su nube se está cerrando (octubre de 2026); no queremos una migración forzada si después vamos a la nube.
- pgvector: la mejor opción si hubiera Postgres; el proyecto usa SQLite.
- Pinecone: solo gestionada, con cuenta y límites, sin modo local para tests.

## Consecuencias
- El mismo código funciona contra un servidor Qdrant en Docker o Qdrant Cloud (plan gratis) cambiando cómo se crea el cliente.
- En modo local la búsqueda es exacta: sirve para desarrollo, tests y demos chicas; no para mucho tráfico ni para varios procesos abriendo la misma carpeta.
- Tests sin red con Qdrant en memoria.
- Cambiar de modelo de embeddings obliga a reindexar (python -m rag.ingesta y python -m rag.vectorial --indexar).
