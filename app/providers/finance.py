"""Provider de datos financieros basado en fichero.

A diferencia de los providers de red (Jira, GitHub), este opera sobre datos locales:
JSON o CSV que el usuario sube o que se leen del filesystem. No abre conexiones de red
ni necesita credenciales. La razón de implementarlo como provider y no como función
suelta: el ciclo de vida (connect/health/close) lo hace intercambiable en el registry
y permite que el health-check lo informe igual que al resto.
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal

from app.schemas.common import DependencyStatus
from app.schemas.domain import Evidence, EvidenceSourceType
from app.schemas.finance_domain import (
    BudgetLine,
    FinanceSnapshot,
    LaborEntry,
    Penalty,
)
from app.schemas.providers import ProviderHealth, ProviderKind


class FinanceProvider:
    """Provider de fichero para datos financieros.

    No requiere red: los datos se cargan desde JSON dict o CSV string que el caller
    proporciona. Implementa el protocolo Provider (connect/health/close) para ser
    registrable en el ProviderRegistry con el mismo contrato que los demás.
    """

    name: str = "finance"
    kind: ProviderKind = ProviderKind.EVENT_SOURCE

    def __init__(self) -> None:
        self._connected: bool = False

    async def connect(self) -> None:
        """Marca el provider como listo. No abre recursos porque opera sobre ficheros."""
        self._connected = True

    async def health(self) -> ProviderHealth:
        """Siempre UP si está conectado, porque no depende de red externa."""
        status = DependencyStatus.UP if self._connected else DependencyStatus.UNKNOWN
        return ProviderHealth(
            provider=self.name,
            status=status,
            latency_ms=0.0,
            detail=None if self._connected else "No conectado aún",
        )

    async def close(self) -> None:
        """Nada que liberar: no hay conexiones abiertas."""
        self._connected = False

    # ---------------------------------------------------------------------------------
    # Carga de datos
    # ---------------------------------------------------------------------------------

    def load_from_json(self, data: dict) -> FinanceSnapshot:
        """Construye un FinanceSnapshot desde un dict (típicamente deserializado de JSON).

        Delega la validación a Pydantic: si los datos no cumplen el schema, se eleva
        ValidationError con detalle de qué campo falló y por qué.
        """
        return FinanceSnapshot.model_validate(data)

    def load_from_csv(self, content: str) -> FinanceSnapshot:
        """Construye un FinanceSnapshot desde contenido CSV.

        Formato esperado: secciones separadas por línea ``[SECTION_NAME]``.
        Secciones: META, BUDGET, LABOR, PENALTIES.

        Se usa csv de stdlib y no pandas porque la dependencia no se justifica para
        parsear unas decenas de filas, y pandas arrastra ~200MB de transitividades.
        """
        sections = self._parse_csv_sections(content)

        # --- META (obligatorio) ---
        meta = sections.get("META", [])
        if not meta:
            raise ValueError("Sección META ausente o vacía en el CSV")
        meta_row = meta[0]
        project_key = meta_row.get("project_key", "")
        commitment_ref = meta_row.get("commitment_ref", "")
        currency = meta_row.get("currency", "USD")
        retained_payments = Decimal(meta_row.get("retained_payments", "0"))
        period_start = date.fromisoformat(meta_row["period_start"])
        period_end = date.fromisoformat(meta_row["period_end"])

        # --- BUDGET (obligatorio, al menos 1 línea) ---
        budget_rows = sections.get("BUDGET", [])
        if not budget_rows:
            raise ValueError("Sección BUDGET ausente o vacía en el CSV")
        budget_lines = [
            BudgetLine(
                concept=row["concept"],
                planned=Decimal(row["planned"]),
                actual=Decimal(row["actual"]),
                currency=row.get("currency", currency),
                category=row.get("category", "general"),
            )
            for row in budget_rows
        ]

        # --- LABOR (opcional) ---
        labor_rows = sections.get("LABOR", [])
        labor_entries = [
            LaborEntry(
                role=row["role"],
                hours=Decimal(row["hours"]),
                hourly_rate=Decimal(row["hourly_rate"]),
                date=date.fromisoformat(row["date"]),
            )
            for row in labor_rows
        ]

        # --- PENALTIES (opcional) ---
        penalty_rows = sections.get("PENALTIES", [])
        penalties = [
            Penalty(
                description=row["description"],
                amount=Decimal(row["amount"]),
                trigger_condition=row["trigger_condition"],
                probability=float(row["probability"]),
            )
            for row in penalty_rows
        ]

        return FinanceSnapshot(
            project_key=project_key,
            commitment_ref=commitment_ref,
            currency=currency,
            budget_lines=budget_lines,
            labor_entries=labor_entries,
            penalties=penalties,
            retained_payments=retained_payments,
            period_start=period_start,
            period_end=period_end,
        )

    def get_evidence(self, snapshot: FinanceSnapshot) -> list[Evidence]:
        """Genera evidencia a partir del snapshot: cada línea presupuestaria es un dato observable."""
        now = datetime.now(UTC)
        evidences: list[Evidence] = []
        for bl in snapshot.budget_lines:
            evidences.append(
                Evidence(
                    source_type=EvidenceSourceType.FINANCE,
                    provider=self.name,
                    field=f"budget_line.{bl.concept}",
                    value=f"planned={bl.planned} actual={bl.actual}",
                    observed_at=now,
                    explanation=(
                        f"Línea '{bl.concept}': planificado {bl.planned} vs ejecutado {bl.actual} "
                        f"({bl.currency})"
                    ),
                )
            )
        for p in snapshot.penalties:
            evidences.append(
                Evidence(
                    source_type=EvidenceSourceType.FINANCE,
                    provider=self.name,
                    field="penalty",
                    value=f"amount={p.amount} prob={p.probability}",
                    observed_at=now,
                    explanation=(
                        f"Penalización '{p.description}': ${p.amount} con probabilidad "
                        f"{p.probability:.0%} si {p.trigger_condition}"
                    ),
                )
            )
        return evidences

    # ---------------------------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------------------------

    @staticmethod
    def _parse_csv_sections(content: str) -> dict[str, list[dict[str, str]]]:
        """Divide el CSV en secciones marcadas con ``[NOMBRE]``.

        Cada sección tiene su propio encabezado en la primera línea tras el marcador.
        """
        sections: dict[str, list[dict[str, str]]] = {}
        current_section: str | None = None
        current_lines: list[str] = []

        for line in content.strip().splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                # Guardar sección anterior
                if current_section and current_lines:
                    reader = csv.DictReader(current_lines)
                    sections[current_section] = list(reader)
                current_section = stripped[1:-1]
                current_lines = []
            else:
                current_lines.append(line)

        # Última sección
        if current_section and current_lines:
            reader = csv.DictReader(current_lines)
            sections[current_section] = list(reader)

        return sections
