# Commitment Twin — Backend: Requisitos

## Contexto

Plataforma para empresas de desarrollo de software que detecta compromisos en riesgo
antes de que provoquen pérdidas económicas. Este documento cubre **exclusivamente el
backend**. No hay requisitos de frontend en este alcance.

La fuente de verdad de los eventos es Jira. La persistencia es Supabase. El análisis lo
realizan agentes backend independientes. Los resultados se exponen por REST y se emiten
en tiempo real por WebSocket.

## Alcance

Dentro del alcance:

- Ingesta de eventos de Jira por webhook.
- Sincronización inicial por JQL.
- Persistencia en Supabase mediante `supabase-py`.
- Análisis de compromisos y riesgo con agentes determinísticos.
- Generación de alertas.
- API REST de lectura.
- Difusión en tiempo real por WebSocket.

Fuera del alcance:

- Frontend, componentes UI, código de cliente.
- Autenticación de usuarios finales (solo se prepara el terreno para JWT).
- LLMs en el camino crítico. Los agentes del MVP son determinísticos, con contratos que
  permiten sustituirlos por un LLM sin tocar los servicios que los invocan.

## Stack obligatorio

Python, FastAPI, Pydantic v2, Supabase, `supabase-py`, `httpx`, WebSockets de FastAPI,
`pytest`, `pydantic-settings`.

Explícitamente prohibidos: Django, Flask, Redis, Celery, Firebase, SQLite, SQLAlchemy,
Alembic.

## Requisitos funcionales

### RF-1 — Configuración por entorno

Como operador quiero que toda la configuración provenga del entorno, para poder desplegar
sin modificar código.

Criterios de aceptación:

1. Cuando la aplicación arranca, el sistema carga la configuración desde variables de
   entorno y, si existe, desde un archivo `.env`.
2. Cuando falta una variable obligatoria, el arranque falla con un mensaje que nombra la
   variable ausente y no incluye ningún valor secreto.
3. El repositorio no contiene ningún secreto. Los archivos con secretos están ignorados
   por git y existe un `.env.example` con las claves y valores vacíos.
4. Cuando se representa la configuración en logs o en una respuesta, los valores de
   `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `JIRA_API_TOKEN` y
   `JIRA_WEBHOOK_SECRET` aparecen ofuscados.

### RF-2 — Health check

Como operador quiero un endpoint de salud, para saber si el servicio y sus dependencias
responden.

Criterios de aceptación:

1. `GET /health` responde `200` con el estado del servicio, su versión y el entorno.
2. `GET /health` no requiere autenticación y no expone configuración sensible.
3. Cuando Supabase no responde, `GET /health` sigue devolviendo `200` con el servicio en
   estado degradado y la dependencia marcada como caída, en lugar de fallar.
4. La comprobación de dependencias tiene un timeout acotado para que el endpoint no se
   quede colgado.

### RF-3 — Cliente de Jira

Como sistema quiero consultar la API de Jira de forma fiable, para obtener issues y sus
metadatos.

Criterios de aceptación:

1. El cliente autentica con Jira mediante HTTP Basic usando email y API token.
2. Toda petición HTTP tiene timeout explícito de conexión y de lectura.
3. Cuando Jira responde `429`, el cliente reintenta respetando la cabecera `Retry-After`,
   con un número máximo de reintentos acotado.
4. Cuando Jira responde `5xx`, el cliente reintenta con espera exponencial hasta el máximo
   de reintentos.
5. Cuando Jira responde `401` o `403`, el cliente no reintenta y eleva un error de
   autenticación.
6. Cuando se agotan los reintentos, el cliente eleva una excepción de dominio propia y no
   propaga la excepción de `httpx` hacia las capas superiores.
7. Los logs del cliente nunca contienen el API token ni la cabecera de autorización.

### RF-4 — Sincronización inicial por JQL

Como usuario quiero cargar el estado actual de un proyecto, para tener una base sobre la
que detectar cambios.

Criterios de aceptación:

1. `POST /jira/sync` acepta una clave de proyecto y, opcionalmente, un JQL propio.
2. Cuando no se indica JQL, el sistema construye uno a partir de la clave de proyecto.
3. La sincronización recorre todas las páginas de resultados hasta agotarlas.
4. Cada issue recuperado se normaliza al modelo interno de evento y se persiste.
5. La respuesta indica cuántos issues se procesaron, cuántos se crearon y cuántos se
   omitieron por duplicado.
6. Cuando el proyecto no existe en Jira, la respuesta es `404` con un error de dominio.
7. La sincronización es idempotente: repetirla con el mismo estado en Jira no crea eventos
   duplicados.

### RF-5 — Recepción de webhooks de Jira

Como sistema quiero recibir cambios de Jira en el momento en que ocurren, sin polling.

Criterios de aceptación:

1. `POST /webhooks/jira` acepta el payload de Jira y responde en menos de un segundo en
   condiciones normales.
2. Cuando el secreto compartido no es válido o falta, la respuesta es `401` y el payload no
   se persiste ni se procesa.
3. El endpoint acepta los tipos de evento de creación de issue, actualización de issue y
   creación de comentario.
4. Cuando el tipo de evento no está soportado, la respuesta es `202` y el evento se
   descarta de forma explícita y registrada.
5. Cuando llega un evento ya recibido, el sistema lo detecta como duplicado, no lo vuelve a
   persistir y responde `200` indicando que fue duplicado.
6. El payload original de Jira se guarda íntegro en una columna JSONB.
7. El análisis se ejecuta fuera del ciclo de petición y respuesta, de modo que un análisis
   lento no retrase la respuesta a Jira.
8. Cuando el análisis en segundo plano falla, el evento ya persistido no se pierde y el
   fallo queda registrado.

### RF-6 — Deduplicación

Como sistema quiero descartar eventos repetidos, para que el análisis no se distorsione.

Criterios de aceptación:

1. Cada evento tiene una huella determinística derivada del identificador del issue, el
   tipo de evento y la marca temporal del cambio.
2. Cuando dos payloads producen la misma huella, solo el primero se persiste.
3. La unicidad se garantiza además con una restricción en base de datos, no solo en código.
4. Cuando la inserción viola la restricción de unicidad, el sistema lo trata como duplicado
   y no como error.

### RF-7 — Persistencia en Supabase

Como sistema quiero un acceso a datos aislado, para poder cambiar el almacenamiento sin
reescribir la lógica de negocio.

Criterios de aceptación:

1. Existen repositorios separados para proyectos, eventos de Jira, compromisos, análisis de
   riesgo y alertas.
2. Los servicios acceden a los datos únicamente a través de repositorios. Ningún servicio,
   ruta o agente invoca el cliente de Supabase directamente.
3. Toda tabla tiene identificador UUID, `created_at` y `updated_at`.
4. Las entidades que representan estado de negocio soportan borrado lógico mediante
   `deleted_at`, y las consultas por defecto excluyen los registros borrados.
5. Cuando Supabase devuelve un error, el repositorio lo traduce a una excepción de dominio.
6. El esquema SQL está versionado en el repositorio como script idempotente.

### RF-8 — Agentes de análisis

Como sistema quiero un análisis modular, para poder evolucionar cada dimensión de riesgo de
forma independiente.

Criterios de aceptación:

1. Existen cinco agentes: compromisos, técnico, financiero, riesgo y orquestador.
2. Cada agente recibe datos estructurados y devuelve un modelo Pydantic.
3. Ningún agente importa FastAPI ni el cliente de Supabase.
4. Cada agente es invocable de forma aislada en un test, sin red y sin base de datos.
5. El orquestador compone los resultados de los demás agentes en un único análisis con
   puntuación global de riesgo y nivel de severidad.
6. Cuando un agente falla, el orquestador registra el fallo, continúa con el resto y marca
   el análisis como parcial.
7. Los agentes son determinísticos: la misma entrada produce la misma salida.

### RF-9 — Generación de alertas

Como responsable de entrega quiero recibir alertas cuando un compromiso entra en riesgo.

Criterios de aceptación:

1. Cuando la puntuación de riesgo de un análisis supera el umbral configurado, el sistema
   crea una alerta.
2. La alerta registra severidad, motivo, impacto económico estimado y el análisis que la
   originó.
3. Cuando ya existe una alerta abierta para el mismo compromiso y motivo, el sistema la
   actualiza en lugar de crear una nueva.
4. Cuando la puntuación de riesgo cae por debajo del umbral, la alerta abierta se resuelve.

### RF-10 — API de lectura

Como consumidor de la API quiero consultar eventos y alertas.

Criterios de aceptación:

1. `GET /events` devuelve eventos paginados, ordenados del más reciente al más antiguo.
2. `GET /events` admite filtro por clave de proyecto y por tipo de evento.
3. `GET /events/{event_id}` devuelve un evento y `404` cuando no existe.
4. `GET /alerts` devuelve alertas paginadas y admite filtro por severidad y por estado.
5. `GET /alerts/{alert_id}` devuelve una alerta y `404` cuando no existe.
6. Cuando los parámetros de paginación están fuera de rango, la respuesta es `422`.
7. Toda respuesta está descrita por un schema Pydantic y aparece en la documentación
   OpenAPI.

### RF-11 — Análisis a demanda

Como usuario quiero poder relanzar el análisis, para reevaluar tras un cambio de criterios.

Criterios de aceptación:

1. `POST /analysis/run` acepta un identificador de evento o una clave de proyecto.
2. Cuando el objetivo no existe, la respuesta es `404`.
3. El análisis persiste su resultado y emite la actualización por WebSocket igual que el
   flujo de webhook.
4. Cuando no se indica ni evento ni proyecto, la respuesta es `422`.

### RF-12 — Difusión en tiempo real

Como consumidor quiero recibir cambios en el momento, sin consultar repetidamente.

Criterios de aceptación:

1. `WS /ws/events` acepta conexiones y las mantiene abiertas.
2. Cuando se persiste un evento y se completa su análisis, el mensaje se difunde a todos los
   clientes conectados.
3. Cuando un cliente se desconecta, el sistema lo retira del registro sin afectar a los
   demás.
4. Cuando el envío a un cliente falla, el fallo se aísla y no interrumpe la difusión al
   resto.
5. Cuando no hay clientes conectados, la difusión no genera error.
6. Los mensajes difundidos tienen un tipo declarado y una carga descrita por un schema.
7. El sistema no usa polling en ningún punto del flujo.

## Requisitos no funcionales

### RNF-1 — Seguridad

1. Ningún secreto está escrito en el código ni en los documentos del repositorio.
2. `SUPABASE_SERVICE_ROLE_KEY` no se expone en ninguna respuesta de la API.
3. Los webhooks se validan antes de cualquier persistencia.
4. Todas las entradas se validan con Pydantic.
5. Todas las llamadas salientes tienen timeout.
6. La estructura permite añadir dependencias de autorización JWT sin reescribir las rutas.

### RNF-2 — Observabilidad

1. La configuración de logging es central y explícita.
2. Cada petición y cada evento procesado se registran con un identificador de correlación.
3. Los errores se registran con traza; los secretos nunca aparecen en los logs.

### RNF-3 — Estructura

1. El árbol del proyecto sigue la estructura acordada bajo `app/`.
2. Las rutas no contienen lógica de negocio; delegan en servicios.
3. Los servicios no contienen SQL ni llamadas al cliente de Supabase.
4. Las integraciones externas están confinadas en `app/integrations/`.

### RNF-4 — Calidad

1. Cada funcionalidad tiene tests con `pytest`.
2. Los tests no requieren red ni una instancia real de Supabase o Jira.
3. Las funciones públicas están tipadas.
4. Todos los endpoints aparecen documentados en OpenAPI.

## Dependencias externas y supuestos

1. Se dispone de un proyecto Supabase con su URL y sus claves.
2. Se dispone de una cuenta de Jira Cloud con email, API token y dominio.
3. El secreto de webhook lo define este backend y se configura en Jira al registrar el
   webhook.
4. Jira Cloud no firma los webhooks con HMAC. La validación se resuelve con un secreto
   compartido que viaja en la URL del webhook o en una cabecera, según se configure en Jira.
5. Sin credenciales reales de Jira, la sincronización y el webhook se validan con tests que
   sustituyen el transporte HTTP.
