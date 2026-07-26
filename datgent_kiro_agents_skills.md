# Orquesta AI — Agentes Especializados & Skills

## Arquitectura Multi-Agente

Sistema de agentes especializados para detección de riesgos en compromisos de proyecto.
Cada agente es una función pura (sin I/O, sin red, sin DB) que recibe contexto y devuelve hallazgos.

```
┌──────────────────────────────────────────────────────┐
│                 [ DATGENT CEREBRO ]                  │
│         (Núcleo de Inteligencia Multiagente)         │
│   Coordina los agentes, tolera fallos parciales      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐   │
│  │ Commitment   │  │  Technical   │  │ Financial │   │
│  │    Agent     │  │    Agent     │  │   Agent   │   │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘   │
│         │                 │                │         │
│         └─────────────────┼────────────────┘         │
│                           ▼                          │
│                   ┌──────────────┐                   │
│                   │  RiskAgent   │                   │
│                   │ (compositor) │                   │
│                   └──────────────┘                   │
└──────────────────────────────────────────────────────┘
```

## Agentes

### 1. CommitmentAgent
**Propósito:** Analiza compromisos y fechas de vencimiento.

**Skills:**
- `overdue` — Detecta compromisos vencidos
- `due_soon` — Alerta de vencimiento próximo (< N días)
- `no_due_date` — Issue sin fecha de entrega
- `reopened` — Compromiso reabierto después de cerrarse

**Score:** 0-100 basado en la señal más grave

### 2. TechnicalAgent
**Propósito:** Detecta señales técnicas de riesgo en el flujo de trabajo.

**Skills:**
- `blocked` — Issue marcado como bloqueado
- `unassigned` — Sin responsable asignado
- `stale` — Sin actividad en X días
- `reassignment_churn` — Múltiples reasignaciones (señal de indefinición)

**Score:** 0-100, peso del peor hallazgo

### 3. FinancialAgent
**Propósito:** Calcula el impacto económico del riesgo.

**Skills:**
- `hours_at_risk` — Horas estimadas que podrían perderse
- `cost_impact` — Costo = horas × tarifa/hora del proyecto
- `budget_exposure` — Porcentaje del presupuesto en peligro

**Score:** 0-100 proporcional al impacto económico

### 4. RiskAgent
**Propósito:** Compone el riesgo global a partir de los resultados de los demás agentes.

**Skills:**
- `weighted_composition` — Combina scores con pesos declarados
- `severity_classification` — Clasifica en low/medium/high/critical
- `dominant_signal` — Identifica la señal más relevante

**Tramos de severidad:**
| Score | Severidad |
|-------|-----------|
| 0-39  | low       |
| 40-59 | medium    |
| 60-79 | high      |
| 80-100| critical  |

### 5. Datgent Cerebro — Núcleo de Inteligencia Multiagente
**Propósito:** Coordina el pipeline completo con tolerancia a fallos.

> Implementado por la clase `RiskOrchestrator` (`app/agents/risk_orchestrator.py`).
> El nombre de clase se mantiene: es el símbolo que aparece en el código y en los tests.

**Skills:**
- `parallel_execution` — Ejecuta agentes de forma independiente
- `fault_tolerance` — Si un agente falla, continúa con los demás (`is_partial=true`)
- `result_composition` — Agrega resultados en un `AnalysisResult` unificado

## API Endpoints

### `GET /agents`
Lista todos los agentes disponibles con sus capabilities.

### `POST /agents/analyze`
Ejecuta el pipeline completo de análisis.

**Request:**
```json
{
  "project_key": "PROJ",
  "issue_key": "PROJ-42",
  "title": "Implementar feature X",
  "due_date": "2026-08-01T00:00:00Z",
  "estimated_hours": 40,
  "hourly_cost": 75.0
}
```

**Response:**
```json
{
  "risk_score": 72,
  "severity": "high",
  "is_partial": false,
  "financial_impact": 3000.0,
  "outcomes": [...],
  "primary_reason": "overdue"
}
```

## OAuth Login Flow

### Providers soportados: GitHub, Google

```
Frontend                    Backend                         Provider
   │                          │                               │
   │  click "Login GitHub"    │                               │
   ├─────────────────────────►│                               │
   │                          │  GET /auth/oauth/github/login │
   │  ◄── redirect ──────────┤                               │
   │                          │                               │
   │  ─── authorize ──────────┼──────────────────────────────►│
   │                          │                               │
   │                          │  callback con code            │
   │                          │◄──────────────────────────────┤
   │                          │                               │
   │                          │  exchange code → access_token │
   │                          │  fetch user profile           │
   │                          │  create JWT                   │
   │                          │                               │
   │  ◄── redirect con JWT ───┤                               │
   │  /auth/callback?token=.. │                               │
   │                          │                               │
   │  guarda JWT, /auth/me    │                               │
   ├─────────────────────────►│                               │
   │  ◄── user data ──────────┤                               │
   └──────────────────────────┴───────────────────────────────┘
```

### Endpoints OAuth Login:
- `GET /auth/oauth/github/login` → Redirige a GitHub OAuth
- `GET /auth/oauth/github/callback` → Recibe code, crea JWT, redirige a frontend
- `GET /auth/oauth/google/login` → Redirige a Google OAuth  
- `GET /auth/oauth/google/callback` → Recibe code, crea JWT, redirige a frontend

### Variables de entorno requeridas:
```env
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
APP_BASE_URL=https://hackaton-codigo-facilito-agentes.onrender.com
FRONTEND_URL=https://hackaton-codigo-facilito-agentes-especializados.vercel.app
```

## Stack

- **Backend:** FastAPI + Pydantic + httpx
- **Auth:** JWT custom (HS256), OAuth 2.0 con GitHub/Google
- **Agents:** Python puro, sin dependencias externas
- **Frontend:** React + Vite + TypeScript + Tailwind
- **Deploy:** Render (backend) + Vercel (frontend)
