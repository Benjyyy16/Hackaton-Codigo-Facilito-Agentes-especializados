"""Acceso a datos de análisis de riesgo."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from app.core.exceptions import InvalidRequestError
from app.repositories.base import BaseRepository, Page, Row


class RiskAnalysisRepository(BaseRepository):
    """Resultados de análisis producidos por el orquestador.

    Histórico sin borrado lógico: la evolución del riesgo a lo largo del tiempo es
    justamente lo que da valor a la plataforma.
    """

    table_name: ClassVar[str] = "risk_analyses"
    soft_delete: ClassVar[bool] = False

    async def record(
        self,
        *,
        risk_score: int,
        severity: str,
        findings: dict[str, Any],
        event_id: UUID | None = None,
        commitment_id: UUID | None = None,
        is_partial: bool = False,
    ) -> Row:
        """Persiste un análisis.

        El esquema exige que haya al menos un objetivo, evento o compromiso; se comprueba
        aquí para fallar con un mensaje del dominio en lugar de con una violación de
        restricción.
        """
        if event_id is None and commitment_id is None:
            raise InvalidRequestError(
                "Un análisis debe referirse a un evento o a un compromiso."
            )

        return await self.create(
            {
                "event_id": str(event_id) if event_id else None,
                "commitment_id": str(commitment_id) if commitment_id else None,
                "risk_score": risk_score,
                "severity": severity,
                "is_partial": is_partial,
                "findings": findings,
            }
        )

    async def get_latest_for_commitment(self, commitment_id: UUID) -> Row | None:
        """Devuelve el análisis más reciente de un compromiso."""
        page = await self.list_page(
            limit=1,
            filters={"commitment_id": str(commitment_id)},
            order_column="created_at",
            descending=True,
        )
        return page.items[0] if page.items else None

    async def list_for_event(self, event_id: UUID, *, limit: int = 20) -> Page[Row]:
        """Análisis asociados a un evento."""
        return await self.list_page(limit=limit, filters={"event_id": str(event_id)})
