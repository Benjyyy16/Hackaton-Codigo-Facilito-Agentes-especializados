"""Administración del esquema: comprobar qué falta y aplicarlo.

Existe porque el esquema de ``db/schema.sql`` hay que aplicarlo a mano en el editor SQL de
Supabase, y hasta que se aplica todos los endpoints del dominio devuelven 503 sin decir
por qué. Eso convierte un despliegue incompleto en un misterio.

Dos operaciones, con niveles de riesgo muy distintos:

* ``GET /admin/schema/status`` — solo lee. Sondea cada tabla esperada con la API REST y
  dice cuáles faltan. Funciona siempre, sin credenciales extra.

* ``POST /admin/schema/apply`` — ejecuta DDL. Requiere ``SUPABASE_DB_URL`` (la cadena de
  conexión de Postgres, que NO es la clave de servicio) y un token de arranque. Aplica
  ``db/schema.sql``, que es idempotente y no contiene ninguna operación destructiva.

SEGURIDAD. Ejecutar DDL desde un endpoint HTTP es la operación más peligrosa de este
backend, así que lleva cuatro cierres:

1. Exige ``SCHEMA_BOOTSTRAP_TOKEN`` configurado. Sin él la ruta responde 404: no existe.
2. Compara el token con ``compare_secret``, en tiempo constante.
3. Solo ejecuta el fichero ``db/schema.sql`` del propio repositorio. No acepta SQL del
   cliente, ni una ruta de fichero, ni un nombre de script. Un endpoint que aceptara SQL
   arbitrario sería una puerta de ejecución remota con otro nombre.
4. Rechaza el script si contiene una sentencia destructiva. ``schema.sql`` no las tiene,
   pero la comprobación protege del caso en que alguien las añada más tarde: la validación
   no confía en que el fichero siga siendo el que era.

``db/rollback.sql`` no se puede ejecutar por esta vía en ningún caso.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import compare_secret

logger = get_logger("api.schema")

router = APIRouter(prefix="/admin/schema", tags=["admin"])

SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

#: Tablas que el dominio necesita. El orden es el de ``db/schema.sql``.
EXPECTED_TABLES: Final[tuple[str, ...]] = (
    "projects",
    "commitments",
    "provider_connections",
    "source_events",
    "agent_runs",
    "findings",
    "evidence",
    "risk_cases",
    "alerts",
    "decisions",
    "timeline_events",
    "documents",
    "integrations",
)

#: Sentencias que jamás deben salir de este endpoint. Se comprueban sobre el fichero
#: antes de ejecutarlo, no sobre una entrada del cliente: el cliente no envía SQL.
FORBIDDEN_STATEMENTS: Final[tuple[str, ...]] = (
    r"\bdrop\s+table\b",
    r"\bdrop\s+schema\b",
    r"\bdrop\s+database\b",
    r"\btruncate\b",
    r"\bdelete\s+from\b",
)


class TableStatus(BaseModel):
    name: str
    exists: bool


class SchemaStatus(BaseModel):
    """Estado del esquema en la base de datos configurada."""

    ready: bool = Field(description="Todas las tablas esperadas existen.")
    tables: list[TableStatus]
    missing: list[str]
    #: Si es ``False``, ``POST /admin/schema/apply`` no puede funcionar y hay que aplicar
    #: ``db/schema.sql`` a mano desde el editor SQL de Supabase.
    can_apply_automatically: bool
    hint: str


class ApplyReport(BaseModel):
    applied: bool
    statements_executed: int = 0
    tables_created: list[str] = Field(default_factory=list)
    message: str


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def _require_bootstrap_token(
    settings: Settings, provided: str | None
) -> None:
    """Exige el token de arranque.

    Sin token configurado la ruta responde 404 y no 403: revelar que existe un endpoint
    capaz de ejecutar DDL, aunque esté cerrado, es información que no hace falta dar.
    """
    expected = getattr(settings, "SCHEMA_BOOTSTRAP_TOKEN", None)
    secret = expected.get_secret_value() if hasattr(expected, "get_secret_value") else expected

    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No encontrado.")

    if not provided or not compare_secret(provided, secret):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Token de arranque inválido."
        )


def _assert_script_is_safe(sql: str) -> None:
    """Rechaza el script si contiene una sentencia destructiva."""
    lowered = sql.lower()
    for pattern in FORBIDDEN_STATEMENTS:
        if re.search(pattern, lowered):
            logger.error("El script de esquema contiene una sentencia destructiva")
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=(
                    "El script contiene una sentencia destructiva y no se ejecutará. "
                    "Revisar db/schema.sql."
                ),
            )


async def _probe_tables(settings: Settings) -> list[TableStatus]:
    """Sondea la existencia de cada tabla con la API REST.

    Se usa la API REST y no una consulta al catálogo porque es lo único disponible con la
    clave de servicio. Un 404 de PostgREST sobre una tabla significa que no existe en el
    esquema expuesto, que es exactamente lo que interesa saber.
    """
    import httpx

    base = settings.SUPABASE_URL.rstrip("/")
    key = settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    results: list[TableStatus] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for table in EXPECTED_TABLES:
            try:
                response = await client.get(
                    f"{base}/rest/v1/{table}", params={"limit": 1}, headers=headers
                )
                results.append(TableStatus(name=table, exists=response.status_code == 200))
            except Exception as error:  # noqa: BLE001 - informar, no fallar
                logger.warning(
                    "No se pudo sondear la tabla %s: %s", table, type(error).__name__
                )
                results.append(TableStatus(name=table, exists=False))

    return results


def _db_url(settings: Settings) -> str | None:
    raw = getattr(settings, "SUPABASE_DB_URL", None)
    if raw is None:
        return None
    return raw.get_secret_value() if hasattr(raw, "get_secret_value") else str(raw)


@router.get(
    "/status",
    response_model=SchemaStatus,
    summary="Comprobar si el esquema está aplicado",
    description=(
        "Sondea cada tabla del dominio y devuelve las que faltan. Solo lee: no modifica "
        "nada y no requiere token.\n\n"
        "Es la respuesta a *por qué los endpoints del dominio devuelven 503*: si `ready` es "
        "`false`, el esquema de `db/schema.sql` no está aplicado."
    ),
)
async def schema_status(settings: SettingsDep) -> SchemaStatus:
    tables = await _probe_tables(settings)
    missing = [t.name for t in tables if not t.exists]
    can_apply = _db_url(settings) is not None

    if not missing:
        hint = "El esquema está completo. Los endpoints del dominio pueden operar."
    elif can_apply:
        hint = (
            f"Faltan {len(missing)} tabla(s). Se pueden crear con "
            "POST /admin/schema/apply usando el token de arranque."
        )
    else:
        hint = (
            f"Faltan {len(missing)} tabla(s). Sin SUPABASE_DB_URL configurado hay que "
            "aplicar db/schema.sql a mano desde el editor SQL de Supabase."
        )

    return SchemaStatus(
        ready=not missing,
        tables=tables,
        missing=missing,
        can_apply_automatically=can_apply,
        hint=hint,
    )


@router.post(
    "/apply",
    response_model=ApplyReport,
    summary="Aplicar db/schema.sql",
    description=(
        "Ejecuta el script de esquema del repositorio contra la base de datos.\n\n"
        "**Requiere** `SCHEMA_BOOTSTRAP_TOKEN` configurado y enviado en la cabecera "
        "`X-Bootstrap-Token`, y `SUPABASE_DB_URL` con la cadena de conexión de Postgres "
        "(que no es la clave de servicio).\n\n"
        "Solo ejecuta `db/schema.sql`, que es idempotente y no contiene operaciones "
        "destructivas. No acepta SQL del cliente. `db/rollback.sql` no se puede ejecutar "
        "por esta vía.\n\n"
        "Códigos: `200` aplicado, `401` token inválido, `404` endpoint deshabilitado, "
        "`409` el script contiene algo destructivo, `503` sin cadena de conexión."
    ),
)
async def apply_schema(
    settings: SettingsDep,
    x_bootstrap_token: Annotated[str | None, Header()] = None,
) -> ApplyReport:
    _require_bootstrap_token(settings, x_bootstrap_token)

    dsn = _db_url(settings)
    if not dsn:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SUPABASE_DB_URL no configurado. Aplicar db/schema.sql a mano desde el "
                "editor SQL de Supabase."
            ),
        )

    if not SCHEMA_PATH.exists():  # pragma: no cover - el fichero va en el repositorio
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="db/schema.sql no encontrado."
        )

    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    _assert_script_is_safe(sql)

    try:
        import asyncpg
    except ImportError as error:  # pragma: no cover - dependencia declarada
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="asyncpg no instalado: no se puede ejecutar DDL.",
        ) from error

    before = {t.name for t in await _probe_tables(settings) if t.exists}

    connection = None
    try:
        connection = await asyncpg.connect(dsn, timeout=20)
        # El script se ejecuta completo y no sentencia a sentencia: contiene bloques
        # ``do $$ ... $$`` que un troceado naive por ";" partiría por la mitad.
        await connection.execute(sql)
    except Exception as error:  # noqa: BLE001 - frontera con la base de datos
        logger.error("Fallo al aplicar el esquema", exc_info=error)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo aplicar el esquema: {type(error).__name__}",
        ) from error
    finally:
        if connection is not None:
            await connection.close()

    after = {t.name for t in await _probe_tables(settings) if t.exists}
    created = sorted(after - before)

    logger.info("Esquema aplicado; tablas nuevas: %s", ", ".join(created) or "ninguna")

    return ApplyReport(
        applied=True,
        statements_executed=1,
        tables_created=created,
        message=(
            f"Esquema aplicado. {len(created)} tabla(s) creada(s), "
            f"{len(after)} de {len(EXPECTED_TABLES)} presentes."
        ),
    )
