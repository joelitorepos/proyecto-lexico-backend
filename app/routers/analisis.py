
"""Endpoint protegido para registrar análisis léxicos."""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text

from app.database import engine
from app.dependencias import obtener_usuario_actual

router = APIRouter(
    prefix="/api/analisis",
    tags=["Análisis léxico"],
)

MAX_ARCHIVO_BYTES = 5 * 1024 * 1024


@router.post("")
async def analizar_archivo(
    archivo: UploadFile = File(...),
    idioma: str = Form("es"),
    id_usuario: int = Depends(obtener_usuario_actual),
):
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible",
        )

    if idioma not in ("es", "en"):
        raise HTTPException(
            status_code=422,
            detail="Idioma no válido",
        )

    if not archivo.filename or Path(archivo.filename).suffix.lower() != ".txt":
        raise HTTPException(
            status_code=422,
            detail="Solo se permiten archivos TXT",
        )

    contenido = await archivo.read(MAX_ARCHIVO_BYTES + 1)

    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="El archivo supera los 5 MB",
        )

    try:
        texto_archivo = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="El archivo debe estar en UTF-8",
        )

    palabras = re.findall(
        r"[^\W\d_]+(?:['’][^\W\d_]+)*",
        texto_archivo,
        flags=re.UNICODE,
    )

    cantidad_palabras = len(palabras)

    # Por ahora no almacenamos el archivo físico.
    # La ruta indica que el contenido se procesó en memoria.
    ruta_archivo = "memoria://archivo-no-persistido"

    with engine.begin() as conn:
        resultado = conn.execute(
            text(
                """
                INSERT INTO analisis
                    (id_usuario, nombre_archivo, idioma,
                     ruta_archivo, cantidad_palabras, estado)
                VALUES
                    (:id_usuario, :nombre_archivo, :idioma,
                     :ruta_archivo, :cantidad_palabras, :estado)
                """
            ),
            {
                "id_usuario": id_usuario,
                "nombre_archivo": Path(archivo.filename).name,
                "idioma": idioma,
                "ruta_archivo": ruta_archivo,
                "cantidad_palabras": cantidad_palabras,
                "estado": "COMPLETADO",
            },
        )

        id_analisis = resultado.lastrowid

    return {
        "mensaje": "Análisis registrado correctamente",
        "idAnalisis": id_analisis,
        "idUsuario": id_usuario,
        "nombreArchivo": Path(archivo.filename).name,
        "idioma": idioma,
        "cantidadPalabras": cantidad_palabras,
        "estado": "COMPLETADO",
    }
