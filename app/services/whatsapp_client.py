"""Adaptador hacia WhatsApp Web (basado en el bot.py de la compañera).

Funcionamiento: abre WhatsApp Web en el navegador del equipo con el chat y el
texto ya escritos, y una persona debe presionar "Enviar" en el navegador.
Por eso solo funciona en una máquina con escritorio y WhatsApp Web ya iniciado
(no en un servidor sin pantalla) y no puede enviar archivos adjuntos.

Este es el ÚNICO archivo que habla con WhatsApp: si más adelante se cambia a la
API oficial, solo se reemplaza `enviar`.
"""
import logging
import os
import re
import webbrowser
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _normalizar_telefono(telefono: str) -> str:
    """Deja solo dígitos con código de país (WhatsApp Web no acepta '+' ni espacios)."""
    digitos = re.sub(r"\D", "", telefono or "")
    if len(digitos) == 8:
        # Número local sin código de país
        digitos = os.getenv("WHATSAPP_CODIGO_PAIS", "502") + digitos
    if not 8 <= len(digitos) <= 15:
        raise ValueError("Número de teléfono no válido")
    return digitos


def enviar_mensaje_whatsapp(telefono: str, mensaje: str) -> None:
    """Abre WhatsApp Web con el mensaje listo para enviar."""
    numero = _normalizar_telefono(telefono)
    mensaje_codificado = quote(mensaje or "", safe="")
    url = f"https://web.whatsapp.com/send?phone={numero}&text={mensaje_codificado}"

    logger.info("Abriendo WhatsApp Web para el número ***%s", numero[-4:])
    if not webbrowser.open(url):
        raise RuntimeError("No se pudo abrir el navegador")


def enviar(telefono: str, contenido: str, ruta_adjunto: str | None = None) -> None:
    """Contrato que usa mensajeria.py. Debe lanzar una excepción si falla."""
    if ruta_adjunto:
        logger.warning("WhatsApp Web no permite adjuntar archivos por URL; se ignora el adjunto")
    enviar_mensaje_whatsapp(telefono, contenido)


if __name__ == "__main__":
    # Prueba manual: python -m app.services.whatsapp_client NUMERO "mensaje"
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 3:
        print('Uso: python -m app.services.whatsapp_client NUMERO "mensaje"')
    else:
        enviar(sys.argv[1], sys.argv[2])