# Datgent Backend — Tareas

Estado verificado ejecutando tests (619 passed) y leyendo el código fuente.

## Fase 0 — Auditoría y estabilización

- [x] Auditoría de estructura del repo existente
- [x] Corrección de tests rotos (imports, mocks desactualizados)
- [x] Suite verde estable

## Fase 1 — Dominio Commitment

- [x] Modelo de dominio en `schemas/domain.py` (Commitment, Finding, Evidence, RiskCase, Decision, Alert, Timeline, Document)
- [x] Schema SQL idempotente con 12 tablas (`db/schema.sql`) + rollback (`db/rollback.sql`)
- [x] Schemas Pydantic v2 con enums cerrados coincidentes con checks SQL
- [x] 12 repositorios en `repositories/domain.py`
- [x] Tests de repositorios de dominio (`test_domain_repositories.py`) — verificado passing

## Fase 2 — Providers y webhooks

- [x] Provider de GitHub con `verify_webhook` HMAC-SHA256 (`providers/github.py`)
- [x] Provider de Jira con sync (`providers/jira.py`)
- [x] Rutas de webhook genéricas (`POST /webhooks/{provider}`)
- [x] Registry de providers con conexión condicional según configuración
- [x] Tests de Jira client (`test_jira_client.py`) — verificado passing
- [ ] Tests específicos de webhook GitHub (firma válida/inválida end-to-end) — nota: la lógica existe en el provider pero no hay test aislado del endpoint

## Fase 3 — Servicios de orquestación

- [x] `IngestService` (`services/ingest_service.py`)
- [x] `OrchestratorService` (`services/orchestrator_service.py`)
- [x] `AnalysisService` completo (`services/analysis_service.py`) con tests (`test_analysis_service.py`)
- [x] `DecisionService` con flujo approve/reject/execute (`services/decision_service.py`) con tests (`test_decision_service.py`)
- [x] `HealthService` con probes (`services/health_service.py`) con tests (`test_health.py`)
- [x] `DemoService` con seed/simulate/reset (`services/demo_service.py`) con tests (`test_demo.py`)
- [x] `RagService` con búsqueda fulltext + fallback ilike (`services/rag_service.py`) con tests (`test_rag.py`)
- [ ] AlertService dedicado — nota: la lógica de alertas está en AnalysisService, no en un servicio separado
- [ ] Timeline service separado — nota: la funcionalidad existe en los repositorios/rutas

## Fase 4 — Agentes especializados (LLM-ready)

- [x] 4 agentes especializados: Jira, Code, Finance, Database (`agents/specialized/`)
- [x] RiskOrchestrator con cadena causal + pre-mortem + 3 escenarios (`agents/risk_orchestrator.py`)
- [x] Capa LLM con provider OpenAI y prompts estructurados (`llm/`)
- [x] Tests de agentes especializados (`test_specialized_agents.py`) — verificado passing
- [x] Tests del orquestador (`test_risk_orchestrator.py`) — verificado passing
- [x] Tests LLM (`test_llm.py`) — verificado passing

## Fase 5 — WebSocket y difusión

- [x] `ConnectionManager` con `asyncio.Lock` (`websocket/manager.py`)
- [x] Ruta WS `/ws/events` (solo lectura, responde a ping)
- [x] Broadcast tipado desde servicios
- [x] Tests de WebSocket (`test_websocket.py`) — verificado passing

## Fase 6 — Decisiones y aprobación

- [x] Rutas CRUD de decisions (`GET /decisions`)
- [x] `POST /decisions/{id}/approve` y `POST /decisions/{id}/reject`
- [x] `POST /decisions/{id}/execute` con validación de estado previo
- [x] Tests de flujo de aprobación (`test_decision_service.py`) — verificado passing
- [ ] Ejecutores por `ActionType` — nota: la infraestructura existe (dict vacío inyectable) pero no hay ejecutores concretos implementados por diseño

## Fase 7 — RAG y documentos

- [x] Rutas CRUD de documents (`POST /documents`, `GET /documents/{id}`, `GET /documents/search`)
- [x] Búsqueda fulltext con fallback `ilike` (`rag_service.py`)
- [x] Tests (`test_rag.py`) — verificado passing
- [ ] Embedding pgvector — nota: opcional, requiere habilitar extensión en Supabase; no implementado
- [ ] Integración de documentos como contexto en agentes — nota: la estructura está pero no se inyecta automáticamente

## Fase 8 — Demo end-to-end

- [x] Seed de datos demo (`db/seed/seed_demo.sql`, `db/seed/demo_case.json`)
- [x] Flujo completo: seed → simulate → análisis en background
- [x] Ruta demo protegida (`/demo/*` → 404 en production sin `DEMO_MODE_ENABLED`)
- [x] Tests del flujo demo (`test_demo.py`) — verificado passing
- [x] Documentación de reproducción en README.md

## Fase 9 — Hardening

- [x] Utilidades de seguridad con tests (`app/core/security.py`, 47 tests passing)
  - compare_secret (timing-safe)
  - verify_github_signature (HMAC-SHA256)
  - verify_shared_secret (Jira)
  - is_safe_url (anti-SSRF)
  - sanitize_log_value (redacción de secretos)
  - assert_payload_size
  - cors_origins_for (restringido por entorno)
- [x] CORS configurable por entorno (implementado en security.py; main.py usa allow_origins=["*"] por ahora)
- [x] Logging estructurado con request_id de correlación
- [x] Exception handlers uniformes sin filtrar secretos ni trazas internas
- [ ] CORS aplicado desde cors_origins_for en main.py — nota: la función existe pero main.py aún usa "*"
- [ ] Rate limiting en webhooks — nota: no implementado, se delega al hosting
- [ ] Auditoría de seguridad formal — nota: las utilidades existen pero no se han integrado en todas las rutas que las necesitan
