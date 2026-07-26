# Datgent Backend — Diseño

## 1. Arquitectura

Regla de dependencia única, hacia dentro:

```
api/routes  →  services  →  repositories  →  integrations/supabase
                   ↓
               agents (puros, sin I/O)
                   ↓
               schemas/domain
```

Providers (`providers/`) implementan protocolos definidos en `providers/base.py`. La lógica de negocio depende del protocolo, nunca del concreto.

## 2. Modelo de datos — 12 tablas

```
1.  projects              — raíz, agrupa compromisos y conexiones
2.  commitments           — entidad CENTRAL, todo cuelga de ella
3.  provider_connections  — estado de cada integración por proyecto
4.  source_events         — eventos crudos deduplicados por event_hash
5.  agent_runs            — ejecución de un agente, unidad de auditoría
6.  findings              — hallazgo concreto de un agente
7.  evidence              — dato observable que respalda un finding
8.  risk_cases            — riesgo consolidado (salida del orquestador)
9.  alerts                — aviso cuando score cruza umbral
10. decisions             — acción propuesta pendiente de aprobación
11. timeline_events       — historia legible de un compromiso
12. documents             — fragmentos para RAG
```

Plus tabla legacy: `integrations` (OAuth por usuario).

### Convenciones SQL

- UUID pk generado en BD (`gen_random_uuid()`).
- `created_at` + `updated_at` en todas, `updated_at` por trigger.
- `deleted_at` solo donde borrado lógico tiene sentido (projects, commitments, alerts).
- RLS activo sin políticas permisivas. Backend usa service role.
- Checks cerrados coinciden con enums Python. Divergencia = error en inserción (deseado).

## 3. Flujo del orquestador

```
Evento recibido (webhook / sync)
  │
  ├─ Validar autenticidad (HMAC / secreto)
  ├─ Normalizar → ExternalEvent
  ├─ Calcular event_hash, deduplicar
  ├─ Persistir en source_events (ANTES del análisis)
  ├─ Responder al caller (rápido)
  │
  └─ BackgroundTask:
       ├─ Resolver commitment afectado
       ├─ Construir AgentContext (snapshot + eventos recientes)
       ├─ OrchestratorAgent.run():
       │    ├─ CommitmentAgent.run(ctx)  — vencimiento, reapertura
       │    ├─ TechnicalAgent.run(ctx)   — bloqueos, estancamiento
       │    ├─ FinancialAgent.run(ctx)   — exposición económica
       │    └─ RiskAgent.run(outputs)    — combinación ponderada
       │    Cada uno en try/except. Fallo → is_partial=True.
       │
       ├─ Persistir AgentRun + Findings + Evidence
       ├─ Persistir RiskCase (cadena causal, pre-mortem, escenarios)
       ├─ Evaluar umbral de alerta → crear/actualizar/resolver
       ├─ Registrar timeline_event
       └─ Broadcast WebSocket
```

## 4. Contrato de agentes

```python
class AgentContext(BaseModel):
    commitment: CommitmentSnapshot  # frozen
    project: ProjectSnapshot        # frozen
    recent_events: list[SourceEventRead]
    now: datetime

class AgentOutput(BaseModel):
    agent: str
    risk_score: RiskScore           # 0-100
    severity: Severity
    confidence: Confidence          # 0.0-1.0
    findings: list[Finding]
    evidence: list[Evidence]
    missing_information: list[str]
    recommended_actions: list[RecommendedAction]
    requires_human_approval: bool = False
```

## 5. Providers

Dos protocolos en `providers/base.py`:

- `EventSourceProvider` — Jira, GitHub, Notion, Slack, Vercel: `connect`, `health`, `sync`, `fetch_events`, `verify_webhook`, `parse_webhook`.
- `StorageProvider` — Supabase: `connect`, `health`, `close`, `repositories()`.

`ProviderRegistry` en `providers/registry.py`: registra, conecta, cierra todos. Solo se registra el provider cuyas credenciales están presentes.

## 6. LLM

Los agentes actuales son determinísticos (reglas). Están diseñados para sustituirse por LLM sin cambiar el protocolo:
- Misma entrada (`AgentContext`), misma salida (`AgentOutput`).
- El LLM viviría dentro de un agente nuevo que implemente el mismo `Protocol`.
- `model` y `prompt_version` en `agent_runs` permiten auditar qué versión produjo cada resultado.

## 7. WebSocket

`ConnectionManager` con `asyncio.Lock`:
- `broadcast(message)` envía a todos; un socket muerto se retira sin afectar al resto.
- Tipos de mensaje: `event.created`, `analysis.completed`, `alert.created`, `alert.resolved`.

## 8. Decisiones de diseño

| Decisión | Razón |
|---|---|
| Un módulo `domain.py` para 12 repos | Son delgados (~20 líneas cada uno); 12 archivos de 20 líneas dificultan ver el modelo |
| `CommitmentSnapshot` frozen | Un agente no puede alterar el contexto que otro va a leer |
| `BackgroundTasks` y no Celery | Suficiente para MVP, sin infra extra. Frontera aislada para sustituir |
| `event_hash` único en BD | La deduplicación la cierra la base de datos, no la app (race condition) |
| Pesos como constantes nombradas | Auditables, no números mágicos en fórmulas |
| `ilike` en lugar de full-text para RAG | Funciona sin depender de que el índice FTS esté creado |
| Errores de dominio → handlers centrales | Un solo lugar para el mapeo exception → HTTP status |
| CORS `*` solo en dev | El middleware ya está; en prod se restringe a FRONTEND_URL |
