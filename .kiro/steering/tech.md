---
inclusion: auto
---

# Stack Técnico

## Obligatorio

| Tecnología | Rol | Por qué |
|---|---|---|
| Python 3.12+ | Lenguaje | Tipado gradual, async nativo, ecosistema ML/LLM maduro |
| FastAPI | Framework HTTP | Validación automática con Pydantic, OpenAPI gratis, async |
| Pydantic v2 | Schemas / validación | 5–50× más rápido que v1, `model_config`, `ConfigDict` |
| Supabase (supabase-py) | Base de datos + RLS | PostgREST, Realtime, auth integrada, sin infra propia |
| httpx | Cliente HTTP | Async, pool de conexiones, `MockTransport` para tests |
| WebSockets (FastAPI) | Difusión en tiempo real | Sin polling; el frontend se entera al instante |
| BackgroundTasks (FastAPI) | Trabajo en segundo plano MVP | Sin broker externo; la frontera está aislada para sustituirlo |
| pytest | Tests | Fixtures, parametrize, async nativo con `pytest-asyncio` |

## Prohibido

| Tecnología | Razón de exclusión |
|---|---|
| Django | Monolítico, ORM acoplado, no aporta sobre FastAPI para APIs puras |
| Flask | Sync por defecto, sin validación integrada, inferior a FastAPI en todo lo que necesitamos |
| Firebase | Vendor lock-in de Google, Firestore no soporta joins ni restricciones SQL |
| SQLite | Sin concurrencia real, sin RLS, no escala a producción multiusuario |
| SQLAlchemy | Capa de abstracción innecesaria: Supabase ya expone PostgREST y el repo pattern basta |
| Alembic | Sin ORM no hay modelo declarativo que migrar; el script SQL idempotente es la red |
| Redis | Añade infra operativa para un estado que cabe en PostgreSQL y en memoria del proceso |
| Celery | Requiere broker (Redis/RabbitMQ), complejidad operativa desproporcionada para el MVP |

## Reglas derivadas

- Toda dependencia nueva debe justificarse en el PR. Si existe alternativa en el stack actual, se usa esa.
- Versiones pinneadas en `requirements.txt` / `pyproject.toml`. Sin rangos abiertos.
- Los tests corren sin red: `httpx.MockTransport`, fakes de Supabase, fixtures deterministas.
