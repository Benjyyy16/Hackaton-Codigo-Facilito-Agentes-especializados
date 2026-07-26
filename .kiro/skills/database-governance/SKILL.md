---
name: database-governance
description: Se activa cuando se modifica el schema SQL, se propone una migración, se ejecuta SQL ad-hoc o se cambian políticas de RLS.
---

# database-governance

## Responsabilidad

Proteger la integridad del esquema de datos, garantizar idempotencia del script SQL, y prevenir ejecuciones destructivas sin autorización.

## Cuándo activar

- Se modifica `db/schema.sql` o `db/rollback.sql`.
- Se propone ALTER TABLE, DROP, TRUNCATE o DELETE masivo.
- Se añade o modifica una tabla, índice, trigger o constraint.
- Se cambian políticas de RLS.
- Una `Decision` con `action_type = "execute_sql"` llega a aprobación.

## Procedimiento

1. Verificar que el script sigue siendo idempotente (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
2. Confirmar que `updated_at` trigger existe para la nueva tabla.
3. Verificar que RLS está habilitado (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`).
4. Comprobar consistencia entre schema SQL y schemas Pydantic (enums, checks, tipos).
5. Confirmar que los índices cubren los patrones de consulta de los repositorios.
6. Si hay SQL destructivo: **DETENER y pedir autorización explícita**.

## Salida esperada

- Confirmación de idempotencia.
- Lista de inconsistencias SQL ↔ Pydantic si las hay.
- Propuesta de índices faltantes basada en queries de repositorios.
- Para SQL destructivo: descripción del impacto + solicitud de aprobación.

## Límites

- **NUNCA ejecuta SQL destructivo (DROP, TRUNCATE, DELETE masivo, ALTER TABLE DROP COLUMN) sin autorización explícita del usuario.**
- NO propone migraciones con Alembic (excluido del stack).
- NO modifica datos de producción sin la cadena completa: propuesta → Decision → aprobación → ejecución.
- NO asume que un cambio de schema es retrocompatible — lo verifica.
