"""OAuth Login — Iniciar sesión con GitHub o Google.

Flujo:
  1. GET /auth/oauth/{provider}/login       → redirige al provider OAuth
  2. GET /auth/oauth/{provider}/callback     → recibe code, obtiene perfil, crea JWT
"""
from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.schemas.auth import TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth/oauth", tags=["oauth-login"])

SUPPORTED_PROVIDERS = {"github", "google"}


def _get_auth_service(settings: Annotated[Settings, Depends(get_settings_dep)]) -> AuthService:
    return AuthService(settings)


# ── Provider configs ─────────────────────────────────────────────────────────


def _github_cfg(settings: Settings) -> dict:
    return {
        "client_id": settings.GITHUB_CLIENT_ID or "",
        "client_secret": (
            settings.GITHUB_CLIENT_SECRET.get_secret_value()
            if settings.GITHUB_CLIENT_SECRET
            else ""
        ),
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scope": "read:user user:email",
        "callback": f"{settings.APP_BASE_URL}/auth/oauth/github/callback",
    }


def _google_cfg(settings: Settings) -> dict:
    return {
        "client_id": settings.GOOGLE_CLIENT_ID or "",
        "client_secret": (
            settings.GOOGLE_CLIENT_SECRET.get_secret_value()
            if settings.GOOGLE_CLIENT_SECRET
            else ""
        ),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
        "callback": f"{settings.APP_BASE_URL}/auth/oauth/google/callback",
    }


def _get_cfg(provider: str, settings: Settings) -> dict:
    if provider == "github":
        return _github_cfg(settings)
    elif provider == "google":
        return _google_cfg(settings)
    raise HTTPException(404, f"Provider '{provider}' no soportado para login")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/{provider}/login",
    summary="Iniciar login con OAuth",
    description="Redirige al usuario al provider OAuth para autenticación.",
)
def oauth_login(
    provider: str,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(404, f"Provider '{provider}' no soportado. Usa: github, google")

    cfg = _get_cfg(provider, settings)

    if not cfg["client_id"]:
        raise HTTPException(
            503, f"OAuth de {provider} no configurado. Falta {provider.upper()}_CLIENT_ID"
        )

    params: dict[str, str] = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["callback"],
        "scope": cfg["scope"],
        "state": "login",
    }

    if provider == "google":
        params["response_type"] = "code"
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    url = f"{cfg['authorize_url']}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get(
    "/{provider}/callback",
    summary="Callback de OAuth login",
    description="Recibe el code del provider, obtiene perfil del usuario y devuelve JWT.",
)
async def oauth_callback(
    provider: str,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    code: str = Query(...),
    state: str = Query(default="login"),
) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(404, f"Provider '{provider}' no soportado")

    cfg = _get_cfg(provider, settings)

    # 1. Intercambiar code por access_token
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            cfg["token_url"],
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "redirect_uri": cfg["callback"],
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )

        if token_resp.status_code != 200:
            raise HTTPException(502, f"Error obteniendo token de {provider}: {token_resp.text[:200]}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(502, f"Token no encontrado en respuesta de {provider}")

        # 2. Obtener perfil del usuario
        email, name, user_id = await _fetch_user_profile(client, provider, access_token, cfg)

    # 3. Crear JWT con los datos del usuario
    auth_service = AuthService(settings)
    tokens = auth_service.create_tokens(user_id=user_id, email=email, name=name)

    # 4. Redirigir al frontend con tokens en query params
    frontend_url = settings.FRONTEND_URL
    params = urlencode({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token or "",
        "expires_in": str(tokens.expires_in),
    })
    return RedirectResponse(f"{frontend_url}/auth/callback?{params}")


async def _fetch_user_profile(
    client: httpx.AsyncClient,
    provider: str,
    access_token: str,
    cfg: dict,
) -> tuple[str, str, str]:
    """Obtiene email, nombre y user_id del provider."""
    import hashlib

    headers = {"Authorization": f"Bearer {access_token}"}

    if provider == "github":
        headers["Authorization"] = f"token {access_token}"
        # Perfil
        user_resp = await client.get(cfg["user_url"], headers=headers)
        if user_resp.status_code != 200:
            raise HTTPException(502, "No se pudo obtener perfil de GitHub")
        user_data = user_resp.json()

        name = user_data.get("name") or user_data.get("login", "GitHub User")
        email = user_data.get("email")

        # Si email es null, buscar en /user/emails
        if not email:
            emails_resp = await client.get(cfg["emails_url"], headers=headers)
            if emails_resp.status_code == 200:
                emails = emails_resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                email = primary["email"] if primary else emails[0]["email"] if emails else None

        if not email:
            email = f"{user_data.get('login', 'user')}@users.noreply.github.com"

        user_id = f"gh_{user_data.get('id', hashlib.sha256(email.encode()).hexdigest()[:12])}"

    elif provider == "google":
        user_resp = await client.get(cfg["user_url"], headers=headers)
        if user_resp.status_code != 200:
            raise HTTPException(502, "No se pudo obtener perfil de Google")
        user_data = user_resp.json()

        email = user_data.get("email", "")
        name = user_data.get("name", email.split("@")[0])
        user_id = f"go_{user_data.get('id', hashlib.sha256(email.encode()).hexdigest()[:12])}"

    else:
        raise HTTPException(404, f"Provider '{provider}' no soportado")

    return email, name, user_id
