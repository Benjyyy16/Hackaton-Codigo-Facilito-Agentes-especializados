import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { Backdrop } from '@/components/ui/Backdrop'
import { ErrorBoundary } from '@/components/ErrorBoundary'
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

/**
 * Envuelve cada ruta: un fallo de render queda contenido en la vista y el
 * usuario puede reintentar o volver, en lugar de quedarse con la app en blanco.
 * La `key` reinicia el boundary al navegar.
 */
function Page({ name, children }: { name: string; children: ReactNode }) {
  return (
    <ErrorBoundary key={name} label={name}>
      {children}
    </ErrorBoundary>
  )
}

function Router() {
  const location = useLocation()
  return (
    <Suspense fallback={<RouteFallback />}>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route
            path="/"
            element={
              <Page name="Landing">
                <Landing />
              </Page>
            }
          />
          <Route
            path="/app"
            element={
              <Protected>
                <Page name="Dashboard">
                  <Dashboard />
                </Page>
              </Protected>
            }
          />
          <Route
            path="/app/proyecto/:id"
            element={
              <Protected>
                <Page name="ProjectBoard">
                  <ProjectBoard />
                </Page>
              </Protected>
            }
          />
          <Route
            path="/perfil"
            element={
              <Protected>
                <Page name="Profile">
                  <Profile />
                </Page>
              </Protected>
            }
          />
          <Route
            path="/app/datgent"
            element={
              <Protected>
                <Page name="DatgentAnalysis">
                  <DatgentAnalysis />
                </Page>
              </Protected>
            }
          />
          <Route
            path="/app/datgent/select-repo"
            element={
              <Protected>
                <Page name="RepoSelector">
                  <RepoSelector />
                </Page>
              </Protected>
            }
          />
          <Route
            path="/login"
            element={
              <Page name="Login">
                <Login />
              </Page>
            }
          />
          {/*
            El backend puede redirigir a cualquiera de las dos rutas según cómo
            esté configurado `FRONTEND_URL` en su callback
            (`GET /auth/oauth/{provider}/callback`). Ambas apuntan al mismo
            handler para que el login no se rompa por la barra de más.
          */}
          <Route
            path="/oauth/callback"
            element={
              <Page name="OAuthCallback">
                <OAuthCallback />
              </Page>
            }
          />
          <Route
            path="/auth/callback"
            element={
              <Page name="OAuthCallback">
                <OAuthCallback />
              </Page>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
    </Suspense>
  )
}

export default function App() {
  return (
    // Boundary externo: cubre fallos del propio store o del backdrop
    <ErrorBoundary label="App">
      <AppStoreProvider>
        <Backdrop />
        <Router />
      </AppStoreProvider>
    </ErrorBoundary>
  )
}
