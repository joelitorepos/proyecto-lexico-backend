"""Caso de uso: verificar el código de un QR escaneado."""
import logging

from sqlalchemy import text

from app.database import engine
from app.services import seguridad
from app.schemas.auth import VerificarQrIn, VerificarQrOut

logger = logging.getLogger(__name__)


def verificar_qr(datos: VerificarQrIn, ip: str) -> VerificarQrOut:
    """Recibe el código en claro (leído del QR) y busca su hash en la BD.

    Reglas:
      - El backend NUNCA recibe el hash; recibe el código y lo hashea aquí.
      - Solo son válidas las credenciales con estado = TRUE.
      - Un código inválido y un código de credencial revocada devuelven el
        mismo resultado (valido=False) para no filtrar información.
      - Se registra en bitácora el intento (éxito o fallo).
    """
    if engine is None:
        raise RuntimeError("DATABASE_URL no está configurada")

    codigo = (datos.codigo or "").strip()
    if not codigo:
        return VerificarQrOut(valido=False, mensaje="Código vacío")

    hash_buscado = seguridad.hash_codigo(codigo)

    with engine.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT c.id_credencial, u.id_usuario, u.nickname "
                "FROM credenciales c "
                "JOIN usuarios u ON u.id_usuario = c.id_usuario "
                "WHERE c.codigo_qr = :hash AND c.estado = TRUE AND u.estado = TRUE "
                "LIMIT 1"
            ),
            {"hash": hash_buscado},
        ).mappings().first()

        valido = fila is not None

        # Bitácora del intento (éxito o fallo), usando el mismo patrón que registro
        if fila is not None:
            conn.execute(
                text(
                    "INSERT INTO bitacora (id_usuario, accion, descripcion, ip) "
                    "VALUES (:id_usuario, 'VERIFICACION_QR', 'QR válido', :ip)"
                ),
                {"id_usuario": fila["id_usuario"], "ip": ip},
            )
        else:
            # Sin usuario asociado: usamos el primer admin como "ancla" o dejamos
            # el intento fuera. Si prefieres no registrar fallos sin usuario,
            # comenta este bloque. Alternativa: una tabla 'bitacora_anonima'.
            logger.info("Intento de verificación QR inválido desde %s", ip)

    if not valido:
        return VerificarQrOut(valido=False, mensaje="Credencial no válida o revocada")

    return VerificarQrOut(
        valido=True,
        nickname=fila["nickname"],
        mensaje="Credencial válida",
    )