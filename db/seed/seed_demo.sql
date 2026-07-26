-- seed_demo.sql — Inserts idempotentes del caso demo.
-- UUIDs FIJOS para poder re-ejecutar sin duplicar.
-- Ejecutar con: psql o desde el editor SQL de Supabase.

-- 1. Proyecto
INSERT INTO public.projects (id, name, description, status, external_references, hourly_cost, currency)
VALUES (
  'a0000000-0000-4000-8000-000000000001',
  'Pagos Empresariales',
  'Integración de pasarela de pagos para clientes enterprise',
  'active',
  '{"jira": "DAT", "github": "datgent/pagos-enterprise"}'::jsonb,
  75.00,
  'USD'
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  status = EXCLUDED.status,
  external_references = EXCLUDED.external_references,
  hourly_cost = EXCLUDED.hourly_cost;

-- 2. Commitment
INSERT INTO public.commitments (id, project_id, title, description, beneficiary, owner, due_date, financial_exposure, currency, priority, status, source, metadata)
VALUES (
  'a0000000-0000-4000-8000-000000000002',
  'a0000000-0000-4000-8000-000000000001',
  'Entregar integración de pagos empresariales antes del viernes',
  'Módulo completo de pagos enterprise con certificación PCI y pruebas de integración con 3 bancos',
  'Cliente Enterprise',
  'equipo-pagos',
  '2026-07-24T23:59:59Z',
  20000.00,
  'USD',
  'critical',
  'at_risk',
  'demo',
  '{"sla_clause": "Cláusula 7.3 - Penalización por entrega tardía"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
  title = EXCLUDED.title,
  description = EXCLUDED.description,
  beneficiary = EXCLUDED.beneficiary,
  financial_exposure = EXCLUDED.financial_exposure,
  status = EXCLUDED.status;

-- 3. Source events (señales de los 4 providers)
INSERT INTO public.source_events (id, provider, external_id, event_type, event_hash, project_id, commitment_id, payload, occurred_at)
VALUES
  ('a0000000-0000-4000-8000-000000000010', 'finance', 'fin-snapshot-20260721', 'budget_snapshot', 'demo-finance-hash-001', 'a0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
   '{"project_key":"PAGOS-ENT","penalties":[{"amount":"20000","probability":0.85,"description":"Penalización contractual por entrega tardía"}],"budget_lines":[{"concept":"Desarrollo backend pasarela","planned":"18000","actual":"14200"}],"retained_payments":"7200"}'::jsonb,
   '2026-07-21T08:00:00Z'),
  ('a0000000-0000-4000-8000-000000000011', 'jira', 'DAT-42-blocked', 'issue_status_changed', 'demo-jira-hash-001', 'a0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
   '{"issue_key":"DAT-42","status":"Blocked","priority":"Critical","assignee":null,"due_date":"2026-07-24","blocked_by":[{"key":"EXT-101","type":"external_dependency","provider":"Banco Nacional"}],"days_in_status":6}'::jsonb,
   '2026-07-20T10:00:00Z'),
  ('a0000000-0000-4000-8000-000000000012', 'github', 'pr-187-checks-failed', 'check_suite_completed', 'demo-github-hash-001', 'a0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
   '{"pull_request":{"number":187,"status":"open","checks_passed":false,"checks_failed":["integration-tests","security-scan","coverage-check"],"coverage":42},"migration":{"has_rollback":false,"destructive_operations":["DROP TABLE payment_logs_v1"]}}'::jsonb,
   '2026-07-22T15:00:00Z'),
  ('a0000000-0000-4000-8000-000000000013', 'supabase', 'migration-20260720', 'migration_applied', 'demo-supabase-hash-001', 'a0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
   '{"migrations":[{"name":"20260720_add_payment_tables","has_rollback":false}],"security_issues":[{"type":"missing_rls","table":"payments","severity":"high"}],"performance_issues":[{"type":"missing_index","table":"payments","column":"customer_id"}]}'::jsonb,
   '2026-07-20T11:00:00Z')
ON CONFLICT (event_hash) DO NOTHING;

-- 4. Documentos RAG
INSERT INTO public.documents (id, project_id, commitment_id, title, content, source_type, source_url)
VALUES
  ('a0000000-0000-4000-8000-000000000020', 'a0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
   'Cláusula SLA - Penalización por entrega tardía',
   'Cláusula 7.3 del contrato de servicios: Si el módulo de integración de pagos empresariales no se entrega funcional y certificado antes del viernes 25 de julio de 2026, se aplicará una penalización contractual de USD 20,000 (veinte mil dólares). La penalización se deduce del siguiente pago programado. El cliente puede además rescindir el contrato sin penalidad adicional si el retraso supera 5 días hábiles.',
   'document',
   'https://docs.empresa.com/contratos/enterprise-2026/clausula-7.3'),
  ('a0000000-0000-4000-8000-000000000021', 'a0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000002',
   'Acta de acuerdo de fecha de entrega',
   'Acta de reunión 2026-07-10: Se acuerda con Cliente Enterprise que la fecha límite de entrega del módulo de pagos es el viernes 25 de julio de 2026. El equipo acepta el compromiso con la condición de recibir acceso a la API de certificación del banco antes del 15 de julio. NOTA: Al 20 de julio el banco NO ha proporcionado acceso a la API de certificación. El PM ha escalado al director comercial.',
   'document',
   'https://docs.empresa.com/actas/2026-07-10-kickoff-enterprise')
ON CONFLICT (id) DO UPDATE SET
  title = EXCLUDED.title,
  content = EXCLUDED.content;
