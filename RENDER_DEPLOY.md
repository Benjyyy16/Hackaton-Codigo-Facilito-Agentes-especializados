# Deployment en Render

## Estado actual
- URL: https://hackaton-codigo-facilito-agentes-d9ibr7av4c73b6ip6g.onrender.com/
- Service ID: `dep-d9ibr7av4c73b6ip6g`
- Rama: `backend`

## Problema
La app está levantando pero en "fallback mode" porque faltan variables de entorno.

## Solución: Configurar env vars en Render

### Paso 1: Abre el dashboard
Ir a: https://dashboard.render.com/services/dep-d9ibr7av4c73b6ip6g

### Paso 2: Abre la pestaña "Environment"
Click en "Environment" → "Add Environment Variable"

### Paso 3: Agrega estas variables

#### Supabase (ya tenemos estos valores)
```
SUPABASE_URL=https://hiyqrjfutgklmzbpyzob.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpeXFyamZ1dGdrbG16YnB5em9iIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTAzMTU0MCwiZXhwIjoyMTAwNjA3NTQwfQ.RvJglGo6lNDCa4qZt2TsC81B3VS-mrVgGB0n4TExFIU
```

#### Jira (NECESITAS OBTENER ESTOS VALORES)
```
JIRA_BASE_URL=https://tu-org.atlassian.net
JIRA_EMAIL=tu-email@empresa.com
JIRA_API_TOKEN=<obtener-de-jira>
JIRA_WEBHOOK_SECRET=webhook-secret-commitment-twin
```

#### Opcionales
```
ENV=production
LOG_LEVEL=INFO
```

### Paso 4: Obtener valores de Jira

**JIRA_BASE_URL:**
- Va a tu workspace de Jira
- Mira la URL: `https://xxxx.atlassian.net` → usa eso

**JIRA_EMAIL:**
- El email de tu cuenta Jira

**JIRA_API_TOKEN:**
- Ve a Jira Settings → Personal Settings → Security → API Tokens
- Click "Create token"
- Dale un nombre (ej: "commitment-twin-backend")
- Copia el token (solo aparece una vez)

**JIRA_WEBHOOK_SECRET:**
- Puede ser cualquier string aleatorio, ej: `webhook-commitment-twin-xyz123`

### Paso 5: Guarda y redeploy
- Click "Save"
- Click "Redeploy latest commit"
- Espera a que levante (verás "Deployed" en verde)

### Paso 6: Verifica que funciona
```
curl https://hackaton-codigo-facilito-agentes-d9ibr7av4c73b6ip6g.onrender.com/health
```

Debería devolver algo como:
```json
{"status":"healthy","service":"commitment-twin-backend","timestamp":"2026-07-26T00:15:00Z"}
```

---

## Troubleshooting

### Si ves "Not Found" (404)
La app levantó pero no en ruta correcta. Intenta `/health` o `/docs`

### Si ves un error de configuración
Revisa los logs en Render (click "Logs" en el dashboard) para ver qué variable falta

### Si falla el redeploy
Asegúrate de:
1. Todas las variables están configuradas
2. El `Procfile` dice: `web: bash start.sh`
3. La rama es `backend`

