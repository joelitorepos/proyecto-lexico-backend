"""Endpoints de autenticación y registro."""
from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.auth import RegistroIn, RegistroOut
from app.services.archivos import FotoInvalidaError
from app.services.registro import UsuarioDuplicadoError, registrar_usuario

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/register", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
def registrar(datos: RegistroIn, request: Request):
    ip = request.client.host if request.client else "desconocida"
    try:
        return registrar_usuario(datos, ip)
    except UsuarioDuplicadoError:
        raise HTTPException(status_code=409, detail="El correo o el nickname ya están registrados")
    except FotoInvalidaError as error:
        raise HTTPException(status_code=422, detail=str(error))

from app.schemas.auth import LoginIn, LoginOut
from app.services.sesion import CredencialesInvalidasError, iniciar_sesion


@router.post("/login", response_model=LoginOut)
def login(datos: LoginIn, request: Request):
    ip = request.client.host if request.client else "desconocida"
    try:
        return iniciar_sesion(datos, ip)
    except CredencialesInvalidasError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

from app.schemas.auth import VerificarQrIn, VerificarQrOut
from app.services.credencial_qr import verificar_qr


@router.post("/verificar-qr", response_model=VerificarQrOut)
def verificar_qr_endpoint(datos: VerificarQrIn, request: Request):
    ip = request.client.host if request.client else "desconocida"
    return verificar_qr(datos, ip)
