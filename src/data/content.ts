/**
 * Contenido de la landing.
 * Todas las cifras llevan `source` + `url` verificables (ver README).
 * Contenido reformulado para cumplir restricciones de licencia de las fuentes.
 */

export type Stat = {
  value: string
  label: string
  detail: string
  source: string
  url: string
}

/** Cifras del problema: por qué "mostrar avance real" importa. */
export const problemStats: Stat[] = [
  {
    value: '45%',
    label: 'sobrecosto promedio',
    detail:
      'Los grandes proyectos de IT se pasan del presupuesto en promedio un 45%, se retrasan un 7% y entregan 56% menos valor del proyectado.',
    source: 'McKinsey & Oxford',
    url: 'https://www.mckinsey.com/capabilities/tech-and-ai/our-insights/delivering-large-scale-it-projects-on-time-on-budget-and-on-value',
  },
  {
    value: '25–40%',
    label: 'programas fuera de control',
    detail:
      'Entre 25% y 40% de los programas tecnológicos exceden su presupuesto o cronograma en más del 50%.',
    source: 'McKinsey',
    url: 'https://www.mckinsey.com/capabilities/tech-and-ai/our-insights/managing-large-technology-programs-in-the-digital-era',
  },
  {
    value: '16%',
    label: 'del tiempo en código real',
    detail:
      'IDC estima que los devs dedican solo ~16% de su tiempo a desarrollo core; el resto se va en CI/CD, seguridad y monitoreo.',
    source: 'IDC',
    url: 'https://securitybrief.com.au/story/australian-developers-are-losing-half-their-day-most-leaders-have-no-idea',
  },
  {
    value: '30%',
    label: 'no confía en el código IA',
    detail:
      'El 30% de los profesionales reporta poca o ninguna confianza en el código generado por IA. La trazabilidad es el problema, no la velocidad.',
    source: 'DORA 2025 (Google Cloud)',
    url: 'https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report',
  },
]

/** Cifras de contexto IA: por qué orquestar, no solo generar. */
export const contextStats: Stat[] = [
  {
    value: '90%',
    label: 'ya usa IA en su trabajo',
    detail:
      'La adopción de IA entre profesionales de software llegó al 90%, con una mediana de ~2 horas diarias de uso.',
    source: 'DORA 2025 (Google Cloud)',
    url: 'https://blog.google/technology/developers/dora-report-2025/',
  },
  {
    value: '+98%',
    label: 'más PRs fusionados',
    detail:
      'Telemetría de más de 10.000 devs: la IA sube el output individual (+21% tareas, +98% PRs) pero las métricas de entrega organizacional se quedan planas.',
    source: 'Faros AI',
    url: 'https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025',
  },
  {
    value: '-19%',
    label: 'la paradoja de velocidad',
    detail:
      'En un ensayo controlado, devs open-source experimentados tardaron 19% más usando IA, aunque creían haber ido 20% más rápido.',
    source: 'METR (RCT, 2025)',
    url: 'https://www.infoworld.com/article/4020931/ai-coding-tools-can-slow-down-seasoned-developers-by-19.html',
  },
]

/* ------------------------------------------------------------------ */
/* Agentes                                                             */
/* ------------------------------------------------------------------ */

export type Agent = {
  id: string
  name: string
  role: string
  blurb: string
  outputs: string[]
  accent: 'violet' | 'mint' | 'white'
  icon: 'brain' | 'code' | 'shield' | 'chart' | 'search' | 'file'
}

export const agents: Agent[] = [
  {
    id: 'strategist',
    name: 'Estratega',
    role: 'CEO técnico',
    blurb:
      'Traduce objetivos de negocio en roadmap. Decide qué se construye, en qué orden y con qué criterio de éxito medible.',
    outputs: ['Roadmap priorizado', 'OKRs por sprint', 'Criterios de aceptación'],
    accent: 'violet',
    icon: 'brain',
  },
  {
    id: 'architect',
    name: 'Arquitecto',
    role: 'Diseño técnico',
    blurb:
      'Lee tu repo real vía GitHub, mapea dependencias y propone la arquitectura que encaja con lo que ya existe.',
    outputs: ['ADRs', 'Diagrama de dependencias', 'Plan de migración'],
    accent: 'white',
    icon: 'code',
  },
  {
    id: 'builder',
    name: 'Constructor',
    role: 'Ejecución',
    blurb:
      'Abre ramas, escribe código, levanta PRs. Cada cambio queda ligado a una tarjeta del tablero automáticamente.',
    outputs: ['Pull requests', 'Migraciones Supabase', 'Tests'],
    accent: 'mint',
    icon: 'code',
  },
  {
    id: 'auditor',
    name: 'Auditor',
    role: 'Calidad y riesgo',
    blurb:
      'Revisa cada PR: seguridad, deuda técnica, cobertura. Bloquea lo que no cumple antes de que llegue a main.',
    outputs: ['Review por PR', 'Score de riesgo', 'Alertas de seguridad'],
    accent: 'violet',
    icon: 'shield',
  },
  {
    id: 'analyst',
    name: 'Analista',
    role: 'Finanzas del proyecto',
    blurb:
      'Convierte commits, horas y consumo de infra en costo real. Burn rate, proyección y varianza contra presupuesto.',
    outputs: ['Burn rate', 'Costo por feature', 'Forecast a cierre'],
    accent: 'mint',
    icon: 'chart',
  },
  {
    id: 'scribe',
    name: 'Cronista',
    role: 'Documentación viva',
    blurb:
      'Documenta a partir del repo, no de lo que alguien recuerda. Si el código cambió, el doc cambió.',
    outputs: ['Changelog', 'Docs técnicas', 'Reporte ejecutivo'],
    accent: 'white',
    icon: 'file',
  },
]

/* ------------------------------------------------------------------ */
/* Integraciones                                                       */
/* ------------------------------------------------------------------ */

export type Integration = {
  id: string
  name: string
  category: 'Código' | 'Datos' | 'Deploy' | 'Comunicación' | 'Producto' | 'Finanzas'
  what: string
  reads: string[]
  status: 'live' | 'beta' | 'soon'
}

export const integrations: Integration[] = [
  {
    id: 'github',
    name: 'GitHub',
    category: 'Código',
    what: 'La fuente de verdad. Commits, PRs, issues, Actions y reviews alimentan el tablero.',
    reads: ['Commits & diffs', 'Pull requests', 'Issues & labels', 'Actions / CI'],
    status: 'live',
  },
  {
    id: 'supabase',
    name: 'Supabase',
    category: 'Datos',
    what: 'Esquema, migraciones y políticas RLS. Los agentes ven el modelo de datos vivo.',
    reads: ['Schema & tablas', 'Migraciones', 'Políticas RLS', 'Edge Functions'],
    status: 'live',
  },
  {
    id: 'vercel',
    name: 'Vercel',
    category: 'Deploy',
    what: 'Estado de despliegues y previews ligados a cada PR del tablero.',
    reads: ['Deployments', 'Preview URLs', 'Build logs'],
    status: 'live',
  },
  {
    id: 'slack',
    name: 'Slack',
    category: 'Comunicación',
    what: 'Reportes de avance donde ya vive el equipo. Sin dashboards que nadie abre.',
    reads: ['Canales de proyecto', 'Hilos de decisión'],
    status: 'live',
  },
  {
    id: 'linear',
    name: 'Linear',
    category: 'Producto',
    what: 'Sincronía bidireccional de issues y ciclos con las tarjetas del canvas.',
    reads: ['Issues', 'Cycles', 'Roadmap'],
    status: 'beta',
  },
  {
    id: 'notion',
    name: 'Notion',
    category: 'Producto',
    what: 'Publica documentación generada y actas de decisión en tu wiki.',
    reads: ['Databases', 'Páginas de specs'],
    status: 'beta',
  },
  {
    id: 'figma',
    name: 'Figma',
    category: 'Producto',
    what: 'Compara el diseño con lo implementado y marca desviaciones.',
    reads: ['Frames', 'Design tokens'],
    status: 'soon',
  },
  {
    id: 'stripe',
    name: 'Stripe',
    category: 'Finanzas',
    what: 'Cruza ingresos reales con el costo de desarrollo por feature.',
    reads: ['MRR', 'Suscripciones', 'Cohortes'],
    status: 'soon',
  },
]

/* ------------------------------------------------------------------ */
/* Casos de uso                                                        */
/* ------------------------------------------------------------------ */

export type UseCase = {
  id: string
  audience: string
  title: string
  problem: string
  solution: string
  metrics: { label: string; value: string }[]
  accent: 'violet' | 'mint'
}

export const useCases: UseCase[] = [
  {
    id: 'finance',
    audience: 'Finanzas / CFO',
    title: 'Del commit al estado de resultados',
    problem:
      'El área financiera aprueba presupuesto sin ver qué se construyó. Los reportes llegan en PDF, tarde y sin evidencia.',
    solution:
      'El Analista une actividad del repo, horas del equipo y consumo de infra. Cada peso gastado se ancla a un commit verificable.',
    metrics: [
      { label: 'Costo por feature', value: 'trazable al commit' },
      { label: 'Burn rate', value: 'actualizado a diario' },
      { label: 'Varianza vs presupuesto', value: 'alerta automática' },
    ],
    accent: 'mint',
  },
  {
    id: 'investors',
    audience: 'Inversores / Board',
    title: 'Evidencia, no humo',
    problem:
      'El deck dice "80% listo". Nadie puede auditar ese número. La confianza se erosiona en la siguiente ronda.',
    solution:
      'Reporte firmado contra el repositorio: qué se mergeó, quién lo revisó, qué tests pasaron y qué queda. Con enlaces directos.',
    metrics: [
      { label: 'Avance', value: 'derivado de PRs merged' },
      { label: 'Auditoría', value: 'link a cada commit' },
      { label: 'Reporte mensual', value: 'generado, no redactado' },
    ],
    accent: 'violet',
  },
  {
    id: 'agency',
    audience: 'Agencias / Consultoras',
    title: 'Facturación defendible',
    problem:
      'El cliente cuestiona las horas. Justificar el trabajo consume tanto tiempo como hacerlo.',
    solution:
      'Cada entregable llega con su historia: rama, PR, review y deploy. La discusión pasa de "¿hicieron esto?" a "¿qué sigue?".',
    metrics: [
      { label: 'Horas justificadas', value: 'con artefacto' },
      { label: 'Disputas de factura', value: 'evidencia adjunta' },
      { label: 'Reporte al cliente', value: 'semanal, automático' },
    ],
    accent: 'violet',
  },
  {
    id: 'cto',
    audience: 'CTO / Eng. Manager',
    title: 'Deuda técnica con precio',
    problem:
      'Sabés que hay deuda. No podés ponerle un número y por eso nunca gana la discusión de prioridades.',
    solution:
      'El Auditor puntúa riesgo por módulo y el Analista lo traduce a costo estimado de mantener vs refactorizar.',
    metrics: [
      { label: 'Riesgo por módulo', value: 'score 0–100' },
      { label: 'Costo de la deuda', value: 'estimado en USD' },
      { label: 'Cobertura', value: 'tendencia por sprint' },
    ],
    accent: 'mint',
  },
]

/* ------------------------------------------------------------------ */
/* Flujo                                                               */
/* ------------------------------------------------------------------ */

export const flowSteps = [
  {
    n: '01',
    title: 'Conectá el repo',
    body: 'OAuth con GitHub. Los agentes indexan historial, estructura y convenciones del proyecto.',
  },
  {
    n: '02',
    title: 'Se genera el tablero',
    body: 'El canvas nace poblado desde issues y ramas existentes. No arrancás de cero.',
  },
  {
    n: '03',
    title: 'Los agentes trabajan',
    body: 'Planifican, ejecutan y revisan en paralelo. Cada acción queda anclada a una tarjeta.',
  },
  {
    n: '04',
    title: 'El repo actualiza el tablero',
    body: 'Merge de PR mueve la tarjeta. La documentación se reescribe con el diff real.',
  },
  {
    n: '05',
    title: 'Reporte con evidencia',
    body: 'Avance técnico y financiero, con enlace a cada commit que lo respalda.',
  },
] as const

export const faqs = [
  {
    q: '¿Los agentes escriben directo en main?',
    a: 'No. Trabajan en ramas y abren PRs. El Auditor revisa antes y siempre queda un humano aprobando el merge. Los permisos se configuran por proyecto.',
  },
  {
    q: '¿Qué pasa si la IA se equivoca?',
    a: 'Todo cambio pasa por PR con diff visible y review automatizado. Nada se aplica sin trazabilidad y nada evita tu aprobación. El registro es auditable commit por commit.',
  },
  {
    q: '¿Cómo calculan el avance real?',
    a: 'No usamos estimaciones declarativas. El avance se deriva de artefactos verificables: PRs mergeados, tests que pasan y deploys exitosos, ligados a criterios de aceptación definidos al inicio.',
  },
  {
    q: '¿Necesito mover mi stack?',
    a: 'No. Orquesta se conecta por encima de lo que ya usás: GitHub, Supabase, Vercel, Slack. Tu repositorio sigue siendo la fuente de verdad.',
  },
  {
    q: '¿Un tablero por proyecto?',
    a: 'Sí. Cada proyecto tiene su canvas, su repo conectado, sus agentes y sus colaboradores. Los espacios están aislados entre sí.',
  },
]
