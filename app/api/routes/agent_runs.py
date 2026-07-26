"""Rutas de ejecuciones de agentes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DomainRepositoriesDep, ProviderRegistryDep
from app.schemas.domain import AgentRunRead

router = APIRouter(tags=["agents"])


@router.get(
    "/agents/status",
    summary="Estado de los agentes registrados",
    description="Devuelve los providers registrados y su estado de salud.",
)
async def agents_status(registry: ProviderRegistryDep) -> list[dict]:
    """Informa el estado de cada provider registrado como agente."""
    results = []
    for name in registry.names():
        provider = registry.get(name)
        if provider is None:
            continue
        health = await provider.health()
        results.append({
            "name": name.value,
            "status": health.status.value if hasattr(health.status, "value") else str(health.status),
            "latency_ms": health.latency_ms,
        })
    return results


agent_runs_router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@agent_runs_router.get(
    "/{agent_run_id}",
    response_model=AgentRunRead,
    summary="Obtener ejecución de agente",
    description="Devuelve una ejecución de agente por ID. 404 si no existe.",
)
async def get_agent_run(
    agent_run_id: UUID,
    repos: DomainRepositoriesDep,
) -> AgentRunRead:
    row = await repos.agent_runs.get_or_raise(agent_run_id)
    return AgentRunRead.model_validate(row)
