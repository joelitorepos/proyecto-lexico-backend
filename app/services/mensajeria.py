"""Utilidades de mensajería: programar, enviar (vía cola) y reprogramar mensajes.

Canales soportados:
    - WHATSAPP  → whatsapp_client.enviar  (abre WhatsApp Web; sin adjuntos)
    - CORREO    → correo_client.enviar    (Gmail SMTP; sí adjunta PDF)

Uso desde el resto del backend:
    enviar_whatsapp(id_usuario, "CREDENCIAL", "Hola, aquí está tu credencial", ruta_pdf)
    enviar_correo(id_usuario, "CREDENCIAL", "Hola, aquí está tu credencial", ruta_pdf)
    reprogramar_mensaje(id_mensaje)

`enviar_whatsapp` y `enviar_correo` NO envían en el momento: dejan el mensaje en
la cola con la hora más temprana permitida. El ciclo de envío (`ciclo_envio`) lo
manda cuando le toca.
"""
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import engine
from app.services import correo_client, whatsapp_client

logger = logging.getLogger(__name__)

CANAL_WHATSAPP = "WHATSAPP"
CANAL_CORREO = "CORREO"
RETRASO_REINTENTO_SEG = 60
INTERVALO_REVISION_SEG = 5
CODIGO_ERROR_NEGOCIO = 1644  # SIGNAL SQLSTATE '45000' en los procedimientos


class MensajeriaError(Exception):
    """Error de negocio al programar o reprogramar un mensaje."""


def _obtener_engine():
    if engine is None:
        raise RuntimeError("DATABASE_URL no está configurada")
    return engine


def _llamar(procedimiento: str, parametros: dict) -> dict | None:
    """Ejecuta un procedimiento almacenado y devuelve la primera fila, si hay.

    El nombre del procedimiento es siempre una constante interna; los valores
    viajan como parámetros, nunca concatenados.
    """
    marcadores = ", ".join(f":{nombre}" for nombre in parametros)
    try:
        with _obtener_engine().begin() as conn:
            resultado = conn.execute(text(f"CALL {procedimiento}({marcadores})"), parametros)
            if not resultado.returns_rows:
                return None
            fila = resultado.mappings().first()
            return dict(fila) if fila else None
    except DBAPIError as exc:
        args = getattr(exc.orig, "args", ())
        if len(args) > 1 and args[0] == CODIGO_ERROR_NEGOCIO:
            raise MensajeriaError(args[1]) from exc
        raise


# ---------------------------------------------------------------------------
# Programación
# ---------------------------------------------------------------------------

def programar_mensaje(
    id_usuario: int,
    canal: str,
    tipo: str,
    contenido: str,
    ruta_adjunto: str | None = None,
) -> dict:
    """Pone un mensaje en cola. Devuelve {'id_mensaje', 'programado_para'}."""
    return _llamar(
        "sp_programar_mensaje",
        {
            "id_usuario": id_usuario,
            "canal": canal,
            "tipo": tipo,
            "contenido": contenido,
            "ruta_adjunto": ruta_adjunto,
        },
    )


def enviar_whatsapp(
    id_usuario: int,
    tipo: str,
    contenido: str,
    ruta_adjunto: str | None = None,
) -> dict:
    """Punto de entrada para mandar un WhatsApp a un usuario.

    Falla con MensajeriaError si el usuario no habilitó WhatsApp.
    """
    return programar_mensaje(id_usuario, CANAL_WHATSAPP, tipo, contenido, ruta_adjunto)


def enviar_correo(
    id_usuario: int,
    tipo: str,
    contenido: str,
    ruta_adjunto: str | None = None,
) -> dict:
    """Punto de entrada para mandar un correo a un usuario.

    Falla con MensajeriaError si el usuario no habilitó correo.
    """
    return programar_mensaje(id_usuario, CANAL_CORREO, tipo, contenido, ruta_adjunto)


def reprogramar_mensaje(id_mensaje: int, retraso_segundos: int = RETRASO_REINTENTO_SEG) -> dict:
    """Devuelve a la cola un mensaje fallido, respetando el intervalo del usuario.

    Falla con MensajeriaError si el mensaje no está en ERROR o ya agotó sus intentos.
    """
    return _llamar(
        "sp_reprogramar_mensaje",
        {"id_mensaje": id_mensaje, "retraso": retraso_segundos},
    )


# ---------------------------------------------------------------------------
# Procesamiento de la cola
# ---------------------------------------------------------------------------

def _marcar(id_mensaje: int, exito: bool, error: str | None = None) -> None:
    _llamar(
        "sp_marcar_mensaje",
        {"id_mensaje": id_mensaje, "exito": exito, "error": error},
    )


def _procesar_canal(canal: str, enviar_fn) -> bool:
    """Envía el siguiente mensaje del canal. Devuelve True si había uno.

    `enviar_fn` es la función del adaptador con contrato:
        enviar_fn(destino, contenido, ruta_adjunto) -> None
    Si lanza excepción, el mensaje se marca como ERROR y se reprograma.
    """
    mensaje = _llamar("sp_tomar_siguiente_mensaje", {"canal": canal})
    if mensaje is None:
        return False

    id_mensaje = mensaje["id_mensaje"]
    try:
        enviar_fn(mensaje["destino"], mensaje["contenido"], mensaje["ruta_adjunto"])
    except Exception as exc:  # cualquier fallo del proveedor se trata como reintentable
        logger.warning(
            "Falló el envío del mensaje %s (%s): %s",
            id_mensaje,
            canal,
            exc.__class__.__name__,
        )
        _marcar(id_mensaje, False, str(exc)[:250])
        try:
            reprogramar_mensaje(id_mensaje)
        except MensajeriaError as motivo:
            logger.info("Mensaje %s no se reprogramó: %s", id_mensaje, motivo)
    else:
        _marcar(id_mensaje, True)
    return True


def procesar_siguiente_whatsapp() -> bool:
    """Envía el siguiente WhatsApp que ya le toca. Devuelve True si había uno."""
    return _procesar_canal(CANAL_WHATSAPP, whatsapp_client.enviar)


def procesar_siguiente_correo() -> bool:
    """Envía el siguiente correo que ya le toca. Devuelve True si había uno."""
    return _procesar_canal(CANAL_CORREO, correo_client.enviar)


async def ciclo_envio() -> None:
    """Revisa la cola cada pocos segundos mientras la aplicación esté viva."""
    while True:
        try:
            # Vaciar primero WhatsApp y luego correo; el próximo ciclo reintenta ambos.
            while await asyncio.to_thread(procesar_siguiente_whatsapp):
                pass
            while await asyncio.to_thread(procesar_siguiente_correo):
                pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error en el ciclo de envío")
        await asyncio.sleep(INTERVALO_REVISION_SEG)