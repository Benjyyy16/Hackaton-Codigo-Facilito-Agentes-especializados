import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Collaborator, Project, Task, TaskStatus, User } from './types'
import { seedCollaborators, seedProjects } from './seed'
import { api, saveTokens, clearTokens, getTokens, type ApiError } from '../lib/api'

const STORAGE_KEY = 'orquesta.session.v1'

/** Credenciales de la cuenta de demostración, visibles a propósito. */
export const DEMO_CREDENTIALS = {
  email: 'demo@orquesta.dev',
  password: 'orquesta2026',
} as const

interface AppStore {
  user: User | null
  loading: boolean
  authError: string | null
  projects: Project[]
  collaborators: Collaborator[]
  signIn: (email: string, password: string, provider?: 'password' | 'google') => Promise<void>
  signUp: (input: { name: string; email: string; password: string }) => Promise<void>
  /** Entra con la cuenta demo sin pasar por el formulario */
  signInDemo: () => void
  signOut: () => Promise<void>
  updateProfile: (patch: Partial<Pick<User, 'name' | 'specialty' | 'title'>>) => void
  createProject: (input: { name: string; description: string; repoFullName?: string }) => Project
  deleteProject: (id: string) => void
  connectRepo: (projectId: string, fullName: string) => void
  disconnectRepo: (projectId: string) => void
  moveTask: (projectId: string, taskId: string, status: TaskStatus) => void
  addTask: (projectId: string, task: Omit<Task, 'id'>) => void
  getProject: (id: string) => Project | undefined
}

const AppStoreContext = createContext<AppStore | null>(null)

const uid = (p: string) => `${p}${Math.random().toString(36).slice(2, 8)}`

function nameFromEmail(email: string) {
  const raw = email.split('@')[0]?.replace(/[._-]+/g, ' ') ?? 'Invitado'
  return raw.replace(/\b\w/g, (c) => c.toUpperCase())
}

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? (JSON.parse(raw) as User) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [projects, setProjects] = useState<Project[]>(seedProjects)
  const [collaborators, setCollaborators] = useState<Collaborator[]>(seedCollaborators)

  useEffect(() => {
    try {
      if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* almacenamiento no disponible */
    }
  }, [user])

  // Restaurar sesión desde token existente al montar
  useEffect(() => {
    const tokens = getTokens()
    if (tokens && !user) {
      api.auth.me().then((me) => {
        setUser({
          id: me.id,
          name: me.name,
          email: me.email,
          specialty: 'Definí tu especialidad en el perfil',
          title: 'Colaborador',
          avatarHue: 200,
          provider: 'password',
        })
      }).catch(() => {
        clearTokens()
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const signInDemo = useCallback(() => {
    setUser({
      id: 'u_demo',
      name: 'Ramón Ortega',
      email: DEMO_CREDENTIALS.email,
      specialty: 'Full-stack · React + Postgres',
      title: 'Tech Lead · cuenta demo',
      avatarHue: 265,
      provider: 'password',
      isDemo: true,
    })
  }, [])

  const signIn = useCallback(
    async (email: string, password: string, provider: 'password' | 'google' = 'password') => {
      if (email.trim().toLowerCase() === DEMO_CREDENTIALS.email) {
        signInDemo()
        return
      }
      setLoading(true)
      setAuthError(null)
      try {
        const tokens = await api.auth.login({ email, password })
        saveTokens(tokens)
        const me = await api.auth.me()
        setUser({
          id: me.id,
          name: me.name,
          email: me.email,
          specialty: 'Full-stack · React + Postgres',
          title: 'Tech Lead',
          avatarHue: 265,
          provider,
        })
      } catch (err) {
        const apiErr = err as ApiError
        setAuthError(apiErr.detail || 'Error al iniciar sesión')
        throw err
      } finally {
        setLoading(false)
      }
    },
    [signInDemo],
  )

  const signUp = useCallback(async ({ name, email, password }: { name: string; email: string; password: string }) => {
    setLoading(true)
    setAuthError(null)
    try {
      const tokens = await api.auth.register({ email, name, password })
      saveTokens(tokens)
      setUser({
        id: tokens.access_token.slice(-8), // temporal hasta llamar /me
        name: name.trim() || nameFromEmail(email),
        email,
        specialty: 'Definí tu especialidad en el perfil',
        title: 'Colaborador',
        avatarHue: 155,
        provider: 'password',
      })
      // Obtener id real
      api.auth.me().then((me) => {
        setUser((prev) => prev ? { ...prev, id: me.id } : prev)
      }).catch(() => { /* fallback silencioso */ })
    } catch (err) {
      const apiErr = err as ApiError
      setAuthError(apiErr.detail || 'Error al registrar')
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout()
    } catch {
      /* ignorar error de logout */
    } finally {
      clearTokens()
      setUser(null)
    }
  }, [])

  const updateProfile = useCallback((patch: Partial<User>) => {
    setUser((u) => (u ? { ...u, ...patch } : u))
  }, [])

  const createProject = useCallback(
    ({
      name,
      description,
      repoFullName,
    }: {
      name: string
      description: string
      repoFullName?: string
    }) => {
      const project: Project = {
        id: uid('p_'),
        name,
        description,
        hue: Math.floor(Math.random() * 60) + 250,
        createdAt: new Date().toISOString().slice(0, 10),
        budget: { allocated: 0, spent: 0, currency: 'USD' },
        collaboratorIds: ['c1'],
        repo: repoFullName
          ? {
              provider: 'github',
              fullName: repoFullName,
              branch: 'main',
              connectedAt: new Date().toISOString().slice(0, 10),
              lastSync: 'ahora',
              stats: { commits: 0, openPRs: 0, mergedPRs: 0, contributors: 1, coverage: 0 },
            }
          : null,
        database: null,
        tasks: [
          {
            id: uid('t_'),
            title: 'Indexar repositorio y detectar convenciones',
            status: repoFullName ? 'progress' : 'backlog',
            owner: 'Arquitecto',
            source: 'agent',
            points: 3,
          },
          {
            id: uid('t_'),
            title: 'Proponer roadmap inicial con criterios de aceptación',
            status: 'backlog',
            owner: 'Estratega',
            source: 'agent',
            points: 5,
          },
        ],
      }
      setProjects((prev) => [project, ...prev])
      return project
    },
    [],
  )

  const deleteProject = useCallback((id: string) => {
    setProjects((prev) => prev.filter((p) => p.id !== id))
    setCollaborators((prev) =>
      prev.map((c) => ({ ...c, projectIds: c.projectIds.filter((pid) => pid !== id) })),
    )
  }, [])

  const connectRepo = useCallback((projectId: string, fullName: string) => {
    setProjects((prev) =>
      prev.map((p) =>
        p.id !== projectId
          ? p
          : {
              ...p,
              repo: {
                provider: 'github',
                fullName,
                branch: 'main',
                connectedAt: new Date().toISOString().slice(0, 10),
                lastSync: 'ahora',
                stats: {
                  commits: 128,
                  openPRs: 2,
                  mergedPRs: 31,
                  contributors: p.collaboratorIds.length,
                  coverage: 54,
                },
              },
            },
      ),
    )
  }, [])

  const disconnectRepo = useCallback((projectId: string) => {
    setProjects((prev) => prev.map((p) => (p.id === projectId ? { ...p, repo: null } : p)))
  }, [])

  const moveTask = useCallback((projectId: string, taskId: string, status: TaskStatus) => {
    setProjects((prev) =>
      prev.map((p) =>
        p.id !== projectId
          ? p
          : {
              ...p,
              tasks: p.tasks.map((t) => (t.id === taskId ? { ...t, status } : t)),
            },
      ),
    )
  }, [])

  const addTask = useCallback((projectId: string, task: Omit<Task, 'id'>) => {
    setProjects((prev) =>
      prev.map((p) =>
        p.id !== projectId ? p : { ...p, tasks: [...p.tasks, { ...task, id: uid('t_') }] },
      ),
    )
  }, [])

  const getProject = useCallback(
    (id: string) => projects.find((p) => p.id === id),
    [projects],
  )

  const value = useMemo<AppStore>(
    () => ({
      user,
      loading,
      authError,
      projects,
      collaborators,
      signIn,
      signUp,
      signInDemo,
      signOut,
      updateProfile,
      createProject,
      deleteProject,
      connectRepo,
      disconnectRepo,
      moveTask,
      addTask,
      getProject,
    }),
    [
      user,
      loading,
      authError,
      projects,
      collaborators,
      signIn,
      signUp,
      signInDemo,
      signOut,
      updateProfile,
      createProject,
      deleteProject,
      connectRepo,
      disconnectRepo,
      moveTask,
      addTask,
      getProject,
    ],
  )

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}

export function useAppStore() {
  const ctx = useContext(AppStoreContext)
  if (!ctx) throw new Error('useAppStore debe usarse dentro de <AppStoreProvider>')
  return ctx
}
