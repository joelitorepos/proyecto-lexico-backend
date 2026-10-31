"""Adaptador hacia Gmail SMTP (basado en el módulo del compañero).

Este es el ÚNICO archivo que habla con el servidor de correo. Si más adelante
se cambia a otro proveedor (SendGrid, SES, etc.), solo se reemplaza `enviar`.

Contrato que usa mensajeria.py:
    enviar(destinatario, contenido, ruta_adjunto=None, asunto=..., carnet=..., password_acceso=...)

`ruta_adjunto` es una ruta RELATIVA a UPLOADS_DIR (así se guarda en la BD).
Aquí se resuelve a absoluta con `archivos.absoluta` antes de leerla.
"""
import logging
import os
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from app.services.archivos import absoluta

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _credenciales() -> tuple[str, str]:
    usuario = os.getenv("SMTP_USUARIO")
    password = os.getenv("SMTP_PASSWORD")
    if not usuario or not password:
        raise RuntimeError("SMTP_USUARIO y SMTP_PASSWORD no están configurados")
    return usuario, password


def _cuerpo_html(contenido: str, carnet: str | None, password_acceso: str | None) -> str:
    """Plantilla HTML sencilla. Si hay carnet/contraseña, se agrega el bloque de credenciales."""
    bloque = ""
    if carnet or password_acceso:
        filas = ""
        if carnet:
            filas += f"<p><strong>Carnet:</strong> <code>{carnet}</code></p>"
        if password_acceso:
            filas += (
                "<p><strong>Contraseña temporal:</strong> "
                f"<code style='color:#B31B1B;font-weight:bold'>{password_acceso}</code></p>"
                "<p style='font-size:11px;color:#666;font-style:italic'>"
                "Debe cambiarla al iniciar sesión por primera vez.</p>"
            )
        bloque = (
            "<div style='background:#FFF9E6;padding:18px;border:1px solid #E5A93B;"
            f"border-radius:6px;margin:20px 0'>{filas}</div>"
        )

    return f"""<html><body style='font-family:"Segoe UI",sans-serif;color:#333;line-height:1.6'>
      <div style='background:#1A3668;padding:25px;text-align:center;color:#FFF'>
        <h1 style='margin:0;font-size:22px'>LexiScan / UMG</h1>
      </div>
      <div style='padding:30px;background:#FAFAFA;border-left:4px solid #1A3668;border-right:4px solid #1A3668'>
        <p>{contenido}</p>
        {bloque}
        <p>Adjunto encontrará su <strong>credencial digital</strong> en formato PDF.</p>
      </div>
      <div style='background:#F0F0F0;padding:15px;text-align:center;font-size:11px;color:#666'>
        Sistema de Control Biométrico &copy; 2026
      </div>
    </body></html>"""


def _resolver_adjunto(ruta_adjunto: str) -> Path:
    """Devuelve la ruta absoluta del adjunto, resolviendo relativas contra UPLOADS_DIR.

    Falla con FileNotFoundError si el archivo no existe, para que la cola
    marque el mensaje como ERROR y lo reprograme.
    """
    ruta = Path(ruta_adjunto)
    if not ruta.is_absolute():
        ruta = absoluta(ruta_adjunto)
    if not ruta.exists():
        raise FileNotFoundError(f"El adjunto no existe: {ruta}")
    return ruta


def enviar(
    destinatario: str,
    contenido: str,
    ruta_adjunto: str | None = None,
    asunto: str = "Credenciales de Acceso - LexiScan",
    carnet: str | None = None,
    password_acceso: str | None = None,
) -> None:
    """Contrato que usa mensajeria.py. Debe lanzar una excepción si falla."""
    usuario, password = _credenciales()

    msg = MIMEMultipart()
    msg["From"] = formataddr(("LexiScan UMG", usuario))
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(_cuerpo_html(contenido, carnet, password_acceso), "html", "utf-8"))

    if ruta_adjunto:
        ruta = _resolver_adjunto(ruta_adjunto)
        parte = MIMEBase("application", "octet-stream")
        parte.set_payload(ruta.read_bytes())
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", f"attachment; filename={ruta.name}")
        msg.attach(parte)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as servidor:
        servidor.starttls(context=context)
        servidor.login(usuario, password)
        servidor.sendmail(usuario, destinatario, msg.as_string())

    logger.info("Correo enviado a %s", destinatario)