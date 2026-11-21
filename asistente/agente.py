"""Agente con tool use: el modelo pide herramientas, este código las corre y le devuelve el resultado.

Usa el formato de chat compatible con OpenAI, que entienden Gemini, Groq y Ollama, con fallback
entre proveedores como en asistente/llm.py.

Barandas de L06, en código y no en el prompt:
- Las herramientas de LECTURA que llegan juntas en un turno corren en paralelo, con timeout.
- Las de ESCRITURA pasan por una puerta: una por turno, nunca en el mismo pedido en que se creó
  el borrador, y solo si el último mensaje del cliente es una confirmación clara.
- Un error o un bug de una herramienta vuelve al modelo como dato: nunca tumba la conversación.
"""

import json
import logging
import os
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openai import OpenAI

from asistente.herramientas import HERRAMIENTAS, HERRAMIENTAS_DE_ESCRITURA, ejecutar
from asistente.llm import SinProveedorError
from asistente.prompt import envolver_mensaje

log = logging.getLogger(__name__)

PLANTILLA = Path(__file__).resolve().parent.parent / 'prompts' / 'agente.md'
MAX_VUELTAS = 6
TIMEOUT_HERRAMIENTA = 15  # segundos por herramienta (buscar_manual llama a la API de embeddings)
DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')

# Confirmación: un sí claro al principio, sin peros ni negaciones. Ante la duda, NO se escribe.
AFIRMATIVO = re.compile(
    r'^\W*(s[ií]|confirmo|confirmado|dale|de acuerdo|ok|okay|listo|perfecto|yes)\b', re.IGNORECASE
)
NEGATIVO = re.compile(r'\b(no|pero|esper[aá]|todav[ií]a|cancel\w*|cambi\w*)\b', re.IGNORECASE)

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix='herramienta')

# Proveedor: (URL base compatible con OpenAI, variable de la clave, variable del modelo, modelo por defecto)
PROVEEDORES = {
    'gemini': (
        'https://generativelanguage.googleapis.com/v1beta/openai/',
        'GEMINI_API_KEY',
        'GEMINI_MODEL',
        'gemini-flash-latest',
    ),
    'groq': ('https://api.groq.com/openai/v1', 'GROQ_API_KEY', 'GROQ_MODEL', 'openai/gpt-oss-20b'),
    # Mismo proveedor, otro modelo: Groq limita tokens por minuto por modelo, así duplicamos el cupo gratis
    'groq_grande': (
        'https://api.groq.com/openai/v1',
        'GROQ_API_KEY',
        'GROQ_MODEL_GRANDE',
        'openai/gpt-oss-120b',
    ),
    'ollama': (None, None, 'OLLAMA_MODEL', 'gemma4:e4b'),
}


class LimiteDeVueltasError(RuntimeError):
    """El modelo siguió pidiendo herramientas sin llegar a una respuesta."""


@dataclass
class ResultadoAgente:
    texto: str
    proveedor: str
    modelo: str
    llamadas: list[dict]
    vueltas: int
    segundos: float
    historial: list[dict]


def cargar_instrucciones(fecha: date | None = None) -> str:
    """System prompt del agente con la fecha y el día de la semana."""
    hoy = fecha or date.today()
    texto = PLANTILLA.read_text(encoding='utf-8')
    texto = texto.replace('{{FECHA}}', hoy.isoformat()).replace('{{DIA}}', DIAS[hoy.weekday()])
    if '{{' in texto:
        raise ValueError('prompts/agente.md tiene marcadores sin reemplazar')
    return texto


def crear_cliente(nombre: str) -> tuple[OpenAI, str]:
    """Cliente compatible con OpenAI para el proveedor pedido, y el modelo a usar."""
    if nombre not in PROVEEDORES:
        raise ValueError(f'Proveedor desconocido: {nombre}')
    base_url, var_clave, var_modelo, modelo_por_defecto = PROVEEDORES[nombre]
    if var_clave is None:  # Ollama corre en tu Mac y no pide clave
        base_url, clave = os.environ.get('OLLAMA_URL', 'http://localhost:11434/v1'), 'ollama'
    else:
        clave = os.environ.get(var_clave, '').strip()
        if not clave:
            raise RuntimeError(f'Falta la variable de entorno {var_clave}')
    modelo = os.environ.get(var_modelo, modelo_por_defecto)
    return OpenAI(base_url=base_url, api_key=clave, timeout=60, max_retries=1), modelo


def cliente_confirmo(mensaje: str) -> bool:
    """True solo si el mensaje del cliente es una confirmación clara (sí, confirmo, dale...)."""
    return bool(AFIRMATIVO.search(mensaje)) and not NEGATIVO.search(mensaje)


def _argumentos(tc) -> dict | None:
    """Los argumentos de un tool_call como dict, o None si no son un objeto JSON válido."""
    try:
        argumentos = json.loads(tc.function.arguments or '{}')
    except json.JSONDecodeError:
        return None
    return argumentos if isinstance(argumentos, dict) else None


def _correr(nombre: str, argumentos: dict | None) -> dict:
    """Corre una herramienta y SIEMPRE devuelve un dict: los errores también son datos."""
    if argumentos is None:
        return {'error': 'los argumentos no son un objeto JSON válido'}
    try:
        return json.loads(ejecutar(nombre, argumentos))
    except Exception:  # un bug en una herramienta no puede tumbar la conversación
        log.exception('falla inesperada en la herramienta %s', nombre)
        return {'error': f'falla interna en {nombre}; ofrecé que lo vea una persona del equipo'}


def _esperar(nombre: str, futuro: Future) -> dict:
    """Espera el resultado con un tope. Ojo: un timeout NO prueba que la herramienta no haya corrido."""
    try:
        return futuro.result(timeout=TIMEOUT_HERRAMIENTA)
    except TimeoutError:
        log.warning('la herramienta %s tardó más de %s s', nombre, TIMEOUT_HERRAMIENTA)
        return {'error': f'{nombre} tardó demasiado; probá una vez más o derivá', 'reintentable': True}


def _motivo_para_no_escribir(
    argumentos: dict | None, mensaje_cliente: str, preparados: set[str], escrituras: int
) -> str | None:
    """Por qué NO se puede escribir todavía, o None si se puede."""
    if escrituras > 0:
        return 'una sola escritura por turno: esperá el resultado de la anterior'
    if argumentos and argumentos.get('borrador_id') in preparados:
        return 'el cliente todavía no vio este borrador: mostrale el resumen y preguntale si confirma'
    if not cliente_confirmo(mensaje_cliente):
        return 'el cliente no confirmó en su último mensaje: mostrale el resumen y pedile que responda sí'
    return None


def _ejecutar_turno(tool_calls: list, mensaje_cliente: str, preparados: set[str]) -> list[dict]:
    """Corre los pedidos de un turno: lecturas en paralelo, escrituras de a una y detrás de la puerta."""
    pedidos = [(tc.function.name, _argumentos(tc)) for tc in tool_calls]
    futuros = {
        i: _POOL.submit(_correr, nombre, argumentos)
        for i, (nombre, argumentos) in enumerate(pedidos)
        if nombre not in HERRAMIENTAS_DE_ESCRITURA
    }
    resultados = {i: _esperar(pedidos[i][0], futuro) for i, futuro in futuros.items()}
    for resultado in resultados.values():
        if resultado.get('nuevo') and 'borrador_id' in resultado:
            preparados.add(resultado['borrador_id'])
    escrituras = 0
    for i, (nombre, argumentos) in enumerate(pedidos):
        if i in resultados:
            continue
        motivo = _motivo_para_no_escribir(argumentos, mensaje_cliente, preparados, escrituras)
        if motivo:
            log.info('puerta de escritura: %s bloqueada (%s)', nombre, motivo)
            resultados[i] = {'error': f'no ejecuté {nombre}: {motivo}'}
            continue
        escrituras += 1
        resultados[i] = _esperar(nombre, _POOL.submit(_correr, nombre, argumentos))
    return [resultados[i] for i in range(len(pedidos))]


def _bucle(
    cliente: OpenAI,
    modelo: str,
    mensajes: list[dict],
    llamadas: list[dict],
    max_vueltas: int,
    mensaje_cliente: str,
) -> tuple[str, int]:
    """El loop de herramientas: pedir, ejecutar, devolver, hasta que el modelo responda con texto."""
    preparados: set[str] = set()  # borradores creados en ESTE pedido: el cliente todavía no los vio
    for vuelta in range(1, max_vueltas + 1):
        r = cliente.chat.completions.create(
            model=modelo, messages=mensajes, tools=HERRAMIENTAS, temperature=0.2
        )
        mensaje = r.choices[0].message
        if not mensaje.tool_calls:
            texto = (mensaje.content or '').strip()
            if not texto:
                raise RuntimeError('el modelo devolvió una respuesta vacía')
            return texto, vuelta
        # 1) Guardar el pedido del modelo completo (con sus ids y campos extra) ANTES de los resultados
        pedidos = [tc.model_dump(exclude_none=True) for tc in mensaje.tool_calls]
        asistente = {'role': 'assistant', 'tool_calls': pedidos}
        if mensaje.content:
            asistente['content'] = mensaje.content
        mensajes.append(asistente)
        # 2) Ejecutar el turno: lecturas en paralelo, escrituras detrás de la puerta
        resultados = _ejecutar_turno(mensaje.tool_calls, mensaje_cliente, preparados)
        # 3) Devolver un resultado por cada id, en el mismo orden en que se pidieron
        for tc, resultado in zip(mensaje.tool_calls, resultados, strict=True):
            estado = 'error' if 'error' in resultado else 'ok'
            log.info('vuelta %d: %s -> %s', vuelta, tc.function.name, estado)
            llamadas.append(
                {'herramienta': tc.function.name, 'argumentos': _argumentos(tc), 'resultado': resultado}
            )
            contenido = json.dumps(resultado, ensure_ascii=False)
            mensajes.append({'role': 'tool', 'tool_call_id': tc.id, 'content': contenido})
    raise LimiteDeVueltasError(f'el modelo pidió herramientas {max_vueltas} veces sin responder')


def conversar(
    mensaje: str,
    historial: list[dict] | None = None,
    proveedores: list[str] | None = None,
    max_vueltas: int = MAX_VUELTAS,
) -> ResultadoAgente:
    """Responde un mensaje usando herramientas; prueba los proveedores en orden hasta que uno responda."""
    orden = proveedores or os.environ.get('PROVEEDORES', 'gemini,groq,ollama').split(',')
    previos = list(historial or [])
    entrada = {'role': 'user', 'content': envolver_mensaje(mensaje)}
    base = [{'role': 'system', 'content': cargar_instrucciones()}, *previos, entrada]
    errores = []
    for nombre in (n.strip() for n in orden):
        inicio = time.perf_counter()
        llamadas: list[dict] = []
        try:
            cliente, modelo = crear_cliente(nombre)
            texto, vueltas = _bucle(cliente, modelo, list(base), llamadas, max_vueltas, mensaje)
        except Exception as e:  # noqa: BLE001 (red, cuota, clave o loop -> siguiente)
            log.warning('%s falló: %s', nombre, e)
            errores.append(f'{nombre}: {type(e).__name__}')
            continue
        historial_nuevo = [*previos, entrada, {'role': 'assistant', 'content': texto}]
        segundos = time.perf_counter() - inicio
        return ResultadoAgente(texto, nombre, modelo, llamadas, vueltas, segundos, historial_nuevo)
    raise SinProveedorError('Ningún proveedor respondió: ' + '; '.join(errores))
