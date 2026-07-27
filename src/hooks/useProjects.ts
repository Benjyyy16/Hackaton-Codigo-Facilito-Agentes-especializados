import { useCallback, useEffect, useState } from 'react'
import { listProjects, createProject, type ProjectRead } from '@/lib/projectsApi'

export function useProjects() {
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listProjects()
      setProjects(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error cargando proyectos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const addProject = useCallback(async (name: string, description?: string) => {
    const project = await createProject(name, description)
    setProjects(prev => [project, ...prev])
    return project
  }, [])

  return { projects, loading, error, refresh, addProject }
}
