"""Traducción de payloads de Jira al evento del dominio.

Único punto del sistema que conoce la forma de los datos de Jira. Reemplaza al normalizador
anterior, que producía un modelo con nombres de campo de Jira; ahora produce ``ExternalEvent``,
que es agnóstico.

Dos rarezas de Jira que se absorben aquí:

* ``timeoriginalestimate`` viene en **segundos**, no en horas.
* El cuerpo de los comentarios llega en Atlassian Document Format, un árbol de nodos.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Final

from app.core.exceptions import UnsupportedEventError
from app.core.logging import get_logger
from app.schemas.events import EventKind, ExternalEvent, FieldChange, ProviderName

logger = get_logger("jira.mapper")

SECONDS_PER_HOUR: Final[float] = 3600.0

#: Correspondencia entre el evento del webhook de Jira y el vocabulario del dominio. Lo que no
#: está aquí se descarta de forma explícita (RF-5.4).
WEBHOOK_EVENT_MAP: Final[dict[str, EventKind]] = {
    "jira:issue_created": EventKind.WORK_ITEM_CREATED,
    "jira:issue_updated": EventKind.WORK_ITEM_UPDATED,
    "comment_created": EventKind.COMMENT_ADDED,
    "jira:comment_created": EventKind.COMMENT_ADDED,
}

_DATE_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
)


def parse_jira_datetime(value: Any) -> datetime | None:
    """Interpreta una marca temporal de Jira y la devuelve en UTC.

    Devuelve ``None`` en lugar de elevar: un campo de fecha ilegible no debe tumbar la ingesta
    de un evento por lo demás válido.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if not isinstance(value, str):
        return None

    text = value.strip()
    try:
        parsed: datetime | None = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
        for pattern in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue

    if parsed is None:
        logger.warning("Marca temporal de Jira no reconocida")
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def seconds_to_hours(value: Any) -> float | None:
    """Convierte segundos de Jira a horas.

    Jira expresa ``timeoriginalestimate`` en segundos. Tratarlo como horas multiplicaría la
    estimación por 3600 y con ella el impacto económico.
    """
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return round(seconds / SECONDS_PER_HOUR, 2)


def _display_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    return node.get("displayName") or node.get("name") or node.get("emailAddress")


def _nested_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    return node.get("name")


def _workspace_key(fields: dict[str, Any], issue_key: str) -> str:
    """Determina la clave del proyecto.

    Si el payload no la trae, se deduce del prefijo de la clave del issue, que en Jira es
    siempre ``PROYECTO-numero``.
    """
    project = fields.get("project")
    if isinstance(project, dict) and project.get("key"):
        return str(project["key"])
    return issue_key.split("-", 1)[0] if "-" in issue_key else issue_key


def _flatten_adf(node: Any) -> str:
    """Aplana un documento Atlassian Document Format a texto llano."""
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            return node["text"]
        return " ".join(
            fragment
            for fragment in (_flatten_adf(child) for child in node.get("content", []))
            if fragment
        )
    if isinstance(node, list):
        return " ".join(
            fragment for fragment in (_flatten_adf(item) for item in node) if fragment
        )
    return ""


def _comment_text(payload: dict[str, Any]) -> str | None:
    comment = payload.get("comment")
    if not isinstance(comment, dict):
        return None
    body = comment.get("body")
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        return _flatten_adf(body) or None
    return None


def _changes(payload: dict[str, Any]) -> list[FieldChange]:
    """Traduce el ``changelog`` del webhook a la lista de campos modificados."""
    changelog = payload.get("changelog")
    if not isinstance(changelog, dict):
        return []
    items = changelog.get("items")
    if not isinstance(items, list):
        return []

    changed: list[FieldChange] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field_name = item.get("field") or item.get("fieldId")
        if not field_name:
            continue
        changed.append(
            FieldChange(
                field=str(field_name),
                from_value=_stringify(item.get("fromString") or item.get("from")),
                to_value=_stringify(item.get("toString") or item.get("to")),
            )
        )
    return changed


def _stringify(value: Any) -> str | None:
    return None if value is None else str(value)


def _occurred_at(
    payload: dict[str, Any], fields: dict[str, Any], kind: EventKind
) -> datetime:
    """Determina el instante del cambio.

    Forma parte de la huella de deduplicación, así que la precedencia es explícita:

    1. ``timestamp`` del webhook, el dato más fiel al momento del cambio, que Jira repite en los
       reintentos de la misma entrega.
    2. La marca del comentario, más precisa que la del issue cuando el evento es un comentario.
    3. ``updated`` y ``created`` del issue, que es la vía de la sincronización por consulta y la
       que hace que repetirla sin cambios produzca la misma huella.
    """
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        return datetime.fromtimestamp(timestamp / 1000, tz=UTC)

    candidates: list[Any] = []
    if kind is EventKind.COMMENT_ADDED:
        comment = payload.get("comment")
        if isinstance(comment, dict):
            candidates.extend([comment.get("updated"), comment.get("created")])
    candidates.extend([fields.get("updated"), fields.get("created")])

    for candidate in candidates:
        parsed = parse_jira_datetime(candidate)
        if parsed is not None:
            return parsed

    logger.warning("Evento de Jira sin marca temporal utilizable; se usa el instante actual")
    return datetime.now(UTC)


def _build(
    *, payload: dict[str, Any], issue: dict[str, Any], kind: EventKind, base_url: str | None
) -> ExternalEvent:
    raw_fields = issue.get("fields")
    fields: dict[str, Any] = raw_fields if isinstance(raw_fields, dict) else {}
    issue_key = str(issue.get("key") or "")

    return ExternalEvent(
        provider=ProviderName.JIRA,
        workspace_key=_workspace_key(fields, issue_key),
        external_id=str(issue.get("id") or issue_key),
        external_key=issue_key,
        kind=kind,
        occurred_at=_occurred_at(payload, fields, kind),
        title=fields.get("summary"),
        state=_nested_name(fields.get("status")),
        owner=_display_name(fields.get("assignee")),
        priority=_nested_name(fields.get("priority")),
        due_date=parse_jira_datetime(fields.get("duedate")),
        estimated_hours=seconds_to_hours(fields.get("timeoriginalestimate")),
        labels=[str(label) for label in (fields.get("labels") or [])],
        changes=_changes(payload),
        comment=_comment_text(payload),
        url=f"{base_url}/browse/{issue_key}" if base_url and issue_key else None,
        raw_payload=payload,
    )


def map_webhook_payload(
    payload: dict[str, Any], *, base_url: str | None = None
) -> ExternalEvent:
    """Convierte un payload de webhook en un evento del dominio.

    Eleva ``UnsupportedEventError`` cuando el tipo no interesa, que la ruta traduce a ``202``.
    """
    raw_event = payload.get("webhookEvent") or payload.get("issue_event_type_name")
    kind = WEBHOOK_EVENT_MAP.get(str(raw_event)) if raw_event else None
    if kind is None:
        raise UnsupportedEventError(
            f"Tipo de evento no soportado: {raw_event}",
            details={"webhook_event": str(raw_event)},
        )

    issue = payload.get("issue")
    if not isinstance(issue, dict) or not issue.get("key"):
        raise UnsupportedEventError(
            "El payload no contiene un issue identificable.",
            details={"webhook_event": str(raw_event)},
        )

    return _build(payload=payload, issue=issue, kind=kind, base_url=base_url)


def map_issue(issue: dict[str, Any], *, base_url: str | None = None) -> ExternalEvent:
    """Convierte un issue de una búsqueda JQL en un evento del dominio (RF-4.4).

    La sincronización no observa cambios sino el estado actual, así que el evento se clasifica
    como actualización. Su instante es el ``updated`` del issue, lo que hace la sincronización
    idempotente: repetirla sin cambios en Jira produce la misma huella (RF-4.7).
    """
    if not isinstance(issue, dict) or not issue.get("key"):
        raise UnsupportedEventError("El issue no tiene clave identificable.")

    return _build(
        payload={"issue": issue, "source": "jql_sync"},
        issue=issue,
        kind=EventKind.WORK_ITEM_UPDATED,
        base_url=base_url,
    )
