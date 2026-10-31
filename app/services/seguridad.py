"""Funciones de seguridad: hash de contraseñas y códigos de credencial."""
import hashlib
import secrets

import bcrypt

COSTO_BCRYPT = 12


def hash_password(password: str) -> str:
    """Devuelve el hash BCrypt (60 caracteres). La contraseña original nunca se guarda."""
    sal = bcrypt.gensalt(rounds=COSTO_BCRYPT)
    return bcrypt.hashpw(password.encode("utf-8"), sal).decode("ascii")


def verificar_password(password: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("ascii"))


def hash_codigo(codigo: str) -> str:
    """SHA-256 del código del QR; es lo único que se guarda en la base de datos."""
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def generar_codigo_qr() -> tuple[str, str]:
    """Devuelve (código para dibujar en el QR, hash para guardar en la BD)."""
    codigo = secrets.token_urlsafe(32)
    return codigo, hash_codigo(codigo)