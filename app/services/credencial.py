"""Generación de la credencial en PDF con código QR."""
import io
from pathlib import Path

import qrcode
from fpdf import FPDF
from PIL import Image, ImageOps

COLOR_PRINCIPAL = (79, 70, 229)  # índigo, el mismo acento que usa el frontend
ANCHO_MM, ALTO_MM = 54, 86       # tamaño aproximado de una tarjeta de identificación


def _png_en_memoria(imagen: Image.Image) -> io.BytesIO:
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _foto_cuadrada(ruta_foto: Path) -> io.BytesIO:
    with Image.open(ruta_foto) as foto:
        return _png_en_memoria(ImageOps.fit(foto.convert("RGB"), (300, 300)))


def _qr(codigo: str) -> io.BytesIO:
    buffer = io.BytesIO()
    qrcode.make(codigo).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def generar_pdf(ruta_pdf: Path, nickname: str, codigo: str, ruta_foto: Path | None) -> None:
    """Crea la credencial: foto (si hay), nickname y el QR con el código."""
    pdf = FPDF(unit="mm", format=(ANCHO_MM, ALTO_MM))
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_fill_color(*COLOR_PRINCIPAL)
    pdf.rect(0, 0, ANCHO_MM, 16, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(0, 4)
    pdf.cell(ANCHO_MM, 8, "LexiScan", align="C")

    if ruta_foto is not None:
        pdf.image(_foto_cuadrada(ruta_foto), x=15, y=19, w=24, h=24)

    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(0, 45)
    pdf.cell(ANCHO_MM, 6, nickname, align="C")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(0, 51)
    pdf.cell(ANCHO_MM, 4, "Credencial de inscripción", align="C")

    pdf.image(_qr(codigo), x=15, y=58, w=24, h=24)
    pdf.output(str(ruta_pdf))