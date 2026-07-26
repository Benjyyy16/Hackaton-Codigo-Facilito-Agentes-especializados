# Prompt: Reproducir el caso demo

## Pre-requisitos

```bash
# 1. Clonar y entrar al backend
cd /path/to/hackaton-codigo-facilito-agentes-especializados/backend

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con:
#   SUPABASE_URL=https://tu-proyecto.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY=eyJ...
#   ENV=development
```

## Aplicar schema

```bash
# Copiar contenido de db/schema.sql al editor SQL de Supabase y ejecutar.
# Es idempotente: se puede reejecutar sin efectos secundarios.
```

## Arrancar el servidor

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

## Verificar salud

```bash
curl http://localhost:8000/health | python -m json.tool
```

## Crear proyecto demo

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Proyecto Demo Hackaton",
    "description": "Compromiso de entrega para el cliente Acme",
    "external_references": {"jira": "DAT", "github": "org/repo"},
    "hourly_cost": 85.00,
    "currency": "USD"
  }'
```

## Crear commitment

```bash
curl -X POST http://localhost:8000/commitments \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<UUID del proyecto>",
    "title": "Entrega módulo de pagos - Sprint 14",
    "beneficiary": "Acme Corp",
    "owner": "equipo-backend",
    "due_date": "2026-08-01T00:00:00Z",
    "financial_exposure": 150000.00,
    "currency": "USD",
    "priority": "high",
    "source": "demo"
  }'
```

## Ejecutar tests

```bash
python -m pytest app/tests/ -v --tb=short
```

## Notas

- Las rutas demo (`source: "demo"`) solo funcionan con `ENV != production`.
- El flujo completo (webhook → análisis → alerta → WebSocket) requiere Fases 2–5 completadas.
- Para probar WebSocket: `websocat ws://localhost:8000/ws/events`.
