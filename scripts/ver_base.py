"""Muestra qué hay en la base: versión del esquema, filas por tabla y reservas de la demo.

Uso:
    python -m scripts.ver_base
"""

from dotenv import load_dotenv

from asistente import base as bd

TABLAS = ('autos', 'clientes', 'reservas', 'borradores', 'conversaciones', 'mensajes')
COLUMNAS = ('id', 'auto_id', 'desde', 'hasta', 'estado')


def main() -> None:
    load_dotenv()
    base = bd.obtener()
    print(f'Base: {base.ruta} (esquema versión {base.version()})')
    with base.conexion() as con:
        for tabla in TABLAS:  # nombres fijos nuestros: nunca armes SQL con texto que venga de afuera
            cantidad = con.execute(f'SELECT COUNT(*) FROM {tabla}').fetchone()[0]
            print(f'  {tabla:<15}{cantidad:>4} filas')
        filas = con.execute(
            'SELECT id, auto_id, desde, hasta, estado FROM reservas WHERE estado != ? ORDER BY creada, id',
            ('bloqueo',),
        ).fetchall()
    print('Reservas de la demo (sin los días bloqueados de la semilla):')
    for fila in filas:
        print('  ' + '  '.join(str(fila[columna]) for columna in COLUMNAS))
    if not filas:
        print('  (todavía ninguna)')


if __name__ == '__main__':
    main()
