from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.schemas.integrations import (
    ConnectIntegrationRequest,
    IntegrationProvider,
    IntegrationResponse,
)
from app.services.auth_service import AuthService, AuthenticationError

router = APIRouter(prefix="/integrations", tags=["integrations"])
security = HTTPBearer()


def _get_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> str:
    try:
        svc = AuthService(settings)
        user = svc.get_current_user(credentials.credentials)
        return user.id
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))


UserDep = Annotated[str, Depends(_get_user)]


def _supabase(settings: Annotated[Settings, Depends(get_settings_dep)]):
    """Cliente Supabase síncrono para operaciones simples."""
    from supabase import create_client
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
    )


SupabaseDep = Annotated[object, Depends(_supabase)]


@router.post(
    "/{provider}",
    response_model=IntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Vincular integración",
    description="Guarda las credenciales del provider para el usuario autenticado.",
)
def connect_integration(
    provider: IntegrationProvider,
    body: ConnectIntegrationRequest,
    user_id: UserDep,
    sb=Depends(_supabase),
) -> IntegrationResponse:
    # No guardar tokens en texto plano — en producción cifrar con KMS
    row = {
        "user_id": user_id,
        "provider": provider.value,
        "credentials": body.credentials,
        "config": body.config,
        "status": "active",
    }
    res = sb.table("integrations").upsert(row, on_conflict="user_id,provider").execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="No se pudo guardar la integración")
    d = res.data[0]
    return IntegrationResponse(
        id=d["id"], user_id=d["user_id"], provider=d["provider"],
        status=d["status"], config=d.get("config", {}),
        created_at=d["created_at"], updated_at=d["updated_at"],
    )


@router.get(
    "",
    response_model=list[IntegrationResponse],
    summary="Listar integraciones del usuario",
)
def list_integrations(user_id: UserDep, sb=Depends(_supabase)) -> list[IntegrationResponse]:
    res = sb.table("integrations").select("*").eq("user_id", user_id).eq("status", "active").execute()
    return [
        IntegrationResponse(
            id=d["id"], user_id=d["user_id"], provider=d["provider"],
            status=d["status"], config=d.get("config", {}),
            created_at=d["created_at"], updated_at=d["updated_at"],
        )
        for d in (res.data or [])
    ]


@router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desconectar integración",
)
def disconnect_integration(
    provider: IntegrationProvider,
    user_id: UserDep,
    sb=Depends(_supabase),
) -> None:
    sb.table("integrations").update({"status": "inactive"}).eq("user_id", user_id).eq("provider", provider.value).execute()


@router.get(
    "/{provider}/test",
    summary="Probar conexión de una integración",
)
def test_integration(
    provider: IntegrationProvider,
    user_id: UserDep,
    sb=Depends(_supabase),
) -> dict:
    """Verifica que las credenciales guardadas siguen siendo válidas."""
    res = sb.table("integrations").select("credentials,config").eq("user_id", user_id).eq("provider", provider.value).eq("status", "active").execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Integración no encontrada")

    creds = res.data[0].get("credentials", {})
    cfg = res.data[0].get("config", {})

    # Test rápido por provider
    import httpx
    tests = {
        "github": ("GET", "https://api.github.com/rate_limit", {"Authorization": f"Bearer {creds.get('token','')}"}),
        "notion": ("GET", "https://api.notion.com/v1/users/me", {"Authorization": f"Bearer {creds.get('token','')}", "Notion-Version": "2022-06-28"}),
        "vercel": ("GET", "https://api.vercel.com/v2/user", {"Authorization": f"Bearer {creds.get('token','')}"}),
        "slack":  ("POST", "https://slack.com/api/auth.test", {"Authorization": f"Bearer {creds.get('token','')}"}),
    }

    if provider.value not in tests:
        return {"provider": provider.value, "status": "ok", "message": "Sin test automático"}

    method, url, headers = tests[provider.value]
    try:
        fn = httpx.get if method == "GET" else httpx.post
        r = fn(url, headers=headers, timeout=5)
        ok = r.status_code == 200 and r.json().get("ok", True) is not False
        return {"provider": provider.value, "status": "ok" if ok else "error", "http_status": r.status_code}
    except Exception as e:
        return {"provider": provider.value, "status": "error", "detail": str(e)}
