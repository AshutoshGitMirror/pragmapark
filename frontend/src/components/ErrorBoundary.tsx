import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="flex items-center justify-center min-h-[200px] rounded-xl bg-[#0e0e18] border border-[rgba(255,255,255,0.06)] p-8">
          <div className="text-center max-w-md">
            <div className="text-3xl mb-3 opacity-50">⚠</div>
            <h3 className="text-sm font-semibold text-[#94a3b8] mb-2">Something went wrong</h3>
            <p className="text-[10px] text-[#475569] mb-4 font-mono">{this.state.error?.message}</p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 rounded-lg text-xs font-mono border border-[rgba(255,255,255,0.1)] text-[#94a3b8] hover:border-[#00d4ff] hover:text-[#00d4ff] transition-all"
            >
              Try Again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
