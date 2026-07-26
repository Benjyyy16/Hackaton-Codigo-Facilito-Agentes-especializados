"""Sincronización inicial por JQL.

Carga el estado actual de un proyecto para tener una base sobre la que detectar cambios. Los
cambios posteriores llegan por webhook; esto se ejecuta una vez, a demanda.

Es idempotente: la huella de cada evento se deriva del ``updated`` del issue, así que repetir
la sincronización sin cambios en Jira produce las mismas huellas y por tanto duplicados que se
descartan (RF-4.7).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.integrations.jira.client import JiraClient
from app.integrations.jira.normalizer import normalize_issue
from app.schemas.jira import JiraSyncResult
from app.services.webhook_service import WebhookService

logger = get_logger("jira.sync")


def build_project_jql(project_key: str) -> str:
    """Construye el JQL por defecto para un proyecto (RF-4.2).

    Se ordena por ``updated`` descendente para que, si la recogida se corta por un límite, lo
    que se haya traído sea lo más reciente y por tanto lo más relevante.

    La clave se interpola entre comillas y con las comillas internas escapadas, para que un
    valor inesperado no pueda alterar la estructura de la consulta.
    """
    safe_key = project_key.replace('"', '\\"')
    return f'project = "{safe_key}" ORDER BY updated DESC'


class JiraSyncService:
    """Recorre los issues de un JQL y los ingiere como eventos."""

    def __init__(self, jira: JiraClient, webhooks: WebhookService) -> None:
        self._jira = jira
        self._webhooks = webhooks

    async def sync_project(
        self,
        project_key: str,
        *,
        jql: str | None = None,
        max_issues: int | None = None,
    ) -> JiraSyncResult:
        """Sincroniza un proyecto y devuelve el recuento de lo ocurrido (RF-4.5).

        Comprueba primero que el proyecto existe en Jira, de modo que una clave equivocada
        produzca un ``404`` claro en lugar de una sincronización vacía silenciosa (RF-4.6).

        Un issue que falla no aborta la sincronización: se cuenta y se sigue. Abortar dejaría
        el proyecto a medio cargar por un solo registro defectuoso.
        """
        # Eleva JiraNotFoundError si la clave no existe, que la ruta traduce a 404.
        await self._jira.get_project(project_key)

        effective_jql = jql or build_project_jql(project_key)
        processed = created = skipped = failed = 0

        async for issue in self._jira.iter_issues(effective_jql, max_issues=max_issues):
            processed += 1
            try:
                event = normalize_issue(issue)
                outcome = await self._webhooks.ingest_event(event)
            except Exception as error:  # noqa: BLE001 - un issue roto no aborta la carga
                failed += 1
                logger.warning(
                    "Issue %s no se pudo sincronizar: %s",
                    issue.get("key"),
                    type(error).__name__,
                )
                continue

            if outcome.duplicated:
                skipped += 1
            else:
                created += 1

        truncated = max_issues is not None and processed >= max_issues
        logger.info(
            "Sincronización de %s: %d procesados, %d creados, %d omitidos, %d fallidos",
            project_key,
            processed,
            created,
            skipped,
            failed,
        )

        return JiraSyncResult(
            project_key=project_key,
            jql=effective_jql,
            processed=processed,
            created=created,
            skipped=skipped,
            failed=failed,
            truncated=truncated,
        )
