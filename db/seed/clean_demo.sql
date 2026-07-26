-- clean_demo.sql — Borra SOLO los datos del caso demo.
-- DESTRUCTIVO pero ACOTADO: solo afecta filas con los UUIDs fijos del demo.
-- Orden de borrado respeta FKs (hijos antes que padres).

-- Documentos
DELETE FROM public.documents WHERE id IN (
  'a0000000-0000-4000-8000-000000000020',
  'a0000000-0000-4000-8000-000000000021'
);

-- Source events
DELETE FROM public.source_events WHERE id IN (
  'a0000000-0000-4000-8000-000000000010',
  'a0000000-0000-4000-8000-000000000011',
  'a0000000-0000-4000-8000-000000000012',
  'a0000000-0000-4000-8000-000000000013'
);

-- Timeline events del commitment demo
DELETE FROM public.timeline_events
WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002';

-- Decisions vinculadas al commitment demo
DELETE FROM public.decisions
WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002';

-- Alerts del commitment demo
DELETE FROM public.alerts
WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002';

-- Risk cases del commitment demo
DELETE FROM public.risk_cases
WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002';

-- Evidence y findings (via agent_runs)
DELETE FROM public.evidence WHERE finding_id IN (
  SELECT id FROM public.findings
  WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002'
);
DELETE FROM public.findings
WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002';

-- Agent runs
DELETE FROM public.agent_runs
WHERE commitment_id = 'a0000000-0000-4000-8000-000000000002';

-- Commitment
DELETE FROM public.commitments WHERE id = 'a0000000-0000-4000-8000-000000000002';

-- Proyecto (solo si no tiene otros commitments)
DELETE FROM public.projects
WHERE id = 'a0000000-0000-4000-8000-000000000001'
  AND NOT EXISTS (
    SELECT 1 FROM public.commitments
    WHERE project_id = 'a0000000-0000-4000-8000-000000000001'
      AND id != 'a0000000-0000-4000-8000-000000000002'
  );
