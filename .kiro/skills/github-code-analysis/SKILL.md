---
name: github-code-analysis
description: Se activa cuando se trabaja con el provider de GitHub, webhooks de PR/commits, o el agente técnico que analiza señales de código.
---

# github-code-analysis

## Responsabilidad

Garantizar la correcta ingesta de señales de GitHub y su traducción a hallazgos técnicos vinculados a compromisos.

## Cuándo activar

- Se modifica `providers/github.py` o su webhook handler.
- Se trabaja en el agente técnico con señales de PRs, commits, reviews.
- Se añade un nuevo event type de GitHub.
- Se ajusta la firma HMAC de webhooks GitHub.

## Procedimiento

1. Verificar firma HMAC SHA-256 (`X-Hub-Signature-256`) con `hmac.compare_digest`.
2. Confirmar que el provider implementa `EventSourceProvider` correctamente.
3. Verificar que los eventos se normalizan a `ExternalEvent` antes de persistir.
4. Comprobar que las señales técnicas (PR bloqueado, build roto, review pendiente) se traducen a `Finding` con evidencia.
5. Validar que `source_url` apunta al recurso real en GitHub.
6. Confirmar que tokens de GitHub nunca aparecen en logs ni payloads persistidos.

## Salida esperada

- Mapeo de event types GitHub → señales del dominio.
- Confirmación de seguridad del webhook.
- Verificación de que el agente técnico puede consumir los datos sin I/O.

## Límites

- NO ejecuta llamadas reales a la API de GitHub.
- NO decide qué métricas de código son relevantes — eso es producto.
- NO modifica la firma del protocolo `EventSourceProvider`.
