# Datgent API — Referencia de Endpoints

Generado verificando `app.openapi()` de la aplicación real. No contiene endpoints inventados.

## Health

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/health` | Estado del servicio y de sus dependencias | 200 |
| GET | `/ready` | Readiness probe | 200 |

## Auth

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| POST | `/auth/register` | Registrar nuevo usuario | 201, 422 |
| POST | `/auth/login` | Login con email y contraseña | 200, 401, 422 |
| POST | `/auth/logout` | Logout | 200 |
| GET | `/auth/me` | Obtener usuario actual | 200, 401 |
| GET | `/auth/oauth/{provider}/login` | Iniciar login con OAuth | 302 |
| GET | `/auth/oauth/{provider}/callback` | Callback de OAuth login | 302 |

## Commitments

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/commitments` | Listar compromisos | 200 |
| POST | `/commitments` | Crear compromiso | 201, 422 |
| GET | `/commitments/{commitment_id}` | Obtener compromiso | 200, 404 |
| PATCH | `/commitments/{commitment_id}` | Actualizar compromiso | 200, 404, 422 |
| POST | `/commitments/{commitment_id}/analyze` | Disparar análisis de riesgo | 202, 404 |
| GET | `/commitments/{commitment_id}/findings` | Hallazgos del compromiso | 200, 404 |
| GET | `/commitments/{commitment_id}/timeline` | Cronología del compromiso | 200, 404 |

## Risk Cases

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/risk-cases` | Listar casos de riesgo | 200 |
| GET | `/risk-cases/{risk_case_id}` | Obtener caso de riesgo | 200, 404 |
| POST | `/risk-cases/{risk_case_id}/reanalyze` | Reanalizar caso de riesgo | 202, 404 |

## Alerts

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/alerts` | Listar alertas | 200 |
| PATCH | `/alerts/{alert_id}/acknowledge` | Reconocer alerta | 200, 404 |

## Decisions

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/decisions` | Listar decisiones | 200 |
| POST | `/decisions/{decision_id}/approve` | Aprobar decisión | 200, 404, 409 |
| POST | `/decisions/{decision_id}/reject` | Rechazar decisión | 200, 404, 409 |
| POST | `/decisions/{decision_id}/execute` | Ejecutar decisión aprobada | 200, 404, 409 |

## Agents

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/agents` | Listar agentes disponibles | 200 |
| GET | `/agents/status` | Estado de los agentes registrados | 200 |
| POST | `/agents/analyze` | Ejecutar análisis de riesgo | 202, 422 |
| POST | `/agents/chat` | Chat con los agentes | 200, 422 |
| GET | `/agent-runs/{agent_run_id}` | Obtener ejecución de agente | 200, 404 |

## Documents

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| POST | `/documents` | Indexar documento | 201, 422 |
| GET | `/documents/search` | Buscar documentos por texto | 200 |
| GET | `/documents/{document_id}` | Obtener documento por ID | 200, 404 |

## Demo

Disponibles solo si `ENV != production` o `DEMO_MODE_ENABLED=true`. Devuelven 404 en producción sin la bandera (no revelar existencia).

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| POST | `/demo/seed` | Crear datos del caso demo | 201, 404 |
| POST | `/demo/simulate` | Simular análisis del caso demo | 202, 404 |
| DELETE | `/demo/reset` | Limpiar datos del caso demo | 200, 404 |

## Providers & Integrations

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/providers` | Providers registrados y su estado | 200 |
| POST | `/providers/{provider}/sync` | Sincroniza contenedor via provider | 200, 404, 502 |
| GET | `/integrations` | Listar integraciones del usuario | 200 |
| POST | `/integrations/{provider}` | Vincular integración | 201, 422 |
| DELETE | `/integrations/{provider}` | Desconectar integración | 200, 404 |
| GET | `/integrations/{provider}/test` | Probar conexión | 200, 502 |

## OAuth

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| GET | `/oauth/{provider}/authorize` | Iniciar flujo OAuth | 302 |
| GET | `/oauth/{provider}/callback` | Callback OAuth | 302 |

## Finance

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| POST | `/finance/upload` | Subir Excel o CSV financiero | 200, 422 |
| POST | `/finance/erp` | Conectar con ERP | 200, 422 |

## Webhooks

| Método | Ruta | Propósito | Códigos |
|--------|------|-----------|---------|
| POST | `/webhooks/{provider}` | Recibe evento de un provider externo | 200, 202, 401 |

## WebSocket

| Protocolo | Ruta | Propósito |
|-----------|------|-----------|
| WS | `/ws/events` | Canal de eventos en tiempo real (solo lectura) |

Mensajes de salida tipados: `event.created`, `analysis.completed`, `alert.created`, `alert.resolved`, `decision.updated`.

El cliente solo puede enviar `ping` (recibe `pong`). Cualquier otro mensaje se ignora.
