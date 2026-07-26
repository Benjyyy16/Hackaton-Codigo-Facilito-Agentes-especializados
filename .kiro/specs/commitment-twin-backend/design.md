# Commitment Twin — Backend: Diseño

## 1. Principio rector

Una única regla de dependencia, hacia dentro:

```
api/routes  →  services  →  repositories  →  integrations/supabase
                  ↓
               agents (puros)
                  ↓
               schemas
```

Consecuencias que se aplican sin excepción:

- Las rutas traducen HTTP a llamadas de servicio. No contienen reglas de negocio.
- Los servicios orquestan. No construyen consultas ni tocan el cliente de Supabase.
- Los repositorios son el único lugar donde aparece `client.table(...)`.
- Los agentes son funciones puras sobre datos estructurados. No importan `fastapi` ni
  `supabase`. Esto es lo que permite sustituirlos por un LLM más adelante sin tocar nada más.
- `integrations/` es el único lugar donde vive el conocimiento de APIs externas.

## 2. Árbol de módulos

```
app/
    main.py                     app factory, lifespan, registro de routers y handlers
    api/
        deps.py                 dependencias FastAPI (cliente, repos, servicios)
        routes/
            health.py           GET  /health
            webhooks.py         POST /webhooks/jira
            jira.py             POST /jira/sync
            events.py           GET  /events, GET /events/{event_id}
            alerts.py           GET  /alerts, GET /alerts/{alert_id}
            analysis.py         POST /analysis/run
    core/
        config.py               Settings (pydantic-settings) + SecretStr
        logging.py              configuración central, filtro de secretos
        exceptions.py           jerarquía de errores de dominio + handlers
    schemas/
        common.py               Page, HealthResponse, envolturas
        jira.py                 payload de webhook, issue normalizado
        events.py               EventCreate, EventRead
        commitments.py          CommitmentRead
        analysis.py             contratos de agentes y de análisis
        alerts.py               AlertRead
        ws.py                   sobre de mensajes WebSocket
    repositories/
        base.py                 BaseRepository (CRUD + soft delete + paginación)
        projects.py             ProjectRepository
        jira_events.py          JiraEventRepository
        commitments.py          CommitmentRepository
        risk_analyses.py        RiskAnalysisRepository
        alerts.py               AlertRepository
    services/
        health_service.py       estado del servicio y de dependencias
        jira_sync_service.py    sincronización inicial por JQL
        webhook_service.py      validación, normalización, dedupe, persistencia
        analysis_service.py     invoca orquestador, persiste, decide alerta, difunde
        alert_service.py        alta, actualización y resolución de alertas
    agents/
        base.py                 protocolo Agent, AgentContext, AgentOutcome
        commitment_agent.py     CommitmentAgent
        technical_agent.py      TechnicalAgent
        financial_agent.py      FinancialAgent
        risk_agent.py           RiskAgent
        orchestrator.py         OrchestratorAgent
    integrations/
        jira/
            client.py           cliente httpx, auth, reintentos, timeouts
            normalizer.py       payload de Jira → modelo interno
            security.py         validación del secreto de webhook
        supabase/
            client.py           ciclo de vida del AsyncClient
    websocket/
        manager.py              ConnectionManager
        routes.py               WS /ws/events
    tests/
```

## 3. Configuración

`core/config.py` expone un único objeto `Settings`. Los secretos se declaran como
`SecretStr`, de modo que la representación por defecto los ofusca y un log accidental del
objeto no filtra nada (RF-1.4, RNF-1.1).

| Variable | Obligatoria | Notas |
| --- | --- | --- |
| `SUPABASE_URL` | sí | URL del proyecto |
| `SUPABASE_SERVICE_ROLE_KEY` | sí | uso exclusivo servidor, nunca en respuestas |
| `SUPABASE_ANON_KEY` | no | reservada para el futuro flujo con JWT de usuario |
| `JIRA_BASE_URL` | sí | `https://<org>.atlassian.net` |
| `JIRA_EMAIL` | sí | cuenta del API token |
| `JIRA_API_TOKEN` | sí | Basic auth |
| `JIRA_WEBHOOK_SECRET` | sí | secreto compartido del webhook |
| `RISK_ALERT_THRESHOLD` | no | por defecto `70`, rango 0–100 |
| `HTTP_TIMEOUT_SECONDS` | no | por defecto `10.0` |
| `HTTP_MAX_RETRIES` | no | por defecto `3` |
| `ENV` | no | `development` por defecto |
| `LOG_LEVEL` | no | `INFO` por defecto |

La carga usa `.env` con precedencia del entorno real del proceso. Falta de una variable
obligatoria significa fallo en el arranque, no un valor por defecto silencioso.

Sobre las claves de Supabase: el backend escribe con la clave de service role porque opera
como servicio de confianza y necesita saltarse RLS. La contrapartida es que RLS debe quedar
activo y sin políticas permisivas para `anon`, de modo que la clave anónima no dé acceso a
estas tablas. Queda registrado como decisión y no como descuido.

## 4. Modelo de datos

Cinco tablas. UUID como clave primaria, `created_at` y `updated_at` en todas, `deleted_at`
solo donde el borrado lógico tiene sentido de negocio (RF-7.3, RF-7.4).

```
projects
  id                uuid pk
  jira_project_key  text unique not null
  name              text not null
  hourly_cost       numeric(12,2) not null default 0     -- coste/hora para el cálculo financiero
  created_at, updated_at, deleted_at

jira_events
  id                uuid pk
  project_id        uuid fk → projects(id)
  jira_issue_id     text not null
  jira_issue_key    text not null
  event_type        text not null                        -- issue_created | issue_updated | comment_created
  fingerprint       text unique not null                 -- clave de deduplicación
  occurred_at       timestamptz not null
  raw_payload       jsonb not null                       -- payload original íntegro (RF-5.6)
  created_at, updated_at

commitments
  id                uuid pk
  project_id        uuid fk → projects(id)
  jira_issue_key    text not null
  title             text not null
  due_date          timestamptz null
  status            text not null                        -- open | at_risk | breached | met
  estimated_hours   numeric(10,2) null
  created_at, updated_at, deleted_at
  unique (project_id, jira_issue_key)

risk_analyses
  id                uuid pk
  event_id          uuid fk → jira_events(id) null
  commitment_id     uuid fk → commitments(id) null
  risk_score        integer not null                     -- 0..100
  severity          text not null                        -- low | medium | high | critical
  is_partial        boolean not null default false       -- algún agente falló (RF-8.6)
  findings          jsonb not null                      -- salida por agente
  created_at, updated_at

alerts
  id                uuid pk
  commitment_id     uuid fk → commitments(id) null
  risk_analysis_id  uuid fk → risk_analyses(id)
  severity          text not null
  reason            text not null
  financial_impact  numeric(14,2) not null default 0
  status            text not null                        -- open | resolved
  resolved_at       timestamptz null
  created_at, updated_at, deleted_at
```

Índices: `jira_events(fingerprint)` único, `jira_events(project_id, occurred_at desc)` para
el listado paginado, `alerts(status, severity)` para el filtrado, y un índice parcial
`alerts(commitment_id, reason) where status = 'open'` que respalda la actualización de
alerta abierta en lugar de duplicarla (RF-9.3).

`updated_at` se mantiene con un trigger, no desde la aplicación, para que ninguna escritura
pueda olvidarlo.

El esquema vive en `db/schema.sql` como script idempotente (`create table if not exists`).
Se aplica a mano desde el editor SQL de Supabase. No hay herramienta de migraciones porque
Alembic está excluido del stack; a cambio, el script debe poder reejecutarse sin efectos.

## 5. Capa de repositorios

`BaseRepository` concentra lo repetitivo y deja a las subclases solo sus consultas propias:

```python
class BaseRepository:
    table_name: ClassVar[str]
    soft_delete: ClassVar[bool] = False

    def __init__(self, client: AsyncClient) -> None: ...

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def get(self, entity_id: UUID) -> dict[str, Any] | None: ...
    async def update(self, entity_id: UUID, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def soft_delete_by_id(self, entity_id: UUID) -> None: ...
    async def list_page(self, *, limit: int, offset: int, filters: dict, order: str) -> Page: ...
```

Detalles que importan:

- Cuando `soft_delete` está activo, toda lectura añade `.is_("deleted_at", "null")`. El
  filtrado por borrado lógico no queda a criterio de quien llama (RF-7.4).
- La paginación usa `.range(offset, offset + limit - 1)` con `count="exact"`, de modo que
  la respuesta puede informar el total.
- Todo error de `postgrest` se captura y se traduce a excepción de dominio. El código
  PostgreSQL `23505` (violación de unicidad) se traduce a `DuplicateEventError`, que el
  servicio de webhook interpreta como duplicado y no como fallo (RF-6.4).

## 6. Integración con Jira

### 6.1 Cliente

Un `httpx.AsyncClient` de vida larga, creado en el `lifespan` y reutilizado. Crear un
cliente por petición desperdiciaría el pool de conexiones.

- Auth: `httpx.BasicAuth(email, api_token)`.
- Timeout: `httpx.Timeout(connect=..., read=..., write=..., pool=...)` explícito (RF-3.2).
- Reintentos, implementados en el cliente y no delegados a `httpx`:
  - `429` → esperar lo que indique `Retry-After`, reintentar hasta el máximo (RF-3.3).
  - `5xx` → espera exponencial con jitter (RF-3.4).
  - `401`/`403` → `JiraAuthError` inmediato, sin reintento (RF-3.5).
  - `404` → `JiraNotFoundError`, sin reintento.
  - agotados los reintentos → `JiraUnavailableError` (RF-3.6).
- Los logs registran método, ruta y código de estado. Nunca cabeceras (RF-3.7).

### 6.2 Búsqueda por JQL

Resuelto contra la documentación de Atlassian, y con consecuencias concretas:

- El endpoint clásico `/rest/api/3/search` **ya no existe**: fue retirado y responde
  `410 Gone`. El vigente es `/rest/api/3/search/jql`.
- La paginación usa `nextPageToken` e `isLast`. Desaparecen `startAt` y `total`, así que no
  se puede saber de antemano cuántas páginas hay ni informar de un total.
- La primera llamada **no** debe enviar `nextPageToken`; enviarlo produce `400`.
- El endpoint devuelve un conjunto mínimo de campos si no se piden explícitamente, así que
  `fields` es obligatorio en la práctica: sin él el análisis se queda sin señales.

Hay casos documentados en los que `isLast` nunca llega a `true` y los tokens se encadenan
indefinidamente, dejando integraciones en bucle infinito. Por eso `iter_issues(jql)` no
confía solo en `isLast` y corta por cuatro vías: `isLast`, ausencia de token, página vacía, y
las dos defensas propias, token ya visto y tope duro de páginas.

El servicio consume issues sin saber cómo se paginan. Si Atlassian vuelve a cambiar el
mecanismo, cambia solo este método.

### 6.3 Normalización

`normalizer.py` convierte el payload de Jira en un `NormalizedEvent` de Pydantic: clave y
id del issue, tipo de evento, instante del cambio, resumen, estado, asignado, fecha de
vencimiento, estimación y el payload original intacto. El resto del sistema solo conoce
`NormalizedEvent`. Un cambio de forma en Jira se absorbe aquí.

### 6.4 Validación del webhook

Jira Cloud no firma los webhooks con HMAC, así que no hay firma que verificar. El mecanismo
es un secreto compartido que este backend define y que se configura en Jira al registrar el
webhook: llega en la cabecera `X-Hook-Secret` o, si Jira solo permite URL, en un parámetro
de consulta. La comparación usa `hmac.compare_digest` para no filtrar información por
tiempo de respuesta. Sin secreto válido: `401`, y ni se persiste ni se procesa (RF-5.2).

### 6.5 Deduplicación

```
fingerprint = sha256(f"{jira_issue_id}:{event_type}:{occurred_at_iso}")
```

Determinística y estable. Se comprueba antes de insertar y, sobre todo, la protege una
restricción de unicidad en la tabla: dos webhooks simultáneos con el mismo contenido no
pueden colarse por una condición de carrera, porque la segunda inserción falla en la base
de datos y se trata como duplicado (RF-6.2, RF-6.3, RF-6.4).

## 7. Flujo del webhook

```
POST /webhooks/jira
  │
  ├─ validar secreto ──────────── inválido → 401, fin
  ├─ parsear y normalizar ─────── no soportado → 202 descartado
  ├─ calcular fingerprint
  ├─ persistir evento ─────────── duplicado → 200 duplicated
  ├─ registrar BackgroundTask
  └─ 200  (respuesta a Jira, rápida)

BackgroundTask (fuera del ciclo petición/respuesta)
  ├─ upsert del compromiso derivado del issue
  ├─ OrchestratorAgent.run(context)
  ├─ persistir risk_analysis
  ├─ alta / actualización / resolución de alerta según umbral
  └─ broadcast por WebSocket
```

Dos decisiones explícitas:

- El evento se persiste **antes** del análisis. Si el análisis falla, el evento sigue
  registrado y el fallo queda en el log; no se pierde información (RF-5.8).
- `BackgroundTasks` de FastAPI es suficiente para el MVP y evita Redis y Celery, que están
  descartados. Su límite conocido es que las tareas viven en el proceso: un reinicio pierde
  las pendientes. Aceptable para una demo, y la frontera queda aislada en
  `analysis_service` para poder cambiar el mecanismo sin tocar el resto.

## 8. Agentes

Contrato común, deliberadamente estrecho:

```python
class AgentContext(BaseModel):
    event: NormalizedEvent
    commitment: CommitmentSnapshot | None
    project: ProjectSnapshot | None
    now: datetime

class AgentOutcome(BaseModel):
    agent: str
    score: int = Field(ge=0, le=100)     # contribución al riesgo
    signals: list[Signal]                # hallazgos legibles
    detail: dict[str, Any]

class Agent(Protocol):
    name: str
    def run(self, context: AgentContext) -> AgentOutcome: ...
```

Sin `async`, sin E/S, sin dependencias del framework. Un agente es una función de datos a
datos, lo que lo hace testeable sin red ni base de datos (RF-8.3, RF-8.4).

Reglas determinísticas del MVP:

| Agente | Qué observa | Señales |
| --- | --- | --- |
| `CommitmentAgent` | vencimiento, estado, reapertura | vencido, vence en menos de N días, sin fecha, reabierto |
| `TechnicalAgent` | transiciones, actividad, bloqueos | bloqueado, sin asignar, estancado, muchas reasignaciones |
| `FinancialAgent` | estimación y coste/hora del proyecto | horas en riesgo × coste/hora → impacto estimado |
| `RiskAgent` | las salidas anteriores | combinación ponderada → 0–100 y severidad |
| `OrchestratorAgent` | todo | ejecuta, agrega, tolera fallos parciales |

`RiskAgent` combina con pesos declarados como constantes con nombre, no con números
sueltos, para que el umbral de alerta sea razonable y auditable. Severidad por tramos:
`<40` bajo, `40–59` medio, `60–79` alto, `>=80` crítico.

El orquestador envuelve cada agente en su propio try/except: un agente que revienta se
registra, su contribución se omite y el análisis se marca `is_partial=True` en lugar de
tumbar el flujo completo (RF-8.6).

Sustituir un agente por Bedrock más adelante significa escribir una clase nueva que cumpla
el mismo protocolo. Ningún servicio cambia.

## 9. Alertas

`alert_service` aplica el umbral configurable:

- `risk_score >= RISK_ALERT_THRESHOLD` y no hay alerta abierta para ese compromiso y motivo
  → crear.
- `risk_score >= umbral` y ya hay una abierta → actualizar severidad, motivo e impacto
  (RF-9.3).
- `risk_score < umbral` y hay una abierta → resolver con `resolved_at` (RF-9.4).

El impacto económico lo aporta `FinancialAgent`. No se recalcula en el servicio, para que
exista un solo lugar donde vive esa fórmula.

## 10. WebSocket

`ConnectionManager` mantiene el conjunto de conexiones activas protegido por un
`asyncio.Lock`, porque conexiones y desconexiones concurrentes mutan el conjunto.

```python
async def connect(ws: WebSocket) -> None
async def disconnect(ws: WebSocket) -> None
async def broadcast(message: WsMessage) -> None
```

`broadcast` envía a cada cliente dentro de su propio try/except y recoge los que fallan para
retirarlos después. Un socket muerto no impide la entrega al resto (RF-12.4). Sin clientes
conectados, `broadcast` no es un error: simplemente no hay a quién enviar (RF-12.5).

Los mensajes son sobres tipados:

```json
{ "type": "analysis.completed", "data": { ... }, "emitted_at": "..." }
```

Tipos previstos: `event.created`, `analysis.completed`, `alert.created`,
`alert.resolved`. El tipo declarado permite al consumidor discriminar sin inspeccionar la
forma de la carga (RF-12.6).

En ningún punto del diseño hay polling.

## 11. Errores

Jerarquía en `core/exceptions.py`, con una única traducción a HTTP registrada como
manejadores de excepción en la app:

| Excepción | HTTP |
| --- | --- |
| `EntityNotFoundError` | 404 |
| `DuplicateEventError` | 200 con marca de duplicado |
| `WebhookAuthError` | 401 |
| `JiraAuthError` | 502 |
| `JiraNotFoundError` | 404 |
| `JiraUnavailableError` | 502 |
| `SupabaseError` | 503 |
| `ValidationError` de Pydantic | 422 |

Las rutas no construyen `HTTPException`. Elevan errores de dominio y los manejadores hacen
la traducción, que es lo que mantiene el mapeo en un solo sitio.

El cuerpo de error es uniforme: `{"error": {"code": ..., "message": ..., "request_id": ...}}`.
Nunca incluye detalle interno ni valores de configuración.

## 12. Observabilidad

Un middleware asigna un `request_id` a cada petición, lo propaga por `contextvars` y lo
devuelve en la cabecera de respuesta. El formateador de logs lo incluye, de forma que las
líneas de una misma petición y las de su tarea en segundo plano se pueden correlacionar
(RNF-2.2).

`logging.py` instala además un filtro que redacta patrones de secreto conocidos. Es una
segunda barrera; la primera es que los secretos son `SecretStr` y no se imprimen solos.

## 13. Preparación para JWT

No se implementa autenticación de usuario, pero se deja el hueco: una dependencia
`get_current_principal` en `api/deps.py` que hoy devuelve un principal de servicio y mañana
valida un JWT. Las rutas ya la declaran, así que activar la autenticación no obliga a
reescribir firmas (RNF-1.6).

## 14. Estrategia de tests

Sin red y sin instancias reales (RNF-4.2).

- Agentes: entrada y salida directas. Es la capa más valiosa de testear y la más barata,
  precisamente porque es pura.
- Repositorios: doble del `AsyncClient` de Supabase que registra las llamadas encadenadas y
  devuelve respuestas preparadas.
- Cliente de Jira: `httpx.MockTransport`, que permite ejercitar `429`, `5xx` y `401` de
  verdad, incluida la lógica de reintentos.
- Rutas: `httpx.ASGITransport` con `ASGITransport` sobre la app y las dependencias
  sobrescritas mediante `dependency_overrides`.
- WebSocket: `TestClient.websocket_connect` para conexión, difusión y desconexión.

Las pruebas de tiempo inyectan `now` a través de `AgentContext` en lugar de parchear
`datetime`, lo que hace que los casos de vencimiento sean deterministas.

## 15. Deuda asumida y puntos a confirmar

Registrado de forma explícita para que nadie lo descubra por sorpresa:

1. `BackgroundTasks` pierde tareas pendientes si el proceso se reinicia. Aceptado para el
   MVP; la frontera está aislada.
2. El esquema se aplica a mano en Supabase. Sin migraciones versionadas, el script
   idempotente es la única red de seguridad.
3. ~~La forma exacta de la paginación por JQL en Jira Cloud se confirma contra credenciales
   reales.~~ **Resuelto**: ver 6.2. El endpoint clásico está retirado y la paginación es por
   `nextPageToken`. Queda por confirmar contra credenciales reales únicamente el
   comportamiento observado de `isLast`, para el que ya existen dos defensas.
4. El coste/hora por proyecto se introduce a mano. Sin él, el impacto económico es cero y
   las alertas pierden su argumento más fuerte.
5. Los pesos del riesgo son una primera aproximación. Sirven para demostrar el mecanismo, no
   son un modelo calibrado.
6. El scaffold plano actual en la raíz (`config.py`, `db.py`, `main.py`) se sustituye por
   `app/`. `main.py` usa además `@app.on_event`, que está obsoleto; se reemplaza por
   `lifespan`.
