# 0011. Modelo de embeddings y límites de la similitud
Fecha: 2026-11-22 · Estado: aceptada

## Contexto
El RAG del manual (E2) usa embeddings de Gemini para buscar por significado. En L08 armamos un laboratorio
(exploracion/embeddings.py) para entender qué miden esos vectores y comparamos con un modelo local. Vimos que
frases contrarias ("se puede fumar" / "no se puede fumar") quedan casi tan cerca como una paráfrasis correcta,
y que cada modelo tiene su propia escala de puntajes.

## Decisión
- El producto sigue con gemini-embedding-001 a 768 dimensiones: sigue disponible para texto, tiene free tier,
  el índice del manual ya está hecho con él y el umbral MINIMO_SENTIDO (0.62) está calibrado para su escala.
- Siempre se compara con coseno (o producto punto sobre vectores normalizados): a 768 dimensiones este modelo
  no entrega vectores normalizados.
- La similitud no decide sola: umbral de relevancia, búsqueda híbrida con BM25 y respuestas con cita.
  Precios, disponibilidad y fechas no se buscan por similitud: salen de herramientas y de la base (L03, L07).
- Plan B local: EmbeddingGemma con Ollama (gratis, privado), para clientes cuyos datos no pueden salir.

## Alternativas consideradas
- gemini-embedding-2 (estable desde abril de 2026, multimodal, normaliza solo): conviene si el manual suma
  imágenes o planos. Usa prefijos en vez de task_type y obliga a reindexar y recalibrar el umbral.
- EmbeddingGemma 2 y Qwen3-Embedding 0.6B (locales): buenas opciones; requieren medir calidad en español
  con nuestras preguntas antes de cambiar.
- Modelos pagos (OpenAI, Cohere, Voyage): no hacen falta para la demo y suman costo.

## Consecuencias
- Cambiar de modelo = reindexar todo y recalibrar el umbral. El índice guarda el nombre del modelo.
- Las preguntas trampa (negaciones, números, vigencia) van al conjunto de evaluación del RAG (L13).
- El laboratorio queda en exploracion/ y no es dependencia del producto.
