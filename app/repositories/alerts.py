"""Acceso a datos de alertas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Final
from uuid import UUID

from app.repositories.base import BaseRepository, Page, Row

STATUS_OPEN: Final[str] = "open"
STATUS_RESOLVED: Final[str] = "resolved"


class AlertRepository(BaseRepository):
    """Alertas generadas a partir de los análisis de riesgo."""

    table_name: ClassVar[str] = "alerts"
    soft_delete: ClassVar[bool] = True

    async def find_open(self, commitment_id: UUID, reason: str) -> Row | None:
        """Devuelve la alerta abierta para ese compromiso y motivo, si existe.

        Es la consulta que decide entre crear una alerta nueva y actualizar la existente
        (RF-9.3). Está respaldada por el índice parcial único del esquema.
        """
        return await self.find_one(
            {
                "commitment_id": str(commitment_id),
                "reason": reason,
                "status": STATUS_OPEN,
            }
        )

    async def open_alert(
        self,
        *,
        risk_analysis_id: UUID,
        severity: str,
        reason: str,
        financial_impact: float,
        commitment_id: UUID | None = None,
    ) -> Row:
        """Crea una alerta abierta."""
        return await self.create(
            {
                "commitment_id": str(commitment_id) if commitment_id else None,
                "risk_analysis_id": str(risk_analysis_id),
                "severity": severity,
                "reason": reason,
                "financial_impact": financial_impact,
                "status": STATUS_OPEN,
                "resolved_at": None,
            }
        )

    async def refresh_alert(
        self,
        alert_id: UUID,
        *,
        risk_analysis_id: UUID,
        severity: str,
        financial_impact: float,
    ) -> Row:
        """Actualiza una alerta abierta con el resultado del análisis más reciente."""
        return await self.update(
            alert_id,
            {
                "risk_analysis_id": str(risk_analysis_id),
                "severity": severity,
                "financial_impact": financial_impact,
            },
        )

    async def resolve(self, alert_id: UUID) -> Row:
        """Marca la alerta como resuelta.

        El esquema exige que una alerta resuelta tenga ``resolved_at``, así que ambos campos
        viajan en la misma actualización.
        """
        return await self.update(
            alert_id,
            {
                "status": STATUS_RESOLVED,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        )

    async def list_alerts(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        severity: str | None = None,
        status: str | None = None,
    ) -> Page[Row]:
        """Lista alertas con filtro por severidad y estado (RF-10.4)."""
        return await self.list_page(
            limit=limit,
            offset=offset,
            filters={"severity": severity, "status": status},
            order_column="created_at",
            descending=True,
        )
