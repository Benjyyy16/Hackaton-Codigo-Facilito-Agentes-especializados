---
name: jira-realtime
description: Se activa cuando se trabaja con webhooks de Jira, sincronización JQL o normalización de eventos Jira.
---

# jira-realtime

## Responsabilidad

Asegurar la correcta ingesta, deduplicación y normalización de eventos desde Jira Cloud.

## Cuándo activar

- Se modifica el provider de Jira o su webhook handler.
- Se trabaja en la normalización de payloads Jira.
- Se ajusta la lógica de deduplicación (`event_hash`).
- Se cambia la paginación JQL (`/rest/api/3/search/jql` con `nextPageToken`).

## Procedimiento

1. Verificar que el webhook valida el secreto compartido con `hmac.compare_digest`.
2. Confirmar deduplicación: `sha256(provider:external_id:event_type:occurred_at)` → `event_hash` único en BD.
3. Verificar que la respuesta a Jira es rápida (persistir evento, luego BackgroundTask).
4. Confirmar que la paginación usa `nextPageToken` / `isLast` (NO `startAt`/`total`, endpoint retirado).
5. Verificar defensas contra bucle infinito: token repetido, tope de páginas, página vacía.
6. Comprobar que el normalizador traduce a `ExternalEvent` del dominio, no expone structs de Jira.

## Salida esperada

- Confirmación de que la cadena webhook → persistencia → análisis es correcta.
- Lista de event types soportados y su mapeo.
- Verificación de que errores no pierden el evento (se persiste ANTES del análisis).

## Límites

- NO ejecuta llamadas reales a Jira en revisión — solo verifica lógica.
- NO decide qué campos de Jira son relevantes para el negocio.
- NO modifica el schema de `source_events`.
