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

  _isChunkError(error: Error): boolean {
    const msg = error?.message || ''
    return /Failed to fetch dynamically imported module|Loading chunk.*failed|ChunkLoadError/i.test(msg)
  }

  _handleRetry = () => {
    if (this.state.error && this._isChunkError(this.state.error)) {
      // Chunk load errors mean the JS bundle was renamed during deploy.
      // A full page reload fetches the new HTML with correct chunk hashes.
      window.location.reload()
    } else {
      this.setState({ hasError: false, error: null })
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="flex items-center justify-center min-h-[200px] rounded-xl bg-deeper border border-[rgba(255,255,255,0.06)] p-8">
          <div className="text-center max-w-md">
            <div className="text-3xl mb-3 opacity-50">⚠</div>
            <h3 className="text-sm font-semibold text-muted mb-2">A new version has been deployed</h3>
            <p className="text-[10px] text-dim mb-4 font-mono">The app needs to refresh to apply the latest update.</p>
            <button
              onClick={this._handleRetry}
              className="px-4 py-2 rounded-lg text-xs font-mono border border-[rgba(255,255,255,0.1)] text-muted hover:border-cyan hover:text-cyan transition-all"
            >
              Reload App
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
