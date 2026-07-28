"""Repositorios de GitHub del usuario autenticado.

El token del usuario lo deja el flujo de integraciones
(``GET /oauth/github/authorize`` → ``/oauth/github/callback``), que lo guarda en
la tabla ``integrations`` con scope ``repo``. Acá sólo se lee y se usa para
consultar la API de GitHub en nombre del usuario.

Se devuelve 404 cuando el usuario todavía no vinculó su cuenta: el frontend lo
interpreta como "GitHub sin conectar" y ofrece el botón de conexión en lugar de
mostrar un error.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUserDep, SettingsDep
from app.core.config import Settings

router = APIRouter(tags=["github"])

GITHUB_API = "https://api.github.com"

# GitHub pagina de a 100 como máximo. Se traen varias páginas para que un usuario
# con muchos repos no vea una lista truncada, pero con techo para no colgar la
# request si la cuenta tiene cientos.
_PER_PAGE = 100
_MAX_PAGES = 5


def _supabase(settings: Settings):
    from supabase import create_client

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
    )


def _stored_github_token(settings: Settings, user_id: str) -> str:
    """Token de GitHub guardado para el usuario, o 404 si no vinculó la cuenta."""
    sb = _supabase(settings)
    result = (
        sb.table("integrations")
        .select("credentials,status")
        .eq("user_id", user_id)
        .eq("provider", "github")
        .limit(1)
        .execute()
    )

    rows = result.data or []
    if not rows:
        raise HTTPException(404, "GitHub no está vinculado a esta cuenta.")

    row = rows[0]
    token = (row.get("credentials") or {}).get("token")
    if not token:
        raise HTTPException(404, "La vinculación con GitHub está incompleta. Volvé a conectarla.")

    return str(token)


def _map_repo(raw: dict[str, Any]) -> dict[str, Any]:
    """Proyecta el repo de GitHub al contrato que consume el frontend."""
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "full_name": raw.get("full_name"),
        "description": raw.get("description"),
        "html_url": raw.get("html_url"),
        "private": bool(raw.get("private")),
        "default_branch": raw.get("default_branch") or "main",
        "language": raw.get("language"),
        "stargazers_count": raw.get("stargazers_count") or 0,
        "updated_at": raw.get("updated_at"),
    }


@router.get(
    "/providers/github/repos",
    summary="Repositorios del usuario",
    description=(
        "Lista los repositorios de la cuenta de GitHub vinculada al usuario "
        "autenticado, ordenados por actividad reciente."
    ),
)
async def list_user_repos(
    user: CurrentUserDep,
    settings: SettingsDep,
    affiliation: str = Query(
        "owner,collaborator,organization_member",
        description="Filtro de afiliación que se pasa a la API de GitHub.",
    ),
) -> list[dict[str, Any]]:
    token = _stored_github_token(settings, user.id)

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    repos: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for page in range(1, _MAX_PAGES + 1):
            response = await client.get(
                f"{GITHUB_API}/user/repos",
                headers=headers,
                params={
                    "per_page": _PER_PAGE,
                    "page": page,
                    "sort": "updated",
                    "affiliation": affiliation,
                },
            )

            if response.status_code == 401:
                # El usuario revocó el acceso desde GitHub: se pide reconectar en
                # lugar de propagar un 401, que el frontend leería como sesión
                # vencida y cerraría la sesión de Datgent.
                raise HTTPException(404, "El acceso a GitHub expiró. Volvé a conectar la cuenta.")
            if response.status_code != 200:
                raise HTTPException(502, f"Error consultando GitHub: {response.text[:200]}")

            batch = response.json()
            if not isinstance(batch, list) or not batch:
                break

            repos.extend(_map_repo(item) for item in batch)

            if len(batch) < _PER_PAGE:
                break

    return repos
