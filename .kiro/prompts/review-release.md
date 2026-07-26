# Checklist de revisión antes de release

## Tests

- [ ] `pytest` pasa completamente (0 failures, 0 errors).
- [ ] No hay tests `skip` sin motivo documentado.
- [ ] Tests de agentes son puros (sin mocks de I/O, solo entrada/salida).
- [ ] Tests de repos usan fake de Supabase, no instancia real.

## Seguridad

- [ ] Ningún secreto hardcodeado en el código.
- [ ] `SecretStr` en todos los campos sensibles de `Settings`.
- [ ] Webhooks validan firma/secreto ANTES de procesar payload.
- [ ] Errores HTTP no filtran internals (sin stack traces, sin nombres de tabla).
- [ ] CORS restringido en producción (no `*`).
- [ ] RLS activo en todas las tablas (verificar en Supabase dashboard).
- [ ] Service role key no aparece en ninguna respuesta HTTP.

## Schema y datos

- [ ] `db/schema.sql` es idempotente (reejecutar no produce errores).
- [ ] Enums Python coinciden con checks SQL (comparar manualmente).
- [ ] Triggers de `updated_at` existen en todas las tablas con esa columna.
- [ ] Índices cubren las queries de los repositorios.

## Arquitectura

- [ ] No hay imports invertidos (ruta → repo, agente → httpx).
- [ ] Agentes no importan `fastapi`, `supabase`, `httpx`.
- [ ] Providers implementan el protocolo de `base.py`.
- [ ] Toda escritura pasa por repositorio.

## Configuración

- [ ] Variables obligatorias documentadas en README o `.env.example`.
- [ ] Fallo de config detiene el arranque con mensaje claro (sin valores).
- [ ] `ENV=production` desactiva rutas demo y restringe CORS.

## Observabilidad

- [ ] `request_id` se propaga en logs y se devuelve en respuesta.
- [ ] Filtro de secretos activo en logger.
- [ ] `processing_error` truncado a 500 chars.

## Documentación

- [ ] `tasks.md` refleja el estado real (nada marcado que no esté implementado).
- [ ] Comentarios explican POR QUÉ, no QUÉ.
- [ ] Decisiones de diseño documentadas en `design.md`.
