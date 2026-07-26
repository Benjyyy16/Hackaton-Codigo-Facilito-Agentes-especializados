"""Validación de la autenticidad de los webhooks de Jira.

Jira Cloud **no firma** los webhooks con HMAC, así que no hay firma que verificar. El
mecanismo disponible es un secreto compartido que este backend define y que se configura en
Jira al registrar el webhook. Puede llegar por dos vías:

* una cabecera, cuando quien envía permite añadirlas (reglas de automatización de Jira);
* un parámetro en la URL, que es lo único configurable en algunos formularios de webhook.

La comparación usa ``hmac.compare_digest`` para que el tiempo de respuesta no revele cuántos
caracteres del secreto coinciden. Un ``==`` corriente cortocircuita en el primer byte distinto
y filtra esa información.
"""

from __future__ import annotations

import hmac
from typing import Final

from pydantic import SecretStr

from app.core.exceptions import WebhookAuthError
from app.core.logging import get_logger

logger = get_logger("jira.security")

#: Cabecera preferida para el secreto compartido.
WEBHOOK_SECRET_HEADER: Final[str] = "X-Hook-Secret"

#: Parámetro de consulta alternativo, para cuando solo se puede configurar la URL.
WEBHOOK_SECRET_QUERY_PARAM: Final[str] = "secret"

#: Cabecera informativa que Jira Cloud añade a cada entrega. No sirve para autenticar, pero es
#: útil para correlacionar en los logs.
JIRA_DELIVERY_HEADER: Final[str] = "X-Atlassian-Webhook-Identifier"


def secrets_match(provided: str | None, expected: SecretStr) -> bool:
    """Compara el secreto recibido con el configurado, en tiempo constante."""
    if not provided:
        return False
    return hmac.compare_digest(
        provided.encode("utf-8"), expected.get_secret_value().encode("utf-8")
    )


def verify_webhook_secret(
    expected: SecretStr,
    *,
    header_value: str | None = None,
    query_value: str | None = None,
) -> None:
    """Comprueba el secreto compartido y eleva si no coincide (RF-5.2).

    Acepta la cabecera o el parámetro de consulta, en ese orden de preferencia. Eleva
    ``WebhookAuthError``, que el manejador traduce a ``401``; la ruta no debe haber
    persistido nada antes de llamar aquí.

    El error no distingue entre "secreto ausente" y "secreto incorrecto": esa distinción solo
    ayudaría a quien está probando valores.
    """
    if secrets_match(header_value, expected):
        return
    if secrets_match(query_value, expected):
        return

    # Se registra el hecho, nunca el valor recibido.
    logger.warning("Webhook rechazado: secreto compartido inválido o ausente")
    raise WebhookAuthError()
