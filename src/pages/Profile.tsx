import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Check, GitPullRequest, Pencil, X, Zap } from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Odometer, Stamp } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'
import { useAppStore } from '@/store/AppStore'
import { cn } from '@/lib/cn'

const roleLabel: Record<string, string> = {
  owner: 'propietario',
  maintainer: 'mantenedor',
  collaborator: 'colaborador',
  viewer: 'lector',
}

const roleCls: Record<string, string> = {
  owner: 'border-mint-600 bg-mint-100 text-mint-700',
  maintainer: 'border-violet-600 bg-violet-100 text-violet-700',
  collaborator: 'border-ink-900 bg-paper text-ink-700',
  viewer: 'border-ink-200 bg-paper-100 text-ink-400',
}

export default function Profile() {
  const { user, projects, collaborators, updateProfile } = useAppStore()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({
    name: user?.name ?? '',
    title: user?.title ?? '',
    specialty: user?.specialty ?? '',
  })

  if (!user) return <Navigate to="/" replace />

  // En la demo, el usuario de la sesión corresponde al colaborador c1
  const me = collaborators.find((c) => c.id === 'c1')
  const myProjects = projects.filter((p) => p.collaboratorIds.includes('c1'))

  function save() {
    updateProfile(draft)
    setEditing(false)
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-5 py-9 sm:px-8 sm:py-12">
        {/* ================= Ficha de identidad ================= */}
        <div className="relative overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
          <div className="h-2 bg-hatch bg-[length:9px_9px]" />

          <div className="p-6 sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div className="flex items-start gap-5">
                <motion.div
                  initial={{ scale: 0.7, rotate: -10, opacity: 0 }}
                  animate={{ scale: 1, rotate: 0, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 250, damping: 17 }}
                  className="rounded-lg border-2 border-ink-900 p-1 shadow-hard-sm"
                >
                  <Avatar name={user.name} hue={user.avatarHue} src={user.avatarUrl} size={70} ring={false} />
                </motion.div>

                <div className="min-w-0">
                  {editing ? (
                    <div className="space-y-2">
                      <input
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                        aria-label="Nombre"
                        className="h-10 w-full max-w-xs rounded-lg border-2 border-ink-900 bg-paper px-3 text-[17px] font-bold text-ink-900 focus:border-violet-600 focus:outline-none"
                      />
                      <input
                        value={draft.title}
                        onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                        aria-label="Cargo"
                        placeholder="Cargo"
                        className="h-9 w-full max-w-xs rounded-lg border-2 border-ink-900 bg-paper px-3 text-[13px] text-ink-800 focus:border-violet-600 focus:outline-none"
                      />
                      <input
                        value={draft.specialty}
                        onChange={(e) => setDraft({ ...draft, specialty: e.target.value })}
                        aria-label="Especialidad"
                        placeholder="Especialidad"
                        className="h-9 w-full max-w-md rounded-lg border-2 border-ink-900 bg-paper px-3 text-[13px] text-ink-800 focus:border-violet-600 focus:outline-none"
                      />
                    </div>
                  ) : (
                    <>
                      <p className="label-mono text-ink-400">expediente · colaborador</p>
                      <h1 className="mt-1.5 font-display text-[30px] leading-none tracking-tightest text-ink-900 sm:text-[36px]">
                        {user.name}
                      </h1>
                      <p className="mt-2 text-[14px] font-medium text-ink-600">{user.title}</p>
                      <p className="mt-3 inline-flex items-center gap-2 rounded border-2 border-ink-900 bg-mint-100 px-2.5 py-1 font-mono text-[11px] font-bold uppercase tracking-wider text-mint-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-mint-600" />
                        {user.specialty}
                      </p>
                      <p className="mt-3 font-mono text-[11px] text-ink-400">
                        {user.email} · vía {user.provider === 'google' ? 'Google' : 'correo'}
                      </p>
                    </>
                  )}
                </div>
              </div>

              <div className="flex flex-col items-end gap-3">
                {user.isDemo && (
                  <span className="inline-flex items-center gap-1.5 rounded border-2 border-violet-600 bg-violet-50 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-700">
                    <Zap className="h-3 w-3" />
                    cuenta demo
                  </span>
                )}
                <div className="flex gap-2">
                  {editing ? (
                    <>
                      <Button size="sm" variant="mint" magnetic={false} onClick={save}>
                        <Check className="h-3.5 w-3.5" />
                        Guardar
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        magnetic={false}
                        onClick={() => setEditing(false)}
                      >
                        <X className="h-3.5 w-3.5" />
                        Cancelar
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      variant="paper"
                      onClick={() => {
                        setDraft({ name: user.name, title: user.title, specialty: user.specialty })
                        setEditing(true)
                      }}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Editar perfil
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* métricas del expediente */}
            <div className="mt-8 grid divide-y-2 divide-ink-100 overflow-hidden rounded-lg border-2 border-ink-900 sm:grid-cols-3 sm:divide-y-0 sm:divide-x-2">
              {[
                { l: 'proyectos', v: String(myProjects.length) },
                { l: 'repos conectados', v: String(myProjects.filter((p) => p.repo).length) },
                {
                  l: 'tareas cerradas',
                  v: String(
                    myProjects.reduce(
                      (s, p) => s + p.tasks.filter((t) => t.status === 'done').length,
                      0,
                    ),
                  ),
                },
              ].map((s) => (
                <div key={s.l} className="bg-paper-100 p-4">
                  <p className="label-mono text-ink-400">{s.l}</p>
                  <p className="mt-1.5 font-display text-[28px] leading-none tracking-tightest text-ink-900">
                    <Odometer value={s.v} />
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ================= Colabora en ================= */}
        <div className="mt-12">
          <div className="flex items-end justify-between border-b-2 border-ink-900 pb-2.5">
            <div>
              <p className="label-mono text-violet-700">asignaciones</p>
              <h2 className="mt-1 font-display text-[24px] leading-none tracking-tightest text-ink-900">
                Colabora en
              </h2>
            </div>
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-ink-400">
              {myProjects.length} proyectos
            </span>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            {myProjects.map((p, i) => (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
              >
                <Link
                  to={`/app/proyecto/${p.id}`}
                  className="group block h-full rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard transition-transform hover:-translate-y-1"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span
                        className="h-2.5 w-2.5 border-2 border-ink-900"
                        style={{ background: `hsl(${p.hue} 62% 60%)` }}
                      />
                      <h3 className="text-[15.5px] font-extrabold text-ink-900">{p.name}</h3>
                    </div>
                    <span
                      className={cn(
                        'shrink-0 rounded border-2 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider',
                        roleCls[me?.role ?? 'collaborator'],
                      )}
                    >
                      {roleLabel[me?.role ?? 'collaborator']}
                    </span>
                  </div>

                  <p className="mt-2 line-clamp-2 text-[12.5px] leading-relaxed text-ink-600">
                    {p.description}
                  </p>

                  <div className="mt-4 flex flex-wrap items-center gap-1.5">
                    {p.repo && (
                      <span className="inline-flex items-center gap-1.5 rounded border border-ink-900 bg-paper px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-700">
                        <GitHubLogo className="h-2.5 w-2.5" />
                        {p.repo.fullName.split('/')[1]}
                      </span>
                    )}
                    {p.database && (
                      <span className="inline-flex items-center gap-1.5 rounded border border-ink-900 bg-paper px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-700">
                        <SupabaseLogo className="h-2.5 w-2.5" />
                        {p.database.tables} tablas
                      </span>
                    )}
                    {p.repo && (
                      <span className="inline-flex items-center gap-1.5 rounded border border-ink-900 bg-paper px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-700">
                        <GitPullRequest className="h-2.5 w-2.5" />
                        {p.repo.stats.openPRs}
                      </span>
                    )}
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ================= Equipo ================= */}
        <div className="mt-12">
          <div className="flex items-end justify-between border-b-2 border-ink-900 pb-2.5">
            <div>
              <p className="label-mono text-violet-700">directorio</p>
              <h2 className="mt-1 font-display text-[24px] leading-none tracking-tightest text-ink-900">
                Equipo y especialidad
              </h2>
            </div>
            <Stamp tone="ink" className="hidden sm:inline-flex">
              {collaborators.length} personas
            </Stamp>
          </div>

          <div className="mt-5 overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
            <div className="hidden grid-cols-[1.3fr_1.4fr_auto] items-center gap-4 border-b-2 border-ink-900 bg-ink-900 px-4 py-2 sm:grid">
              {['persona', 'especialidad', 'proyectos'].map((h) => (
                <span
                  key={h}
                  className="font-mono text-[9.5px] font-bold uppercase tracking-[0.16em] text-white/70"
                >
                  {h}
                </span>
              ))}
            </div>

            <div className="divide-y-2 divide-ink-100">
              {collaborators.map((c, i) => (
                <motion.div
                  key={c.id}
                  initial={{ opacity: 0, x: -14 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="grid items-center gap-4 p-4 transition-colors hover:bg-violet-50 sm:grid-cols-[1.3fr_1.4fr_auto]"
                >
                  <div className="flex items-center gap-3">
                    <span className="rounded-full border-2 border-ink-900">
                      <Avatar name={c.name} hue={c.avatarHue} size={36} ring={false} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-bold text-ink-900">{c.name}</p>
                      <span
                        className={cn(
                          'mt-0.5 inline-block rounded border px-1.5 py-0.5 font-mono text-[8.5px] font-bold uppercase tracking-wider',
                          roleCls[c.role],
                        )}
                      >
                        {roleLabel[c.role]}
                      </span>
                    </div>
                  </div>

                  <p className="text-[12.5px] text-ink-600">{c.specialty}</p>

                  <div className="flex flex-wrap gap-1.5 sm:justify-end">
                    {c.projectIds.map((pid) => {
                      const p = projects.find((x) => x.id === pid)
                      if (!p) return null
                      return (
                        <Link
                          key={pid}
                          to={`/app/proyecto/${pid}`}
                          className="inline-flex items-center gap-1.5 rounded border-2 border-ink-200 bg-paper px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-600 transition hover:border-ink-900 hover:text-ink-900"
                        >
                          <span
                            className="h-1.5 w-1.5 border border-ink-900"
                            style={{ background: `hsl(${p.hue} 62% 60%)` }}
                          />
                          {p.name}
                        </Link>
                      )
                    })}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
