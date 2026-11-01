
import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers import auth, analisis
from app.services.mensajeria import MensajeriaError, ciclo_envio, enviar_whatsapp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # El ciclo de envío solo arranca si hay base de datos configurada
    tarea = asyncio.create_task(ciclo_envio()) if engine is not None else None
    yield
    if tarea is not None:
        tarea.cancel()
        with suppress(asyncio.CancelledError):
            await tarea


app = FastAPI(title="Lexico Backend", lifespan=lifespan)

# Permitir comunicación con el frontend Vue durante desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router)
app.include_router(analisis.router)


@app.exception_handler(RequestValidationError)
async def errores_de_validacion(request: Request, exc: RequestValidationError):
    """Responde qué campo falló y por qué, SIN devolver el valor recibido.

    El formato por defecto de FastAPI incluye el dato enviado (por ejemplo, la
    contraseña), y eso no debe viajar de vuelta ni quedar en registros.
    """
    errores = [
        {
            "campo": ".".join(str(parte) for parte in error["loc"][1:]),
            "mensaje": error["msg"].removeprefix("Value error, "),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": "Datos no válidos", "errores": errores},
    )


@app.get("/health")
def health():
    if engine is None:
        return {"status": "ok", "database": "not configured"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {
            "status": "degraded",
            "database": f"error: {e.__class__.__name__}",
        }


class WhatsAppIn(BaseModel):
    id_usuario: int
    tipo: str = Field(max_length=30)
    contenido: str = Field(max_length=1000)


# TEMPORAL, solo para la demo: no tiene autenticación. En el sistema real,
# enviar_whatsapp se llama internamente desde registro, recuperación de
# contraseña y reporte; este endpoint debe quitarse o protegerse con JWT.
@app.post("/mensajes/whatsapp")
def solicitar_whatsapp(datos: WhatsAppIn):
    try:
        return enviar_whatsapp(
            datos.id_usuario,
            datos.tipo,
            datos.contenido,
        )
    except MensajeriaError as error:
        raise HTTPException(status_code=400, detail=str(error))
