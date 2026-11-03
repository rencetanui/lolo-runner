import { Component, type ReactNode } from "react"

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <main className="mx-auto max-w-2xl p-6">
          <h1 className="text-xl font-bold">Something went wrong</h1>
          <pre className="mt-3 overflow-auto rounded border p-3 text-sm">
            {this.state.error.message}
          </pre>
        </main>
      )
    }
    return this.props.children
  }
}