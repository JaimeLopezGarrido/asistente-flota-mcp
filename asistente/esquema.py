"""Esquema de la respuesta del asistente: única fuente de verdad para el prompt, la API y los tests."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Intencion = Literal["disponibilidad", "tarifa", "politica", "reserva", "reclamo", "fuera_de_alcance"]


class Respuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intencion: Intencion = Field(description="Intención principal del mensaje del cliente")
    respuesta: str = Field(description="Texto para el cliente, en su idioma, máximo 80 palabras")
    datos_faltantes: list[str] = Field(description="Datos que hay que pedirle al cliente para avanzar")
    derivar_a_humano: bool = Field(description="True si tiene que intervenir una persona")
    politicas_usadas: list[str] = Field(description="IDs de las políticas usadas, por ejemplo P6")
