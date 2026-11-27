# Bitácora del proyecto

Qué construí en cada sesión, qué decidí y cómo lo explicaría. Todos los datos del proyecto son ficticios.

## L02 · Prompt profesional y salida estructurada

**Qué construí:** el system prompt del asistente con etiquetas XML, reglas que explican el porqué, ejemplos y las políticas numeradas; y una salida JSON validada con Pydantic (intención, respuesta, datos faltantes, derivar a humano y políticas usadas).

**Decisión y trade-off:** elegí salida estructurada con JSON schema en vez de texto libre: el código puede decidir (por ejemplo, derivar a una persona) sin adivinar. A cambio, el prompt es más largo y algunos proveedores no combinan esquema con herramientas.

**Evidencia:** `python -m scripts.correr_casos --repeticiones 3` corre 10 casos difíciles (inyección, reclamos, fechas ambiguas) y muestra cuántos cumplen.

**Cómo lo explicaría:** Antes de escribir código, diseñé las instrucciones del asistente como un documento con secciones y reglas justificadas. Le pedí al modelo que siempre conteste en un formato fijo, así el sistema sabe cuándo derivar a una persona. Armé 10 casos difíciles para medir si cumple, en vez de confiar en que funciona. Eso me permite cambiar el prompt sin miedo a romper algo.

## L03 · Function calling y fallback de proveedores

**Qué construí:** un agente con tool use sobre la flota ficticia: herramientas de disponibilidad, cotización y políticas, con el loop de herramientas, límite de vueltas y fallback entre Gemini, Groq y Ollama.

**Decisión y trade-off:** los precios los calcula siempre el código, nunca el modelo: más llamadas, pero cero montos inventados. Usé el formato compatible con OpenAI para cambiar de proveedor sin reescribir el agente.

**Evidencia:** `python -m pytest tests/test_agente.py tests/test_herramientas.py -q` en verde, y `python -m scripts.chat` respondiendo una cotización con las herramientas usadas.

**Cómo lo explicaría:** El modelo entiende lo que pide el cliente, pero los datos salen del sistema: cuando hace falta un precio, el modelo pide la herramienta y mi código la ejecuta. Así el asistente no inventa disponibilidad ni tarifas. Si un proveedor falla o se queda sin cuota, pasa al siguiente sin que el cliente lo note. Y tiene un límite de vueltas para que nunca quede en un loop.

## L04 · Tokens, temperatura y RAG vs fine-tuning

**Qué construí:** scripts en exploracion/ que muestran cómo se tokeniza un mensaje y cómo la temperatura y top-p cambian las probabilidades del próximo token (numpy y logprobs con Ollama). Y el ADR 0004.

**Decisión y trade-off:** el conocimiento del negocio va por herramientas y RAG, no por fine-tuning: se actualiza editando datos, sin reentrenar, y permite citar la fuente. Fine-tuning queda para cambiar estilo o formato si algún día hace falta.

**Evidencia:** `python -m exploracion.probabilidades` muestra la misma distribución con temperatura 0,2, 1 y 2.

**Cómo lo explicaría:** Quise entender qué pasa adentro del modelo para tomar mejores decisiones técnicas. Por eso uso temperatura baja donde necesito respuestas estables. También documenté por qué no entreno un modelo propio: las políticas y la flota cambian seguido y es más barato y seguro que el modelo las consulte. Cada decisión importante queda escrita en un ADR.

## L05 · Router de intención antes del agente

**Qué construí:** un router que clasifica cada mensaje (política, cotización, reclamo o fuera de alcance) y lo manda al camino más simple que lo resuelve: una llamada para políticas, el agente para cotizar y respuestas fijas para reclamos y consultas ajenas.

**Decisión y trade-off:** elegí workflow por fuera y agente por dentro, en vez de mandar todo al agente. Gano menos tokens en promedio y reclamos que llegan a una persona sin vueltas; a cambio, las cotizaciones suman una llamada. Descarté reglas por palabras clave (fallan con mensajes mezclados) y un framework de agentes (demasiado para cuatro rutas).

**Evidencia:** `python -m scripts.comparar_costos`: 2660 tokens de entrada por mensaje solo con el agente contra 2240 con router (16 % menos), con 2,10 contra 2,45 llamadas por mensaje. 24 tests nuevos en verde.

**Cómo lo explicaría:** No todos los mensajes necesitan un agente con herramientas. Puse un clasificador en la puerta que decide el camino: las preguntas de políticas se responden con una sola llamada y los reclamos van directo a una persona. El agente queda para lo que de verdad es abierto, como cotizar con fechas. Medí el efecto en tokens antes de afirmarlo, y si el clasificador falla, el sistema usa el camino más capaz en lugar de cortarse.

## E1 · El chatbot como API web con FastAPI

**Qué construí:** una API web con FastAPI delante del asistente. `POST /chat` recibe el mensaje y un id de sesión y devuelve la respuesta con la ruta que eligió el router, las herramientas usadas y el proveedor que respondió; `GET /salud` sirve para monitoreo. Guarda el historial por sesión, limita el uso por sesión y por minuto y responde errores claros (422, 429 y 503).

**Decisión y trade-off:** elegí FastAPI con sesiones en memoria y límites propios en vez de una base de datos y una librería de rate limiting: menos piezas para una demo de un solo proceso. A cambio, las conversaciones se pierden al reiniciar y no escala a varios procesos (queda para L07). CORS con la lista exacta de orígenes por variable de entorno, nunca `*`, para que otra web no pueda gastar la cuota de la demo.

**Evidencia:** `python -m pytest -q` en verde, con 16 tests nuevos de la API (TestClient y proveedores falsos, sin internet), y la documentación automática funcionando:

![Documentación automática de la API en /docs](img/e1-docs.png)

**Cómo lo explicaría:** El asistente ya no vive solo en mi terminal: cualquier web, app o flujo de n8n le puede hablar por HTTP con un contrato documentado en /docs. Cada respuesta dice qué camino tomó, qué herramientas usó y qué modelo contestó, así puedo comprobar que no inventa. Antes de abrirlo al público le puse límites de uso, porque una demo sin límites se queda sin cuota en minutos. Y los errores son claros para el usuario sin mostrar detalles internos.

### Cómo lo cuento en la entrevista

**ES:** Convertí un asistente que solo andaba en mi terminal en un servicio web con un contrato claro y documentado automáticamente. Cada respuesta muestra la ruta del router, las herramientas usadas y el proveedor, y eso me permite validar que la IA no inventa datos y depurar rápido. Lo protegí con límites de uso y errores claros antes de publicarlo, con tests que no dependen de ningún proveedor. Lo entregué en un PR chico con CI en verde y dejé anotado lo que sigue (persistencia) para la próxima iteración.

**EN:** I turned an assistant that only ran in my terminal into a web service with a clear, auto-documented contract. Every response shows the router's route, the tools used and the provider that answered, which lets me verify the AI isn't making data up and debug quickly. I added usage limits and clear error handling before making it public, covered by tests that don't depend on any LLM provider. I shipped it as a small PR with green CI and documented the next step (persistence) for the following iteration.


## E2 a E4 · RAG con citas, interfaz web y demo pública

**Qué construí:** el asistente ahora responde con un manual del cliente en PDF: lo corta en fragmentos con su página, los indexa con embeddings y búsqueda por palabras, y cada respuesta cita la página de donde sale. Sumé una interfaz web que muestra la ruta, las herramientas y las fuentes, y lo publiqué en Vercel: https://asistente-rentadora-demo.vercel.app

**Decisión y trade-off:** búsqueda híbrida (embeddings + BM25) en un índice JSON en lugar de una base vectorial: para 21 fragmentos es instantáneo y no suma infraestructura, y si Gemini se cae la búsqueda sigue por palabras. Las citas las exijo en la salida estructurada (campo paginas_manual) porque en la prueba real el modelo solo citaba la mitad de las veces.

**Evidencia:** 114 tests en verde; prueba real: "¿Qué hago si pincho una goma?" responde citando [pág. 7], "capital de Francia" queda fuera de alcance, y la consulta de una camioneta a Chile usa buscar_disponibilidad y cotizar.

![El chat en vivo citando el manual](img/e4-chat.png)

**Cómo lo explicaría:** Un chatbot que inventa es peor que no tener chatbot. Por eso cada dato sale de una herramienta o de un documento, y cada respuesta muestra de dónde salió: el usuario y yo podemos verificarlo. Cuando el modelo no citaba, no le pedí "por favor citá": lo hice obligatorio en el formato de salida y lo controla el código.

### Cómo lo cuento en la entrevista

**ES:** Lo dejé online en un día: RAG con citas, interfaz que muestra cómo decidió cada respuesta, y deploy gratuito con límites de uso. Cuando vi en la prueba real que el modelo no citaba siempre, lo resolví en el esquema y no en el prompt, y cuando Groq se quedó sin cupo, sumé un segundo modelo de respaldo.

**EN:** I shipped it in a day: RAG with citations, a UI that shows how each answer was produced, and a free deployment with usage limits. When real tests showed the model didn't always cite its sources, I enforced it in the output schema instead of the prompt, and when Groq hit its rate limit I added a second fallback model.

## L06 · Herramientas de escritura: reservas con confirmación e idempotencia

**Qué construí:** el asistente ya puede dejar una reserva pendiente de aprobación, en dos pasos: `preparar_reserva` valida los datos, re-verifica que el auto siga libre y devuelve un borrador con el total; `crear_reserva` lo convierte en reserva solo si el cliente confirmó. Además, el agente corre en paralelo las lecturas de un mismo turno, con timeout, y un bug en una herramienta vuelve como dato en vez de cortar la conversación.

**Decisión y trade-off:** la confirmación se controla en código, con una puerta de escritura: una escritura por turno, nunca en el mismo pedido en que se creó el borrador y solo con un sí claro del cliente. El id del borrador es un hash de los datos, así el sí queda atado a esos datos exactos y repetir la llamada (por un reintento o un fallback de proveedor) no duplica la reserva. A cambio, la regla es conservadora: ante un “sí, pero…” vuelve a preguntar. Descarté confiar solo en el prompt y un campo `confirmado` que el modelo podría completar solo.

**Evidencia:** `python -m pytest -q` en verde con 32 tests nuevos (`tests/test_reservas.py` y `tests/test_agente_escritura.py`): diez confirmaciones simultáneas crean una sola reserva, un borrador vencido se rechaza y, si el proveedor se cae después de escribir, el reintento con otro proveedor devuelve la misma reserva.

**Cómo lo explicaría:** Leer datos es barato si sale mal; escribir no. Por eso el asistente nunca reserva en el primer mensaje: arma un borrador, se lo muestra al cliente y espera un sí explícito. Esa regla no depende de que el modelo se porte bien: la controla el código. Y como en sistemas reales todo se reintenta (un timeout, un proveedor caído, un doble clic), cada reserva tiene una clave única que evita duplicados. Lo probé con tests que simulan justamente esos fallos.

## L07 · Persistencia: reservas y conversaciones en SQLite

**Qué construí:** pasé la flota, las reservas, los borradores y las conversaciones a una base SQLite con una capa de acceso a datos (`asistente/base.py`), migraciones numeradas y reglas en el esquema. Ahora una reserva hecha en el chat sobrevive a un reinicio y las herramientas dejan de ofrecer un auto que alguien acaba de reservar.

**Decisión y trade-off:** elegí SQLite (cero infraestructura, viene con Python) con transacciones `BEGIN IMMEDIATE` en lugar del candado en memoria, que solo servía con un proceso. Descarté seguir con JSON (dos escrituras a la vez pierden datos) y, por ahora, Postgres gestionado (otra cuenta y secretos que la demo no necesita). El costo: en Vercel la base vive en `/tmp` de cada instancia y no es permanente; para un cliente real el siguiente paso es Turso o Postgres, y solo cambia la capa de datos.

**Evidencia:** `python -m pytest -q` con todos los tests en verde. Los de L06 pasaron salvo uno, que asumía que cada registro tenía su propia memoria: lo ajusté para que use una base temporal propia y `python -m scripts.ver_base`:

    Base: .../datos/rentadora.db (esquema versión 2)
      autos             8 filas
      reservas          6 filas
    Reservas de la demo (sin los días bloqueados de la semilla):
      R-3F9A1C2E  A02  2026-12-10  2026-12-14  pendiente_de_aprobacion

**Cómo lo explicaría:** El asistente ya no se olvida de nada cuando se reinicia. Lo importante no fue cambiar dónde se guarda, sino garantizar que dos clientes no puedan reservar el mismo auto a la vez: verificar y reservar pasan dentro de una misma transacción, y la base rechaza datos imposibles aunque un bug se saltee la validación. Lo probé con tests que simulan un reinicio y con diez confirmaciones simultáneas. Y soy claro con el límite: la demo serverless no es una base permanente, y sé cuál es el próximo paso.

### Cómo lo cuento en la entrevista

**ES:** Pasé el estado del chatbot de memoria a SQLite sin cambiar su comportamiento: los tests de la iteración anterior fueron mi red de seguridad, y uno me avisó de un supuesto oculto (que cada registro tenía su propia memoria) que corregí. Para que la IA no pueda generar dobles reservas, la verificación y la escritura ocurren en una sola transacción y la base tiene reglas propias, así no dependo de que el modelo mande buenos argumentos. Lo entregué en commits chicos con CI en verde y dejé documentado en un ADR el límite de la demo serverless y cómo se resuelve.

**EN:** I moved the chatbot's state from memory to SQLite without changing its behavior: the previous iteration's tests were my safety net, and one of them flagged a hidden assumption (each registry having its own memory) that I fixed. That was my validation. To make sure the AI can't create double bookings, the availability check and the write happen in a single transaction, and the database enforces its own constraints, so I don't rely on the model sending good arguments. I shipped it in small commits with green CI and documented in an ADR the limits of the serverless demo and how to solve them.

## L08 · Embeddings y búsqueda semántica a mano

**Qué construí:** un laboratorio (`exploracion/embeddings.py`) que convierte en vectores las políticas y el manual de la rentadora y busca la ficha más parecida a una pregunta con similitud coseno escrita a mano en numpy, sin base vectorial. Funciona con Gemini en la nube o con EmbeddingGemma local en Ollama, y mide casos donde la similitud engaña.

**Decisión y trade-off:** mantuve `gemini-embedding-001` en el producto (free tier, índice ya hecho y umbral calibrado) y dejé EmbeddingGemma como plan B local para clientes que no pueden mandar datos afuera. Descarté por ahora `gemini-embedding-2`: es mejor para imágenes, pero obliga a reindexar y recalibrar sin una mejora medida. Quedó en el ADR 0011.

**Evidencia:** salida de `python -m exploracion.embeddings --trampas`:

    Modelo: gemini-embedding-001. Similitud coseno entre dos frases:
    
      0.970  [negación]
             Se puede fumar dentro del auto.
             No se puede fumar dentro del auto.
      0.980  [otro número]
             El alquiler incluye 300 km por día.
             El alquiler incluye 500 km por día.
      0.982  [antes o después]
             Cancelación sin cargo hasta 48 horas antes del retiro.
             Cancelación sin cargo hasta 48 horas después del retiro.
      0.930  [un dato cambia la regla]
             La garantía se deja con tarjeta de crédito.
             La garantía se deja con tarjeta de débito.
      0.885  [paráfrasis correcta]
             ¿Puedo llevar a mi perro?
             Se aceptan mascotas con jaula o funda protectora.
      0.765  [misma palabra, otro tema]
             ¿Puedo llevar a mi perro?
             El perro de la oficina se llama Toto.

**Cómo lo explicaría:** Un embedding es la ubicación de un texto en un mapa de significados: sirve para encontrar "mascotas" cuando alguien pregunta por su perro. Pero mide de qué habla un texto, no si es cierto: en mis pruebas, "se puede fumar" y "no se puede fumar" quedaron casi pegadas. Por eso en el asistente la búsqueda solo trae candidatos: hay un umbral para decir "no sé", se combina con búsqueda por palabras, el modelo cita la fuente y los datos exactos (precios, disponibilidad) salen del sistema, no de la similitud.

### Cómo lo cuento en la entrevista

**ES:** Antes de confiar en el RAG que ya tenía online, abrí la caja: reimplementé la búsqueda con numpy y medí casos trampa. Descubrí que frases contrarias quedan casi tan cerca como una paráfrasis correcta, así que validé que el sistema no dependa solo de la similitud: umbral, búsqueda híbrida, citas y datos exactos por herramientas. Lo entregué como un módulo aparte con 16 tests sin red y dejé la decisión del modelo en un ADR.

**EN:** Before trusting the RAG I already had online, I opened the box: I reimplemented the search with numpy and measured tricky cases. Opposite sentences ended up almost as close as a correct paraphrase, so I made sure the system doesn't rely on similarity alone: a relevance threshold, hybrid search, citations, and exact data coming from tools. I shipped it as a separate module with 16 offline tests and documented the model choice in an ADR.

## L09 · Ingesta de documentos: PDF, chunking y metadatos

**Qué construí:** un generador de un PDF de práctica armado como los reales (texto corrido, encabezado, pie de página y una tabla) y un laboratorio (`exploracion/chunking.py`) que lo extrae con pypdf conservando la página, saca el ruido de maquetación y lo corta de cuatro formas, con metadatos de fuente, páginas y sección en cada fragmento.

**Decisión y trade-off:** medí cuántos fragmentos cortan oraciones, mezclan secciones o cruzan páginas, y qué datos clave quedan partidos. El producto sigue cortando por oraciones sin cruzar páginas porque el manual actual tiene una sección por página; para PDFs reales de clientes la elección es cortar por secciones y citar un rango de páginas. Descarté el tamaño fijo (parte reglas) y el chunking semántico (más caro, sin mejora medida). Quedó en el ADR 0012.

**Evidencia:** salida de `python -m exploracion.chunking`:

    PDF: folleto_rentadora.pdf | 8 páginas | título: Manual del cliente · Rentadora de autos de Bariloche
    Texto útil: 6115 caracteres | secciones encontradas: 11
    
    estrategia             frag.  prom.  cruzan pág.  mezclan secc.  cortan oración
    fijo                      15    407            7             11              14
    fijo_solapado             18    415            8             12              18
    oraciones_por_pagina      27    297            0             14               6
    secciones                 14    436            6              0               1
    
    ¿Cada dato quedó entero en algún fragmento?
      permiso notarial + 72 horas
          fijo=OK  fijo_solapado=OK  oraciones_por_pagina=OK  secciones=OK
      Pinchadura + auxilio
          fijo=OK  fijo_solapado=OK  oraciones_por_pagina=OK  secciones=OK
      ¿Puedo llevar mascotas? + jaula
          fijo=OK  fijo_solapado=OK  oraciones_por_pagina=OK  secciones=OK
      Lavado especial + 25.000
          fijo=OK  fijo_solapado=OK  oraciones_por_pagina=OK  secciones=OK

**Cómo lo explicaría:** La calidad de un RAG se decide antes de la búsqueda, cuando se preparan los documentos. Un PDF no tiene párrafos: tiene letras en posiciones, con encabezados y números de página en el medio. Por eso extraigo página por página para poder citar, saco lo que se repite en todas las hojas y corto respetando las secciones, para que una regla no quede separada de su excepción. No elegí la estrategia por intuición: la medí con un control automático de los datos que tienen que quedar enteros.

### Cómo lo cuento en la entrevista

**ES:** Mi RAG ya funcionaba con un PDF que yo mismo había generado, así que lo puse a prueba con uno armado como los reales. Comparé cuatro formas de cortar el documento y medí cuántos fragmentos partían oraciones, mezclaban secciones o perdían un dato clave. Con esos números documenté cuándo conviene cada estrategia en un ADR, y dejé tests que fallan si un dato importante queda partido.

**EN:** My RAG already worked with a PDF I had generated myself, so I stress-tested it with one laid out like real-world documents. I compared four chunking strategies and measured how many chunks split sentences, mixed sections or lost a key fact. With those numbers I documented in an ADR when each strategy makes sense, and I added tests that fail if an important fact gets split.

## L10 · Base vectorial: indexar y recuperar

**Qué construí:** los fragmentos del manual cargados en una base vectorial (Qdrant en modo local, sin servidor) con su página y sección como metadatos, y un comando que muestra los fragmentos más parecidos a cualquier pregunta, con puntaje, filtros por sección o página y umbral. Más un chequeo de que la base devuelve lo mismo que la búsqueda exacta hecha a mano.

**Decisión y trade-off:** elegí Qdrant local porque tiene filtros completos y el mismo código sirve después contra un servidor o su nube gratis. Descarté sqlite-vec (todavía no llegó a la versión 1), Chroma (su nube se está cerrando) y pgvector (el proyecto no usa Postgres). No la puse todavía en la demo pública: en Vercel el disco es efímero y con 21 fragmentos la búsqueda actual alcanza. Los vectores se regeneran desde indice.json, así que cambiar de base no me ata a un proveedor.

**Evidencia:** `python -m rag.vectorial 'Se me pinchó una goma en la ruta 40' --k 5 --comparar` muestra el top-5 con página y sección y termina en "Búsqueda exacta a mano vs Qdrant: coinciden". `python -m pytest tests/test_vectorial.py -q`: 11 tests en verde, sin internet.

**Cómo lo explicaría:** Un asistente que responde con documentos primero tiene que encontrar el pedazo correcto, y eso lo hace una base vectorial: guarda el significado de cada fragmento como números y devuelve los más parecidos a la pregunta. Le sumé filtros por metadatos, que es donde entran las reglas del negocio: en una clínica, solo la sede del paciente; en un estudio, solo los expedientes de ese cliente. Antes de conectar la búsqueda al modelo, la inspecciono sola: miro si la página correcta aparece arriba y si los puntajes separan bien. Si la búsqueda falla, ningún prompt lo arregla, así que la mido aparte.
