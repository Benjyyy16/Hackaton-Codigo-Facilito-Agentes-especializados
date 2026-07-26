-- ============================================================================
-- Datgent - esquema de Supabase
--
-- Script idempotente: se puede reejecutar sin efectos secundarios. Se aplica a mano
-- desde el editor SQL de Supabase. No hay herramienta de migraciones (Alembic esta
-- excluido del stack), asi que la idempotencia es la unica red de seguridad.
--
-- Convenciones:
--   * clave primaria UUID generada en base de datos
--   * created_at y updated_at en todas las tablas, updated_at por trigger
--   * deleted_at solo donde el borrado logico tiene sentido de negocio
--   * RLS activo sin politicas permisivas: el backend usa service role y se la salta;
--     la clave anonima no puede leer nada
--
-- REVERSION: ver db/rollback.sql. Este script NO ejecuta DROP en ningun caso.
-- ============================================================================

create extension if not exists "pgcrypto";

-- ----------------------------------------------------------------------------
-- updated_at por trigger
--
-- Se mantiene en base de datos y no desde la aplicacion: asi ninguna escritura puede
-- olvidarlo, incluida una hecha a mano desde el editor SQL.
-- ----------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================================
-- 1. projects
--    Raiz del modelo. Un proyecto agrupa compromisos y conexiones a providers.
-- ============================================================================

create table if not exists public.projects (
  id                    uuid primary key default gen_random_uuid(),
  name                  text not null,
  description           text,
  status                text not null default 'active' check (
                          status in ('active', 'paused', 'closed', 'archived')
                        ),
  -- Referencias a este proyecto en sistemas externos:
  -- {"jira": "DAT", "github": "owner/repo", "supabase": "project-ref"}
  -- Es un mapa y no columnas fijas porque cada provider identifica distinto y
  -- anadir uno nuevo no debe requerir una migracion.
  external_references   jsonb not null default '{}'::jsonb,
  -- Coste por hora del equipo. Alimenta el calculo de exposicion economica: sin el,
  -- el impacto sale cero y las alertas pierden su argumento mas fuerte.
  hourly_cost           numeric(12,2) not null default 0 check (hourly_cost >= 0),
  currency              text not null default 'USD' check (char_length(currency) = 3),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  deleted_at            timestamptz
);

create index if not exists projects_status_idx
  on public.projects (status) where deleted_at is null;

-- ============================================================================
-- 2. commitments
--    Entidad central. TODOS los agentes analizan un commitment, no un dashboard
--    propio. Es lo que hace que el sistema no sea cuatro herramientas separadas.
-- ============================================================================

create table if not exists public.commitments (
  id                    uuid primary key default gen_random_uuid(),
  project_id            uuid not null references public.projects (id) on delete cascade,
  title                 text not null,
  description           text,
  -- Quien recibe el compromiso: cliente, area interna, regulador.
  beneficiary           text,
  -- Quien responde por el dentro de la organizacion.
  owner                 text,
  due_date              timestamptz,
  -- Dinero expuesto si el compromiso se incumple: penalizacion, pago retenido,
  -- coste de recuperacion. Es el numero que convierte un retraso tecnico en una
  -- conversacion de negocio.
  financial_exposure    numeric(14,2) not null default 0 check (financial_exposure >= 0),
  currency              text not null default 'USD' check (char_length(currency) = 3),
  priority              text not null default 'medium' check (
                          priority in ('low', 'medium', 'high', 'critical')
                        ),
  status                text not null default 'open' check (
                          status in ('open', 'at_risk', 'breached', 'met', 'cancelled')
                        ),
  -- De donde nacio el compromiso: contrato, Jira, decision interna, seed de demo.
  source                text not null default 'manual' check (
                          source in ('manual', 'contract', 'jira', 'github', 'import', 'demo')
                        ),
  metadata              jsonb not null default '{}'::jsonb,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  deleted_at            timestamptz
);

create index if not exists commitments_project_idx
  on public.commitments (project_id) where deleted_at is null;

create index if not exists commitments_status_due_idx
  on public.commitments (status, due_date) where deleted_at is null;

create index if not exists commitments_priority_idx
  on public.commitments (priority) where deleted_at is null;

-- ============================================================================
-- 3. provider_connections
--    Estado de la conexion a cada sistema externo, por proyecto.
--
--    SEGURIDAD: `config` NO almacena secretos en claro. Los secretos viven en
--    variables de entorno del servicio. Aqui solo van referencias
--    (p.ej. {"secret_ref": "JIRA_API_TOKEN"}) y parametros no sensibles.
-- ============================================================================

create table if not exists public.provider_connections (
  id                    uuid primary key default gen_random_uuid(),
  project_id            uuid references public.projects (id) on delete cascade,
  provider              text not null check (
                          provider in (
                            'jira', 'github', 'supabase', 'finance',
                            'notion', 'aws', 'rightway', 'slack', 'vercel'
                          )
                        ),
  status                text not null default 'unknown' check (
                          status in ('connected', 'error', 'disabled', 'unknown')
                        ),
  -- Parametros no sensibles + referencias a secretos. Nunca el secreto en si.
  config                jsonb not null default '{}'::jsonb,
  last_sync_at          timestamptz,
  -- Ultimo error como texto sanitizado. Nunca cabeceras ni tokens.
  last_error            text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  unique (project_id, provider)
);

create index if not exists provider_connections_provider_idx
  on public.provider_connections (provider, status);

-- ============================================================================
-- 4. source_events
--    Evento crudo de un provider, normalizado a vocabulario del dominio.
--    `event_hash` unico es lo que cierra la condicion de carrera entre dos
--    entregas simultaneas del mismo webhook: la segunda insercion falla en la
--    base de datos, no en la aplicacion.
-- ============================================================================

create table if not exists public.source_events (
  id                    uuid primary key default gen_random_uuid(),
  provider              text not null check (
                          provider in (
                            'jira', 'github', 'supabase', 'finance',
                            'notion', 'aws', 'rightway', 'slack', 'vercel'
                          )
                        ),
  external_id           text not null,
  event_type            text not null,
  -- sha256(provider:external_id:event_type:occurred_at). Deterministico y estable.
  event_hash            text not null unique,
  project_id            uuid references public.projects (id) on delete set null,
  commitment_id         uuid references public.commitments (id) on delete set null,
  -- Payload original del provider, intacto. Permite reprocesar sin volver a llamar.
  payload               jsonb not null default '{}'::jsonb,
  occurred_at           timestamptz not null,
  received_at           timestamptz not null default now(),
  processing_status     text not null default 'pending' check (
                          processing_status in ('pending', 'processing', 'processed', 'failed', 'skipped')
                        ),
  processing_error      text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists source_events_commitment_occurred_idx
  on public.source_events (commitment_id, occurred_at desc);

create index if not exists source_events_project_occurred_idx
  on public.source_events (project_id, occurred_at desc);

create index if not exists source_events_status_idx
  on public.source_events (processing_status) where processing_status in ('pending', 'failed');

create index if not exists source_events_provider_external_idx
  on public.source_events (provider, external_id);

-- ============================================================================
-- 5. agent_runs
--    Una ejecucion de un agente sobre un commitment. Es la unidad de auditoria:
--    permite responder "que vio el agente, con que modelo y que devolvio".
-- ============================================================================

create table if not exists public.agent_runs (
  id                    uuid primary key default gen_random_uuid(),
  agent_name            text not null,
  commitment_id         uuid references public.commitments (id) on delete cascade,
  status                text not null default 'pending' check (
                          status in ('pending', 'running', 'completed', 'failed', 'skipped')
                        ),
  started_at            timestamptz,
  finished_at           timestamptz,
  -- Modelo y version de prompt: sin esto un resultado no es reproducible ni auditable.
  model                 text,
  prompt_version        text,
  -- Referencia a la entrada (id de evento, hash del contexto). No el payload completo.
  input_reference       text,
  output                jsonb not null default '{}'::jsonb,
  error                 text,
  duration_ms           integer check (duration_ms is null or duration_ms >= 0),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists agent_runs_commitment_created_idx
  on public.agent_runs (commitment_id, created_at desc);

create index if not exists agent_runs_agent_status_idx
  on public.agent_runs (agent_name, status);

-- ============================================================================
-- 6. findings
--    Hallazgo concreto producido por un agente. Un agent_run produce N findings.
-- ============================================================================

create table if not exists public.findings (
  id                    uuid primary key default gen_random_uuid(),
  agent_run_id          uuid not null references public.agent_runs (id) on delete cascade,
  commitment_id         uuid references public.commitments (id) on delete cascade,
  -- Familia del hallazgo: schedule, technical, financial, data, security, process.
  category              text not null,
  -- Codigo estable del hallazgo, para agrupar y para decidir el motivo de una alerta.
  code                  text not null,
  severity              text not null check (severity in ('low', 'medium', 'high', 'critical')),
  risk_score            integer not null check (risk_score between 0 and 100),
  -- 0..1. Un hallazgo derivado de un dato duro tiene confianza alta; uno inferido, baja.
  confidence            numeric(3,2) not null default 1.0 check (confidence between 0 and 1),
  summary               text not null,
  impact                text,
  status                text not null default 'open' check (
                          status in ('open', 'mitigated', 'accepted', 'dismissed', 'resolved')
                        ),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists findings_commitment_created_idx
  on public.findings (commitment_id, created_at desc);

create index if not exists findings_run_idx on public.findings (agent_run_id);

create index if not exists findings_severity_status_idx
  on public.findings (severity, status);

-- ============================================================================
-- 7. evidence
--    Dato observable que respalda un finding. Sin evidencia un hallazgo es opinion.
-- ============================================================================

create table if not exists public.evidence (
  id                    uuid primary key default gen_random_uuid(),
  finding_id            uuid not null references public.findings (id) on delete cascade,
  provider              text not null,
  source_type           text not null check (
                          source_type in ('jira', 'github', 'finance', 'supabase', 'document', 'computed')
                        ),
  external_id           text,
  source_url            text,
  -- Campo observado y su valor: ("assignee", null) es evidencia de "sin responsable".
  field                 text,
  value                 text,
  content               text,
  metadata              jsonb not null default '{}'::jsonb,
  observed_at           timestamptz not null default now(),
  created_at            timestamptz not null default now()
);

create index if not exists evidence_finding_idx on public.evidence (finding_id);

create index if not exists evidence_source_idx
  on public.evidence (source_type, external_id);

-- ============================================================================
-- 8. risk_cases
--    Riesgo consolidado de un commitment: la salida del orquestador. Es lo que
--    correlaciona los hallazgos de los cuatro agentes en una sola historia.
-- ============================================================================

create table if not exists public.risk_cases (
  id                    uuid primary key default gen_random_uuid(),
  commitment_id         uuid not null references public.commitments (id) on delete cascade,
  consolidated_score    integer not null check (consolidated_score between 0 and 100),
  severity              text not null check (severity in ('low', 'medium', 'high', 'critical')),
  confidence            numeric(3,2) not null default 1.0 check (confidence between 0 and 1),
  -- Cadena causal: [{"step": 1, "cause": "...", "effect": "...", "evidence_ids": [...]}]
  causal_chain          jsonb not null default '[]'::jsonb,
  -- Pre-mortem: {"assumed_failure": "...", "failure_modes": [...], "early_signals": [...]}
  premortem             jsonb not null default '{}'::jsonb,
  -- Tres escenarios: no actuar / anadir capacidad / renegociar alcance.
  scenarios             jsonb not null default '[]'::jsonb,
  -- Separacion explicita entre lo que se sabe y lo que se supone.
  facts                 jsonb not null default '[]'::jsonb,
  inferences            jsonb not null default '[]'::jsonb,
  assumptions           jsonb not null default '[]'::jsonb,
  missing_information   jsonb not null default '[]'::jsonb,
  summary               text,
  -- El analisis quedo incompleto porque algun agente fallo.
  is_partial            boolean not null default false,
  status                text not null default 'open' check (
                          status in ('open', 'monitoring', 'mitigated', 'closed')
                        ),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists risk_cases_commitment_created_idx
  on public.risk_cases (commitment_id, created_at desc);

create index if not exists risk_cases_severity_status_idx
  on public.risk_cases (severity, status);

-- ============================================================================
-- 9. alerts
--    Aviso derivado de un risk_case que cruzo el umbral configurado.
-- ============================================================================

create table if not exists public.alerts (
  id                    uuid primary key default gen_random_uuid(),
  risk_case_id          uuid references public.risk_cases (id) on delete cascade,
  commitment_id         uuid references public.commitments (id) on delete cascade,
  severity              text not null check (severity in ('low', 'medium', 'high', 'critical')),
  title                 text not null,
  description           text,
  status                text not null default 'open' check (
                          status in ('open', 'acknowledged', 'resolved')
                        ),
  acknowledged_by       text,
  acknowledged_at       timestamptz,
  resolved_at           timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  deleted_at            timestamptz,
  -- Una alerta reconocida tiene quien y cuando; una abierta, no.
  constraint alerts_acknowledged_consistency
    check (
      (status = 'open' and acknowledged_at is null)
      or (status in ('acknowledged', 'resolved') and acknowledged_at is not null)
    )
);

-- Indice unico parcial: dos analisis concurrentes no pueden abrir dos alertas para
-- el mismo commitment. Actualizar en lugar de duplicar.
create unique index if not exists alerts_open_unique_idx
  on public.alerts (commitment_id)
  where status = 'open' and deleted_at is null;

create index if not exists alerts_status_severity_idx
  on public.alerts (status, severity) where deleted_at is null;

-- ============================================================================
-- 10. decisions
--     Accion propuesta por el sistema que requiere aprobacion humana antes de
--     ejecutarse. El backend propone; una persona decide. Auditoria completa.
-- ============================================================================

create table if not exists public.decisions (
  id                    uuid primary key default gen_random_uuid(),
  risk_case_id          uuid references public.risk_cases (id) on delete cascade,
  commitment_id         uuid references public.commitments (id) on delete cascade,
  action_type           text not null check (
                          action_type in (
                            'post_accounting_entry', 'update_jira_issue', 'close_critical_alert',
                            'execute_sql', 'block_deployment', 'create_pull_request',
                            'merge_pull_request', 'send_external_communication',
                            'reassign_owner', 'renegotiate_scope', 'add_capacity'
                          )
                        ),
  title                 text not null,
  rationale             text,
  -- Que se ejecutaria exactamente si se aprueba. Auditable antes de correr.
  proposed_payload      jsonb not null default '{}'::jsonb,
  approval_status       text not null default 'pending' check (
                          approval_status in ('pending', 'approved', 'rejected', 'expired')
                        ),
  requested_by          text not null default 'orchestrator-agent',
  approved_by           text,
  approved_at           timestamptz,
  rejection_reason      text,
  execution_status      text not null default 'not_started' check (
                          execution_status in ('not_started', 'running', 'succeeded', 'failed', 'skipped')
                        ),
  execution_result      jsonb not null default '{}'::jsonb,
  executed_at           timestamptz,
  error                 text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  -- No se puede ejecutar lo que no se aprobo. La regla vive en la base de datos y no
  -- solo en el servicio, para que ninguna ruta pueda saltarsela.
  constraint decisions_execution_requires_approval
    check (
      execution_status = 'not_started'
      or approval_status = 'approved'
    ),
  constraint decisions_approval_consistency
    check (
      (approval_status = 'pending' and approved_at is null)
      or (approval_status = 'approved' and approved_at is not null)
      or (approval_status in ('rejected', 'expired'))
    )
);

create index if not exists decisions_risk_case_idx on public.decisions (risk_case_id);

create index if not exists decisions_approval_idx
  on public.decisions (approval_status, created_at desc);

-- ============================================================================
-- 11. timeline_events
--     Historia legible de un commitment: que paso, quien lo hizo, cuando.
--     Es lo que permite reconstruir el caso sin leer JSON de agentes.
-- ============================================================================

create table if not exists public.timeline_events (
  id                    uuid primary key default gen_random_uuid(),
  commitment_id         uuid not null references public.commitments (id) on delete cascade,
  actor_type            text not null check (actor_type in ('system', 'agent', 'human', 'provider')),
  actor_name            text not null,
  event_type            text not null,
  summary               text not null,
  payload               jsonb not null default '{}'::jsonb,
  created_at            timestamptz not null default now()
);

create index if not exists timeline_events_commitment_created_idx
  on public.timeline_events (commitment_id, created_at desc);

-- ============================================================================
-- 12. documents  (RAG minimo)
--     Fragmentos de texto asociados a proyecto y compromiso, recuperables para
--     alimentar el analisis con contexto documental.
--
--     pgvector es opcional: si la extension existe se crea la columna embedding y
--     un indice ivfflat; si no, la recuperacion es textual con full-text search.
--     El MVP no se bloquea por la ausencia de pgvector.
-- ============================================================================

create table if not exists public.documents (
  id                    uuid primary key default gen_random_uuid(),
  project_id            uuid references public.projects (id) on delete cascade,
  commitment_id         uuid references public.commitments (id) on delete cascade,
  title                 text not null,
  content               text not null,
  source_type           text not null default 'document',
  source_url            text,
  metadata              jsonb not null default '{}'::jsonb,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists documents_project_idx on public.documents (project_id);
create index if not exists documents_commitment_idx on public.documents (commitment_id);

-- Full-text search en espanol. Es la ruta por defecto: funciona sin extensiones extra.
create index if not exists documents_content_fts_idx
  on public.documents using gin (to_tsvector('spanish', coalesce(title, '') || ' ' || content));

-- pgvector opcional. El bloque no falla si la extension no esta disponible.
do $$
begin
  if exists (select 1 from pg_available_extensions where name = 'vector') then
    create extension if not exists vector;
    begin
      alter table public.documents add column if not exists embedding vector(1536);
    exception when others then
      raise notice 'documents.embedding no se pudo crear: %', sqlerrm;
    end;
  else
    raise notice 'pgvector no disponible: la recuperacion sera textual (full-text search)';
  end if;
end;
$$;

-- ============================================================================
-- Triggers de updated_at
-- ============================================================================

do $$
declare
  target text;
begin
  for target in
    select unnest(array[
      'projects', 'commitments', 'provider_connections', 'source_events',
      'agent_runs', 'findings', 'risk_cases', 'alerts', 'decisions', 'documents'
    ])
  loop
    -- drop + create en lugar de "create if not exists": PostgreSQL no admite
    -- "create trigger if not exists", y esta pareja mantiene el script reejecutable.
    execute format('drop trigger if exists set_updated_at on public.%I', target);
    execute format(
      'create trigger set_updated_at before update on public.%I
         for each row execute function public.set_updated_at()',
      target
    );
  end loop;
end;
$$;

-- ============================================================================
-- Row Level Security
--
-- El backend escribe con la clave de service role, que se salta RLS por diseno.
-- Activar RLS sin definir ninguna politica permisiva es precisamente lo que impide
-- que la clave anonima lea o escriba estas tablas. Sin esto, cualquiera con la clave
-- publica del proyecto tendria acceso de lectura a todo.
--
-- Si en el futuro el frontend consulta Supabase directamente, hay que anadir
-- politicas explicitas por tabla. Hasta entonces, la ausencia de politicas ES la
-- politica.
-- ============================================================================

alter table public.projects              enable row level security;
alter table public.commitments           enable row level security;
alter table public.provider_connections  enable row level security;
alter table public.source_events         enable row level security;
alter table public.agent_runs            enable row level security;
alter table public.findings              enable row level security;
alter table public.evidence              enable row level security;
alter table public.risk_cases            enable row level security;
alter table public.alerts                enable row level security;
alter table public.decisions             enable row level security;
alter table public.timeline_events       enable row level security;
alter table public.documents             enable row level security;

-- ============================================================================
-- integrations (credenciales OAuth por usuario)
--
-- Se conserva del esquema anterior: la usa el flujo OAuth de /oauth/{provider}.
-- ============================================================================

create table if not exists public.integrations (
  id          uuid primary key default gen_random_uuid(),
  user_id     text not null,
  provider    text not null check (
                provider in ('jira','github','notion','aws','rightway','slack','vercel','erp')
              ),
  credentials jsonb not null default '{}'::jsonb,
  config      jsonb not null default '{}'::jsonb,
  status      text not null default 'active' check (status in ('active','inactive')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, provider)
);

drop trigger if exists set_updated_at on public.integrations;
create trigger set_updated_at before update on public.integrations
  for each row execute function public.set_updated_at();

alter table public.integrations enable row level security;
