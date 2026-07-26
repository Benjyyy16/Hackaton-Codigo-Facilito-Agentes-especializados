"""Cliente de la API de Jira Cloud.

Un ``httpx.AsyncClient`` de vida larga, creado en el ``lifespan`` y reutilizado: crear un
cliente por petición desperdiciaría el pool de conexiones y el handshake TLS.

Sobre la búsqueda por JQL: el endpoint clásico ``/rest/api/3/search`` fue **retirado** de Jira
Cloud y responde ``410 Gone``. El vigente es ``/rest/api/3/search/jql``, cuya paginación usa
``nextPageToken`` e ``isLast`` en lugar de ``startAt`` y ``total``. Detalles que condicionan la
implementación:

* La primera llamada no debe enviar ``nextPageToken``; hacerlo devuelve ``400``.
* La respuesta no trae recuento total, así que no se puede saber de antemano cuántas páginas
  hay.
* Hay casos documentados en los que ``isLast`` no llega nunca a ``true`` y los tokens se
  encadenan indefinidamente. Por eso el iterador no confía solo en ``isLast``: corta también
  por token repetido, por página vacía y por un tope duro de páginas.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from typing import Any, Final

import httpx

from app.core.config import Settings
from app.core.exceptions import (
    JiraAuthError,
    JiraNotFoundError,
    JiraRateLimitError,
    JiraUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger("jira.client")

#: Endpoint vigente de búsqueda por JQL.
SEARCH_JQL_PATH: Final[str] = "/rest/api/3/search/jql"
PROJECT_PATH: Final[str] = "/rest/api/3/project"
MYSELF_PATH: Final[str] = "/rest/api/3/myself"

#: Campos que se piden explícitamente. El endpoint nuevo devuelve un conjunto mínimo si no se
#: indican, y sin ellos el análisis se queda sin señales.
DEFAULT_ISSUE_FIELDS: Final[tuple[str, ...]] = (
    "summary",
    "status",
    "assignee",
    "priority",
    "duedate",
    "timeoriginalestimate",
    "labels",
    "created",
    "updated",
    "project",
)

#: Tamaño de página solicitado. Jira puede devolver menos.
PAGE_SIZE: Final[int] = 50

#: Tope duro de páginas. Es la red de seguridad contra el encadenamiento infinito de tokens.
MAX_PAGES: Final[int] = 200

#: Espera base para el reintento exponencial, en segundos.
RETRY_BASE_DELAY: Final[float] = 0.5

#: Techo de espera entre reintentos. Sin él, un ``Retry-After`` alto bloquearía la tarea.
MAX_RETRY_DELAY: Final[float] = 30.0

_RETRYABLE_STATUSES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})


def create_jira_http_client(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """Construye el cliente HTTP de Jira.

    Autenticación HTTP Basic con email y API token, que es el mecanismo de Jira Cloud
    (RF-3.1). Timeouts explícitos en las cuatro fases (RF-3.2).

    ``transport`` existe para que los tests inyecten un ``MockTransport`` y puedan ejercitar
    la autenticación y los reintentos reales sin tocar atributos privados del cliente.
    """
    timeout = httpx.Timeout(
        connect=settings.HTTP_TIMEOUT_SECONDS,
        read=settings.HTTP_TIMEOUT_SECONDS,
        write=settings.HTTP_TIMEOUT_SECONDS,
        pool=settings.HTTP_TIMEOUT_SECONDS,
    )
    return httpx.AsyncClient(
        base_url=settings.JIRA_BASE_URL,
        auth=httpx.BasicAuth(
            settings.JIRA_EMAIL, settings.JIRA_API_TOKEN.get_secret_value()
        ),
        timeout=timeout,
        headers={"Accept": "application/json"},
        follow_redirects=True,
        transport=transport,
    )


class JiraClient:
    """Acceso a la API de Jira con reintentos y errores de dominio."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        max_retries: int = 3,
        max_pages: int = MAX_PAGES,
    ) -> None:
        self._http = http
        self._max_retries = max_retries
        self._max_pages = max_pages

    # --- Transporte ---------------------------------------------------------------

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        """Lee ``Retry-After`` cuando viene expresado en segundos.

        La cabecera admite también una fecha HTTP; en ese caso se ignora y se recurre a la
        espera exponencial, que es más simple que arrastrar un parser de fechas por un caso
        que Jira no usa en práctica.
        """
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return max(0.0, float(raw.strip()))
        except ValueError:
            return None

    def _delay_for_attempt(self, attempt: int, response: httpx.Response | None) -> float:
        """Calcula la espera antes del siguiente intento.

        ``429`` respeta ``Retry-After`` (RF-3.3). El resto usa espera exponencial con jitter
        (RF-3.4); el jitter evita que varias tareas reintenten sincronizadas.
        """
        if response is not None and response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            advised = self._retry_after_seconds(response)
            if advised is not None:
                return min(advised, MAX_RETRY_DELAY)

        exponential = RETRY_BASE_DELAY * (2**attempt)
        jitter = random.uniform(0, RETRY_BASE_DELAY)  # noqa: S311 - no es criptográfico
        return min(exponential + jitter, MAX_RETRY_DELAY)

    @staticmethod
    def _raise_for_terminal_status(response: httpx.Response, path: str) -> None:
        """Traduce los estados que no admiten reintento."""
        status = response.status_code
        if status in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
            # Reintentar credenciales inválidas solo suma latencia (RF-3.5).
            raise JiraAuthError(details={"status": status})
        if status == httpx.codes.NOT_FOUND:
            raise JiraNotFoundError(details={"path": path})
        if status == httpx.codes.GONE:
            # El endpoint clásico de búsqueda responde así desde su retirada.
            raise JiraUnavailableError(
                "Jira indica que el endpoint solicitado ha sido retirado.",
                details={"path": path, "status": status},
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ejecuta una petición aplicando la política de reintentos.

        Los logs registran método, ruta y estado. Nunca cabeceras, que llevan la credencial
        (RF-3.7).
        """
        last_response: httpx.Response | None = None
        # ``timeout`` permite un presupuesto más corto que el del cliente para las llamadas que
        # lo necesitan, como la sonda de salud.
        extra: dict[str, Any] = {} if timeout is None else {"timeout": timeout}

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.request(method, path, params=params, **extra)
            except httpx.TimeoutException as error:
                logger.warning(
                    "Jira %s %s agotó el tiempo (intento %d/%d)",
                    method,
                    path,
                    attempt + 1,
                    self._max_retries + 1,
                )
                if attempt >= self._max_retries:
                    raise JiraUnavailableError(
                        "Jira no respondió dentro del tiempo permitido.",
                        details={"path": path},
                    ) from error
                await asyncio.sleep(self._delay_for_attempt(attempt, None))
                continue
            except httpx.HTTPError as error:
                logger.warning(
                    "Jira %s %s falló en transporte: %s",
                    method,
                    path,
                    type(error).__name__,
                )
                if attempt >= self._max_retries:
                    raise JiraUnavailableError(
                        "No se pudo contactar con Jira.", details={"path": path}
                    ) from error
                await asyncio.sleep(self._delay_for_attempt(attempt, None))
                continue

            logger.info("Jira %s %s -> %d", method, path, response.status_code)
            self._raise_for_terminal_status(response, path)

            if response.status_code in _RETRYABLE_STATUSES:
                last_response = response
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._delay_for_attempt(attempt, response))
                continue

            if response.is_success:
                return self._decode(response, path)

            # Cualquier otro 4xx es un error del cliente: reintentarlo no lo arregla.
            raise JiraUnavailableError(
                "Jira rechazó la petición.",
                details={"path": path, "status": response.status_code},
            )

        # Reintentos agotados sobre un estado reintentable (RF-3.6).
        status = last_response.status_code if last_response else None
        if status == httpx.codes.TOO_MANY_REQUESTS:
            raise JiraRateLimitError(details={"path": path})
        raise JiraUnavailableError(details={"path": path, "status": status})

    @staticmethod
    def _decode(response: httpx.Response, path: str) -> dict[str, Any]:
        """Interpreta el cuerpo como objeto JSON."""
        try:
            payload = response.json()
        except ValueError as error:
            raise JiraUnavailableError(
                "Jira devolvió una respuesta que no es JSON válido.",
                details={"path": path},
            ) from error
        if not isinstance(payload, dict):
            raise JiraUnavailableError(
                "Jira devolvió un cuerpo con una forma inesperada.",
                details={"path": path},
            )
        return payload

    # --- Operaciones --------------------------------------------------------------

    async def get_project(self, project_key: str) -> dict[str, Any]:
        """Devuelve un proyecto. Eleva ``JiraNotFoundError`` si no existe (RF-4.6)."""
        return await self._request("GET", f"{PROJECT_PATH}/{project_key}")

    async def get_current_user(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Devuelve la cuenta autenticada.

        Es la sonda de salud: la llamada más barata que además confirma que las credenciales
        siguen siendo válidas. Un ``401`` aquí se traduce a ``JiraAuthError``, que distingue
        "Jira caído" de "credenciales revocadas".
        """
        return await self._request("GET", MYSELF_PATH, timeout=timeout)

    async def search_page(
        self,
        jql: str,
        *,
        next_page_token: str | None = None,
        page_size: int = PAGE_SIZE,
    ) -> dict[str, Any]:
        """Recupera una página de resultados de JQL.

        ``nextPageToken`` se omite en la primera llamada a propósito: enviarlo vacío o nulo
        provoca ``400``.
        """
        params: dict[str, Any] = {
            "jql": jql,
            "maxResults": page_size,
            "fields": ",".join(DEFAULT_ISSUE_FIELDS),
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        return await self._request("GET", SEARCH_JQL_PATH, params=params)

    async def iter_issues(
        self, jql: str, *, max_issues: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Itera todos los issues que devuelve un JQL, página a página (RF-4.3).

        Encapsula la paginación para que el servicio consuma issues sin saber cómo se paginan.
        Si Jira vuelve a cambiar el mecanismo, cambia solo este método.

        Corta por cuatro vías, no solo por ``isLast``:

        1. ``isLast`` verdadero.
        2. Ausencia de ``nextPageToken``.
        3. Página sin issues, que indica que no hay más que recoger.
        4. Token repetido o tope de páginas, que son las defensas contra el encadenamiento
           infinito documentado en este endpoint.
        """
        token: str | None = None
        seen_tokens: set[str] = set()
        emitted = 0

        for page_number in range(1, self._max_pages + 1):
            payload = await self.search_page(jql, next_page_token=token)
            issues = payload.get("issues") or []

            if not issues:
                logger.info("JQL sin más resultados en la página %d", page_number)
                return

            for issue in issues:
                yield issue
                emitted += 1
                if max_issues is not None and emitted >= max_issues:
                    logger.info("Alcanzado el tope de %d issues solicitado", max_issues)
                    return

            if payload.get("isLast") is True:
                return

            token = payload.get("nextPageToken") or None
            if token is None:
                return

            if token in seen_tokens:
                # Defensa contra el bucle infinito: Jira ha repetido un token ya usado.
                logger.warning(
                    "Jira repitió un token de paginación; se detiene la recogida tras "
                    "%d páginas",
                    page_number,
                )
                return
            seen_tokens.add(token)

        logger.warning(
            "Se alcanzó el tope de %d páginas; la recogida se detiene por seguridad",
            self._max_pages,
        )


async def close_jira_http_client(client: httpx.AsyncClient | None) -> None:
    """Cierra el cliente HTTP. Un fallo al apagar se registra y no se propaga."""
    if client is None:
        return
    try:
        await client.aclose()
    except Exception as error:  # noqa: BLE001 - el apagado nunca debe romper
        logger.warning("Fallo al cerrar el cliente de Jira: %s", type(error).__name__)
