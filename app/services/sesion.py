
"""Caso de uso: iniciar sesión de un usuario."""
import logging

from sqlalchemy import text

from app.database import engine
from app.services import seguridad
from app.services.jwt_service import generar_token
from app.schemas.auth import LoginIn, LoginOut

logger = logging.getLogger(__name__)


class CredencialesInvalidasError(Exception):
    """Correo o contraseña incorrectos, o cuenta deshabilitada."""


def iniciar_sesion(datos: LoginIn, ip: str) -> LoginOut:
    """Verifica las credenciales, registra el acceso y genera un JWT."""

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

        # No revelar si el correo existe.
        if fila is None or not fila["estado"]:
            raise CredencialesInvalidasError()

        # Verificar contraseña con bcrypt.
        if not seguridad.verificar_password(
            datos.password,
            fila["password_hash"],
        ):
            raise CredencialesInvalidasError()

        # Registrar el inicio de sesión en la bitácora.
        conn.execute(
            text(
                "CALL sp_registrar_login("
                ":id_usuario, :ip, :descripcion)"
            ),
            {
                "id_usuario": fila["id_usuario"],
                "ip": ip,
                "descripcion": "Inicio de sesión exitoso",
            },
        )

    # Generar token JWT después de verificar las credenciales.
    token = generar_token(fila["id_usuario"])

    return LoginOut(
        id_usuario=fila["id_usuario"],
        nickname=fila["nickname"],
        mensaje="Inicio de sesión correcto",
        access_token=token,
        token_type="bearer",
    )
