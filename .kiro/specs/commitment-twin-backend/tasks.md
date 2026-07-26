# Commitment Twin — Backend: Tareas

Orden de implementación. Cada tarea es pequeña, deja el repositorio en estado ejecutable y
termina con `pytest` en verde. Se implementa una a la vez.

Referencias: `RF-n` y `RNF-n` remiten a `requirements.md`.

---

## 1. Entorno y configuración — completado

- [x] 1.1 Entorno de desarrollo
  - `.venv` con Python 3.12, `requirements.txt` con versiones fijadas.
  - Retirar el scaffold plano de la raíz (`config.py`, `db.py`, `main.py`) al reemplazarlo
    por `app/`.
  - _Cierra: RNF-3.1_

- [x] 1.2 `app/core/config.py`
  - `Settings` con `pydantic-settings`, secretos como `SecretStr`.
  - Fallo de arranque cuando falta una variable obligatoria, sin revelar valores.
  - `.env.example` con todas las claves y valores vacíos.
  - _Cierra: RF-1.1, RF-1.2, RF-1.3, RF-1.4_

- [x] 1.3 `app/core/logging.py`
  - Configuración central, nivel desde `Settings`, filtro de redacción de secretos.
  - _Cierra: RNF-2.1, RNF-2.3_

- [x] 1.4 `app/core/exceptions.py`
  - Jerarquía de errores de dominio y cuerpo de error uniforme.
  - _Cierra: RNF-1.4 (parcial), tabla de errores del diseño_

- [x] 1.5 Tests
  - Config falla sin variables obligatorias; `repr` de `Settings` no filtra secretos.

Notas de implementación:

- `load_settings(**overrides)` acepta sobrescrituras para que los tests desactiven la
  lectura de `.env` con `_env_file=None`. El repositorio contiene `.env.local` real, así que
  sin esa costura un test de variable ausente encontraría valores y pasaría en falso.
- La cadena de excepciones se corta con `from None` al traducir `ValidationError`: su traza
  incluye los valores de entrada y volcarla en el arranque filtraría secretos.
- Los `.env` se leen en orden `(".env", ".env.local")`, con precedencia del entorno real.
- El filtro de redacción ignora valores de menos de 8 caracteres, que producirían ruido
  sobre texto legítimo.
- Versiones resueltas: FastAPI 0.140.0, Pydantic 2.13.4, supabase 2.31.0, httpx 0.28.1,
  pytest 9.1.1.

---

## 2. Persistencia — completado

- [x] 2.1 `db/schema.sql`
  - Cinco tablas, UUID, `created_at`, `updated_at`, `deleted_at` donde corresponde.
  - Índices, restricción única de `fingerprint`, trigger de `updated_at`, RLS activo.
  - Script idempotente y reejecutable.
  - _Cierra: RF-7.3, RF-7.4, RF-7.6, RF-6.3_

- [x] 2.2 `app/integrations/supabase/client.py`
  - `AsyncClient` vía `acreate_client`, creado y cerrado en el `lifespan`.
  - _Cierra: RF-7.2 (base)_

- [x] 2.3 `app/repositories/base.py`
  - CRUD, paginación con `count="exact"`, exclusión automática de borrados lógicos,
    traducción de errores de `postgrest` (incluido `23505` → duplicado).
  - _Cierra: RF-7.4, RF-7.5, RF-6.4_

- [x] 2.4 Los cinco repositorios
  - `ProjectRepository`, `JiraEventRepository`, `CommitmentRepository`,
    `RiskAnalysisRepository`, `AlertRepository`, cada uno con sus consultas propias.
  - _Cierra: RF-7.1, RF-7.2_

- [x] 2.5 Tests
  - Doble del `AsyncClient` que registra la cadena de llamadas; verificar filtro de
    borrados, paginación y traducción del error de unicidad.

Notas de implementación:

- El cliente se guarda en el estado de la app, no en una variable de módulo. Un singleton de
  importación obligaría a los tests a parchear globales y ataría el ciclo de vida al orden
  de los imports.
- `supabase-py` 2.31.0 no expone `aclose` ni `close` en `AsyncClient`, comprobado por
  introspección. `close_supabase_client` lo detecta por `getattr` y no falla si no existe.
- `ping()` devuelve booleano en lugar de elevar, porque su consumidor es el health check y su
  contrato es reportar estado (RF-2.3).
- Se añadieron dos verificaciones que el diseño no pedía pero que el esquema sí exige:
  `risk_analyses` debe referirse a un evento o a un compromiso, y una alerta resuelta debe
  tener `resolved_at`. Ambas se comprueban en el repositorio para fallar con un error de
  dominio en lugar de con una violación de restricción.
- `upsert_from_issue` omite los campos `None` a propósito: un payload de Jira sin fecha de
  vencimiento no debe borrar la que ya estaba registrada.
- Índice parcial único `alerts (commitment_id, reason) where status = 'open'`: impide que dos
  análisis concurrentes abran dos alertas para el mismo motivo.
- `MAX_PAGE_SIZE = 100` acota el rango que un cliente puede pedir.

Verificación del esquema:

- Sintaxis SQL validada con el parser real de PostgreSQL vía `pglast`: 22 sentencias
  analizadas sin error.
- El cuerpo del bloque `DO` se validó por separado, envolviéndolo como función
  `returns void`, con control negativo que sí detecta el error al quitar `end loop`.
- El cuerpo de `set_updated_at()` **no** se pudo validar: `pglast` falla con
  `JSONDecodeError` en toda función `returns trigger`, incluida una mínima de tres líneas,
  así que es una limitación de la herramienta y no del script. Ese cuerpo queda pendiente de
  confirmar al aplicar el esquema en Supabase.
- No hay Postgres local, así que **el esquema no se ha ejecutado contra ningún motor**. La
  validación es sintáctica, no de ejecución.
- `pglast` se retiró tras la verificación: no forma parte del stack.

---

## 3. Aplicación y health check — completado

- [x] 3.1 `app/main.py`
  - App factory, `lifespan` (sustituye `@app.on_event`), registro de routers y de
    manejadores de excepción, middleware de `request_id`.
  - _Cierra: RNF-2.2, RNF-3.2_

- [x] 3.2 `app/api/deps.py`
  - Dependencias de cliente, repositorios y servicios. `get_current_principal` como hueco
    para JWT.
  - _Cierra: RNF-1.6_

- [x] 3.3 `GET /health`
  - Estado, versión, entorno y dependencias. Degradado devuelve `200`; comprobación con
    timeout acotado.
  - _Cierra: RF-2.1, RF-2.2, RF-2.3, RF-2.4_

- [x] 3.4 Tests
  - `200` en condiciones normales; `200` degradado con Supabase caído; ausencia de datos
    sensibles en la respuesta.

Notas de implementación:

- No hay instancia de app a nivel de módulo. Se arranca con
  `uvicorn app.main:create_app --factory`, porque instanciarla en el import obligaría a tener
  el entorno completo resuelto solo para importar el módulo, incluida la recolección de
  tests.
- El `lifespan` **no** aborta el arranque si Supabase falla: el servicio queda degradado y
  `GET /health` lo reporta. Abortar dejaría al operador sin forma de consultar qué falla.
- Se distingue `unknown` de `down` en el estado de dependencia. No haber podido comprobar no
  es lo mismo que estar caído, y solo `down` degrada el servicio.
- El presupuesto de la sonda es 2 s, más corto que `HTTP_TIMEOUT_SECONDS`, para que el health
  check responda rápido incluso con la dependencia agonizando.
- Si el cliente ya envía `X-Request-ID`, se respeta, de modo que una traza que atraviesa
  varios servicios conserva el identificador.
- `Principal` y `get_current_principal` existen ya como hueco de JWT, con `PrincipalDep`
  listo para que las rutas lo declaren.

Verificación de extremo a extremo (ejecutada, no inferida):

- El proceso arranca con uvicorn y `GET /health` responde `200`.
- La cabecera `X-Request-ID` se genera, y una suministrada por el cliente se conserva.
- El identificador de correlación aparece en las líneas de log de la petición, incluidas las
  de la llamada saliente de `httpx`.
- Contra la Supabase real del proyecto: las credenciales **funcionan** (PostgREST contesta
  `404` a `/rest/v1/projects`, no `401`), y el `404` confirma que **el esquema todavía no
  está aplicado**. El endpoint devolvió `200` con `status=degraded` y la dependencia en
  `down`, así que la ruta degradada quedó verificada contra una dependencia real y no solo
  con un doble.

Pendiente conocido:

- `db/schema.sql` sigue sin aplicarse en Supabase. Hay que ejecutarlo desde el editor SQL del
  proyecto; `supabase-py` no puede lanzar DDL arbitrario sin una función RPC creada para eso.
- Las líneas de `uvicorn.access` salen con `req=-`: se emiten fuera del alcance del
  `contextvar` del middleware. Las líneas de la aplicación sí llevan el identificador, que es
  donde importa.

---

## 4. Cliente de Jira — completado

- [x] 4.1 `app/integrations/jira/client.py`
  - `httpx.AsyncClient` de vida larga, `BasicAuth`, timeouts explícitos.
  - Reintentos: `429` con `Retry-After`, `5xx` exponencial, `401`/`403` sin reintento.
  - Errores de dominio propios; logs sin cabeceras.
  - _Cierra: RF-3.1 … RF-3.7_

- [x] 4.2 `iter_issues(jql)`
  - Iterador asíncrono que encapsula la paginación.
  - _Cierra: RF-4.3_

- [x] 4.3 `app/integrations/jira/normalizer.py`
  - Payload de Jira → `NormalizedEvent`, conservando el payload original.
  - _Cierra: RF-4.4, RF-5.6_

- [x] 4.4 Tests
  - `httpx.MockTransport` para `429` con reintento, `5xx` agotando reintentos, `401` sin
    reintento, y normalización de los tres tipos de evento.

Hallazgo que cambió el diseño:

- El endpoint `/rest/api/3/search` **está retirado** de Jira Cloud y responde `410 Gone`. Se
  usa `/rest/api/3/search/jql`, con paginación por `nextPageToken` e `isLast`, sin `total` ni
  `startAt`. La primera llamada no debe enviar el token. Detalle en `design.md` 6.2.
- Hay casos documentados de `isLast` que nunca llega a `true` con tokens encadenados sin fin.
  `iter_issues` corta además por token ya visto y por tope duro de páginas
  (`MAX_PAGES = 200`), ambos con test propio que provoca el bucle a propósito.

Notas de implementación:

- Los reintentos son propios y no delegados a `httpx`, porque `429` y `5xx` merecen trato
  distinto: el primero respeta `Retry-After`, el segundo usa espera exponencial con jitter.
  El jitter evita que varias tareas reintenten sincronizadas.
- `Retry-After` se acota a `MAX_RETRY_DELAY = 30 s`: un valor desmesurado bloquearía la tarea.
  La variante con fecha HTTP se ignora y se recurre a la espera exponencial, en lugar de
  arrastrar un parser de fechas por un caso que Jira no usa en práctica.
- `410` se traduce con un mensaje propio, porque es exactamente lo que devuelve el endpoint
  retirado y conviene que el diagnóstico sea inmediato.
- El normalizador absorbe dos rarezas de Jira: `timeoriginalestimate` viene en **segundos**
  (tratarlo como horas inflaría el impacto económico por 3600), y el cuerpo de los
  comentarios llega en Atlassian Document Format, que se aplana a texto.
- `occurred_at` prioriza el `timestamp` del webhook, luego la marca del comentario, luego
  `updated` y `created`. Forma parte de la huella, así que la precedencia es explícita y está
  cubierta con tests.
- Una fecha ilegible devuelve `None` en lugar de elevar: un campo roto no debe tumbar la
  ingesta de un evento por lo demás válido.
- `create_jira_http_client` acepta un `transport` opcional para que los tests inyecten
  `MockTransport` sin tocar atributos privados del cliente.
- El cliente HTTP se crea en el `lifespan` y se cierra al apagar, verificado con test.

---

## 5. Ingesta desde Jira — completado

- [x] 5.1 `app/integrations/jira/security.py`
  - Validación del secreto compartido con `hmac.compare_digest`, por cabecera o por
    parámetro de consulta.
  - _Cierra: RF-5.2, RNF-1.3_

- [x] 5.2 `app/services/webhook_service.py`
  - Validar, normalizar, calcular `fingerprint`, detectar duplicado, persistir.
  - _Cierra: RF-5.3, RF-5.4, RF-5.5, RF-6.1, RF-6.2_

- [x] 5.3 `POST /webhooks/jira`
  - Respuesta rápida; análisis vía `BackgroundTasks`; el evento persiste aunque el análisis
    falle.
  - _Cierra: RF-5.1, RF-5.7, RF-5.8_

- [x] 5.4 `app/services/jira_sync_service.py` y `POST /jira/sync`
  - JQL propio u obtenido de la clave de proyecto, paginación completa, recuento de
    procesados, creados y omitidos, idempotencia, `404` si el proyecto no existe.
  - _Cierra: RF-4.1 … RF-4.7_

- [x] 5.5 Tests
  - Secreto inválido no persiste nada; duplicado responde `200` sin segunda inserción;
    tipo no soportado responde `202`; sincronización repetida no duplica.

Notas de implementación:

- El gancho de post-ingesta (`run_post_ingest` en `api/deps.py`) es una **costura, todavía sin
  análisis real**: hoy solo registra. El orquestador se enchufa en el bloque 7. La ruta ya lo
  programa con `BackgroundTasks` y hay test que lo comprueba, así que enchufarlo no toca la
  ruta.
- La deduplicación tiene dos capas y ambas están cubiertas: la comprobación previa por huella,
  y la restricción de unicidad para la carrera entre dos entregas simultáneas. El segundo caso
  tiene test propio, con la lectura devolviendo vacío y la inserción fallando con `23505`.
- Un duplicado **no** programa análisis: reanalizar un evento ya visto solo gastaría trabajo.
- `build_project_jql` escapa las comillas de la clave de proyecto, para que un valor
  inesperado no pueda alterar la estructura de la consulta. Ordena por `updated DESC` para que,
  si la recogida se corta por un límite, lo traído sea lo más reciente.
- En la sincronización, un issue que falla se cuenta y no aborta la carga: abortar dejaría el
  proyecto a medio cargar por un solo registro defectuoso.
- La existencia del proyecto se comprueba **antes** de iterar, para que una clave equivocada
  dé `404` en lugar de una sincronización vacía silenciosa.
- El doble de Supabase ganó una cola de respuestas (`then`, `then_raises`). Sin ella no se
  puede representar un flujo de lectura y escritura sobre la misma tabla, que es exactamente
  lo que hace la ingesta.
- La fixture `app` instala también un cliente HTTP de Jira sin red. Sin él, cualquier ruta que
  declare esa dependencia fallaba antes de validar el cuerpo, y los tests de validación
  acababan comprobando otra cosa.
- Se quitó el `exc_info` del log del repositorio: el manejador ya registra la traza y estaba
  saliendo duplicada. Tampoco se registra el mensaje de PostgREST, que en algunas violaciones
  incluye valores de la fila.

Verificación de extremo a extremo (ejecutada contra un proceso real):

- Sin secreto y con secreto incorrecto: `401`, y **cero** llamadas a Supabase en el log, así
  que nada se persistió antes de validar.
- Secreto correcto por cabecera y por parámetro de consulta: ambos aceptados.
- Evento no soportado: `202`, sin tocar el almacenamiento.
- Evento válido autenticado: llega hasta la búsqueda por huella y devuelve `503` con
  `PGRST205`, lo que confirma a la vez el orden del flujo y que el esquema sigue sin aplicar.
- El secreto pasado por URL aparece **redactado** en el log de acceso de uvicorn. Sin el filtro
  habría quedado en claro, que es el riesgo real de admitir el secreto en la URL.

---

## 6. Agentes

- [ ] 6.1 `app/agents/base.py`
  - Protocolo `Agent`, `AgentContext`, `AgentOutcome`, `Signal`. Sin `fastapi`, sin
    `supabase`.
  - _Cierra: RF-8.2, RF-8.3_

- [ ] 6.2 `CommitmentAgent`, `TechnicalAgent`, `FinancialAgent`
  - Reglas determinísticas; `now` inyectado por contexto.
  - _Cierra: RF-8.1, RF-8.7_

- [ ] 6.3 `RiskAgent`
  - Pesos como constantes con nombre; puntuación 0–100 y severidad por tramos.
  - _Cierra: RF-8.5_

- [ ] 6.4 `OrchestratorAgent`
  - Agrega resultados; aísla el fallo de cada agente y marca `is_partial`.
  - _Cierra: RF-8.5, RF-8.6_

- [ ] 6.5 Tests
  - Cada agente aislado, sin red ni base de datos; determinismo; fallo de un agente produce
    análisis parcial en lugar de excepción.

---

## 7. Análisis, alertas y API de lectura

- [ ] 7.1 `app/services/analysis_service.py`
  - Compone contexto desde repositorios, ejecuta el orquestador, persiste el análisis.
  - _Cierra: RF-8 (integración), RF-7.2_

- [ ] 7.2 `app/services/alert_service.py`
  - Umbral configurable: crear, actualizar la abierta, resolver al bajar del umbral.
  - Impacto económico tomado de `FinancialAgent`.
  - _Cierra: RF-9.1 … RF-9.4_

- [ ] 7.3 `GET /events`, `GET /events/{event_id}`
  - Paginación descendente, filtros por proyecto y tipo, `404`, `422` fuera de rango.
  - _Cierra: RF-10.1, RF-10.2, RF-10.3, RF-10.6_

- [ ] 7.4 `GET /alerts`, `GET /alerts/{alert_id}`
  - Paginación, filtros por severidad y estado, `404`.
  - _Cierra: RF-10.4, RF-10.5_

- [ ] 7.5 `POST /analysis/run`
  - Por evento o por proyecto; `404` si no existe; `422` si no se indica ninguno; persiste
    y difunde igual que el webhook.
  - _Cierra: RF-11.1 … RF-11.4_

- [ ] 7.6 Schemas y OpenAPI
  - Respuestas descritas por schemas; todos los endpoints en la documentación.
  - _Cierra: RF-10.7, RNF-4.4_

- [ ] 7.7 Tests
  - Paginación, filtros, `404`, `422`, y umbral de alerta en sus tres transiciones.

---

## 8. Tiempo real

- [ ] 8.1 `app/websocket/manager.py`
  - `ConnectionManager` con `asyncio.Lock`; difusión aislada por cliente; sin clientes no
    es error.
  - _Cierra: RF-12.1, RF-12.3, RF-12.4, RF-12.5_

- [ ] 8.2 `WS /ws/events`
  - Acepta y mantiene la conexión; retira limpiamente al desconectar.
  - _Cierra: RF-12.1, RF-12.3_

- [ ] 8.3 Difusión desde el análisis
  - `event.created`, `analysis.completed`, `alert.created`, `alert.resolved` como sobres
    tipados.
  - _Cierra: RF-12.2, RF-12.6, RF-12.7_

- [ ] 8.4 Tests
  - Conexión, recepción de difusión, desconexión sin afectar a otros clientes, difusión sin
    clientes.

---

## 9. Cierre

- [ ] 9.1 Suite completa en verde, sin red ni dependencias reales.
  - _Cierra: RNF-4.1, RNF-4.2_

- [ ] 9.2 Revisión de la regla de dependencia
  - Ningún servicio, ruta o agente importa el cliente de Supabase; ninguna ruta contiene
    lógica de negocio.
  - _Cierra: RNF-3.2, RNF-3.3, RNF-3.4, RF-7.2, RF-8.3_

- [ ] 9.3 Revisión de secretos
  - Sin secretos en el repositorio; `SUPABASE_SERVICE_ROLE_KEY` ausente de toda respuesta;
    logs limpios.
  - _Cierra: RNF-1.1, RNF-1.2_

- [ ] 9.4 `README` de arranque y registro del webhook en Jira
  - Cómo levantar, cómo aplicar el esquema, cómo exponer el webhook para la demo.

---

## Fuera de alcance

Frontend, componentes UI y cliente. Autenticación de usuario final. LLMs en el camino
crítico. Django, Flask, Redis, Celery, Firebase, SQLite, SQLAlchemy, Alembic.
