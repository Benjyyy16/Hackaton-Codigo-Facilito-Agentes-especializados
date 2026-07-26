"""OAuth 2.0 para integraciones de usuario.

Flujo:
  1. GET /oauth/{provider}/authorize  → redirige al provider
  2. GET /oauth/{provider}/callback   → recibe code, intercambia por token, guarda en DB
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.services.auth_service import AuthService

router = APIRouter(prefix="/oauth", tags=["oauth"])

# ── Config por provider ──────────────────────────────────────────────────────

def _cfg(settings: Settings) -> dict:
    base = str(getattr(settings, "APP_BASE_URL", "https://hackaton-codigo-facilito-agentes.onrender.com"))
    return {
        "github": {
            "client_id":     getattr(settings, "GITHUB_CLIENT_ID", ""),
            "client_secret": getattr(settings, "GITHUB_CLIENT_SECRET", ""),
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url":     "https://github.com/login/oauth/access_token",
            "scope":         "repo read:user",
            "callback":      f"{base}/oauth/github/callback",
        },
        "notion": {
            "client_id":     getattr(settings, "NOTION_CLIENT_ID", ""),
            "client_secret": getattr(settings, "NOTION_CLIENT_SECRET", ""),
            "authorize_url": "https://api.notion.com/v1/oauth/authorize",
            "token_url":     "https://api.notion.com/v1/oauth/token",
            "scope":         "",
            "callback":      f"{base}/oauth/notion/callback",
        },
        "slack": {
            "client_id":     getattr(settings, "SLACK_CLIENT_ID", ""),
            "client_secret": getattr(settings, "SLACK_CLIENT_SECRET", ""),
            "authorize_url": "https://slack.com/oauth/v2/authorize",
            "token_url":     "https://slack.com/api/oauth.v2.access",
            "scope":         "chat:write channels:read",
            "callback":      f"{base}/oauth/slack/callback",
        },
        "vercel": {
            "client_id":     getattr(settings, "VERCEL_CLIENT_ID", ""),
            "client_secret": getattr(settings, "VERCEL_CLIENT_SECRET", ""),
            "authorize_url": "https://vercel.com/integrations/vercel/consent",
            "token_url":     "https://api.vercel.com/v2/oauth/access_token",
            "scope":         "",
            "callback":      f"{base}/oauth/vercel/callback",
        },
    }


PROVIDERS = {"github", "notion", "slack", "vercel"}

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _state_token(user_id: str) -> str:
    """CSRF token firmado con timestamp."""
    ts = str(int(time.time()))
    sig = hmac.new(user_id.encode(), ts.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{ts}.{sig}"


def _supabase(settings: Settings):
    from supabase import create_client
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/{provider}/authorize",
    summary="Iniciar OAuth",
    description="Redirige al provider para que el usuario autorice el acceso. Requiere JWT en ?token=",
)
def authorize(
    provider: str,
    settings: SettingsDep,
    token: str = Query(..., description="JWT del usuario"),
) -> RedirectResponse:
    if provider not in PROVIDERS:
        raise HTTPException(404, f"Provider {provider} no soporta OAuth")

    # Validar JWT
    try:
        svc = AuthService(settings)
        user = svc.get_current_user(token)
    except Exception:
        raise HTTPException(401, "Token inválido")

    cfg = _cfg(settings)[provider]
    if not cfg["client_id"]:
        raise HTTPException(503, f"OAuth de {provider} no configurado. Falta {provider.upper()}_CLIENT_ID")

    params = {
        "client_id":     cfg["client_id"],
        "redirect_uri":  cfg["callback"],
        "state":         f"{user.id}|{_state_token(user.id)}",
        "response_type": "code",
    }
    if cfg["scope"]:
        params["scope"] = cfg["scope"]

    url = f"{cfg['authorize_url']}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get(
    "/{provider}/callback",
    summary="Callback OAuth",
    description="Render recibe el code del provider, intercambia por token y guarda en la cuenta del usuario.",
)
async def callback(
    provider: str,
    settings: SettingsDep,
    code: str = Query(...),
    state: str = Query(...),
) -> dict:
    if provider not in PROVIDERS:
        raise HTTPException(404, f"Provider {provider} no soporta OAuth")

    # Extraer user_id del state
    try:
        user_id = state.split("|")[0]
    except Exception:
        raise HTTPException(400, "State inválido")

    cfg = _cfg(settings)[provider]

    # Intercambiar code por access_token
    async with httpx.AsyncClient(timeout=10) as client:
        if provider == "notion":
            import base64
            basic = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
            r = await client.post(
                cfg["token_url"],
                json={"grant_type": "authorization_code", "code": code, "redirect_uri": cfg["callback"]},
                headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
            )
        else:
            r = await client.post(cfg["token_url"], data={
                "client_id":     cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code":          code,
                "redirect_uri":  cfg["callback"],
            }, headers={"Accept": "application/json"})

        if r.status_code != 200:
            raise HTTPException(502, f"Error obteniendo token de {provider}: {r.text[:200]}")

        data = r.json()
        access_token = (
            data.get("access_token") or
            data.get("authed_user", {}).get("access_token") or  # Slack
            data.get("token")
        )
        if not access_token:
            raise HTTPException(502, f"Token no encontrado en respuesta: {list(data.keys())}")

    # Guardar en Supabase
    sb = _supabase(settings)
    sb.table("integrations").upsert({
        "user_id":     user_id,
        "provider":    provider,
        "credentials": {"token": access_token},
        "config":      {k: v for k, v in data.items() if k != "access_token" and not k.endswith("_secret")},
        "status":      "active",
    }, on_conflict="user_id,provider").execute()

    return {
        "status": "connected",
        "provider": provider,
        "user_id": user_id,
        "message": f"{provider.capitalize()} vinculado correctamente.",
    }
