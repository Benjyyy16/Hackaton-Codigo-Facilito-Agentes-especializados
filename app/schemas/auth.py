"""Esquemas de autenticación y autorización."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

# JWT token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 60
REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 7


class RegisterRequest(BaseModel):
    """Datos para registro de nuevo usuario."""

    email: str = Field(..., description="Email del usuario")
    name: str = Field(..., min_length=1, description="Nombre del usuario")
    password: str = Field(..., min_length=8, description="Contraseña del usuario (mínimo 8 caracteres)")


class LoginRequest(BaseModel):
    """Credenciales para login."""

    email: str = Field(..., description="Email del usuario")
    password: str = Field(..., description="Contraseña del usuario")


class TokenResponse(BaseModel):
    """Respuesta con tokens JWT."""

    access_token: str = Field(..., description="Token JWT para autenticación")
    refresh_token: str | None = Field(default=None, description="Token para refrescar el access token")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Segundos hasta que expire el access token")


class CurrentUser(BaseModel):
    """Usuario autenticado extraído del JWT."""

    id: str = Field(..., description="ID único del usuario")
    email: str = Field(..., description="Email del usuario")
    name: str | None = Field(default=None, description="Nombre del usuario")
    avatar: str | None = Field(default=None, description="URL de avatar del usuario")
    roles: list[str] = Field(default_factory=list, description="Roles asignados")


class HealthCheckResponse(BaseModel):
    """Respuesta de health check con auth info."""

    status: str = Field(..., description="Estado del servicio")
    authenticated: bool = Field(..., description="¿Hay un usuario autenticado?")
    user: CurrentUser | None = Field(default=None, description="Usuario autenticado, si existe")
