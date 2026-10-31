"""Caso de uso: iniciar sesión de un usuario."""
import logging

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import engine
from app.services import seguridad
from app.schemas.auth import LoginIn, LoginOut

logger = logging.getLogger(__name__)

CODIGO_ERROR_NEGOCIO = 1644


class CredencialesInvalidasError(Exception):
    """Correo o contraseña incorrectos, o cuenta deshabilitada."""


def iniciar_sesion(datos: LoginIn, ip: str) -> LoginOut:
    """Valida credenciales con bcrypt y registra el login en bitácora.

    No distingue entre 'correo no existe' y 'contraseña incorrecta' en el
    mensaje de error, para no filtrar qué correos están registrados.
    """
    if engine is None:
        raise RuntimeError("DATABASE_URL no está configurada")

    with engine.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT id_usuario, nickname, password_hash, estado "
                "FROM usuarios WHERE correo = :correo"
            ),
            {"correo": datos.email},
        ).mappings().first()

        # Mismo error para "no existe" y "contraseña mal": no filtramos existencia
        if fila is None or not fila["estado"]:
            raise CredencialesInvalidasError()

        if not seguridad.verificar_password(datos.password, fila["password_hash"]):
            raise CredencialesInvalidasError()

        # Registrar login en bitácora con el SP que ya tienes
        conn.execute(
            text("CALL sp_registrar_login(:id_usuario, :ip, :descripcion)"),
            {
                "id_usuario": fila["id_usuario"],
                "ip": ip,
                "descripcion": "Inicio de sesión exitoso",
            },
        )

    return LoginOut(
        id_usuario=fila["id_usuario"],
        nickname=fila["nickname"],
        mensaje="Inicio de sesión correcto",
    )