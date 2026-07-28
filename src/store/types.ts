export type TaskStatus = 'backlog' | 'progress' | 'review' | 'done'
export type TaskSource = 'agent' | 'human' | 'github'

export interface Task {
  id: string
  title: string
  status: TaskStatus
  /** Agente o persona responsable */
  owner: string
  source: TaskSource
  /** Referencia al repo: PR #, rama o commit corto */
  ref?: string
  /** Marca si la tarjeta se movió sola por un evento del repo */
  autoSynced?: boolean
  points?: number
}

export interface RepoConnection {
  provider: 'github'
  /** owner/repo */
  fullName: string
  branch: string
  connectedAt: string
  lastSync: string
  stats: {
    commits: number
    openPRs: number
    mergedPRs: number
    contributors: number
    coverage: number
  }
}

export interface SupabaseConnection {
  provider: 'supabase'
  projectRef: string
  region: string
  tables: number
  migrations: number
  rlsEnabled: boolean
}

export interface Collaborator {
  id: string
  name: string
  /** Especialidad declarada en el perfil */
  specialty: string
  role: 'owner' | 'maintainer' | 'collaborator' | 'viewer'
  avatarHue: number
  /** ids de proyecto donde colabora */
  projectIds: string[]
}

export interface Project {
  id: string
  name: string
  description: string
  /** Color de acento del proyecto (hue) */
  hue: number
  repo: RepoConnection | null
  database: SupabaseConnection | null
  tasks: Task[]
  collaboratorIds: string[]
  budget: {
    /** USD asignado */
    allocated: number
    /** USD consumido */
    spent: number
    currency: 'USD'
  }
  createdAt: string
}

export interface User {
  id: string
  name: string
  email: string
  specialty: string
  title: string
  avatarHue: number
  avatarUrl?: string | null
  provider: 'password' | 'google' | 'github'
  /** Marca la sesión de demostración (datos de ejemplo, no reales) */
  isDemo?: boolean
}
