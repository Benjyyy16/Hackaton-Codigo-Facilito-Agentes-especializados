"""Tests de los endpoints del dominio financiero y de salud por provider.

Cubren los tres endpoints obligatorios que faltaban: ``POST /finance/import``,
``POST /finance/analyze`` y ``GET /providers/{provider}/health``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.schemas.events import ProviderName
from app.tests.conftest import client_for

pytestmark = pytest.mark.anyio

SEED_PATH = Path(__file__).resolve().parents[2] / "db" / "seed" / "finance_seed.json"


@pytest.fixture
def finance_seed() -> dict:
    """Snapshot financiero del caso demo, leído del fichero real.

    Se lee del fichero y no se replica en el test: si el seed cambia y deja de validar,
    este test debe fallar. Una copia en el test lo ocultaría.
    """
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


class TestFinanceImport:
    async def test_valid_json_returns_snapshot_and_analysis(
        self, app: FastAPI, finance_seed: dict
    ) -> None:
        async with client_for(app) as client:
            response = await client.post("/finance/import", json={
                "project_key": "DATGENT",
                "commitment_ref": "Entregar integración de pagos",
                "json_data": finance_seed,
            })

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["snapshot"] is not None
        assert body["analysis"] is not None
        assert body["errors"] == []

    async def test_missing_payload_reports_error_without_failing(
        self, app: FastAPI
    ) -> None:
        """Sin datos se devuelve 200 con el motivo, no un 422 opaco.

        Quien importa un fichero necesita saber qué falta; un 422 sin cuerpo útil obliga a
        adivinar.
        """
        async with client_for(app) as client:
            response = await client.post("/finance/import", json={
                "project_key": "DATGENT",
                "commitment_ref": "X",
            })

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["errors"]

    async def test_invalid_json_reports_the_reason(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post("/finance/import", json={
                "project_key": "DATGENT",
                "commitment_ref": "X",
                "json_data": {"budget_lines": "no es una lista"},
            })

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["errors"]
        assert body["snapshot"] is None

    async def test_import_is_deterministic(
        self, app: FastAPI, finance_seed: dict
    ) -> None:
        """Dos importaciones del mismo fichero producen las mismas cifras.

        Se comparan los importes y los códigos de hallazgo, no la evidencia completa:
        ``observed_at`` registra CUÁNDO se observó el dato y por tanto cambia entre
        llamadas. Exigir que fuera igual obligaría a congelar el reloj, y con ello se
        perdería el registro de cuándo se hizo la lectura.

        Que las cifras coincidan es la propiedad que hace defendible un número ante un
        cliente; que el instante de lectura coincida no aportaría nada.
        """
        payload = {
            "project_key": "DATGENT",
            "commitment_ref": "Entregar integración de pagos",
            "json_data": finance_seed,
        }
        async with client_for(app) as client:
            first = (await client.post("/finance/import", json=payload)).json()
            second = (await client.post("/finance/import", json=payload)).json()

        money_fields = (
            "total_planned",
            "total_actual",
            "variance",
            "variance_pct",
            "labor_cost",
            "margin",
            "margin_pct",
            "burn_rate_daily",
            "penalty_exposure",
            "retained_payments",
            "total_exposure",
            "overtime_hours_projected",
        )
        for field in money_fields:
            assert first["analysis"][field] == second["analysis"][field], field

        codes_first = sorted(f["code"] for f in first["analysis"]["findings"])
        codes_second = sorted(f["code"] for f in second["analysis"]["findings"])
        assert codes_first == codes_second

        scores_first = [f["risk_score"] for f in first["analysis"]["findings"]]
        scores_second = [f["risk_score"] for f in second["analysis"]["findings"]]
        assert scores_first == scores_second


class TestFinanceAnalyze:
    async def test_analyze_returns_exposure_breakdown(
        self, app: FastAPI, finance_seed: dict
    ) -> None:
        async with client_for(app) as client:
            imported = await client.post("/finance/import", json={
                "project_key": "DATGENT",
                "commitment_ref": "Entregar integración de pagos",
                "json_data": finance_seed,
            })
            snapshot = imported.json()["snapshot"]

            response = await client.post("/finance/analyze", json=snapshot)

        assert response.status_code == 200
        body = response.json()
        for field in (
            "total_planned",
            "total_actual",
            "variance",
            "labor_cost",
            "margin",
            "burn_rate_daily",
            "penalty_exposure",
            "total_exposure",
        ):
            assert field in body

    async def test_analyze_rejects_malformed_snapshot(self, app: FastAPI) -> None:
        """Aquí sí procede 422: el cuerpo no cumple el contrato del modelo."""
        async with client_for(app) as client:
            response = await client.post("/finance/analyze", json={"budget_lines": []})

        assert response.status_code == 422

    async def test_demo_seed_produces_exposure(
        self, app: FastAPI, finance_seed: dict
    ) -> None:
        """El caso demo tiene que exponer dinero: es su razón de ser."""
        async with client_for(app) as client:
            imported = await client.post("/finance/import", json={
                "project_key": "DATGENT",
                "commitment_ref": "Entregar integración de pagos",
                "json_data": finance_seed,
            })
            snapshot = imported.json()["snapshot"]
            response = await client.post("/finance/analyze", json=snapshot)

        analysis = response.json()
        assert float(analysis["total_exposure"]) > 0
        assert float(analysis["penalty_exposure"]) > 0
        assert analysis["findings"]


class TestProviderHealth:
    async def test_configured_provider_reports_status(self, app: FastAPI) -> None:
        """La conftest registra Jira, así que su salud se puede consultar."""
        async with client_for(app) as client:
            response = await client.get(f"/providers/{ProviderName.JIRA.value}/health")

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == ProviderName.JIRA.value
        assert "status" in body

    async def test_unconfigured_provider_is_404_not_a_fake_status(
        self, app: FastAPI
    ) -> None:
        """No saber nada de una integración sin configurar no es "está caída".

        Devolver un estado inventado haría que un panel mostrara en rojo algo que nadie
        pidió conectar.
        """
        async with client_for(app) as client:
            response = await client.get(f"/providers/{ProviderName.NOTION.value}/health")

        assert response.status_code == 404

    async def test_unknown_provider_name_is_rejected_by_validation(
        self, app: FastAPI
    ) -> None:
        """El enum cerrado impide consultar un provider inventado."""
        async with client_for(app) as client:
            response = await client.get("/providers/inventado/health")

        assert response.status_code == 422
