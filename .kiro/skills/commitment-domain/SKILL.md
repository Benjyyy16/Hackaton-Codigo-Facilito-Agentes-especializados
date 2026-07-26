---
name: commitment-domain
description: Se activa cuando se trabaja sobre la entidad Commitment, sus schemas, repositorio, ciclo de vida o relaciones con otras entidades.
---

# commitment-domain

## Responsabilidad

Garantizar la integridad del modelo de dominio centrado en Commitment y sus invariantes.

## Cuándo activar

- Se modifica `schemas/domain.py` (modelos de Commitment).
- Se toca `repositories/domain.py` (CommitmentRepository).
- Se añade un campo, estado o transición al compromiso.
- Se integra una nueva fuente que crea o modifica compromisos.

## Procedimiento

1. Verificar que los enums de Python coinciden con los `check` de `db/schema.sql`.
2. Confirmar que las transiciones de estado son válidas: `open → at_risk → (breached | met)`, con `cancelled` como salida lateral.
3. Verificar que `CommitmentSnapshot` (frozen) se usa en agentes, no `CommitmentRead`.
4. Comprobar que `financial_exposure` y `currency` están presentes cuando el compromiso tiene impacto económico.
5. Validar que toda escritura pasa por `CommitmentRepository`, nunca directo a tabla.
6. Confirmar que `project_id` es obligatorio (FK con cascade).

## Salida esperada

- Confirmación de consistencia schema SQL ↔ Pydantic.
- Lista de transiciones de estado validadas.
- Alerta si algún agente muta el snapshot o si hay escritura directa.

## Límites

- NO decide qué transiciones de estado son correctas para el negocio — eso es producto.
- NO modifica el schema SQL (eso es database-governance).
- NO toca tests; solo valida el modelo.
