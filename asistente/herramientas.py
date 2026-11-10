"""Herramientas del asistente sobre datos/flota.json y datos/politicas.md (datos FICTICIOS).

Cada herramienta es una función común de Python. El modelo nunca la ejecuta: pide usarla
y el agente (asistente/agente.py) la corre con ejecutar() y le devuelve el resultado.
"""

import json
import logging
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
FLOTA = RAIZ / 'datos' / 'flota.json'
POLITICAS = RAIZ / 'datos' / 'politicas.md'
CATEGORIAS = ('economico', 'suv', 'camioneta', 'familiar')
MAX_DIAS = 30


class ErrorHerramienta(ValueError):
    """Error esperable (un dato inválido): se le devuelve al modelo para que corrija o pregunte."""


@lru_cache
def cargar_flota() -> dict:
    return json.loads(FLOTA.read_text(encoding='utf-8'))


@lru_cache
def cargar_politicas() -> dict[str, str]:
    """Lee las líneas 'P6. texto' de politicas.md y devuelve {'P6': 'texto'}."""
    politicas = {}
    for linea in POLITICAS.read_text(encoding='utf-8').splitlines():
        id_, _, texto = linea.strip().partition('. ')
        if id_.startswith('P') and id_[1:].isdigit() and texto:
            politicas[id_] = texto
    return politicas


def _fecha(texto, campo: str) -> date:
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ErrorHerramienta(f'{campo} tiene que ser una fecha AAAA-MM-DD y llegó {texto!r}') from None


def _rango(desde, hasta) -> tuple[date, date]:
    inicio, fin = _fecha(desde, 'desde'), _fecha(hasta, 'hasta')
    if fin <= inicio:
        raise ErrorHerramienta('hasta (devolución) tiene que ser posterior a desde (retiro)')
    if (fin - inicio).days > MAX_DIAS:
        raise ErrorHerramienta(f'más de {MAX_DIAS} días: lo cotiza una persona del equipo')
    return inicio, fin


def _si_o_no(valor, campo: str) -> bool:
    if not isinstance(valor, bool):
        raise ErrorHerramienta(f'{campo} tiene que ser true o false y llegó {valor!r}')
    return valor


def _libre(auto: dict, inicio: date, fin: date) -> bool:
    """Libre si ninguna reserva se superpone. Se puede retirar el mismo día que otro devuelve."""
    for reserva in auto['reservas']:
        if inicio < date.fromisoformat(reserva['hasta']) and date.fromisoformat(reserva['desde']) < fin:
            return False
    return True


def _es_temporada_alta(dia: date, temporadas: list[dict]) -> bool:
    return any(date.fromisoformat(t['desde']) <= dia <= date.fromisoformat(t['hasta']) for t in temporadas)


def _ficha(auto: dict) -> dict:
    campos = ('id', 'modelo', 'categoria', 'plazas', 'transmision', 'tarifa_diaria', 'cruce_chile')
    return {c: auto[c] for c in campos}


def buscar_disponibilidad(
    desde: str,
    hasta: str,
    categoria: str | None = None,
    cruce_chile: bool = False,
) -> dict:
    """Autos libres entre desde (retiro) y hasta (devolución), con filtros opcionales."""
    inicio, fin = _rango(desde, hasta)
    cruce_chile = _si_o_no(cruce_chile, 'cruce_chile')
    categoria = categoria or None
    if categoria is not None and categoria not in CATEGORIAS:
        raise ErrorHerramienta(f'categoría desconocida {categoria!r}; opciones: {list(CATEGORIAS)}')
    libres = [
        _ficha(a)
        for a in cargar_flota()['autos']
        if (categoria is None or a['categoria'] == categoria)
        and (a['cruce_chile'] or not cruce_chile)
        and _libre(a, inicio, fin)
    ]
    return {
        'desde': desde,
        'hasta': hasta,
        'dias': (fin - inicio).days,
        'cantidad': len(libres),
        'autos_libres': libres,
    }


def cotizar(
    auto_id: str,
    desde: str,
    hasta: str,
    retiro_aeropuerto: bool = False,
    mascota: bool = False,
    cruce_chile: bool = False,
) -> dict:
    """Precio total de un auto entre dos fechas, con temporada alta y cargos extra."""
    inicio, fin = _rango(desde, hasta)
    flota = cargar_flota()
    auto = next((a for a in flota['autos'] if a['id'] == auto_id), None)
    if auto is None:
        raise ErrorHerramienta(f'no existe el auto {auto_id!r}; usá buscar_disponibilidad para ver los ids')
    pedidos = {
        'retiro_aeropuerto': (_si_o_no(retiro_aeropuerto, 'retiro_aeropuerto'), 'P4'),
        'mascota': (_si_o_no(mascota, 'mascota'), 'P5'),
        'cruce_chile': (_si_o_no(cruce_chile, 'cruce_chile'), 'P6'),
    }
    if cruce_chile and not auto['cruce_chile']:
        raise ErrorHerramienta(f'el auto {auto_id} no tiene permiso para cruzar a Chile')
    cargos = flota['cargos']
    extras = {nombre: cargos[nombre] for nombre, (pedido, _) in pedidos.items() if pedido}
    politicas = ['P2', 'P3'] + [pid for pedido, pid in pedidos.values() if pedido]
    dias = (fin - inicio).days
    tarifa = auto['tarifa_diaria']
    temporadas = flota['temporada_alta']
    dias_alta = sum(_es_temporada_alta(inicio + timedelta(days=i), temporadas) for i in range(dias))
    alquiler = tarifa * dias + tarifa * flota['recargo_temporada_alta_pct'] * dias_alta // 100
    return {
        'auto_id': auto_id,
        'modelo': auto['modelo'],
        'desde': desde,
        'hasta': hasta,
        'dias': dias,
        'disponible': _libre(auto, inicio, fin),
        'dias_temporada_alta': dias_alta,
        'alquiler': alquiler,
        'extras': extras,
        'total': alquiler + sum(extras.values()),
        'km_incluidos': flota['km_por_dia'] * dias,
        'garantia_bloqueada': cargos['garantia'],
        'moneda': flota['moneda'],
        'politicas': politicas,
    }


def consultar_politica(politica_id: str) -> dict:
    """Texto completo de una política por su ID (P1 a P10)."""
    politicas = cargar_politicas()
    if politica_id not in politicas:
        raise ErrorHerramienta(f'no existe la política {politica_id!r}; opciones: {sorted(politicas)}')
    return {'id': politica_id, 'texto': politicas[politica_id]}


FUNCIONES = {
    'buscar_disponibilidad': buscar_disponibilidad,
    'cotizar': cotizar,
    'consultar_politica': consultar_politica,
}

_FECHA = {'type': 'string', 'description': 'Fecha en formato AAAA-MM-DD, por ejemplo 2026-12-20'}


def _herramienta(nombre: str, descripcion: str, propiedades: dict, obligatorios: list[str]) -> dict:
    parametros = {'type': 'object', 'properties': propiedades, 'required': obligatorios}
    funcion = {'name': nombre, 'description': descripcion, 'parameters': parametros}
    return {'type': 'function', 'function': funcion}


# El menú que ve el modelo (formato compatible con OpenAI: Gemini, Groq y Ollama)
HERRAMIENTAS = [
    _herramienta(
        'buscar_disponibilidad',
        'Lista los autos libres para alquilar entre dos fechas. Usala siempre que el cliente pregunte qué '
        'autos hay o si hay disponibilidad. desde es el día de retiro y hasta el de devolución.',
        {
            'desde': _FECHA,
            'hasta': _FECHA,
            'categoria': {
                'type': 'string',
                'enum': list(CATEGORIAS),
                'description': 'Filtra por categoría. Omitila si el cliente no pidió una.',
            },
            'cruce_chile': {
                'type': 'boolean',
                'description': 'true si el cliente quiere cruzar a Chile: solo trae autos con permiso.',
            },
        },
        ['desde', 'hasta'],
    ),
    _herramienta(
        'cotizar',
        'Calcula el precio total de UN auto entre dos fechas, con temporada alta y cargos extra. Usá el id '
        'que devolvió buscar_disponibilidad. Nunca calcules precios sin esta herramienta.',
        {
            'auto_id': {'type': 'string', 'description': 'Id del auto, por ejemplo A03'},
            'desde': _FECHA,
            'hasta': _FECHA,
            'retiro_aeropuerto': {
                'type': 'boolean',
                'description': 'true si retira o devuelve en el aeropuerto',
            },
            'mascota': {'type': 'boolean', 'description': 'true si viaja con mascota'},
            'cruce_chile': {'type': 'boolean', 'description': 'true si va a cruzar a Chile'},
        },
        ['auto_id', 'desde', 'hasta'],
    ),
    _herramienta(
        'consultar_politica',
        'Devuelve el texto de una política de la rentadora. P1 requisitos, P2 garantía, P3 kilometraje, '
        'P4 horarios y aeropuerto, P5 mascotas, P6 cruce a Chile, P7 pagos, P8 cancelación, '
        'P9 combustible, P10 invierno y caminos.',
        {'politica_id': {'type': 'string', 'enum': [f'P{i}' for i in range(1, 11)]}},
        ['politica_id'],
    ),
]


def ejecutar(nombre: str, argumentos: dict) -> str:
    """Corre una herramienta y devuelve JSON. Nunca lanza: los errores vuelven como {'error': ...}."""
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        resultado = {'error': f'herramienta desconocida: {nombre}'}
    else:
        try:
            resultado = funcion(**argumentos)
        except ErrorHerramienta as e:
            resultado = {'error': str(e)}
        except TypeError as e:
            resultado = {'error': f'argumentos inválidos para {nombre}: {e}'}
    log.info('herramienta %s %s -> %s', nombre, argumentos, 'error' if 'error' in resultado else 'ok')
    return json.dumps(resultado, ensure_ascii=False)


def a_formato_anthropic(herramientas: list[dict] = HERRAMIENTAS) -> list[dict]:
    """Traduce el menú al formato de la Messages API de Claude (name, description, input_schema)."""
    return [
        {
            'name': h['function']['name'],
            'description': h['function']['description'],
            'input_schema': h['function']['parameters'],
        }
        for h in herramientas
    ]
