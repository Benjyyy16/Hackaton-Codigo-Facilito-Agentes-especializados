# Datgent — Backend

Sistema multi-agente que detecta compromisos en riesgo a partir de señales de Jira, GitHub, datos financieros y la base de datos Supabase. La entidad central es **Commitment**: una promesa con fecha, dueño y exposición financiera.

## Problema que resuelve

Los equipos rompen compromisos por acumulación silenciosa de señales aisladas: un sprint que resbala, un PR estancado, un gasto que se desborda. Ningún sistema observa TODO a la vez. Datgent lo hace con 4 agentes especializados y un orquestador que produce un **RiskCase** con cadena causal, pre-mortem y 3 escenarios.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Vercel)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / WebSocket
┌──────────────────────────────▼──────────────────────────────────┐
│                        FastAPI (este repo)                        │
│                                                                   │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐ │
│  │  Routes   │→│  Services   │→│   Agents    │→│  LLM (GPT)   │ │
│  └──────────┘  └─────┬──────┘  └────────────┘  └─────────────┘ │
│                       │                                           │
│  ┌────────────────────▼─────────────────────────────────────────┐│
│  │              Repositories (Supabase via postgrest)            ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────┐  ┌──────────────────────────────────────────┐  │
│  │  WebSocket   │  │  Providers (Jira, GitHub, Slack, etc.)   │  │
│  │  /ws/events  │  └──────────────────────────────────────────┘  │
│  └─────────────┘                                                  │
└──────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Supabase (Postgres) │
                    │   12 tablas + RLS    │
                    └─────────────────────┘
```

### Flujo del orquestador

```
Webhook/Trigger → IngestService → deduplicar → persistir SourceEvent
                                             ↓
                              AnalysisService.analyze_commitment
                                             ↓
                    ┌─────────────────────────────────────────┐
                    │  4 agentes especializados (en paralelo)  │
                    │  ┌────────┐ ┌──────┐ ┌───────┐ ┌────┐  │
                    │  │  Jira  │ │ Code │ │Finance│ │ DB │  │
                    │  └────────┘ └──────┘ └───────┘ └────┘  │
                    └──────────────────┬──────────────────────┘
                                       ↓
                              RiskOrchestrator (LLM)
                              → cadena causal
                              → pre-mortem
                              → 3 escenarios (best/likely/worst)
                              → score 0-100
                                       ↓
                              Persistir RiskCase + Findings
                                       ↓
                              Si score >= umbral → Alert
                                       ↓
                              Decision (requiere aprobación humana)
                                       ↓
                              Broadcast via WebSocket
```

## Agentes especializados

| Agente   | Observa                                    | Señales clave                            |
|----------|--------------------------------------------|------------------------------------------|
| Jira     | Issues, sprints, velocidad                 | Reapertura, estancamiento, scope creep   |
| Code     | PRs, commits, cobertura                    | PR bloqueado, sin reviewer, deuda alta   |
| Finance  | Presupuesto, gastos, flujo de caja         | Sobrecoste, burn rate, penalizaciones    |
| Database | Tablas, filas, performance                 | Crecimiento anómalo, queries lentas      |

## Requisitos

- Python 3.12+
- Cuenta de Supabase con proyecto activo
- (Opcional) OpenAI API key para análisis con LLM real

## Instalación

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # solo para tests
```

## Base de datos

Aplicar el esquema en la consola SQL de Supabase:

```bash
# Crear las 12 tablas, enums y triggers
cat db/schema.sql | pbcopy  # pegarlo en Supabase SQL Editor

# Rollback (destructivo)
cat db/rollback.sql
```

El esquema se aplica manualmente. No hay migraciones automáticas.

## Variables de entorno

Copiar `.env.example` a `.env` y rellenar. Las marcadas con ✓ son obligatorias.

| Variable | Obligatoria | Propósito |
|----------|:-----------:|-----------|
| `SUPABASE_URL` | ✓ | URL del proyecto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | ✓ | Clave service role (bypass RLS) |
| `SUPABASE_ANON_KEY` | | Clave anónima (futuro flujo JWT) |
| `SUPABASE_JWT_SECRET` | | Secreto JWT de Supabase |
| `JIRA_BASE_URL` | | URL de la instancia Jira Cloud |
| `JIRA_EMAIL` | | Email de la cuenta de servicio |
| `JIRA_API_TOKEN` | | API token de Jira |
| `JIRA_WEBHOOK_SECRET` | | Secreto compartido para webhooks |
| `GITHUB_TOKEN` | | PAT de GitHub |
| `GITHUB_WEBHOOK_SECRET` | | Secreto HMAC del webhook |
| `GITHUB_ORG` | | Organización de GitHub |
| `SLACK_BOT_TOKEN` | | Token del bot de Slack |
| `SLACK_WEBHOOK_URL` | | URL incoming webhook |
| `SLACK_CHANNEL` | | Canal de alertas (default: #alerts) |
| `VERCEL_TOKEN` | | Token de Vercel |
| `VERCEL_TEAM_ID` | | ID del equipo en Vercel |
| `NOTION_TOKEN` | | Token de integración Notion |
| `NOTION_DATABASE_ID` | | ID de la database en Notion |
| `OPENAI_API_KEY` | | Clave de OpenAI para agentes LLM |
| `OPENAI_MODEL` | | Modelo (default: gpt-4o-mini) |
| `OPENAI_TIMEOUT_SECONDS` | | Timeout del LLM (default: 30) |
| `APP_BASE_URL` | | URL pública del backend |
| `FRONTEND_URL` | | URL del frontend (CORS en prod) |
| `GITHUB_CLIENT_ID` | | OAuth app de GitHub |
| `GITHUB_CLIENT_SECRET` | | OAuth secret de GitHub |
| `GOOGLE_CLIENT_ID` | | OAuth de Google |
| `GOOGLE_CLIENT_SECRET` | | OAuth secret de Google |
| `NOTION_CLIENT_ID` | | OAuth de Notion |
| `NOTION_CLIENT_SECRET` | | OAuth secret de Notion |
| `SLACK_CLIENT_ID` | | OAuth de Slack |
| `SLACK_CLIENT_SECRET` | | OAuth secret de Slack |
| `VERCEL_CLIENT_ID` | | OAuth de Vercel |
| `VERCEL_CLIENT_SECRET` | | OAuth secret de Vercel |
| `RISK_ALERT_THRESHOLD` | | Score mínimo para alertar (default: 70) |
| `HTTP_TIMEOUT_SECONDS` | | Timeout HTTP global (default: 10) |
| `HTTP_MAX_RETRIES` | | Reintentos HTTP (default: 3) |
| `DEMO_MODE_ENABLED` | | Habilitar rutas /demo en producción |
| `ENV` | | development / staging / production / test |
| `LOG_LEVEL` | | DEBUG / INFO / WARNING / ERROR / CRITICAL |

## Arranque local

```bash
export PORT=8000
uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT
```

La app arranca degradada si Supabase no está disponible: `/health` reporta el estado.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Estado actual: **653 passed** (incluye 47 tests de seguridad).

## Endpoints

Agrupados por dominio. Ver `API.md` para detalle completo.

### Health
- `GET /health` — Estado del servicio
- `GET /ready` — Readiness probe

### Auth
- `POST /auth/register` — Registro
- `POST /auth/login` — Login
- `POST /auth/logout` — Logout
- `GET /auth/me` — Usuario actual
- `GET /auth/oauth/{provider}/login` — Iniciar OAuth login
- `GET /auth/oauth/{provider}/callback` — Callback OAuth login

### Commitments
- `GET /commitments` — Listar
- `POST /commitments` — Crear
- `GET /commitments/{id}` — Detalle
- `PATCH /commitments/{id}` — Actualizar
- `POST /commitments/{id}/analyze` — Disparar análisis
- `GET /commitments/{id}/findings` — Hallazgos
- `GET /commitments/{id}/timeline` — Cronología

### Risk Cases
- `GET /risk-cases` — Listar
- `GET /risk-cases/{id}` — Detalle
- `POST /risk-cases/{id}/reanalyze` — Reanalizar

### Alerts
- `GET /alerts` — Listar
- `PATCH /alerts/{id}/acknowledge` — Reconocer

### Decisions
- `GET /decisions` — Listar
- `POST /decisions/{id}/approve` — Aprobar
- `POST /decisions/{id}/reject` — Rechazar
- `POST /decisions/{id}/execute` — Ejecutar

### Agents
- `GET /agents` — Listar disponibles
- `GET /agents/status` — Estado
- `POST /agents/analyze` — Ejecutar análisis
- `POST /agents/chat` — Chat con agentes
- `GET /agent-runs/{id}` — Detalle de ejecución

### Documents
- `POST /documents` — Indexar documento
- `GET /documents/search` — Buscar por texto
- `GET /documents/{id}` — Obtener por ID

### Demo
- `POST /demo/seed` — Crear datos demo
- `POST /demo/simulate` — Simular análisis
- `DELETE /demo/reset` — Limpiar datos demo

### Providers & Integrations
- `GET /providers` — Providers registrados
- `POST /providers/{provider}/sync` — Sincronizar
- `GET /integrations` — Listar integraciones
- `POST /integrations/{provider}` — Vincular
- `DELETE /integrations/{provider}` — Desconectar
- `GET /integrations/{provider}/test` — Probar conexión

### OAuth
- `GET /oauth/{provider}/authorize` — Iniciar flujo OAuth
- `GET /oauth/{provider}/callback` — Callback OAuth

### Finance
- `POST /finance/upload` — Subir Excel/CSV financiero
- `POST /finance/erp` — Conectar ERP

### Webhooks
- `POST /webhooks/{provider}` — Recibe evento de un provider

### WebSocket
- `WS /ws/events` — Canal de eventos en tiempo real

## Reproducir el caso demo

```bash
# 1. Arrancar el backend
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

# 2. Crear datos de seed
curl -X POST http://localhost:8000/demo/seed

# 3. Simular análisis (dispara agentes + orquestador en background)
curl -X POST http://localhost:8000/demo/simulate

# 4. Observar resultado
curl http://localhost:8000/risk-cases

# 5. (Opcional) Conectar al WebSocket para ver eventos en tiempo real
websocat ws://localhost:8000/ws/events

# 6. Limpiar
curl -X DELETE http://localhost:8000/demo/reset
```

Las rutas `/demo/*` solo responden si `ENV != production` o `DEMO_MODE_ENABLED=true`.

## Despliegue en Render

El archivo `render.yaml` contiene la configuración blueprint. Para desplegar:

1. Conectar el repo en Render
2. Configurar las variables de entorno (secretos con `sync: false`)
3. El start command ya apunta a la factoría: `uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT`

## Limitaciones y deuda técnica asumida

- **BackgroundTasks pierde trabajo al reiniciar**: los análisis en curso se pierden si el proceso se reinicia. Una cola persistente (Celery, ARQ) resolvería esto, pero para el hackathon es aceptable.
- **Esquema aplicado a mano**: no hay migraciones automáticas. Se ejecuta `db/schema.sql` manualmente en Supabase SQL Editor.
- **pgvector es opcional**: la búsqueda de documentos usa fulltext con fallback a `ilike`. Los embeddings requieren habilitar la extensión pgvector en Supabase.
- **Ejecutores de Decision vacíos por diseño**: `POST /decisions/{id}/execute` registra la decisión como ejecutada pero no dispara acciones reales (e.g., cerrar PR, mover issue). Los ejecutores por `ActionType` están previstos pero no implementados.
- **CORS abierto en desarrollo**: en producción se restringe a `FRONTEND_URL` solamente.
- **Rate limiting no implementado**: los webhooks no tienen rate limit a nivel de aplicación; se confía en el rate limit del proveedor de hosting.
