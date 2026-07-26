# Prompt: Continuar el backend Datgent

## Contexto

Datgent es un sistema multiagente que detecta compromisos empresariales en riesgo correlacionando señales de Jira, GitHub, Finanzas y Supabase. La entidad central es **Commitment**: todos los agentes analizan el MISMO compromiso.

## Estado actual

- Fase 0 completada: auditoría + 7 tests arreglados, 234 passed.
- Fase 1 completada: dominio Commitment + 12 tablas SQL + schemas Pydantic + 12 repositorios + 31 tests, 265 passed.
- Fases 2–9 pendientes (ver `.kiro/specs/datgent-backend/tasks.md`).

## Stack

Python 3.12+, FastAPI, Pydantic v2, Supabase (supabase-py), httpx, WebSockets, BackgroundTasks, pytest.

**PROHIBIDO**: Django, Flask, Firebase, SQLite, SQLAlchemy, Alembic, Redis, Celery.

## Qué hacer

1. Leer `tasks.md` y continuar con la siguiente fase no completada.
2. Leer el código existente ANTES de escribir — respetar convenciones.
3. Cada módulo nuevo debe:
   - Respetar la regla de dependencia (ver `steering/structure.md`).
   - Tener tests sin red.
   - Usar español en comentarios que expliquen POR QUÉ, no QUÉ.
4. Correr `pytest` después de cada cambio. Solo avanzar si pasa.
5. Actualizar `tasks.md` marcando lo completado.

## Reglas

- NO inventar funcionalidad que no exista en los requisitos (`requirements.md`).
- Los agentes son puros: sin I/O, sin imports de framework.
- Toda acción crítica requiere aprobación humana (vía Decision).
- Errores opacos: nunca filtrar internals al cliente.
- Secrets como `SecretStr`, comparaciones con `hmac.compare_digest`.

## Verificación

Después de cada fase:
```bash
cd /path/to/backend
python -m pytest app/tests/ -v --tb=short
```
