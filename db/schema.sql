-- Commitment Twin - esquema de Supabase
--
-- Script idempotente: se puede reejecutar sin efectos secundarios. Se aplica a mano desde
-- el editor SQL de Supabase. No hay herramienta de migraciones porque Alembic esta excluido
-- del stack, asi que la idempotencia es la unica red de seguridad (RF-7.6).
--
-- Convenciones (RF-7.3, RF-7.4):
--   * clave primaria UUID generada en base de datos
--   * created_at y updated_at en todas las tablas
--   * deleted_at solo donde el borrado logico tiene sentido de negocio

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------------
-- updated_at
--
-- Se mantiene con trigger y no desde la aplicacion: asi ninguna escritura puede
-- olvidarlo, incluida una hecha a mano desde el editor SQL.
-- ---------------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------------
-- projects
-- ---------------------------------------------------------------------------------

create table if not exists public.workspaces (
  id                uuid primary key default gen_random_uuid(),
  -- Provider al que pertenece. La clave sola no identifica: un proyecto "API" en Jira y un
  -- repositorio "API" en GitHub son cosas distintas.
  provider          text not null check (
                      provider in ('jira', 'github', 'notion', 'aws', 'rightway')
                    ),
  workspace_key     text not null,
  name              text not null,
  -- Coste por hora que alimenta el calculo de impacto economico. Sin valor, el impacto
  -- sale cero y las alertas pierden su argumento mas fuerte.
  hourly_cost       numeric(12,2) not null default 0 check (hourly_cost >= 0),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz,
  unique (provider, workspace_key)
);

-- ---------------------------------------------------------------------------------
-- external_events
-- ---------------------------------------------------------------------------------

create table if not exists public.external_events (
  id              uuid primary key default gen_random_uuid(),
  workspace_id    uuid references public.workspaces (id) on delete set null,
  provider        text not null check (
                    provider in ('jira', 'github', 'notion', 'aws', 'rightway')
                  ),
  workspace_key   text not null,
  external_id     text not null,
  external_key    text not null,
  -- Vocabulario del dominio, no de Jira: un issue de Jira, uno de GitHub y una pagina de
  -- Notion son todos work_item.
  kind            text not null check (
                    kind in (
                      'work_item_created', 'work_item_updated', 'comment_added',
                      'review_requested', 'review_completed', 'deployment_state_changed'
                    )
                  ),
  -- Clave de deduplicacion: sha256(provider:external_id:kind:occurred_at). El provider forma
  -- parte del material, asi que dos sistemas con identificadores numericos coincidentes no
  -- producen la misma huella. La restriccion unica es lo que cierra la condicion de carrera
  -- entre dos entregas simultaneas del mismo evento (RF-6.3).
  fingerprint     text not null unique,
  occurred_at     timestamptz not null,
  url             text,
  -- Payload original del provider, intacto (RF-5.6).
  raw_payload     jsonb not null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- Respalda el listado paginado descendente de GET /events (RF-10.1).
create index if not exists external_events_workspace_occurred_idx
  on public.external_events (workspace_id, occurred_at desc);

create index if not exists external_events_key_idx
  on public.external_events (provider, external_key);

create index if not exists external_events_kind_idx
  on public.external_events (kind);

-- ---------------------------------------------------------------------------------
-- commitments
-- ---------------------------------------------------------------------------------

create table if not exists public.commitments (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references public.workspaces (id) on delete cascade,
  provider         text not null check (
                     provider in ('jira', 'github', 'notion', 'aws', 'rightway')
                   ),
  external_key     text not null,
  title            text not null,
  due_date         timestamptz,
  status           text not null default 'open' check (
                     status in ('open', 'at_risk', 'breached', 'met')
                   ),
  estimated_hours  numeric(10,2) check (estimated_hours is null or estimated_hours >= 0),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz,
  -- Un elemento de trabajo representa como maximo un compromiso por contenedor. Soporta el
  -- upsert que hace el analisis al derivar el compromiso desde el evento.
  unique (workspace_id, external_key)
);

create index if not exists commitments_status_idx
  on public.commitments (status)
  where deleted_at is null;

-- ---------------------------------------------------------------------------------
-- risk_analyses
-- ---------------------------------------------------------------------------------

create table if not exists public.risk_analyses (
  id             uuid primary key default gen_random_uuid(),
  event_id       uuid references public.external_events (id) on delete cascade,
  commitment_id  uuid references public.commitments (id) on delete cascade,
  risk_score     integer not null check (risk_score between 0 and 100),
  severity       text not null check (severity in ('low', 'medium', 'high', 'critical')),
  -- Algun agente fallo y su contribucion se omitio. El analisis sigue siendo utilizable,
  -- pero queda marcado como incompleto (RF-8.6).
  is_partial     boolean not null default false,
  -- Salida por agente, tal como la devolvio cada uno.
  findings       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  -- Un analisis se refiere a un evento, a un compromiso, o a ambos, pero no a ninguno.
  constraint risk_analyses_target_present
    check (event_id is not null or commitment_id is not null)
);

create index if not exists risk_analyses_commitment_created_idx
  on public.risk_analyses (commitment_id, created_at desc);

create index if not exists risk_analyses_event_idx
  on public.risk_analyses (event_id);

-- ---------------------------------------------------------------------------------
-- alerts
-- ---------------------------------------------------------------------------------

create table if not exists public.alerts (
  id                uuid primary key default gen_random_uuid(),
  commitment_id     uuid references public.commitments (id) on delete cascade,
  risk_analysis_id  uuid not null references public.risk_analyses (id) on delete cascade,
  severity          text not null check (
                      severity in ('low', 'medium', 'high', 'critical')
                    ),
  reason            text not null,
  financial_impact  numeric(14,2) not null default 0 check (financial_impact >= 0),
  status            text not null default 'open' check (status in ('open', 'resolved')),
  resolved_at       timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz,
  -- Una alerta resuelta tiene fecha de resolucion; una abierta, no.
  constraint alerts_resolved_at_matches_status
    check (
      (status = 'resolved' and resolved_at is not null)
      or (status = 'open' and resolved_at is null)
    )
);

-- Indice parcial que respalda "actualizar la alerta abierta en lugar de duplicarla"
-- (RF-9.3). Al ser unico, dos analisis concurrentes no pueden abrir dos alertas para el
-- mismo compromiso y motivo.
create unique index if not exists alerts_open_unique_idx
  on public.alerts (commitment_id, reason)
  where status = 'open' and deleted_at is null;

create index if not exists alerts_status_severity_idx
  on public.alerts (status, severity)
  where deleted_at is null;

create index if not exists alerts_created_idx
  on public.alerts (created_at desc);

-- ---------------------------------------------------------------------------------
-- Triggers de updated_at
-- ---------------------------------------------------------------------------------

do $$
declare
  target text;
begin
  for target in
    select unnest(array[
      'workspaces', 'external_events', 'commitments', 'risk_analyses', 'alerts'
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

-- ---------------------------------------------------------------------------------
-- Row Level Security
--
-- El backend escribe con la clave de service role, que se salta RLS por diseno. Activar RLS
-- sin definir ninguna politica permisiva es precisamente lo que impide que la clave anonima
-- lea o escriba estas tablas. Sin esto, cualquiera con la clave publica tendria acceso.
-- ---------------------------------------------------------------------------------

alter table public.workspaces       enable row level security;
alter table public.external_events  enable row level security;
alter table public.commitments      enable row level security;
alter table public.risk_analyses    enable row level security;
alter table public.alerts           enable row level security;
