"""Agente con tool use: el modelo pide herramientas, este código las corre y le devuelve el resultado.

Usa el formato de chat compatible con OpenAI, que entienden Gemini, Groq y Ollama, con fallback
entre proveedores como en asistente/llm.py.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openai import OpenAI

from asistente.herramientas import HERRAMIENTAS, ejecutar
from asistente.llm import SinProveedorError
from asistente.prompt import envolver_mensaje

log = logging.getLogger(__name__)

PLANTILLA = Path(__file__).resolve().parent.parent / 'prompts' / 'agente.md'
MAX_VUELTAS = 6
DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')

# Proveedor: (URL base compatible con OpenAI, variable de la clave, variable del modelo, modelo por defecto)
PROVEEDORES = {
    'gemini': (
        'https://generativelanguage.googleapis.com/v1beta/openai/',
        'GEMINI_API_KEY',
        'GEMINI_MODEL',
        'gemini-flash-latest',
    ),
    'groq': ('https://api.groq.com/openai/v1', 'GROQ_API_KEY', 'GROQ_MODEL', 'openai/gpt-oss-20b'),
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


def _bucle(
    cliente: OpenAI,
    modelo: str,
    mensajes: list[dict],
    llamadas: list[dict],
    max_vueltas: int,
) -> tuple[str, int]:
    """El loop de herramientas: pedir, ejecutar, devolver, hasta que el modelo responda con texto."""
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
        # 2) Ejecutar cada herramienta y devolver un resultado por cada id
        for tc in mensaje.tool_calls:
            try:
                argumentos = json.loads(tc.function.arguments or '{}')
            except json.JSONDecodeError:
                argumentos = None
                resultado = json.dumps({'error': 'los argumentos no son JSON válido'})
            else:
                resultado = ejecutar(tc.function.name, argumentos)
            log.info('vuelta %d: %s(%s)', vuelta, tc.function.name, tc.function.arguments)
            llamada = {'herramienta': tc.function.name, 'argumentos': argumentos}
            llamada['resultado'] = json.loads(resultado)
            llamadas.append(llamada)
            mensajes.append({'role': 'tool', 'tool_call_id': tc.id, 'content': resultado})
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
            texto, vueltas = _bucle(cliente, modelo, list(base), llamadas, max_vueltas)
        except Exception as e:  # noqa: BLE001 (red, cuota, clave o loop -> siguiente)
            log.warning('%s falló: %s', nombre, e)
            errores.append(f'{nombre}: {type(e).__name__}')
            continue
        historial_nuevo = [*previos, entrada, {'role': 'assistant', 'content': texto}]
        segundos = time.perf_counter() - inicio
        return ResultadoAgente(texto, nombre, modelo, llamadas, vueltas, segundos, historial_nuevo)
    raise SinProveedorError('Ningún proveedor respondió: ' + '; '.join(errores))
