"""Utilidades de seguridad reutilizables.

Funciones puras sin estado: cada una resuelve exactamente un problema de seguridad y está
testeable de forma aislada. Nada en este módulo toca la red ni la base de datos.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from typing import Final
from urllib.parse import urlparse

from app.core.exceptions import DomainError

# --- Constantes ---------------------------------------------------------------

MAX_PAYLOAD_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MiB


class PayloadTooLargeError(DomainError):
    """El cuerpo de la petición excede el máximo admitido."""

    code = "payload_too_large"
    status_code = 413
    message = "El cuerpo de la petición excede el tamaño máximo permitido."


# --- Comparación de secretos --------------------------------------------------


def compare_secret(provided: str | None, expected: str | None) -> bool:
    """Compara dos secretos en tiempo constante.

    NO se usa ``==`` porque el operador cortocircuita al primer byte diferente, lo que
    permite a un atacante medir el tiempo de respuesta para inferir el secreto carácter a
    carácter (timing attack). ``hmac.compare_digest`` itera siempre sobre toda la longitud.
    """
    if provided is None or expected is None:
        return False
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


# --- Verificación de webhook GitHub -------------------------------------------


def verify_github_signature(
    payload_bytes: bytes,
    header_value: str | None,
    secret: str,
) -> bool:
    """Verifica la firma HMAC-SHA256 de un webhook de GitHub.

    GitHub envía la cabecera ``X-Hub-Signature-256`` con formato ``sha256=<hex>``.
    Se recalcula el HMAC del cuerpo y se compara en tiempo constante.
    """
    if not header_value:
        return False
    prefix = "sha256="
    if not header_value.startswith(prefix):
        return False
    received_hex = header_value[len(prefix):]
    computed = hmac.HMAC(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(received_hex, computed)


# --- Verificación de secreto compartido (Jira) --------------------------------


def verify_shared_secret(provided: str | None, expected: str | None) -> bool:
    """Verifica un secreto compartido en tiempo constante.

    Jira Cloud NO firma el payload con HMAC como GitHub. En su lugar, envía un secreto
    estático en una cabecera o parámetro que se configura al registrar el webhook.
    La verificación se reduce a comparar el valor recibido con el esperado, pero en
    tiempo constante para evitar timing attacks.
    """
    return compare_secret(provided, expected)


# --- Protección SSRF ----------------------------------------------------------

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local + metadatos cloud
    ipaddress.ip_network("::1/128"),
)


def is_safe_url(url: str, allowed_hosts: set[str] | list[str] | None = None) -> bool:
    """Valida que una URL no apunte a recursos internos (protección SSRF).

    Rechaza:
    - Esquemas distintos de http/https
    - localhost, 127.x, ::1, redes privadas (10/8, 172.16/12, 192.168/16)
    - 169.254.169.254 (metadatos de instancias cloud)

    Si se pasa ``allowed_hosts``, además el hostname debe estar en esa lista.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Solo http(s)
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Rechazar localhost explícito
    if hostname in ("localhost", "localhost.localdomain"):
        return False

    # Resolver IP y verificar contra redes privadas
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_NETWORKS:
            if addr in net:
                return False
    except ValueError:
        # No es una IP literal, es un hostname. Verificar que no sea variante de localhost.
        lower = hostname.lower()
        if lower in ("localhost", "localhost.localdomain"):
            return False

    # allowed_hosts: si se especifica, el host debe estar en la lista
    if allowed_hosts is not None:
        if hostname not in allowed_hosts:
            return False

    return True


# --- Sanitización de logs -----------------------------------------------------

_SECRET_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"(?i)\bbearer\s+\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{10,}"),
    re.compile(r"\bgho_[A-Za-z0-9]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}"),  # JWT (base64 empieza con eyJ)
    re.compile(r"(?i)password=[^\s&]+"),
    re.compile(r"(?i)token=[^\s&]+"),
]


def sanitize_log_value(value: str) -> str:
    """Redacta patrones de secreto en un valor antes de registrarlo.

    Sustituye cada coincidencia por ``[REDACTED]``. Nunca deja el valor sensible en la
    salida. Se usa para logs de depuración y mensajes de error que podrían contener datos
    que llegaron del exterior.
    """
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


# --- Payload size -------------------------------------------------------------


def assert_payload_size(size: int) -> None:
    """Eleva ``PayloadTooLargeError`` si el tamaño supera el máximo.

    Se invoca antes de parsear el cuerpo para evitar gastar CPU/memoria en payloads
    desproporcionados.
    """
    if size > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(
            f"Payload de {size} bytes excede el máximo de {MAX_PAYLOAD_BYTES} bytes."
        )


# --- CORS por entorno ---------------------------------------------------------


def cors_origins_for(settings: object) -> list[str]:
    """Devuelve los orígenes CORS permitidos según el entorno.

    En producción SOLO se permite ``FRONTEND_URL``: abrir a localhost en producción
    permite que cualquier proceso local de un atacante con acceso a la máquina haga
    peticiones autenticadas.

    En desarrollo se añaden variantes de localhost para facilitar el trabajo local.
    """
    from app.core.config import Environment

    frontend = getattr(settings, "FRONTEND_URL", "")
    env = getattr(settings, "ENV", Environment.DEVELOPMENT)

    origins: list[str] = []
    if frontend:
        origins.append(frontend)

    if env != Environment.PRODUCTION:
        origins.extend([
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ])

    return origins
