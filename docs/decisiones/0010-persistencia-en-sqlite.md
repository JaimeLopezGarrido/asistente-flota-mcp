# 0010. Persistencia en SQLite con una capa de acceso a datos
Fecha: 2026-11-21 · Estado: aceptada · Complementa la 0009 (reservas en dos pasos)

## Contexto
Hasta L06, las reservas, los borradores y las conversaciones vivían en la memoria del proceso y la flota en un JSON. Al reiniciar el servidor se perdía todo; el candado (threading.Lock) solo ordenaba a los hilos de un proceso; y las herramientas no veían las reservas hechas en el chat, así que un auto recién reservado seguía apareciendo como libre.

## Decisión
- SQLite (módulo sqlite3 de la biblioteca estándar), un archivo por entorno: datos/rentadora.db en local y /tmp/rentadora.db en Vercel, configurable con DB_RUTA.
- Una capa de acceso a datos (asistente/base.py): el resto del código no abre conexiones ni escribe SQL de infraestructura.
- Reglas en el esquema: claves primarias y foráneas, NOT NULL, UNIQUE y CHECK (estados, fechas, ids). Lo que la base puede rechazar, lo rechaza la base.
- Cada escritura en una transacción BEGIN IMMEDIATE: verificar disponibilidad y escribir la reserva pasan juntos, aunque haya varios procesos.
- Migraciones numeradas con PRAGMA user_version, aplicadas al abrir la base.
- flota.json queda como semilla y como configuración de precios; la fuente de verdad de autos y ocupación es la base.
- El límite por minuto sigue en memoria: es un contador de vida corta.

## Alternativas consideradas
- Seguir con JSON: sin transacciones ni reglas; dos escrituras a la vez pueden perder datos.
- Postgres gestionado (Neon, Supabase): lo correcto para varios servidores y datos que no se pueden perder, pero suma una cuenta, red y secretos que hoy la demo no necesita.
- Turso (libSQL, compatible con SQLite): el paso natural si la demo tiene que persistir en serverless, con casi el mismo SQL.
- Un ORM (SQLAlchemy, SQLModel): ahorra SQL repetido pero esconde lo que pasa y suma dependencias. Se reconsidera si el esquema crece.
- Alembic para migraciones: muy completo; para seis tablas alcanza una lista numerada.

## Consecuencias
- Reservas y conversaciones sobreviven a un reinicio local, y las herramientas ven lo que se reservó.
- En Vercel la base vive en /tmp de cada instancia: se borra cuando la instancia se apaga y dos instancias no comparten datos. Para la demo alcanza (la interfaz reenvía el historial); para un cliente real, Turso o Postgres.
- Los tests usan una base temporal por test (tests/conftest.py) y nunca tocan datos reales.
- Se guarda el mínimo de datos personales: solo nombre y apellido, ficticios en la demo.
