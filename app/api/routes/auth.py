"""Rutas de autenticación."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.core.exceptions import DomainError
from app.schemas.auth import CurrentUser, LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService, AuthenticationError

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


def get_auth_service(settings: Annotated[Settings, Depends(get_settings_dep)]) -> AuthService:
    """Crea el servicio de autenticación."""
    return AuthService(settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description=(
        "Crea una nueva cuenta de usuario y devuelve tokens JWT.\n\n"
        "Campos requeridos:\n"
        "- **email**: correo válido del usuario\n"
        "- **name**: nombre del usuario\n"
        "- **password**: contraseña de al menos 8 caracteres"
    ),
    responses={
        201: {"description": "Usuario registrado exitosamente"},
        400: {"description": "Datos inválidos o email ya existe"},
        422: {"description": "Validación de datos fallida"},
    },
)
async def register(
    request: RegisterRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Endpoint para registrar un nuevo usuario.

    **Payload de ejemplo:**
    ```json
    {
      "email": "user@example.com",
      "name": "John Doe",
      "password": "SecurePassword123"
    }
    ```

    **Respuesta:**
    ```json
    {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "token_type": "bearer",
      "expires_in": 3600
    }
    ```

    El usuario queda registrado y puede usar los tokens inmediatamente.
    """
    try:
        tokens = auth_service.register(request.email, request.name, request.password)
        return tokens
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login con email y contraseña",
    description=(
        "Autentica un usuario y devuelve tokens JWT.\n\n"
        "Para este demo, acepta cualquier email válido y contraseña no vacía."
    ),
    responses={
        401: {"description": "Email o contraseña inválidos"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Endpoint de login.

    **Payload de ejemplo:**
    ```json
    {
      "email": "user@example.com",
      "password": "MyPassword123"
    }
    ```

    **Respuesta:**
    ```json
    {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "token_type": "bearer",
      "expires_in": 3600
    }
    ```

    Usa el `access_token` en la cabecera `Authorization: Bearer <token>` para
    acceder a rutas protegidas.
    """
    try:
        tokens = auth_service.login(request.email, request.password)
        return tokens
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/me",
    response_model=CurrentUser,
    status_code=status.HTTP_200_OK,
    summary="Obtener usuario actual",
    description="Devuelve los datos del usuario autenticado a partir del token JWT.",
    responses={
        401: {"description": "Token ausente o inválido"},
    },
)
async def get_me(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: AuthServiceDep,
) -> CurrentUser:
    """Endpoint para obtener el usuario autenticado.

    **Cabecera requerida:**
    ```
    Authorization: Bearer <access_token>
    ```

    **Respuesta:**
    ```json
    {
      "id": "user_id_hash",
      "email": "user@example.com",
      "name": "John Doe",
      "roles": []
    }
    ```
    """
    try:
        user = auth_service.get_current_user(credentials.credentials)
        return user
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Invalida el token actual (para este demo es un no-op).",
)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> None:
    """Endpoint de logout.

    En esta implementación es un no-op porque los tokens JWT son stateless.
    En producción, podrías mantener un blacklist en Redis.
    """
    pass
