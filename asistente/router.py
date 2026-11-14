"""Router de intención: clasifica el mensaje antes del agente y elige el camino (patrón routing).

Una llamada corta, con temperatura 0 y salida JSON validada. Si ningún proveedor responde bien,
devuelve la ruta por defecto (el camino más capaz) en lugar de fallar.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from asistente.agente import crear_cliente
from asistente.prompt import envolver_mensaje

log = logging.getLogger(__name__)

PLANTILLA = Path(__file__).resolve().parent.parent / 'prompts' / 'router.md'
Ruta = Literal['politica', 'cotizacion', 'reclamo', 'fuera_de_alcance']
RUTAS: tuple[str, ...] = get_args(Ruta)
RUTA_POR_DEFECTO: Ruta = 'cotizacion'  # ante la duda, el camino más capaz: el agente


class Clasificacion(BaseModel):
    model_config = ConfigDict(extra='ignore')

    ruta: Ruta
    motivo: str = Field(default='', max_length=300)


@dataclass
class Decision:
    ruta: str
    motivo: str
    proveedor: str  # 'ninguno' si se usó la ruta por defecto


def cargar_instrucciones() -> str:
    """System prompt del router."""
    return PLANTILLA.read_text(encoding='utf-8')


def armar_entrada(mensaje: str, ultimo_asistente: str | None = None) -> str:
    """Mensaje del cliente envuelto, con lo último que dijo el asistente como contexto."""
    partes = []
    if ultimo_asistente:
        partes.append(f'<ultimo_mensaje_asistente>{ultimo_asistente.strip()}</ultimo_mensaje_asistente>')
    partes.append(envolver_mensaje(mensaje))
    return ' '.join(partes)


def _pedir(cliente: OpenAI, modelo: str, entrada: str) -> Clasificacion:
    r = cliente.chat.completions.create(
        model=modelo,
        temperature=0,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': cargar_instrucciones()},
            {'role': 'user', 'content': entrada},
        ],
    )
    return Clasificacion.model_validate_json(r.choices[0].message.content or '')


def clasificar(
    mensaje: str,
    ultimo_asistente: str | None = None,
    proveedores: list[str] | None = None,
) -> Decision:
    """Elige la ruta del mensaje probando los proveedores en orden. Nunca lanza."""
    por_defecto = os.environ.get('PROVEEDORES_ROUTER') or os.environ.get('PROVEEDORES', 'groq,gemini,ollama')
    orden = proveedores or por_defecto.split(',')
    entrada = armar_entrada(mensaje, ultimo_asistente)
    for nombre in (n.strip() for n in orden if n.strip()):
        try:
            cliente, modelo = crear_cliente(nombre)
            modelo = os.environ.get(f'ROUTER_{nombre.upper()}_MODEL') or modelo
            clasificacion = _pedir(cliente, modelo, entrada)
        except ValidationError as e:
            log.warning('router: %s devolvió una clasificación inválida: %s', nombre, e.errors()[:1])
            continue
        except Exception as e:  # noqa: BLE001 (red, cuota o clave faltante -> siguiente proveedor)
            log.warning('router: %s falló: %s', nombre, e)
            continue
        log.info('router: %s -> %s (%s)', nombre, clasificacion.ruta, clasificacion.motivo)
        return Decision(clasificacion.ruta, clasificacion.motivo, nombre)
    log.warning('router: ningún proveedor clasificó; uso la ruta por defecto %s', RUTA_POR_DEFECTO)
    return Decision(RUTA_POR_DEFECTO, 'sin clasificación: ruta por defecto', 'ninguno')
