"""API web del asistente: POST /chat y GET /salud.

Para correrla en tu Mac:
    python -m uvicorn api.main:app --reload
y abrir http://127.0.0.1:8000/docs
"""

import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.config import Ajustes
from api.esquemas import ErrorApi, PedidoChat, RespuestaChat, Salud
from api.sesiones import AlmacenDeSesiones, LimitadorPorMinuto, LimiteAlcanzadoError
from asistente import atencion
from asistente.llm import SinProveedorError
from asistente.prompt import envolver_mensaje

VERSION = '0.7.0'
WEB = Path(__file__).resolve().parent.parent / 'web' / 'index.html'
AVISO_SIN_PROVEEDOR = 'El asistente no está disponible en este momento. Probá de nuevo en unos minutos.'

log = logging.getLogger(__name__)


def crear_app(ajustes: Ajustes | None = None) -> FastAPI:
    """Arma la app con sus límites y su CORS. Los tests la crean con ajustes propios."""
    ajustes = ajustes or Ajustes.desde_entorno()
    sesiones = AlmacenDeSesiones(
        max_sesiones=ajustes.max_sesiones,
        max_mensajes=ajustes.max_mensajes_por_sesion,
        max_historial=ajustes.max_historial,
    )
    limitador = LimitadorPorMinuto(ajustes.max_pedidos_por_minuto)

    app = FastAPI(
        title='Asistente de la rentadora (demo)',
        version=VERSION,
        description='Chatbot de atención de una rentadora de autos, con datos ficticios.',
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ajustes.origenes_cors,
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type'],
    )

    @app.get('/salud', response_model=Salud, tags=['estado'])
    def salud() -> Salud:
        """Dice si el servidor está vivo. La usan los monitores y el hosting (E4)."""
        return Salud(estado='ok', version=VERSION, sesiones_activas=sesiones.cantidad())

    @app.post(
        '/chat',
        response_model=RespuestaChat,
        tags=['chat'],
        responses={429: {'model': ErrorApi}, 503: {'model': ErrorApi}},
    )
    def chat(pedido: PedidoChat, request: Request) -> RespuestaChat:
        """Manda un mensaje al asistente. Es def (no async def) porque atender() espera a la red."""
        # Detrás del proxy del hosting, la IP real del visitante viene en X-Forwarded-For
        reenviada = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
        visitante = reenviada or (request.client.host if request.client else 'desconocido')
        sesion_id = pedido.sesion_id or uuid.uuid4().hex
        try:
            limitador.registrar(visitante)
            previos = sesiones.historial(sesion_id)
            if not previos and pedido.historial:
                # Instancia nueva (serverless): usamos lo que guarda el navegador, con los mensajes del
                # usuario envueltos como datos para que no puedan hacerse pasar por instrucciones
                previos = [
                    {'role': m.role, 'content': envolver_mensaje(m.content) if m.role == 'user' else m.content}
                    for m in pedido.historial[-ajustes.max_historial:]
                ]
        except LimiteAlcanzadoError as e:
            cabeceras = {'Retry-After': str(e.reintentar_en)} if e.reintentar_en else None
            log.info('sesión %s: límite alcanzado (%s)', sesion_id[:8], e.motivo)
            raise HTTPException(status_code=429, detail=e.motivo, headers=cabeceras) from e
        try:
            res = atencion.atender(pedido.mensaje, historial=previos)
        except SinProveedorError as e:
            log.error('sesión %s: ningún proveedor respondió: %s', sesion_id[:8], e)
            raise HTTPException(status_code=503, detail=AVISO_SIN_PROVEEDOR) from e
        restantes = sesiones.guardar(sesion_id, res.historial)
        log.info(
            'sesión %s: ruta=%s proveedor=%s herramientas=%s llamadas=%d',
            sesion_id[:8],
            res.ruta,
            res.proveedor,
            res.herramientas,
            res.llamadas_llm,
        )
        return RespuestaChat(
            sesion_id=sesion_id,
            respuesta=res.texto,
            ruta=res.ruta,
            motivo=res.motivo,
            herramientas=res.herramientas,
            fuentes=res.fuentes,
            proveedor=res.proveedor,
            llamadas_llm=res.llamadas_llm,
            derivar_a_humano=res.derivar_a_humano,
            mensajes_restantes=restantes,
        )

    @app.get('/', include_in_schema=False)
    def pagina_del_chat() -> FileResponse:
        """La interfaz web del chat (web/index.html), servida por la misma API: sin problemas de CORS."""
        return FileResponse(WEB, media_type='text/html')

    return app


load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
app = crear_app()
