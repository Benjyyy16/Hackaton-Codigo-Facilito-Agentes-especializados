-- ============================================================================
-- Datgent - reversion del esquema
--
-- ATENCION: este script DESTRUYE datos. No se ejecuta automaticamente en ningun
-- flujo del backend. Se aplica a mano, de forma deliberada, desde el editor SQL
-- de Supabase.
--
-- El orden respeta las dependencias de claves foraneas: primero las hojas, luego
-- las raices. `drop table if exists ... cascade` seria mas corto pero oculta que
-- se esta borrando mas de lo que se nombra, asi que aqui el orden es explicito.
--
-- Para revertir solo los datos de demostracion y conservar el esquema, usar
-- db/seed_clean.sql en lugar de este archivo.
-- ============================================================================

-- Hojas: no las referencia nadie.
drop table if exists public.timeline_events;
drop table if exists public.evidence;
drop table if exists public.documents;
drop table if exists public.decisions;
drop table if exists public.alerts;

-- Dependen de agent_runs / risk_cases.
drop table if exists public.findings;
drop table if exists public.risk_cases;
drop table if exists public.agent_runs;

-- Dependen de projects / commitments.
drop table if exists public.source_events;
drop table if exists public.provider_connections;
drop table if exists public.commitments;

-- Raiz.
drop table if exists public.projects;

-- Tabla de integraciones OAuth (independiente del modelo de dominio).
drop table if exists public.integrations;

-- La funcion de trigger queda sin usuarios tras borrar las tablas.
drop function if exists public.set_updated_at();

-- pgcrypto y vector NO se eliminan: pueden estar en uso por otros esquemas del
-- mismo proyecto de Supabase.
