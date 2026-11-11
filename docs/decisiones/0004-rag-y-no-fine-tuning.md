# 0004. Conocimiento con herramientas y RAG, sin fine-tuning
Fecha: 2026-11-10 · Estado: aceptada

## Contexto
El asistente tiene que responder sobre datos que cambian (disponibilidad, tarifas por temporada, flota)
y sobre documentos que deben poder citarse (políticas y manual de uso). El presupuesto es gratis primero
y hasta US$ 10 en la API de Claude. No hay un volumen grande de conversaciones etiquetadas, y las
conversaciones reales tendrían datos personales. Los modelos tienen fecha de corte: no conocen las tarifas
ni el estado actual de la flota.

## Decisión
- Las reglas de comportamiento y el tono van en el system prompt (ADR 0002).
- Los datos que cambian se consultan con herramientas (ADR 0003): disponibilidad y cotización.
- Las políticas y el manual se van a consultar con RAG con citas (lecciones L08 a L12).
- No se hace fine-tuning de ningún modelo.

## Alternativas consideradas
- **Fine-tuning (completo o LoRA) con conversaciones de ejemplo:** descartado. Los datos quedarían
  "congelados" en los pesos (cada cambio de tarifa exige reentrenar), no se puede citar la fuente,
  aumenta el riesgo de afirmar datos viejos con seguridad y obliga a anonimizar datos de clientes.
- **Pegar todo el manual en cada pedido (contexto largo):** sirve como línea base mientras el manual es
  chico, pero el costo crece con cada consulta, la atención crece con el cuadrado del largo y empeora
  la calidad con contextos muy largos (context rot).

## Consecuencias
- Actualizar un dato es editar `datos/`, sin reentrenar; cada respuesta puede citar su fuente.
- Hay que construir y mantener la ingesta, el índice y la búsqueda (L08 a L12) y medir su calidad.
- Se revisa esta decisión solo si aparece una tarea angosta y de gran volumen (por ejemplo, clasificar
  millones de mensajes) donde un modelo chico ajustado gane en costo y calidad medido con evals.
