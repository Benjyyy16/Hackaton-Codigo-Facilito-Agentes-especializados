import { useCallback, useEffect, useMemo } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { nodeTypes } from './nodes'
import type { Project } from '@/store/types'

/** Construye el grafo del proyecto: fuentes → agentes → tareas → salidas. */
function buildGraph(project: Project, onConnectRepo: () => void) {
  const nodes: Node[] = []
  const edges: Edge[] = []

  const COL = { source: 0, agent: 320, task: 620, output: 920 }

  /* --- Fuentes --- */
  if (project.repo) {
    nodes.push({
      id: 'repo',
      type: 'repo',
      position: { x: COL.source, y: 120 },
      data: {
        fullName: project.repo.fullName,
        branch: project.repo.branch,
        commits: project.repo.stats.commits,
        openPRs: project.repo.stats.openPRs,
        mergedPRs: project.repo.stats.mergedPRs,
        coverage: project.repo.stats.coverage,
        lastSync: project.repo.lastSync,
      },
    })
  } else {
    nodes.push({
      id: 'repo',
      type: 'emptyRepo',
      position: { x: COL.source, y: 140 },
      data: { onConnect: onConnectRepo },
    })
  }

  if (project.database) {
    nodes.push({
      id: 'db',
      type: 'db',
      position: { x: COL.source, y: 340 },
      data: {
        projectRef: project.database.projectRef,
        region: project.database.region,
        tables: project.database.tables,
        migrations: project.database.migrations,
        rlsEnabled: project.database.rlsEnabled,
      },
    })
  }

  /* --- Agentes --- */
  const agentDefs = [
    { id: 'ag-strategist', name: 'Estratega', role: 'planifica', activity: 'Prioriza el backlog por impacto.', busy: false },
    { id: 'ag-builder', name: 'Constructor', role: 'ejecuta', activity: 'Trabajando en la rama activa.', busy: true },
    { id: 'ag-auditor', name: 'Auditor', role: 'valida', activity: 'Revisando PRs abiertos.', busy: !!project.repo },
    { id: 'ag-analyst', name: 'Analista', role: 'costea', activity: 'Cruzando consumo con presupuesto.', busy: false },
    { id: 'ag-scribe', name: 'Cronista', role: 'documenta', activity: 'Regenerando docs desde el diff.', busy: !!project.repo },
  ]

  agentDefs.forEach((a, i) => {
    nodes.push({
      id: a.id,
      type: 'agent',
      position: { x: COL.agent, y: 20 + i * 118 },
      data: { name: a.name, role: a.role, activity: a.activity, busy: a.busy },
    })
    edges.push({
      id: `e-repo-${a.id}`,
      source: 'repo',
      target: a.id,
      animated: a.busy,
    })
    if (project.database && (a.id === 'ag-auditor' || a.id === 'ag-analyst')) {
      edges.push({ id: `e-db-${a.id}`, source: 'db', target: a.id })
    }
  })

  /* --- Tareas --- */
  const ownerToAgent: Record<string, string> = {
    Estratega: 'ag-strategist',
    Constructor: 'ag-builder',
    Arquitecto: 'ag-strategist',
    Auditor: 'ag-auditor',
    Analista: 'ag-analyst',
    Cronista: 'ag-scribe',
  }

  project.tasks.forEach((t, i) => {
    nodes.push({
      id: t.id,
      type: 'task',
      position: { x: COL.task, y: 10 + i * 108 },
      data: {
        title: t.title,
        status: t.status,
        owner: t.owner,
        bot: t.source === 'agent',
        ref: t.ref,
        autoSynced: t.autoSynced,
        points: t.points,
      },
    })
    const src = ownerToAgent[t.owner] ?? 'ag-strategist'
    edges.push({
      id: `e-${src}-${t.id}`,
      source: src,
      target: t.id,
      animated: t.status === 'progress' || t.status === 'review',
    })
  })

  /* --- Salidas --- */
  const doneCount = project.tasks.filter((t) => t.status === 'done').length
  const pct = project.tasks.length ? Math.round((doneCount / project.tasks.length) * 100) : 0

  nodes.push({
    id: 'out-doc',
    type: 'output',
    position: { x: COL.output, y: 90 },
    data: {
      title: 'Documentación viva',
      kind: 'doc',
      lines: [
        `${doneCount} tareas verificadas contra el repo`,
        project.repo ? `Changelog al día · ${project.repo.branch}` : 'Pendiente: conectar repo',
        'Regenerada en cada merge',
      ],
    },
  })

  nodes.push({
    id: 'out-fin',
    type: 'output',
    position: { x: COL.output, y: 300 },
    data: {
      title: 'Reporte financiero',
      kind: 'finance',
      lines: [
        project.budget.allocated
          ? `$${project.budget.spent.toLocaleString('en-US')} de $${project.budget.allocated.toLocaleString('en-US')}`
          : 'Presupuesto sin definir',
        `Avance verificado: ${pct}%`,
        'Cada monto enlaza a sus commits',
      ],
    },
  })

  edges.push(
    { id: 'e-scribe-doc', source: 'ag-scribe', target: 'out-doc', animated: true },
    { id: 'e-auditor-doc', source: 'ag-auditor', target: 'out-doc' },
    { id: 'e-analyst-fin', source: 'ag-analyst', target: 'out-fin', animated: true },
  )

  return { nodes, edges }
}

export function ProjectCanvas({
  project,
  onConnectRepo,
}: {
  project: Project
  onConnectRepo: () => void
}) {
  const graph = useMemo(() => buildGraph(project, onConnectRepo), [project, onConnectRepo])
  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges)

  // Reconstruye el grafo cuando cambia el proyecto (repo conectado, tareas movidas…)
  useEffect(() => {
    setNodes(graph.nodes)
    setEdges(graph.edges)
  }, [graph, setNodes, setEdges])

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => addEdge({ ...c, animated: true }, eds)),
    [setEdges],
  )

  return (
    <div className="h-[calc(100vh-196px)] min-h-[520px] w-full overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.25}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        {/* cuadrícula de papel milimetrado */}
        <Background variant={BackgroundVariant.Lines} gap={32} size={1} color="rgba(13,11,22,.06)" />
        <Background
          id="fine"
          variant={BackgroundVariant.Lines}
          gap={8}
          size={1}
          color="rgba(13,11,22,.03)"
        />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeStrokeColor="#0D0B16"
          nodeStrokeWidth={2}
          nodeColor={(n) =>
            n.type === 'repo' || n.type === 'emptyRepo'
              ? '#0D0B16'
              : n.type === 'db'
                ? '#3ECF8E'
                : n.type === 'agent'
                  ? '#7C3AED'
                  : n.type === 'output'
                    ? '#D8D6E2'
                    : '#BCA2FF'
          }
          maskColor="rgba(247,247,250,.78)"
        />
      </ReactFlow>
    </div>
  )
}
