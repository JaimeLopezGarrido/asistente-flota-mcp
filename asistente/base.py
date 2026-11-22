"""Base de datos SQLite del asistente: flota, reservas, borradores y conversaciones (datos FICTICIOS).

Es la única puerta a la base: el resto del código no escribe SQL suelto ni abre conexiones a mano.

- conexion(): abre una conexión nueva para cada operación (seguro con los hilos del servidor).
- transaccion(): todo o nada. Si algo falla adentro, ROLLBACK y no queda nada a medias.
- migrar(): crea o actualiza las tablas según PRAGMA user_version (migraciones numeradas).

Dónde vive el archivo: la variable DB_RUTA; si está vacía, datos/rentadora.db en tu Mac o
/tmp/rentadora.db en Vercel (el único lugar con escritura, y se borra cuando la instancia se apaga).
"""

import json
import logging
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
SEMILLA = RAIZ / 'datos' / 'flota.json'

# Una migración es una lista de sentencias SQL. Nunca se cambia una que ya corrió: se agrega otra al final.
MIGRACIONES: list[list[str]] = [
    [  # 1. Esquema inicial
        """
        CREATE TABLE autos (
            id TEXT PRIMARY KEY CHECK (id GLOB 'A[0-9][0-9]'),
            modelo TEXT NOT NULL,
            categoria TEXT NOT NULL CHECK (categoria IN ('economico', 'suv', 'camioneta', 'familiar')),
            plazas INTEGER NOT NULL CHECK (plazas > 0),
            transmision TEXT NOT NULL,
            tarifa_diaria INTEGER NOT NULL CHECK (tarifa_diaria > 0),
            cruce_chile INTEGER NOT NULL CHECK (cruce_chile IN (0, 1))
        )
        """,
        """
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE reservas (
            id TEXT PRIMARY KEY,
            borrador_id TEXT UNIQUE,
            auto_id TEXT NOT NULL REFERENCES autos (id),
            cliente_id INTEGER REFERENCES clientes (id),
            desde TEXT NOT NULL,
            hasta TEXT NOT NULL,
            total INTEGER,
            estado TEXT NOT NULL
                CHECK (estado IN ('bloqueo', 'pendiente_de_aprobacion', 'aprobada', 'cancelada')),
            creada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (desde < hasta)
        )
        """,
        """
        CREATE TABLE borradores (
            id TEXT PRIMARY KEY,
            datos TEXT NOT NULL,
            total INTEGER NOT NULL,
            creado REAL NOT NULL
        )
        """,
        """
        CREATE TABLE conversaciones (
            sesion_id TEXT PRIMARY KEY,
            mensajes_usados INTEGER NOT NULL DEFAULT 0 CHECK (mensajes_usados >= 0),
            uso INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE mensajes (
            sesion_id TEXT NOT NULL REFERENCES conversaciones (sesion_id) ON DELETE CASCADE,
            orden INTEGER NOT NULL,
            rol TEXT NOT NULL CHECK (rol IN ('system', 'user', 'assistant', 'tool')),
            contenido TEXT NOT NULL,
            PRIMARY KEY (sesion_id, orden)
        )
        """,
    ],
    [  # 2. Índices para las consultas que más se repiten
        'CREATE INDEX IF NOT EXISTS reservas_por_auto ON reservas (auto_id, desde, hasta)',
        'CREATE INDEX IF NOT EXISTS conversaciones_por_uso ON conversaciones (uso)',
    ],
]

# Nombres fijos escritos por nosotros: lo único que se permite meter en el SQL con f-string
_COLUMNAS_AUTO = 'id, modelo, categoria, plazas, transmision, tarifa_diaria, cruce_chile'


def ruta_por_defecto() -> str:
    """DB_RUTA si está definida; si no, /tmp en Vercel (solo ahí se puede escribir) o datos/ en tu Mac."""
    ruta = os.environ.get('DB_RUTA', '').strip()
    if ruta:
        return ruta
    if os.environ.get('VERCEL'):
        return '/tmp/rentadora.db'
    return str(RAIZ / 'datos' / 'rentadora.db')


class BaseDeDatos:
    """Un archivo SQLite. Al crearla migra el esquema y, si no tiene autos, carga la semilla."""

    def __init__(self, ruta: str | Path):
        self.ruta = str(ruta)
        Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        self.migrar()

    @contextmanager
    def conexion(self) -> Iterator[sqlite3.Connection]:
        """Conexión para una operación. Con isolation_level=None las transacciones las abrimos nosotros."""
        con = sqlite3.connect(self.ruta, timeout=5, isolation_level=None)
        con.row_factory = sqlite3.Row  # filas que se leen por nombre: fila['modelo']
        con.execute('PRAGMA foreign_keys = ON')  # SQLite no controla las claves foráneas si no se lo pedís
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Connection]:
        """Todo o nada. BEGIN IMMEDIATE toma el turno de escritura al empezar: dos escrituras no se pisan."""
        with self.conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            completa = False
            try:
                yield con
                completa = True
            finally:
                con.execute('COMMIT' if completa else 'ROLLBACK')

    def version(self) -> int:
        """Número de la última migración aplicada."""
        with self.conexion() as con:
            return con.execute('PRAGMA user_version').fetchone()[0]

    def migrar(self) -> None:
        """Aplica, en orden y en una sola transacción, las migraciones que esta base todavía no tiene."""
        with self.conexion() as con:
            con.execute('PRAGMA journal_mode = WAL')  # los que leen no frenan al que escribe
        with self.transaccion() as con:
            actual = con.execute('PRAGMA user_version').fetchone()[0]
            for numero in range(actual + 1, len(MIGRACIONES) + 1):
                for sentencia in MIGRACIONES[numero - 1]:
                    con.execute(sentencia)
                con.execute(f'PRAGMA user_version = {numero}')
                log.info('migración %d aplicada en %s', numero, self.ruta)
            if con.execute('SELECT COUNT(*) FROM autos').fetchone()[0] == 0:
                _sembrar(con)


def _sembrar(con: sqlite3.Connection) -> None:
    """Primera vez: copia los autos y los días ya ocupados de datos/flota.json (la semilla)."""
    flota = json.loads(SEMILLA.read_text(encoding='utf-8'))
    for auto in flota['autos']:
        con.execute(
            f'INSERT INTO autos ({_COLUMNAS_AUTO}) VALUES '
            '(:id, :modelo, :categoria, :plazas, :transmision, :tarifa_diaria, :cruce_chile)',
            auto,
        )
        auto_id = auto['id']
        for numero, ocupado in enumerate(auto['reservas'], start=1):
            con.execute(
                'INSERT INTO reservas (id, auto_id, desde, hasta, estado) VALUES (?, ?, ?, ?, ?)',
                (f'F-{auto_id}-{numero}', auto_id, ocupado['desde'], ocupado['hasta'], 'bloqueo'),
            )
    log.info('base sembrada con %d autos de %s', len(flota['autos']), SEMILLA.name)


def _auto(fila: sqlite3.Row) -> dict:
    return {**dict(fila), 'cruce_chile': bool(fila['cruce_chile'])}


def listar_autos(con: sqlite3.Connection) -> list[dict]:
    """Todos los autos de la flota, ordenados por id."""
    return [_auto(fila) for fila in con.execute(f'SELECT {_COLUMNAS_AUTO} FROM autos ORDER BY id')]


def buscar_auto(con: sqlite3.Connection, auto_id: str) -> dict | None:
    """Un auto por su id, o None si no existe."""
    fila = con.execute(f'SELECT {_COLUMNAS_AUTO} FROM autos WHERE id = ?', (auto_id,)).fetchone()
    return None if fila is None else _auto(fila)


def auto_libre(con: sqlite3.Connection, auto_id: str, desde: str, hasta: str) -> bool:
    """Libre si ninguna reserva activa se superpone. Se puede retirar el mismo día que otro devuelve."""
    choque = con.execute(
        'SELECT 1 FROM reservas WHERE auto_id = ? AND estado != ? AND ? < hasta AND desde < ? LIMIT 1',
        (auto_id, 'cancelada', desde, hasta),
    ).fetchone()
    return choque is None


_actual: BaseDeDatos | None = None
_candado = threading.Lock()


def obtener() -> BaseDeDatos:
    """La base del proceso, creada la primera vez que alguien la usa (los tests la reemplazan)."""
    global _actual
    with _candado:
        if _actual is None:
            _actual = BaseDeDatos(ruta_por_defecto())
        return _actual
