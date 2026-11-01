
"""Generación y verificación de tokens JWT."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from jwt import InvalidTokenError

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
DURACION_MINUTOS = 60


def generar_token(id_usuario: int) -> str:
    """Genera un token válido durante 60 minutos."""
    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY no está configurada")

    ahora = datetime.now(timezone.utc)

    payload = {
        "sub": str(id_usuario),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=DURACION_MINUTOS),
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> int | None:
    """Verifica la firma y vencimiento del token."""
    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY no está configurada")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return int(payload["sub"])
    except (InvalidTokenError, ValueError, TypeError):
        return None
