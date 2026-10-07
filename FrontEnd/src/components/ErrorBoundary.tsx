import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface Props { children: ReactNode; resetKey: string }
interface State { error: Error | null }

/**
 * A page that fails to draw shows this card instead of a blank screen. It clears itself when
 * the user moves to another page (resetKey = the path).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page failed to draw', error, info.componentStack)
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <main className="page">
        <div className="alert alert-err" role="alert" style={{ flexDirection: 'column', gap: 8 }}>
          <strong>This page could not be shown.</strong>
          <span>Try again. If it keeps happening, tell the admin what you clicked. ({this.state.error.message})</span>
          <div><button type="button" className="btn btn-sec btn-sm" onClick={() => this.setState({ error: null })}>Try again</button></div>
        </div>
      </main>
    )
  }
}
