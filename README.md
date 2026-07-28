<div align="center">
  <img src="public/datgent-logo.png" alt="Datgent" width="96" />

# Datgent

**Tu CEO técnico con multi-agentes de IA.**
Agentes especializados que investigan tu proyecto, cruzan evidencia verificable y reportan el avance y el riesgo real, no lo que alguien recuerda.

Hackatón Código Facilito · Agentes especializados

</div>

---

## Qué es

Datgent es un *commitment twin*: un gemelo del compromiso que tu equipo asumió. En lugar de pedir estimaciones declarativas ("vamos 80%"), varios agentes especializados investigan las fuentes reales del proyecto (repositorio, tablero, base de datos, costos), producen **evidencia trazable** y un orquestador —el **Cerebro**— consolida todo en un caso de riesgo con score, cadena causal, premortem y escenarios.

Cada dato que llega a la pantalla trae su procedencia (`real` o `demo`), su proveedor y una explicación de por qué importa. Las acciones que los agentes proponen quedan como **decisiones pendientes de aprobación humana**: nada se ejecuta sin que alguien apruebe.

Este repositorio contiene el **frontend** (React + Vite + TypeScript). El backend (FastAPI, agentes LLM, Supabase, canal de eventos) corre como servicio aparte en Render.

## Demo rápida

```bash
npm ci
npm run dev
```

Abrí `http://localhost:5173`, entrá con **la cuenta demo** desde `/login` y andá a **Datgent → Analizar compromiso**.

La cuenta demo no toca el backend de autenticación, así que sirve para recorrer el flujo completo incluso si la instancia no tiene GitHub OAuth configurado. Con GitHub conectado, el login real habilita `/app/datgent/select-repo` para lanzar el análisis sobre un repositorio propio.

> El backend de producción está en el plan gratuito de Render: la primera petición puede tardar cerca de 30 segundos en despertar el servicio. El frontend lo contempla con timeouts largos y mensajes explícitos.

## Los agentes

El backend expone agentes especializados que corren en paralelo y reportan al orquestador:

| Agente | Investiga | Salida |
| --- | --- | --- |
| Agente Jira 📋 | Tablero, tickets, bloqueos, fechas | Findings de planificación |
| Agente Código ⚙️ | Repositorio, commits, PRs, ramas | Findings de ejecución técnica |
| Agente Datos 🗄️ | Esquema, migraciones, integridad | Findings de modelo de datos |
| Agente Finanzas 💰 | Costos, burn rate, varianza | Findings económicos |
| **Datgent Cerebro** 🧠 | Consolida a los anteriores | Caso de riesgo + decisiones |

Ciclo de vida del Cerebro (`CerebroState`):

```
ready → starting_agents → gathering_evidence → consolidating
      → generating_scenarios → awaiting_approval → completed
                                                 ↘ partial_error
```

Si un agente falla o le falta información, la sesión se marca como **parcial** en lugar de inventar el dato faltante: `missing_information` viaja hasta la UI.

La landing describe además la visión de producto completa (Estratega, Arquitecto, Constructor, Auditor, Analista, Cronista) con cifras del problema, cada una con fuente citada y enlace verificable en `src/data/content.ts`.

## Stack

| Capa | Elección | Por qué |
| --- | --- | --- |
| UI | React 18 + TypeScript 5.7 (`strict`) | Tipado del contrato con el backend de punta a punta |
| Build | Vite 6 | Dev server rápido, code splitting por ruta |
| Estilos | Tailwind CSS 3.4 con design tokens propios | Estética de papel impreso: sombras sólidas, cuadrícula, sin glow |
| Animación | Framer Motion 11 | Transiciones de ruta y entrada de evidencias |
| Canvas | React Flow 11 | Tablero de proyecto con nodos y dependencias |
| Rutas | React Router 6 | Rutas protegidas + lazy loading |
| Iconos | Lucide React | — |

Sin librería de estado externa: el estado global vive en `AppStore` (Context + reducer) y el flujo vivo en el hook `useAnalysis`.

## Arquitectura del frontend

```
src/
├── App.tsx                 Rutas, lazy loading, ErrorBoundary por vista
├── main.tsx                Entry point
├── index.css               Tailwind + capas de componentes propias
│
├── pages/
│   ├── Landing.tsx         Landing pública (única ruta en el bundle inicial)
│   ├── Login.tsx           GitHub OAuth + cuenta demo
│   ├── OAuthCallback.tsx   Canje del token del provider
│   ├── Dashboard.tsx       Listado de proyectos
│   ├── ProjectBoard.tsx    Canvas del proyecto (React Flow)
│   ├── RepoSelector.tsx    Elegir repo de GitHub a analizar
│   ├── DatgentAnalysis.tsx Flujo vivo: Agentes / Evidencias / Decisiones / Timeline
│   ├── RiskAnalysis.tsx    Vista de presentación (?demo=true), sin ruta asignada
│   └── Profile.tsx
│
├── components/
│   ├── datgent/            Cerebro, AgentCard, EvidenceList, DecisionPanel,
│   │                       TimelineView, ProvenanceBanner, WsIndicator…
│   ├── canvas/             Nodos y lienzo de React Flow
│   ├── landing/            Secciones de la landing
│   ├── app/                AppShell (sidebar) y modales
│   ├── layout/             Navbar, Footer
│   ├── ui/                 Button, Skeleton, Avatar, Backdrop, primitivas
│   └── ErrorBoundary.tsx
│
├── hooks/
│   ├── useAnalysis.ts      Reducer del flujo vivo + start/approve/reject
│   ├── useWsEvents.ts      WebSocket → polling → offline
│   ├── useProjects.ts      Carga de proyectos
│   └── useFocusTrap.ts     Accesibilidad en modales
│
├── lib/
│   ├── http.ts             fetch con timeout, errores tipados, mensajes legibles
│   ├── authApi.ts          Sesión, JWT, expiración, OAuth
│   ├── analysisApi.ts      Endpoints /live/*
│   ├── projectsApi.ts      Endpoints /projects
│   ├── githubApi.ts        /providers/github/repos
│   ├── storage.ts          localStorage tolerante a fallos
│   └── cn.ts               clsx + tailwind-merge
│
├── store/
│   ├── AppStore.tsx        Sesión, proyectos, avisos
│   ├── analysisTypes.ts    Espejo tipado del dominio del backend + eventos WS
│   └── types.ts, seed.ts
│
└── data/content.ts         Copy de la landing con fuentes citadas
```

### Decisiones de ingeniería que vale conocer

**Canal de eventos con degradación controlada.** `useWsEvents` intenta WebSocket (`/ws/events`), reintenta con backoff exponencial hasta 3 veces, degrada a polling de `GET /live/analysis/{id}` cada 2,5 s y, si en 60 s no hubo ni conexión ni un poll exitoso, declara `offline` y deja de consumir recursos. En producción Vercel proxea HTTP pero no WebSockets, así que sin `VITE_BACKEND_URL` absoluta el hook va directo a polling en lugar de gastar reintentos condenados. El polling reconstruye los eventos que la UI espera a partir del estado de la sesión, así el reducer es el mismo en ambos caminos.

**Todo fetch tiene timeout.** `lib/http.ts` combina el `AbortSignal` del llamador con un timeout propio (15 s por defecto, 60 s para arrancar el análisis). Sin eso, un pre-flight CORS fallido o un backend dormido deja el spinner girando para siempre. Los errores se distinguen entre `NetworkError` y `HttpError` y se traducen a mensajes que dicen qué hacer.

**La sesión se apaga sola.** `authApi` guarda `expires_at` (de `expires_in` o del `exp` del JWT), aplica 30 s de margen y avisa por suscripción para que el store cierre sesión en lugar de mandar un Bearer que dará 401. Migra el formato viejo (`datgent_token`) al nuevo (`datgent.auth.v1`).

**`localStorage` nunca tumba la app.** En Safari privado o con la cuota llena, `localStorage` lanza. Todo acceso pasa por `lib/storage.ts`, que cae a un `Map` en memoria: la sesión se pierde al recargar, pero la app no revienta.

**Un `ErrorBoundary` por ruta.** Un fallo de render queda contenido en la vista, con opción de reintentar, en lugar de dejar la pantalla en blanco. La `key` reinicia el boundary al navegar.

**Bundle dividido.** Solo la landing va en el bundle inicial. Las rutas internas (que arrastran React Flow) se cargan por demanda.

## Contrato con el backend

Base URL: `import.meta.env.VITE_BACKEND_URL` con fallback a `http://localhost:8000`. En producción queda vacía y se usan rutas relativas que Vercel reescribe.

### Autenticación

| Método | Ruta | Uso |
| --- | --- | --- |
| `POST` | `/auth/login` | Email + password → tokens |
| `POST` | `/auth/register` | Alta de cuenta |
| `GET` | `/auth/me` | Usuario actual |
| `POST` | `/auth/logout` | Cierre en servidor |
| `GET` | `/auth/oauth/{provider}/login` | Inicio de OAuth (`github`, `google`) |
| `GET` | `/auth/oauth/{provider}/callback` | Vuelve al frontend con el token |

El callback aterriza en `/oauth/callback` o `/auth/callback` según cómo esté configurado `FRONTEND_URL` en el backend. Ambas rutas apuntan al mismo handler para que el login no se rompa por una barra de más.

### Flujo vivo

| Método | Ruta | Uso |
| --- | --- | --- |
| `POST` | `/live/analysis` | Inicia análisis (caso demo o `commitment` + `signals` de un repo) |
| `GET` | `/live/analysis/{id}` | Estado completo de la sesión |
| `POST` | `/live/decisions/{id}/approve` | Aprobar decisión |
| `POST` | `/live/decisions/{id}/reject` | Rechazar con motivo |
| `POST` | `/live/simulate/jira` | Inyecta un evento crítico (demo) |
| `DELETE` | `/live/reset` | Limpia sesiones en memoria (demo) |
| `GET` | `/live/provenance` | Qué proveedores son reales y cuáles demo |
| `WS` | `/ws/events` | Canal único de eventos |

### Proyectos, repos y salud

`GET`/`POST` `/projects` · `GET /providers/github/repos` · `GET /health` · `GET /admin/schema/status`

### Eventos WebSocket

Unión discriminada validada en runtime por `parseWsEvent`; los mensajes desconocidos se descartan sin romper el reducer.

`analysis.started` · `agent_run.started` · `agent_run.completed` · `evidence.created` · `risk_case.created` · `risk_case.updated` · `alert.created` · `alert.acknowledged` · `alert.resolved` · `decision.created` · `decision.updated` · `decision.approved` · `decision.rejected` · `decision.executed` · `commitment.status_changed` · `timeline.appended` · `cerebro.state_changed` · `analysis.completed` · `source_event.received` · `pong`

## Puesta en marcha

Requisitos: Node.js 20 o superior y npm.

```bash
git clone https://github.com/Benjyyy16/Hackaton-Codigo-Facilito-Agentes-especializados.git
cd Hackaton-Codigo-Facilito-Agentes-especializados
npm ci
npm run dev          # http://localhost:5173
```

### Variables de entorno

Creá un `.env.local` (está en `.gitignore`):

```bash
# URL absoluta del backend. Omitila para usar http://localhost:8000.
# Dejala vacía en producción para pegar a rutas relativas vía proxy de Vercel.
VITE_BACKEND_URL=http://localhost:8000
```

Solo `VITE_BACKEND_URL` afecta al frontend. Del lado del backend hacen falta, entre otras, `OPENAI_API_KEY` (agentes LLM), `FRONTEND_URL` (CORS y destino del callback OAuth), `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` (OAuth y lectura de repos) y `DEMO_MODE_ENABLED` (habilita `simulate` y `reset`).

> `.env.local` en este workspace puede contener un token OIDC generado por la CLI de Vercel. No se versiona y no hace falta para desarrollar.

### Backend en local

```bash
uvicorn app.main:app --reload    # en el repo del backend
```

Con el backend arriba y `VITE_BACKEND_URL=http://localhost:8000`, el WebSocket funciona y el análisis llega en vivo, sin polling.

## Scripts

| Comando | Qué hace |
| --- | --- |
| `npm run dev` | Dev server de Vite en el puerto 5173 |
| `npm run build` | `tsc -b` y build de producción a `dist/` |
| `npm run preview` | Sirve el build |
| `npm run lint` | `tsc --noEmit` (chequeo de tipos) |
| `npm run check:classes` | Detecta clases de Tailwind usadas pero no generadas en el CSS |
| `npm run verify` | Tipos + build + chequeo de clases |

`check:classes` recorre `src/`, extrae las utilities de Tailwind usadas —incluidas las que viven en mapas de clases, no solo en `className`— y las compara con el CSS emitido en `dist/assets`. Atrapa el error clásico de Tailwind: una clase construida dinámicamente que el JIT nunca vio y que en producción simplemente no existe. Requiere un `build` previo.

## Deploy

Vercel, configurado en `vercel.json`:

- Build `npm run build`, salida `dist`, install `npm ci`.
- SPA fallback: todo lo no reconocido va a `/index.html`.
- Rewrites de `/live/*`, `/auth/*`, `/providers/*`, `/projects*` y `/health` hacia el backend en Render.

El proxy hace que el navegador hable solo con el dominio del propio sitio, así CORS no entra en juego y el backend puede seguir restringiendo su origen permitido. La contrapartida: Vercel no proxea WebSockets, por eso en producción el canal de eventos usa polling. Si quisieras WS en producción, hay que apuntar `VITE_BACKEND_URL` al backend directo y agregar el dominio de Vercel a su `FRONTEND_URL`.

## Sistema de diseño

Estética de documento impreso, no de dashboard oscuro con neón. Tokens en `tailwind.config.js`:

- **paper** (blancos, fondo dominante), **ink** (texto y bordes duros), **violet** (acento), **mint** (estados verificados), **clay** (advertencias del ledger).
- Tipografías: Inter (texto), Instrument Serif (display), JetBrains Mono (datos y etiquetas).
- Sombras sólidas desplazadas (`shadow-hard`), cuadrícula de papel milimetrado, tramas diagonales.
- Animaciones con intención: `stamp-in` para sellos, `dash-run` para flujos activos, `tick-up` para contadores.

Accesibilidad: roles y `aria-live` en regiones que cambian solas, `aria-busy` en acciones en vuelo, focus trap en modales, foco visible en todos los controles.

## Trabajo con Kiro

El desarrollo se apoyó en Kiro. En `.kiro/` quedan:

- `session-handoff.md` — estado, pruebas ejecutadas y próxima tarea exacta al cerrar cada sesión, para retomar sin arqueología.
- `steering/` — reglas de contexto que Kiro carga en cada interacción.

## Estado

Funcional de punta a punta: login (OAuth y demo), selección de repo, análisis en vivo con agentes en paralelo, evidencias con procedencia, caso de riesgo consolidado, aprobación/rechazo de decisiones y timeline. `tsc --noEmit` y `vite build` limpios.

Pendiente: las integraciones marcadas como `beta` y `soon` en `src/data/content.ts` (Linear, Notion, Figma, Stripe) son roadmap, no código.

## Créditos

Las cifras de la landing citan a McKinsey & Oxford, IDC, el DORA Report 2025 de Google Cloud, Faros AI y un ensayo controlado de METR. Cada una lleva `source` y `url` en `src/data/content.ts`. El contenido fue reformulado para cumplir las restricciones de licencia de las fuentes.

Proyecto construido para la Hackatón de Código Facilito, track de agentes especializados.
