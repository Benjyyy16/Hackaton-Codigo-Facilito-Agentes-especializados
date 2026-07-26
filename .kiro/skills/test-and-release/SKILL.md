---
name: test-and-release
description: Se activa cuando se escriben tests, se ejecuta la suite, se prepara un release o se verifica cobertura.
---

# test-and-release

## Responsabilidad

Garantizar que los tests son deterministas, sin red, cubren el comportamiento crítico y que el release es reproducible.

## Cuándo activar

- Se añade funcionalidad nueva (debe tener test).
- Se corrige un bug (debe tener test de regresión).
- Se prepara un release o deploy.
- Los tests fallan y hay que diagnosticar.
- Se revisa cobertura.

## Procedimiento

1. Verificar que los tests corren sin red: `httpx.MockTransport`, fakes de Supabase, sin llamadas reales.
2. Confirmar que los tests de agentes son puramente de entrada/salida (sin mocks de I/O).
3. Verificar que los tests de tiempo inyectan `now` via contexto, no parchean `datetime`.
4. Comprobar que `pytest` pasa completamente antes de declarar ready.
5. Para release:
   - Todos los tests pasan.
   - No hay warnings de deprecation sin plan.
   - El schema SQL es consistente con los schemas Pydantic.
   - Las variables de entorno obligatorias están documentadas.
   - El `conftest.py` no depende de estado externo.

## Salida esperada

- Resultado de `pytest` (passed/failed/skipped).
- Lista de tests faltantes para funcionalidad nueva.
- Para release: checklist completa con estado de cada punto.

## Límites

- NO ejecuta tests contra servicios reales (Jira, Supabase, GitHub).
- NO decide qué funcionalidad testear — eso lo dicta el cambio.
- NO bloquea un release por cobertura insuficiente si la funcionalidad crítica está cubierta.
