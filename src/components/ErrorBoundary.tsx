import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Etiqueta para saber qué parte falló (aparece en consola y en el detalle). */
  label?: string
  /** UI alternativa; si no se pasa, se usa la pantalla por defecto. */
  fallback?: (error: Error, reset: () => void) => ReactNode
}

interface State {
  error: Error | null
}

/**
 * Contiene errores de render para que un componente roto no tumbe toda la app.
 *
 * Los error boundaries sólo capturan errores durante render / lifecycle. Los
 * rechazos de promesas y los errores en handlers async se manejan en los
 * propios hooks (ver `useAnalysis`, `useProjects`).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary${this.props.label ? ` · ${this.props.label}` : ''}]`, error, info.componentStack)
  }

  reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    if (this.props.fallback) return this.props.fallback(error, this.reset)

    return (
      <div className="grid min-h-screen place-items-center px-4 py-10" role="alert">
        <div className="w-full max-w-md rounded-2xl border-2 border-ink-900 bg-paper p-6 shadow-hard">
          <p className="label-mono text-clay-600">error inesperado</p>
          <h1 className="mt-2 font-display text-[26px] leading-tight tracking-tightest text-ink-900">
            Algo se rompió en esta vista
          </h1>
          <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
            El resto de la aplicación sigue funcionando. Podés reintentar o volver al inicio.
          </p>

          <pre className="mt-4 max-h-32 overflow-auto rounded-lg border-2 border-ink-200 bg-ink-50 p-3 font-mono text-[11px] leading-relaxed text-ink-700">
            {this.props.label ? `${this.props.label}: ` : ''}
            {error.message || String(error)}
          </pre>

          <div className="mt-5 flex flex-wrap gap-2.5">
            <button
              onClick={this.reset}
              className="h-10 rounded-[10px] border-2 border-ink-900 bg-violet-600 px-4 text-[13.5px] font-semibold text-white shadow-hard-sm transition hover:bg-violet-500"
            >
              Reintentar
            </button>
            <button
              onClick={() => {
                window.location.href = '/'
              }}
              className="h-10 rounded-[10px] border-2 border-ink-300 bg-paper px-4 text-[13.5px] font-semibold text-ink-800 transition hover:border-ink-900"
            >
              Ir al inicio
            </button>
          </div>
        </div>
      </div>
    )
  }
}
