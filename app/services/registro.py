"""Caso de uso: registrar un usuario y programar el envío de su credencial."""
import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import engine
from app.schemas.auth import RegistroIn, RegistroOut
from app.services import archivos, credencial, seguridad
from app.services.mensajeria import programar_mensaje

logger = logging.getLogger(__name__)

CODIGO_MYSQL_DUPLICADO = 1062
CANALES_POR_METODO = {
    "EMAIL": ["CORREO"],
    "WHATSAPP": ["WHATSAPP"],
    "AMBOS": ["CORREO", "WHATSAPP"],
}


class UsuarioDuplicadoError(Exception):
    """El correo o el nickname ya existen."""


def _es_duplicado(exc: IntegrityError) -> bool:
    args = getattr(exc.orig, "args", ())
    return bool(args) and args[0] == CODIGO_MYSQL_DUPLICADO


def _guardar_foto(foto: str | None, creados: list[str]) -> str | None:
    if foto is None:
        return None
    ruta = archivos.guardar_foto(foto)
    creados.append(ruta)
    return ruta


def registrar_usuario(datos: RegistroIn, ip: str) -> RegistroOut:
    """Guarda al usuario y todo lo relacionado en UNA transacción.

    Si algo falla, no queda nada a medias: se revierte la base de datos y se
    borran los archivos que ya se hubieran escrito.
    """
    if engine is None:
        raise RuntimeError("DATABASE_URL no está configurada")

    password_hash = seguridad.hash_password(datos.password)
    codigo, codigo_hash = seguridad.generar_codigo_qr()
    metodo = datos.metodo_notificacion
    creados: list[str] = []

    try:
        ruta_original = _guardar_foto(datos.foto_original, creados)
        ruta_modificada = _guardar_foto(datos.foto_modificada, creados)
        ruta_pdf = archivos.ruta_nueva_credencial()
        creados.append(ruta_pdf)

        with engine.begin() as conn:
            id_usuario = conn.execute(
                text(
                    "INSERT INTO usuarios (correo, telefono, fecha_nacimiento, nickname, password_hash) "
                    "VALUES (:correo, :telefono, :fecha_nacimiento, :nickname, :password_hash)"
                ),
                {
                    "correo": datos.email,
                    "telefono": datos.telefono,
                    "fecha_nacimiento": datos.fecha_nacimiento,
                    "nickname": datos.nickname,
                    "password_hash": password_hash,
                },
            ).lastrowid

            # Sin método elegido no se crea la fila: la tabla exige al menos un medio
            if metodo is not None:
                conn.execute(
                    text(
                        "INSERT INTO notificaciones (id_usuario, correo, whatsapp) "
                        "VALUES (:id_usuario, :correo, :whatsapp)"
                    ),
                    {
                        "id_usuario": id_usuario,
                        "correo": metodo in ("EMAIL", "AMBOS"),
                        "whatsapp": metodo in ("WHATSAPP", "AMBOS"),
                    },
                )

            if ruta_original is not None:
                conn.execute(
                    text(
                        "INSERT INTO fotografias (id_usuario, ruta_original, ruta_modificada) "
                        "VALUES (:id_usuario, :original, :modificada)"
                    ),
                    {"id_usuario": id_usuario, "original": ruta_original, "modificada": ruta_modificada},
                )

            ruta_foto_pdf = ruta_modificada or ruta_original
            credencial.generar_pdf(
                archivos.absoluta(ruta_pdf),
                datos.nickname,
                codigo,
                archivos.absoluta(ruta_foto_pdf) if ruta_foto_pdf else None,
            )
            conn.execute(
                text(
                    "INSERT INTO credenciales (id_usuario, codigo_qr, ruta_pdf) "
                    "VALUES (:id_usuario, :codigo_qr, :ruta_pdf)"
                ),
                {"id_usuario": id_usuario, "codigo_qr": codigo_hash, "ruta_pdf": ruta_pdf},
            )
            conn.execute(
                text(
                    "INSERT INTO bitacora (id_usuario, accion, descripcion, ip) "
                    "VALUES (:id_usuario, 'REGISTRO', 'Registro de usuario', :ip)"
                ),
                {"id_usuario": id_usuario, "ip": ip},
            )
    except IntegrityError as exc:
        archivos.borrar(creados)
        if _es_duplicado(exc):
            raise UsuarioDuplicadoError() from exc
        raise
    except Exception:
        archivos.borrar(creados)
        raise

    return RegistroOut(
        id_usuario=id_usuario,
        nickname=datos.nickname,
        notificaciones_programadas=_programar_credencial(id_usuario, datos.nickname, metodo, ruta_pdf),
        mensaje="Usuario registrado correctamente",
    )


def _programar_credencial(id_usuario: int, nickname: str, metodo: str | None, ruta_pdf: str) -> list[str]:
    """Deja la credencial en la cola de mensajes. Un fallo aquí no deshace el registro."""
    programadas: list[str] = []
    contenido = (
        f"Hola {nickname}, tu registro en LexiScan fue exitoso. "
        "Tu credencial de inscripción con código QR está lista."
    )
    for canal in CANALES_POR_METODO.get(metodo, []):
        try:
            programar_mensaje(id_usuario, canal, "CREDENCIAL", contenido, ruta_pdf)
            programadas.append(canal)
        except Exception:
            logger.exception("No se pudo programar la credencial del usuario %s por %s", id_usuario, canal)
    return programadas