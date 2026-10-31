"""Modelos de entrada y salida de los endpoints de autenticación."""
import base64
import binascii
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator
from pydantic.alias_generators import to_camel

MAX_FOTO_BYTES = 2 * 1024 * 1024
MAX_FOTO_BASE64 = (MAX_FOTO_BYTES * 4) // 3 + 8
EDAD_MAXIMA_ANIOS = 120


class RegistroIn(BaseModel):
    """Datos del registro. Los nombres JSON van en camelCase, como en Postman."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    email: EmailStr
    telefono: str
    fecha_nacimiento: date
    nickname: str
    password: str
    foto_original: str | None = None
    foto_modificada: str | None = None
    metodo_notificacion: Literal["EMAIL", "WHATSAPP", "AMBOS"] | None = None
    recaptcha_token: str | None = None  # se acepta, pero aún no se verifica

    @field_validator("email", "telefono", "nickname", mode="before")
    @classmethod
    def quitar_espacios(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        if len(valor) > 150:
            raise ValueError("El correo no puede superar 150 caracteres")
        return valor.lower()

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str) -> str:
        limpio = re.sub(r"[\s\-().]", "", valor)
        if not re.fullmatch(r"\+?\d{8,15}", limpio):
            raise ValueError("El teléfono debe tener entre 8 y 15 dígitos")
        return limpio

    @field_validator("nickname")
    @classmethod
    def validar_nickname(cls, valor: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", valor):
            raise ValueError(
                "El nickname debe tener de 3 a 30 caracteres: letras, números, punto, guion y guion bajo"
            )
        return valor

    @field_validator("password")
    @classmethod
    def validar_password(cls, valor: str) -> str:
        if len(valor) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if len(valor.encode("utf-8")) > 72:  # límite de bcrypt
            raise ValueError("La contraseña no puede superar 72 bytes")
        if not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
            raise ValueError("La contraseña debe incluir letras y números")
        return valor

    @field_validator("fecha_nacimiento")
    @classmethod
    def validar_fecha(cls, valor: date) -> date:
        hoy = date.today()
        if valor >= hoy:
            raise ValueError("La fecha de nacimiento debe ser anterior a hoy")
        if hoy.year - valor.year > EDAD_MAXIMA_ANIOS:
            raise ValueError("La fecha de nacimiento no es válida")
        return valor

    @field_validator("foto_original", "foto_modificada")
    @classmethod
    def validar_foto(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        if valor.startswith("data:"):  # acepta "data:image/png;base64,...."
            valor = valor.partition(",")[2]
        if len(valor) > MAX_FOTO_BASE64:
            raise ValueError("La fotografía supera el tamaño máximo de 2 MB")
        try:
            base64.b64decode(valor, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("La fotografía no es base64 válido")
        return valor

    @model_validator(mode="after")
    def validar_fotos(self):
        if self.foto_modificada and not self.foto_original:
            raise ValueError("Para enviar fotoModificada también se requiere fotoOriginal")
        return self


class RegistroOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id_usuario: int
    nickname: str
    notificaciones_programadas: list[str]
    mensaje: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id_usuario: int
    nickname: str
    mensaje: str


class VerificarQrIn(BaseModel):
    codigo: str


class VerificarQrOut(BaseModel):
    valido: bool
    nickname: str | None = None
    mensaje: str