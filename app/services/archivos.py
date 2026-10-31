"""Almacenamiento en disco de fotografías y credenciales PDF.

En la base de datos se guardan rutas RELATIVAS a UPLOADS_DIR (variable de entorno,
por defecto ./uploads), así el proyecto funciona igual en cualquier máquina.
"""
import base64
import io
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image

FORMATOS_PERMITIDOS = {"JPEG": ".jpg", "PNG": ".png"}


class FotoInvalidaError(Exception):
    """La fotografía recibida no es una imagen JPEG o PNG válida."""


def carpeta_base() -> Path:
    return Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()


def absoluta(ruta_relativa: str) -> Path:
    return carpeta_base() / ruta_relativa


def _nueva_ruta(subcarpeta: str, extension: str) -> str:
    (carpeta_base() / subcarpeta).mkdir(parents=True, exist_ok=True)
    return f"{subcarpeta}/{uuid4().hex}{extension}"  # el nombre nunca viene del usuario


def guardar_foto(foto_base64: str) -> str:
    """Valida que sea una imagen real JPEG/PNG y la guarda. Devuelve la ruta relativa."""
    try:
        contenido = base64.b64decode(foto_base64, validate=True)
        with Image.open(io.BytesIO(contenido)) as imagen:
            formato = imagen.format
            imagen.verify()
    except Exception as exc:
        raise FotoInvalidaError("La fotografía no es una imagen válida") from exc

    extension = FORMATOS_PERMITIDOS.get(formato)
    if extension is None:
        raise FotoInvalidaError("La fotografía debe ser JPEG o PNG")

    ruta = _nueva_ruta("fotos", extension)
    absoluta(ruta).write_bytes(contenido)
    return ruta


def ruta_nueva_credencial() -> str:
    return _nueva_ruta("credenciales", ".pdf")


def borrar(rutas: list[str]) -> None:
    for ruta in rutas:
        absoluta(ruta).unlink(missing_ok=True)