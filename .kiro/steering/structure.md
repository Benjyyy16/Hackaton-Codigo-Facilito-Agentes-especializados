---
inclusion: auto
---

# Estructura y Regla de Dependencia

## Dirección única: hacia dentro

```
api/routes  →  services  →  repositories  →  integrations/supabase
                   ↓
               agents (puros, sin I/O)
                   ↓
               schemas / domain
```

## Consecuencias (sin excepción)

1. **Rutas** traducen HTTP ↔ llamadas de servicio. No contienen reglas de negocio, no construyen queries.
2. **Servicios** orquestan flujo: invocan agentes, persisten via repositorios, difunden via WebSocket. No tocan `client.table(...)`.
3. **Repositorios** son el ÚNICO lugar donde aparece el cliente de Supabase. Traducen errores PostgREST a excepciones de dominio.
4. **Agentes** son funciones puras: reciben datos estructurados (`CommitmentSnapshot`, contexto), devuelven `AgentOutput`. No importan `fastapi`, `supabase`, `httpx`. Esto es lo que permite sustituirlos por un LLM sin tocar nada más.
5. **Providers** implementan los puertos de `providers/base.py`. La lógica de negocio depende del protocolo, nunca del concreto. Añadir un provider es registrarlo en `main.py`, nada más.
6. **Integrations** encapsulan el conocimiento de APIs externas (Jira, GitHub). Los servicios no saben cómo se pagina Jira ni cómo firma GitHub.

## Qué NO se permite

- Una ruta importando un repositorio directamente.
- Un agente haciendo I/O (HTTP, filesystem, DB).
- Un servicio importando `supabase` o `postgrest`.
- Un repositorio conociendo la existencia de FastAPI.
- Dependencias circulares entre capas.

## Módulos transversales

- `core/config.py` — configuración (`Settings`).
- `core/exceptions.py` — jerarquía de errores de dominio.
- `core/logging.py` — logger con `request_id` y filtro de secretos.
- `core/enums.py` — `StrEnum` base.
- `schemas/` — modelos Pydantic compartidos entre capas.
