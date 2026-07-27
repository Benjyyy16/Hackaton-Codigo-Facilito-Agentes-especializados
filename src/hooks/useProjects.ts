import { useCallback, useEffect, useRef, useState } from 'react'
import { listProjects, createProject, type ProjectRead } from '@/lib/projectsApi'
import { errorMessage, isAbortError } from '@/lib/http'

export function useProjects() {
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  /** Cancela la carga anterior si se pide un refresh o el componente se va. */
  const abortRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  const refresh = useCallback(async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    try {
      const data = await listProjects(20, 0, controller.signal)
      if (!mountedRef.current || controller.signal.aborted) return
      setProjects(data)
    } catch (err: unknown) {
      if (isAbortError(err) || !mountedRef.current) return
      setError(errorMessage(err, 'Error cargando proyectos'))
    } finally {
      if (mountedRef.current && !controller.signal.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const addProject = useCallback(async (name: string, description?: string) => {
    const project = await createProject(name, description)
    if (mountedRef.current) setProjects((prev) => [project, ...prev])
    return project
  }, [])

  return { projects, loading, error, refresh, addProject }
}
