"""Traducción de los payloads de Jira al modelo interno.

Único punto del sistema que conoce la forma de los datos de Jira. Todo lo de fuera trabaja con
``NormalizedEvent``.

Dos rarezas de Jira que se absorben aquí:

* ``timeoriginalestimate`` viene en **segundos**, no en horas.
* Las marcas temporales llegan con desplazamiento sin dos puntos (``+0000``), que
  ``datetime.fromisoformat`` no aceptaba antes de Python 3.11 y que sigue siendo cómodo
  normalizar de forma explícita.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Final

from app.core.exceptions import UnsupportedEventError
from app.core.logging import get_logger
from app.schemas.jira import (
    WEBHOOK_EVENT_MAP,
    ChangedField,
    EventType,
    NormalizedEvent,
)

logger = get_logger("jira.normalizer")

SECONDS_PER_HOUR: Final[float] = 3600.0

#: Formatos de fecha que Jira emite, en orden de probabilidad.
_DATE_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
)


def parse_jira_datetime(value: Any) -> datetime | None:
    """Interpreta una marca temporal de Jira y la devuelve en UTC.

    Devuelve ``None`` en lugar de elevar: un campo de fecha ilegible no debe tumbar la
    ingesta de un evento por lo demás válido.
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
        parsed = datetime.fromisoformat(text)
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

    Jira expresa ``timeoriginalestimate`` en segundos. Tratarlo como horas inflaría la
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


def _extract_display_name(node: Any) -> str | None:
    """Saca el nombre visible de un usuario de Jira."""
    if not isinstance(node, dict):
        return None
    return node.get("displayName") or node.get("name") or node.get("emailAddress")


def _extract_nested_name(node: Any) -> str | None:
    """Saca ``name`` de una estructura anidada como ``status`` o ``priority``."""
    if not isinstance(node, dict):
        return None
    return node.get("name")


def _extract_project_key(fields: dict[str, Any], issue_key: str) -> str:
    """Determina la clave del proyecto.

    Si el payload no trae el proyecto, se deduce del prefijo de la clave del issue, que en
    Jira es siempre ``PROYECTO-numero``.
    """
    project = fields.get("project")
    if isinstance(project, dict) and project.get("key"):
        return str(project["key"])
    return issue_key.split("-", 1)[0] if "-" in issue_key else issue_key


def _extract_comment_body(payload: dict[str, Any]) -> str | None:
    """Extrae el texto del comentario.

    La API v3 devuelve el cuerpo en Atlassian Document Format, un árbol de nodos. Se recorre
    para quedarse solo con el texto, que es lo único que el análisis necesita.
    """
    comment = payload.get("comment")
    if not isinstance(comment, dict):
        return None
    body = comment.get("body")
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        return _flatten_adf(body) or None
    return None


def _flatten_adf(node: Any) -> str:
    """Aplana un documento ADF a texto llano."""
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


def _extract_changed_fields(payload: dict[str, Any]) -> list[ChangedField]:
    """Traduce el ``changelog`` del webhook a la lista de campos modificados."""
    changelog = payload.get("changelog")
    if not isinstance(changelog, dict):
        return []
    items = changelog.get("items")
    if not isinstance(items, list):
        return []

    changed: list[ChangedField] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field_name = item.get("field") or item.get("fieldId")
        if not field_name:
            continue
        changed.append(
            ChangedField(
                field=str(field_name),
                from_value=_stringify(item.get("fromString") or item.get("from")),
                to_value=_stringify(item.get("toString") or item.get("to")),
            )
        )
    return changed


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _resolve_occurred_at(
    payload: dict[str, Any], fields: dict[str, Any], event_type: EventType
) -> datetime:
    """Determina el instante del cambio.

    Es una pieza sensible: forma parte de la huella de deduplicación, así que debe ser
    estable para un mismo evento. Se prefiere el dato más específico disponible y, como
    último recurso, se recurre al instante actual, que rompería la idempotencia pero evita
    descartar el evento.
    """
    # 1. ``timestamp`` del webhook, en milisegundos desde época. Es el dato más fiel al
    #    momento del cambio y Jira lo repite en los reintentos de la misma entrega, lo que
    #    mantiene estable la huella.
    timestamp = payload.get("timestamp")
    if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        return datetime.fromtimestamp(timestamp / 1000, tz=UTC)

    # 2. Para un comentario, su propia marca temporal es más precisa que la del issue.
    candidates: list[Any] = []
    if event_type is EventType.COMMENT_CREATED:
        comment = payload.get("comment")
        if isinstance(comment, dict):
            candidates.extend([comment.get("updated"), comment.get("created")])

    # 3. Estado del issue: es la vía que usa la sincronización por JQL, y la que hace que
    #    repetirla sin cambios produzca la misma huella.
    candidates.extend([fields.get("updated"), fields.get("created")])

    for candidate in candidates:
        parsed = parse_jira_datetime(candidate)
        if parsed is not None:
            return parsed

    logger.warning(
        "Evento de Jira sin marca temporal utilizable; se usa el instante actual"
    )
    return datetime.now(UTC)


def _build_event(
    *,
    payload: dict[str, Any],
    issue: dict[str, Any],
    event_type: EventType,
) -> NormalizedEvent:
    """Construye el evento normalizado a partir del issue y del payload completo."""
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    fields = fields or {}
    issue_key = str(issue.get("key") or "")

    return NormalizedEvent(
        jira_issue_id=str(issue.get("id") or issue_key),
        jira_issue_key=issue_key,
        project_key=_extract_project_key(fields, issue_key),
        event_type=event_type,
        occurred_at=_resolve_occurred_at(payload, fields, event_type),
        summary=fields.get("summary"),
        status=_extract_nested_name(fields.get("status")),
        assignee=_extract_display_name(fields.get("assignee")),
        priority=_extract_nested_name(fields.get("priority")),
        due_date=parse_jira_datetime(fields.get("duedate")),
        estimated_hours=seconds_to_hours(fields.get("timeoriginalestimate")),
        labels=[str(label) for label in (fields.get("labels") or [])],
        changed_fields=_extract_changed_fields(payload),
        comment_body=_extract_comment_body(payload),
        raw_payload=payload,
    )


def normalize_webhook_payload(payload: dict[str, Any]) -> NormalizedEvent:
    """Convierte un payload de webhook en un evento normalizado.

    Eleva ``UnsupportedEventError`` cuando el tipo no está soportado, que la ruta traduce a
    ``202`` y descarta de forma explícita (RF-5.4).
    """
    raw_event = payload.get("webhookEvent") or payload.get("issue_event_type_name")
    event_type = WEBHOOK_EVENT_MAP.get(str(raw_event)) if raw_event else None
    if event_type is None:
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

    return _build_event(payload=payload, issue=issue, event_type=event_type)


def normalize_issue(issue: dict[str, Any]) -> NormalizedEvent:
    """Convierte un issue de una búsqueda JQL en un evento normalizado (RF-4.4).

    La sincronización inicial no observa cambios, sino el estado actual, así que el evento se
    clasifica como actualización. Su instante es el ``updated`` del issue, lo que hace la
    sincronización idempotente: repetirla sin cambios en Jira produce la misma huella y por
    tanto el mismo duplicado (RF-4.7).
    """
    if not isinstance(issue, dict) or not issue.get("key"):
        raise UnsupportedEventError("El issue no tiene clave identificable.")

    return _build_event(
        payload={"issue": issue, "source": "jql_sync"},
        issue=issue,
        event_type=EventType.ISSUE_UPDATED,
    )
