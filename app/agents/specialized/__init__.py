"""Agentes especializados de Datgent.

Cuatro agentes analizan el mismo ``Commitment`` desde su dominio, y ninguno sabe de los
demás. La correlación es trabajo del orquestador, que es el único que ve las cuatro
salidas a la vez.
"""

from app.agents.specialized.base import (
    AgentContext,
    BaseSpecializedAgent,
    SpecializedAgent,
)
from app.agents.specialized.code_agent import CodeAgent
from app.agents.specialized.database_agent import DatabaseAgent
from app.agents.specialized.finance_agent import FinanceAgent
from app.agents.specialized.jira_agent import JiraAgent

#: Orden de ejecución por defecto. No hay dependencias entre agentes, así que el orden
#: no altera el resultado; se fija para que la salida sea reproducible y los tests
#: puedan afirmar sobre posiciones.
DEFAULT_AGENTS: tuple[type[BaseSpecializedAgent], ...] = (
    JiraAgent,
    CodeAgent,
    FinanceAgent,
    DatabaseAgent,
)

__all__ = [
    "AgentContext",
    "BaseSpecializedAgent",
    "SpecializedAgent",
    "JiraAgent",
    "CodeAgent",
    "FinanceAgent",
    "DatabaseAgent",
    "DEFAULT_AGENTS",
]
