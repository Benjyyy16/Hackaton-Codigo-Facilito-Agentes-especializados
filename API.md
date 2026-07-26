# Commitment Twin Backend - API Reference

## Autenticación

### 1. Registrar nuevo usuario

**Endpoint:** `POST /auth/register`

**Descripción:** Crea una nueva cuenta de usuario.

**Request:**
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "SecurePassword123"
}
```

**Response (201 Created):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Validaciones:**
- Email debe ser válido (contener @)
- Nombre no puede estar vacío
- Contraseña debe tener al menos 8 caracteres

**Status codes:**
- `201`: Usuario registrado exitosamente
- `400`: Datos inválidos
- `422`: Error de validación

---

### 2. Login

**Endpoint:** `POST /auth/login`

**Descripción:** Autentica un usuario y devuelve tokens JWT.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Validaciones:**
- Email debe ser válido
- Contraseña no puede estar vacía

**Status codes:**
- `200`: Login exitoso
- `401`: Email o contraseña inválidos
- `422`: Error de validación

---

### 3. Obtener usuario actual

**Endpoint:** `GET /auth/me`

**Descripción:** Devuelve los datos del usuario autenticado.

**Headers requeridos:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": "user_id_hash",
  "email": "user@example.com",
  "name": "John Doe",
  "roles": []
}
```

**Status codes:**
- `200`: Datos del usuario
- `401`: Token inválido o expirado

---

### 4. Logout

**Endpoint:** `POST /auth/logout`

**Descripción:** Invalida la sesión actual.

**Headers requeridos:**
```
Authorization: Bearer <access_token>
```

**Response (204 No Content):**
(Sin body)

**Status codes:**
- `204`: Logout exitoso
- `401`: Token inválido

---

## Health Check

**Endpoint:** `GET /health`

**Descripción:** Verifica el estado del servicio y sus dependencias.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "commitment-twin-backend",
  "timestamp": "2026-07-26T12:00:00Z",
  "dependencies": {
    "supabase": {
      "status": "up",
      "latency_ms": 45
    },
    "jira": {
      "status": "up",
      "latency_ms": 120
    }
  }
}
```

**Status codes:**
- `200`: Servicio operacional
- `503`: Servicio degradado o caído

---

## Providers

### 1. Listar providers disponibles

**Endpoint:** `GET /providers`

**Descripción:** Devuelve la lista de providers configurados.

**Response (200 OK):**
```json
{
  "providers": [
    {
      "name": "jira",
      "kind": "event_source",
      "status": "up",
      "capabilities": ["issues", "comments"]
    },
    {
      "name": "github",
      "kind": "event_source",
      "status": "unknown",
      "capabilities": ["issues", "pull_requests"]
    },
    {
      "name": "aws",
      "kind": "event_source",
      "status": "down",
      "capabilities": ["logs", "events"]
    }
  ]
}
```

---

### 2. Sincronizar eventos de un provider

**Endpoint:** `POST /providers/{provider}/sync`

**Descripción:** Realiza una sincronización manual de eventos.

**Parámetros:**
- `provider`: Nombre del provider (jira, github, aws, notion, rightway)

**Request:**
```json
{
  "workspace_id": "workspace-1",
  "cursor": null
}
```

**Response (200 OK):**
```json
{
  "provider": "jira",
  "workspace_id": "workspace-1",
  "processed": 42,
  "created": 15,
  "skipped": 25,
  "failed": 2,
  "message": "Sincronización completada"
}
```

**Status codes:**
- `200`: Sincronización exitosa
- `404`: Provider no encontrado
- `503`: Provider no disponible

---

## Webhooks

### Recibir webhook de Jira

**Endpoint:** `POST /webhooks/jira`

**Descripción:** Recibe eventos de webhooks de Jira.

**Headers requeridos:**
```
X-Hook-Secret: <webhook_secret>
X-Atlassian-Webhook-Identifier: <webhook_id>
```

**Response (202 Accepted):**
```json
{
  "event_id": "evt_123456",
  "project_id": "PROJ",
  "message": "Evento procesado"
}
```

**Status codes:**
- `202`: Evento aceptado (se procesa en background)
- `401`: Secreto inválido o ausente
- `415`: Content-Type no soportado

---

## Ejemplos de uso con cURL

### Registrar usuario
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "name": "New User",
    "password": "SecurePass123"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123"
  }'
```

### Obtener usuario actual
```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

### Health check
```bash
curl -X GET http://localhost:8000/health
```

### Sincronizar Jira
```bash
curl -X POST http://localhost:8000/providers/jira/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "workspace_id": "workspace-1"
  }'
```

---

## Autenticación entre rutas

La mayoría de rutas **no requieren autenticación** en este MVP. En producción:

1. Se agregará la validación de JWT en las rutas que lo necesiten
2. Se usará el header `Authorization: Bearer <token>`
3. Se extraerá el usuario de `CurrentUserDep`

Ejemplo de ruta protegida (futura):

```python
@router.post("/sync")
async def sync(
    request: SyncRequest,
    user: CurrentUserDep,  # Requiere autenticación
    service: OrchestratorServiceDep,
) -> SyncReport:
    # Usar user.id para registrar quién hizo la solicitud
    return await service.sync(request)
```

---

## Status

- ✅ Autenticación JWT (login/register/me/logout)
- ✅ Health check
- ✅ Providers (Jira, GitHub, AWS)
- ✅ Webhooks (Jira)
- 🔄 Endpoints de lectura (events, alerts, analysis) - próximamente
- 🔄 WebSocket (eventos en tiempo real) - próximamente
- 🔄 Agentes especializados integrados - próximamente

---

## Variables de entorno requeridas

```env
# Supabase
SUPABASE_URL=https://...supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...

# Jira
JIRA_BASE_URL=https://...atlassian.net
JIRA_EMAIL=...
JIRA_API_TOKEN=...
JIRA_WEBHOOK_SECRET=...

# AWS (opcional)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# GitHub (opcional)
GITHUB_TOKEN=...

# App
ENV=development
LOG_LEVEL=INFO
```
