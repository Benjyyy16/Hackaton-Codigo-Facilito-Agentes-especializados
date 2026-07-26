# Datgent Backend — Requisitos

## Requisitos Funcionales

### RF-1: Configuración y arranque

- **RF-1.1** — El sistema DEBE arrancar con las variables de entorno obligatorias (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`). Ausencia = fallo inmediato.
- **RF-1.2** — Los mensajes de error de configuración DEBEN nombrar la variable ausente pero NUNCA su valor.
- **RF-1.3** — Los secretos DEBEN declararse como `SecretStr` para que su repr los ofusque.
- **RF-1.4** — Un fallo al conectar storage NO DEBE impedir el arranque: el servicio queda degradado.

### RF-2: Health y providers

- **RF-2.1** — `GET /health` DEBE reportar el estado de cada provider registrado.
- **RF-2.2** — Solo se registran providers cuyas credenciales están presentes.
- **RF-2.3** — `health()` de cada provider NO DEBE elevar excepciones.

### RF-3: Ingesta de eventos

- **RF-3.1** — Cada provider normaliza sus eventos a `ExternalEvent` antes de persistir.
- **RF-3.2** — Deduplicación por `event_hash` = `sha256(provider:external_id:event_type:occurred_at)`, único en BD.
- **RF-3.3** — El evento se persiste ANTES del análisis. Si el análisis falla, el evento sigue.
- **RF-3.4** — Webhooks responden rápido: persistir + BackgroundTask.
- **RF-3.5** — Eventos no soportados → 202 descartado explícito.

### RF-4: Webhooks y seguridad

- **RF-4.1** — GitHub: verificar HMAC SHA-256 con `hmac.compare_digest`. Sin firma → 401.
- **RF-4.2** — Jira: verificar secreto compartido con `hmac.compare_digest`. Sin secreto → 401.
- **RF-4.3** — Payload > 1 MB se rechaza antes de parsear.

### RF-5: Dominio Commitment

- **RF-5.1** — Commitment es la entidad central. Toda tabla tiene FK directa o transitiva hacia ella.
- **RF-5.2** — Ciclo de vida: `open → at_risk → (breached | met)`, `cancelled` como salida lateral.
- **RF-5.3** — `at_risk` lo fija el orquestador cuando el score cruza el umbral, no se declara a mano.
- **RF-5.4** — `CommitmentSnapshot` (frozen) es lo que reciben los agentes. Inmutable.

### RF-6: Agentes

- **RF-6.1** — Contrato común: `Agent.run(context) → AgentOutput`.
- **RF-6.2** — Sin I/O: función pura de datos a datos.
- **RF-6.3** — Cada hallazgo DEBE tener evidencia; sin ella pesa menos.
- **RF-6.4** — `missing_information` obligatorio cuando no puede concluir.
- **RF-6.5** — Acciones propuestas con `requires_human_approval=True`.

### RF-7: Orquestador

- **RF-7.1** — Ejecuta agentes cada uno en `try/except`. Fallo individual = `is_partial=True`.
- **RF-7.2** — Score consolidado con pesos constantes nombrados.
- **RF-7.3** — Produce RiskCase: cadena causal + pre-mortem + 3 escenarios.
- **RF-7.4** — Tres escenarios obligatorios: `do_nothing`, `add_capacity`, `renegotiate_scope`.
- **RF-7.5** — Separación: `facts` / `inferences` / `assumptions`.

### RF-8: Alertas

- **RF-8.1** — Score ≥ `RISK_ALERT_THRESHOLD` + sin alerta abierta → crear alerta.
- **RF-8.2** — Score ≥ umbral + alerta existente → actualizar.
- **RF-8.3** — Score < umbral + alerta abierta → resolver.
- **RF-8.4** — Índice único parcial: solo una alerta abierta por commitment.

### RF-9: Decisiones

- **RF-9.1** — Toda acción crítica requiere aprobación humana vía `Decision`.
- **RF-9.2** — No se puede ejecutar lo que no se aprobó (constraint en BD).
- **RF-9.3** — `ActionType` es enum cerrado: cada valor tiene un ejecutor.

### RF-10: WebSocket

- **RF-10.1** — Difusión en tiempo real sin polling.
- **RF-10.2** — Un socket muerto no impide la entrega al resto.
- **RF-10.3** — Mensajes tipados: `{"type": "...", "data": {...}, "emitted_at": "..."}`.

### RF-11: Timeline

- **RF-11.1** — Todo evento significativo se registra en `timeline_events`.
- **RF-11.2** — Actores tipados: system, agent, human, provider.

### RF-12: Documentos (RAG)

- **RF-12.1** — Fragmentos asociables a proyecto o compromiso.
- **RF-12.2** — Recuperación textual funciona sin pgvector (fallback a `ilike`).

---

## Requisitos No Funcionales

- **RNF-1** — Tests sin red: `MockTransport`, fakes, fixtures deterministas.
- **RNF-2** — Correlación de logs: `request_id` en cada línea, propagado por `contextvars`.
- **RNF-3** — Timeouts configurables. Ninguna llamada externa sin timeout.
- **RNF-4** — Script SQL idempotente. Sin migraciones. Reejecutar = sin efecto.
- **RNF-5** — Errores opacos: nunca filtran stack traces, nombres de tabla, ni valores de config.
- **RNF-6** — `updated_at` por trigger en BD, no desde aplicación.
- **RNF-7** — Latencia de respuesta a webhooks < 500ms (persiste y delega).
- **RNF-8** — RLS activo en todas las tablas sin políticas permisivas para anon.
