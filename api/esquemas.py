"""Modelos de entrada y salida de la API: Pydantic valida lo que llega y documenta lo que sale."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LARGO_MAXIMO = 1000
PATRON_SESION = r'^[A-Za-z0-9_-]{8,64}$'


class MensajePrevio(BaseModel):
    model_config = ConfigDict(extra='forbid')

    role: Literal['user', 'assistant']
    content: str = Field(max_length=4000)


class PedidoChat(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        str_strip_whitespace=True,
        json_schema_extra={
            'examples': [{'mensaje': '¿Tienen SUV del 10 al 14 de diciembre?', 'sesion_id': 'demo-sesion-0001'}]
        },
    )

    mensaje: str = Field(min_length=1, max_length=LARGO_MAXIMO, description='Lo que escribe el visitante')
    sesion_id: str | None = Field(
        default=None,
        pattern=PATRON_SESION,
        description='Id de la conversación. Si no lo mandás, la API crea uno y te lo devuelve.',
    )
    historial: list[MensajePrevio] | None = Field(
        default=None,
        max_length=40,
        description='Opcional: los mensajes anteriores que guarda el navegador. Se usan solo si el servidor no '
        'recuerda la sesión (en el hosting serverless cada pedido puede caer en una instancia nueva).',
    )


class Fuente(BaseModel):
    pagina: int
    seccion: str
    extracto: str


class RespuestaChat(BaseModel):
    sesion_id: str = Field(description='Mandalo en el próximo mensaje para seguir la conversación')
    respuesta: str
    ruta: str = Field(description='Camino del router: politica, cotizacion, reclamo o fuera_de_alcance')
    motivo: str
    herramientas: list[str] = Field(description='Herramientas que usó el agente, en orden')
    fuentes: list[Fuente] = Field(default_factory=list, description='Páginas del manual citadas en la respuesta')
    proveedor: str = Field(description='Quién escribió la respuesta (ninguno si fue una respuesta fija)')
    llamadas_llm: int
    derivar_a_humano: bool
    mensajes_restantes: int


class Salud(BaseModel):
    estado: str
    version: str
    sesiones_activas: int


class ErrorApi(BaseModel):
    detail: str
