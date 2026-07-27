import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { Backdrop } from '@/components/ui/Backdrop'
import { AppStoreProvider, useAppStore } from '@/store/AppStore'
import Landing from '@/pages/Landing'

// Las rutas internas cargan React Flow: se separan del bundle de la landing
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const ProjectBoard = lazy(() => import('@/pages/ProjectBoard'))
const Profile = lazy(() => import('@/pages/Profile'))
const DatgentAnalysis = lazy(() => import('@/pages/DatgentAnalysis'))
const Login = lazy(() => import('@/pages/Login'))
const OAuthCallback = lazy(() => import('@/pages/OAuthCallback'))
const RepoSelector = lazy(() => import('@/pages/RepoSelector'))

/** Bloquea rutas de la app si no hay sesión. */
function Protected({ children }: { children: ReactNode }) {
  const { user } = useAppStore()
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RouteFallback() {
  return (
    <div className="grid min-h-screen place-items-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        <span className="text-[13px] text-violet-200/50">Cargando tablero…</span>
      </div>
    </div>
  )
}

function Router() {
  const location = useLocation()
  return (
    <Suspense fallback={<RouteFallback />}>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<Landing />} />
          <Route
            path="/app"
            element={
              <Protected>
                <Dashboard />
              </Protected>
            }
          />
          <Route
            path="/app/proyecto/:id"
            element={
              <Protected>
                <ProjectBoard />
              </Protected>
            }
          />
          <Route
            path="/perfil"
            element={
              <Protected>
                <Profile />
              </Protected>
            }
          />
          <Route
            path="/app/datgent"
            element={
              <Protected>
                <DatgentAnalysis />
              </Protected>
            }
          />
          <Route
            path="/app/datgent/select-repo"
            element={
              <Protected>
                <RepoSelector />
              </Protected>
            }
          />
          <Route path="/login" element={<Login />} />
          <Route path="/oauth/callback" element={<OAuthCallback />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
    </Suspense>
  )
}

export default function App() {
  return (
    <AppStoreProvider>
      <Backdrop />
      <Router />
    </AppStoreProvider>
  )
}
