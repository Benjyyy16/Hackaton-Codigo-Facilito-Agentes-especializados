# Configurar Render para Commitment Twin Backend

## Tu URL de Render
🔗 https://dashboard.render.com/services/dep-d9ibr7av4c73b6ip6g

## Paso 1: Abre el Dashboard

1. Ve a: https://dashboard.render.com
2. Selecciona tu servicio: **hackaton-codigo-facilito-agentes-d9ibr7av4c73b6ip6g**

## Paso 2: Configurar Python 3.12

1. En el dashboard, click en **"Settings"** (pestaña arriba)
2. Scroll hasta encontrar **"Runtime"**
3. En **"Python Version"** → selecciona **3.12**
4. Click **"Save"**

![paso 2](./docs/render-python-version.png)

## Paso 3: Configurar Build Command

1. Aún en **"Settings"**
2. Busca **"Build Command"**
3. Borra lo que esté ahí y reemplaza con:
   ```
   bash build.sh
   ```
4. Click **"Save"**

## Paso 4: Configurar Start Command

1. Busca **"Start Command"**
2. Borra lo que esté y reemplaza con:
   ```
   bash start.sh
   ```
3. Click **"Save"**

## Paso 5: Agregar Variables de Entorno

1. Ve a la pestaña **"Environment"**
2. Click en **"Add Environment Variable"**
3. Agrega estas variables (una por una):

### Supabase (copia exactamente)
```
SUPABASE_URL
https://hiyqrjfutgklmzbpyzob.supabase.co

SUPABASE_SERVICE_ROLE_KEY
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpeXFyamZ1dGdrbG16YnB5em9iIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTAzMTU0MCwiZXhwIjoyMTAwNjA3NTQwfQ.RvJglGo6lNDCa4qZt2TsC81B3VS-mrVgGB0n4TExFIU

SUPABASE_JWT_SECRET
FVX8WXQQ2dFD$br
```

### Jira (reemplaza con tus valores)
```
JIRA_BASE_URL
https://tu-org.atlassian.net

JIRA_EMAIL
tu-email@empresa.com

JIRA_API_TOKEN
(obtener de Jira Settings > Security > API tokens)

JIRA_WEBHOOK_SECRET
webhook-secret-commitment-twin
```

### App Config
```
ENV
production

LOG_LEVEL
INFO

HTTP_TIMEOUT_SECONDS
10.0

HTTP_MAX_RETRIES
3
```

**Cada variable:** Nombre → Valor → Click "Add" → se agrega a la lista

## Paso 6: Redeploy

1. De vuelta en el dashboard principal
2. Click en **"Redeploy latest commit"** (botón superior)
3. Espera a que termine (verás "Deployed ✓" en verde)

---

## ¿Cómo obtener credenciales de Jira?

### JIRA_BASE_URL
- Abre tu Jira en el navegador
- La URL es tipo: `https://mi-empresa.atlassian.net`
- Copia eso

### JIRA_EMAIL
- Tu email de cuenta Jira

### JIRA_API_TOKEN
1. En Jira: Settings (arriba a la derecha) → Security
2. "API tokens" → "Create token"
3. Dale un nombre (ej: "commitment-twin")
4. Copia el token (solo aparece una vez)
5. Pégalo en Render

---

## Verificar que funciona

Una vez que esté "Deployed", abre en el navegador:

```
https://hackaton-codigo-facilito-agentes-d9ibr7av4c73b6ip6g.onrender.com/
```

Debería devolver JSON como:
```json
{
  "service": "commitment-twin-backend",
  "status": "ok",
  "version": "0.1.0"
}
```

O ve a:
```
https://hackaton-codigo-facilito-agentes-d9ibr7av4c73b6ip6g.onrender.com/health
```

---

## Si algo falla

### Error 500 "Internal Server Error"
- Revisa que Python Version sea 3.12
- Haz Redeploy nuevamente

### Error 404
- El app está levantando pero la ruta no existe
- Prueba `/docs` para ver la documentación interactiva

### Error en logs
- En el dashboard, click "Logs"
- Mira los errores que aparecen
- Generalmente es falta de env variables

---

## Rutas disponibles

Una vez funcionando:

```
GET  /                   → Info del servicio
GET  /health            → Estado del backend
GET  /docs              → Documentación interactiva (Swagger)

POST /auth/register     → Crear usuario
POST /auth/login        → Login con email/contraseña
GET  /auth/me           → Datos del usuario actual (requiere JWT)
POST /auth/logout       → Logout

GET  /providers         → Listar providers
POST /providers/{name}/sync → Sincronizar eventos
```

---

## Ejemplo: Registrar usuario

```bash
curl -X POST https://hackaton-codigo-facilito-agentes-d9ibr7av4c73b6ip6g.onrender.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "name": "John Doe",
    "password": "SecurePassword123"
  }'
```

Respuesta:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Soporte

- Docs: `/docs`
- API Reference: `API.md` en el repo
- Dashboard Render: https://dashboard.render.com/services/dep-d9ibr7av4c73b6ip6g
