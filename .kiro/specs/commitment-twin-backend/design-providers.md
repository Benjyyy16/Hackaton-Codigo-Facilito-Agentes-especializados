# Commitment Twin — Arquitectura de Providers

Addendum a `design.md`. Sustituye la sección 6 (integración con Jira) por un modelo en el que
Jira es solo el primer provider de varios.

## 1. El problema que resuelve

El diseño actual acopla el dominio a Jira en tres sitios, y ninguno es el cableado:

| Acoplamiento | Dónde | Consecuencia |
| --- | --- | --- |
| Nombres de campo | `NormalizedEvent.jira_issue_id`, `jira_issue_key` | Un evento de GitHub no cabe en el modelo |
| Nombre de tabla | `jira_events` | Los eventos de otras fuentes no tienen dónde ir |
| Vocabulario | `EventType.issue_created`, `comment_created` | Son conceptos de Jira, no del dominio |

Añadir un provider sin tocar la lógica de negocio exige arreglar esos tres antes que nada.
Crear seis clases sobre el modelo actual daría una fachada de extensibilidad sin
extensibilidad real.

## 2. Puertos

Aquí hay una desviación deliberada de lo pedido, y el motivo es SOLID.

Lo pedido era una única interfaz común con `connect()`, `sync()`, `fetch_events()` y
`health()` para los seis providers, Supabase incluido. Pero Supabase no es una fuente de
eventos: es el almacén donde se guardan. `sync()` y `fetch_events()` no tienen significado
para él, así que solo podría implementarlos devolviendo vacío o lanzando "no soportado". Eso
es una interfaz que el implementador no puede cumplir (viola la segregación de interfaces) y
un subtipo que no es sustituible por su base (viola la sustitución de Liskov). Las dos letras
que se piden por su nombre.

La segregación mínima que mantiene el resto de la intención intacta:

```
                    ┌─────────────────┐
                    │    Provider     │   ciclo de vida
                    │  connect()      │
                    │  health()       │
                    │  close()        │
                    └────────┬────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
┌───────────────────────┐         ┌───────────────────────┐
│ EventSourceProvider   │         │   StorageProvider     │
│  sync()               │         │   repositories()      │
│  fetch_events()       │         │                       │
└───────────────────────┘         └───────────────────────┘
   Jira, GitHub, Notion,                  Supabase
   AWS, Rightway
```

Los cinco providers de integración implementan los cuatro métodos pedidos. Supabase implementa
el ciclo de vida común, que es lo que de verdad comparte con ellos.

```python
class Provider(Protocol):
    name: ProviderName
    kind: ProviderKind

    async def connect(self) -> None: ...
    async def health(self) -> ProviderHealth: ...
    async def close(self) -> None: ...


class EventSourceProvider(Provider, Protocol):
    capabilities: frozenset[ProviderCapability]

    async def sync(self, request: SyncRequest) -> SyncReport: ...
    def fetch_events(self, request: FetchRequest) -> AsyncIterator[ExternalEvent]: ...
    def parse_webhook(self, payload: dict, headers: Mapping[str, str]) -> ExternalEvent: ...
    def verify_webhook(self, headers: Mapping[str, str], params: Mapping[str, str]) -> None: ...
```

`parse_webhook` y `verify_webhook` viven en el puerto porque cada servicio autentica distinto:
Jira Cloud no firma y usa secreto compartido, GitHub firma con HMAC SHA-256 en
`X-Hub-Signature-256`, Notion firma con su propio esquema. Si la validación viviera en la ruta,
la ruta tendría un `if` por provider, que es justo lo que se quiere evitar.

`capabilities` existe porque no todos pueden todo: un provider puede saber sincronizar y no
recibir webhooks. Declararlo es mejor que fallar al invocarlo.

## 3. Modelo de evento agnóstico

`NormalizedEvent` pasa a ser `ExternalEvent`, con vocabulario del dominio en lugar de
vocabulario de Jira:

```python
class ExternalEvent(BaseModel):
    provider: ProviderName          # jira | github | notion | aws | rightway
    workspace_key: str              # proyecto Jira, repo GitHub, database Notion
    external_id: str                # id en el sistema de origen
    external_key: str               # referencia legible: DEMO-42, owner/repo#17
    kind: EventKind                 # vocabulario del dominio, no de Jira
    occurred_at: datetime
    # señales que el análisis necesita, comunes a cualquier fuente
    title, state, owner, priority, due_date, estimated_hours, labels,
    changes, comment, url
    raw_payload: dict
```

`EventKind` deja de hablar de issues:

| `EventKind` | Jira | GitHub | Notion |
| --- | --- | --- | --- |
| `work_item_created` | issue creado | issue abierto | página creada |
| `work_item_updated` | issue actualizado | issue editado | página editada |
| `comment_added` | comentario | comentario | comentario |
| `review_requested` | — | PR abierto | — |
| `review_completed` | — | PR revisado | — |
| `deployment_state_changed` | — | — | — (AWS) |

Los agentes trabajan sobre `EventKind`, así que una señal de PR de GitHub alimenta el mismo
`TechnicalAgent` sin tocarlo.

La huella pasa a incluir el provider:

```
fingerprint = sha256(f"{provider}:{external_id}:{kind}:{occurred_at_utc}")
```

Sin el provider en el material, dos sistemas con identificadores numéricos que coincidan
producirían la misma huella y uno de los dos eventos se descartaría como duplicado falso.

## 4. Cambio de esquema

Aprovechando que el esquema todavía no se ha aplicado en Supabase, el cambio es gratis:

```
jira_events            →  external_events
  jira_issue_id        →  external_id
  jira_issue_key       →  external_key
  event_type           →  kind
  (nueva)              →  provider text not null
  (nueva)              →  workspace_key text not null
  (nueva)              →  url text

projects               →  workspaces
  jira_project_key     →  workspace_key
  (nueva)              →  provider text not null
  unique (jira_...)    →  unique (provider, workspace_key)

commitments
  jira_issue_key       →  external_key
  (nueva)              →  provider text not null
```

La restricción de unicidad del evento sigue siendo sobre `fingerprint` a secas, porque el
provider ya forma parte del material de la huella.

`JiraEventRepository` pasa a `EventRepository`. La clase no tenía nada de Jira salvo el nombre.

## 5. Registro y resolución

```python
class ProviderRegistry:
    def register(self, provider: EventSourceProvider) -> None
    def get(self, name: ProviderName) -> EventSourceProvider   # KeyError → 404 de dominio
    def event_sources(self) -> list[EventSourceProvider]
    def with_capability(self, capability) -> list[EventSourceProvider]
```

Se construye una vez en el `lifespan`, a partir de la configuración: **solo se registra el
provider cuyas credenciales están presentes**. Un provider sin configurar no se registra, en
lugar de registrarse y fallar al usarlo. Así `/health` puede informar de qué está conectado sin
inventar estados.

Las rutas dejan de ser por provider:

```
POST /webhooks/jira        →  POST /webhooks/{provider}
POST /jira/sync            →  POST /providers/{provider}/sync
                              GET  /providers            (qué hay registrado y su salud)
```

La ruta resuelve el provider por nombre en el registro y delega. No tiene ninguna rama por
provider: añadir GitHub no la toca.

## 6. Inyección de dependencias

La cadena queda:

```
lifespan  →  construye providers desde Settings  →  ProviderRegistry  →  app.state
   ↓
deps.get_provider_registry()  →  deps.get_event_source(provider_name)
   ↓
rutas y Orchestrator reciben el puerto, nunca la clase concreta
```

Ni un servicio ni un agente importa `JiraProvider`. La única parte del código que menciona una
clase concreta de provider es la factoría del `lifespan`, que es precisamente donde debe estar
la decisión de qué implementación usar.

## 7. Papel del Orchestrator

Queda como único coordinador, y con dos responsabilidades separadas:

```
OrchestratorService            (coordina providers, tiene E/S)
  ├── resuelve providers en el registro
  ├── recoge eventos vía el puerto
  ├── compone el contexto de análisis desde los repositorios
  └── invoca OrchestratorAgent

OrchestratorAgent             (compone agentes, puro, sin E/S)
  ├── CommitmentAgent
  ├── TechnicalAgent
  ├── FinancialAgent
  └── RiskAgent
```

La separación importa porque el agente debe seguir siendo testeable sin red ni base de datos.
Un único "Orchestrator" que hiciera las dos cosas perdería esa propiedad, que es la que hace
que los agentes sean la capa más barata de probar.

Los agentes reciben `ExternalEvent` y no saben de dónde vino. Ese es el criterio de aceptación
de todo este addendum: un agente que necesite un `if provider == "jira"` significa que el
diseño falló.

## 8. Estado de cada provider

Honestidad sobre lo que hay y lo que falta:

| Provider | Estado | Qué falta |
| --- | --- | --- |
| Jira | implementado, 205 tests | adaptar al puerto |
| Supabase | implementado | adaptar al puerto de almacenamiento |
| GitHub | por hacer | definir qué señal de compromiso aporta un PR; token |
| Notion | por hacer | definir qué se lee; token de integración |
| AWS | por hacer | **qué servicio**: CloudWatch, CodePipeline, Cost Explorer no son lo mismo |
| Rightway | bloqueado | **no se ha identificado el producto ni su API** |

Los cuatro pendientes necesitan credenciales y, antes, una definición de qué señal aportan.
Registrar clases vacías que devuelvan listas vacías daría seis providers en el árbol de
archivos y una sola integración real.

## 9. Riesgo de este addendum

El cambio toca el modelo de datos, el esquema, los repositorios, los servicios de ingesta y
sus tests: unos 261 tests que hoy están en verde. Es un refactor de fondo, no aditivo. Se hace
ahora porque cada provider nuevo que se añadiera antes multiplicaría el coste, y porque el
esquema aún no está aplicado y renombrar es gratis hoy y caro mañana.
