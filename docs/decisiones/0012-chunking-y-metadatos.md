# 0012. Chunking y metadatos de la ingesta
Fecha: 2026-11-24 · Estado: aceptada

## Contexto
El RAG del manual (E2) corta por oraciones (unas 420 letras, una oración de solapamiento) y nunca mezcla
páginas. Funciona porque el PDF de E2 se generó con una sección por página. En L09 armamos un folleto A6
con texto corrido, encabezado, pie y una tabla, como los PDFs reales, y comparamos cuatro estrategias
(exploracion/chunking.py): fijo, fijo con solapamiento, oraciones por página y por secciones.

## Decisión
- El producto sigue con oraciones por página mientras el manual sea el PDF de E2: una sección por página
  hace que la cita sea exacta y que no se mezclen secciones.
- Si el manual pasa a un PDF de texto corrido (como cualquier PDF de un cliente real), cambiamos a
  "por secciones, subdividiendo las largas por oraciones" y guardamos la lista de páginas de cada
  fragmento: preferimos citar un rango de páginas antes que partir una regla.
- Antes de cortar se sacan los encabezados y pies (líneas repetidas en la mitad de las páginas o más).
- Metadatos mínimos por fragmento: fuente, páginas, sección, id y posición. Vigencia y versión se suman
  cuando haya más de un documento (filtro en la base vectorial, L10).
- Extracción con pypdf: alcanza para PDFs nativos de una columna.

## Alternativas consideradas
- Tamaño fijo, con o sin solapamiento: corta oraciones y mezcla secciones; el solapamiento infla el índice.
- Chunking semántico o con LLM: más caro, sin una mejora medida en un manual con títulos claros.
- Docling o pymupdf4llm (este último con licencia AGPL): para PDFs con columnas, tablas o escaneos.

## Consecuencias
- Cambiar la estrategia obliga a reindexar y a revisar el umbral de búsqueda.
- Los datos que tienen que quedar enteros (HECHOS en exploracion/chunking.py) pasan al conjunto de
  evaluación del RAG (L13).
- Los precios de la tabla de cargos no se buscan por similitud: los datos exactos salen de herramientas.
