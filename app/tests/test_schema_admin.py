"""Tests del endpoint de administración del esquema.

Es el endpoint más peligroso del backend: ejecuta DDL. Los tests se centran en los
cierres, no en el camino feliz, porque un fallo en un cierre no se manifiesta como un
error visible sino como una puerta abierta.
"""

from __future__ import annotations

import pytest

from app.api.routes.schema_admin import (
    EXPECTED_TABLES,
    FORBIDDEN_STATEMENTS,
    SCHEMA_PATH,
    _assert_script_is_safe,
    _require_bootstrap_token,
)
from app.tests.conftest import build_settings

pytestmark = pytest.mark.anyio


class TestBootstrapToken:
    def test_without_token_configured_the_endpoint_does_not_exist(self) -> None:
        """404 y no 403: no se revela que existe un endpoint capaz de ejecutar DDL."""
        from fastapi import HTTPException

        settings = build_settings()

        with pytest.raises(HTTPException) as excinfo:
            _require_bootstrap_token(settings, "cualquier-cosa")

        assert excinfo.value.status_code == 404

    def test_wrong_token_is_rejected(self) -> None:
        from fastapi import HTTPException

        settings = build_settings(SCHEMA_BOOTSTRAP_TOKEN="el-correcto")

        with pytest.raises(HTTPException) as excinfo:
            _require_bootstrap_token(settings, "el-incorrecto")

        assert excinfo.value.status_code == 401

    def test_missing_token_header_is_rejected(self) -> None:
        from fastapi import HTTPException

        settings = build_settings(SCHEMA_BOOTSTRAP_TOKEN="el-correcto")

        with pytest.raises(HTTPException) as excinfo:
            _require_bootstrap_token(settings, None)

        assert excinfo.value.status_code == 401

    def test_correct_token_passes(self) -> None:
        settings = build_settings(SCHEMA_BOOTSTRAP_TOKEN="el-correcto")

        _require_bootstrap_token(settings, "el-correcto")  # no eleva

    def test_empty_token_does_not_open_the_door(self) -> None:
        """Un token configurado como cadena vacía equivale a no configurarlo."""
        from fastapi import HTTPException

        settings = build_settings(SCHEMA_BOOTSTRAP_TOKEN="")

        with pytest.raises(HTTPException) as excinfo:
            _require_bootstrap_token(settings, "")

        assert excinfo.value.status_code == 404


class TestDestructiveStatementGuard:
    @pytest.mark.parametrize(
        "sql",
        [
            "drop table public.commitments;",
            "DROP TABLE projects;",
            "drop   table  x;",
            "truncate public.alerts;",
            "TRUNCATE findings;",
            "delete from public.decisions;",
            "DELETE FROM evidence WHERE true;",
            "drop schema public cascade;",
            "drop database postgres;",
        ],
    )
    def test_destructive_scripts_are_refused(self, sql: str) -> None:
        """El guardián protege del caso en que alguien añada un DROP a schema.sql."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            _assert_script_is_safe(sql)

        assert excinfo.value.status_code == 409

    def test_creation_statements_are_allowed(self) -> None:
        safe = """
        create table if not exists public.projects (id uuid primary key);
        create index if not exists projects_idx on public.projects (id);
        alter table public.projects enable row level security;
        """

        _assert_script_is_safe(safe)  # no eleva

    def test_drop_trigger_is_allowed_because_it_is_how_idempotency_works(self) -> None:
        """``drop trigger`` sí se permite: PostgreSQL no admite ``create trigger if not
        exists``, así que la pareja drop+create es lo que hace reejecutable el script.
        No destruye datos."""
        _assert_script_is_safe(
            "drop trigger if exists set_updated_at on public.projects;"
        )


class TestRealSchemaFile:
    def test_the_shipped_schema_passes_the_guard(self) -> None:
        """El fichero real del repositorio no contiene nada destructivo."""
        _assert_script_is_safe(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_the_schema_declares_every_expected_table(self) -> None:
        """Si el esquema y la lista de tablas divergen, el sondeo miente."""
        sql = SCHEMA_PATH.read_text(encoding="utf-8").lower()

        for table in EXPECTED_TABLES:
            assert f"create table if not exists public.{table}" in sql, table

    def test_the_schema_is_idempotent(self) -> None:
        """Toda creación de tabla usa ``if not exists``: el script se puede reejecutar."""
        sql = SCHEMA_PATH.read_text(encoding="utf-8").lower()

        creates = sql.count("create table ")
        idempotent = sql.count("create table if not exists ")

        assert creates == idempotent

    def test_rollback_file_would_be_refused_by_the_guard(self) -> None:
        """db/rollback.sql no se puede colar por este endpoint.

        Es la comprobación que demuestra que el guardián sirve para algo: el fichero de
        reversión existe en el repositorio y contiene DROP, y el endpoint lo rechazaría.
        """
        from fastapi import HTTPException

        rollback = SCHEMA_PATH.parent / "rollback.sql"
        assert rollback.exists()

        with pytest.raises(HTTPException):
            _assert_script_is_safe(rollback.read_text(encoding="utf-8"))


class TestForbiddenPatterns:
    def test_every_pattern_is_a_valid_regex(self) -> None:
        import re

        for pattern in FORBIDDEN_STATEMENTS:
            re.compile(pattern)
