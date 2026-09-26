'use client'

import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    // Could send to error reporting service here
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  handleGoHome = () => {
    window.location.href = '/dashboard'
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-secondary-50 dark:bg-secondary-950">
          <div className="max-w-md w-full bg-white dark:bg-secondary-900 rounded-xl border border-secondary-200 dark:border-secondary-700 shadow-xl p-8">
            <div className="text-center">
              <div className="mx-auto w-16 h-16 rounded-full bg-error-100 dark:bg-error-900/30 flex items-center justify-center mb-6">
                <AlertTriangle className="w-8 h-8 text-error-600 dark:text-error-400" aria-hidden="true" />
              </div>
              <h1 className="text-2xl font-bold text-secondary-900 dark:text-white mb-2">
                Something went wrong
              </h1>
              <p className="text-secondary-600 dark:text-secondary-400 mb-6">
                We encountered an unexpected error. Our team has been notified.
              </p>

              {this.state.error && (
                <details className="mb-6 text-left">
                  <summary className="text-sm font-medium text-secondary-600 dark:text-secondary-400 cursor-pointer mb-2">
                    Error details
                  </summary>
                  <pre className="bg-secondary-100 dark:bg-secondary-800 p-3 rounded-lg text-xs overflow-x-auto text-secondary-700 dark:text-secondary-300 max-h-40 overflow-y-auto">
                    {this.state.error.message}
                    {this.state.error.stack && `\n\n${this.state.error.stack}`}
                  </pre>
                </details>
              )}

              <div className="flex gap-3 justify-center">
                <Button onClick={this.handleRetry} className="btn-primary">
                  <RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" />
                  Try Again
                </Button>
                <Button onClick={this.handleGoHome} variant="outline" className="btn-secondary">
                  <Home className="w-4 h-4 mr-2" aria-hidden="true" />
                  Go Home
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => window.open('https://github.com/OpKnock/RIFT/issues/new', '_blank')}
                  className="text-error-600 hover:text-error-700 dark:text-error-400 dark:hover:text-error-300"
                >
                  <Bug className="w-4 h-4 mr-2" aria-hidden="true" />
                  Report Issue
                </Button>
              </div>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}