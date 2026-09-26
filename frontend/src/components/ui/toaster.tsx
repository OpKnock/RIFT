'use client'

import { useState, useEffect, useCallback } from 'react'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '@/utils/cn'

export interface Toast {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
}

let toastId = 0

const generateId = () => `toast-${++toastId}-${Date.now()}`

const createToastStore = () => {
  let toasts: Toast[] = []
  const listeners: Array<(toasts: Toast[]) => void> = []

  const notify = () => {
    listeners.forEach(listener => listener([...toasts]))
  }

  return {
    getToasts: () => [...toasts],
    subscribe: (listener: (toasts: Toast[]) => void) => {
      listeners.push(listener)
      return () => {
        const index = listeners.indexOf(listener)
        if (index > -1) listeners.splice(index, 1)
      }
    },
    addToast: (toast: Omit<Toast, 'id'>) => {
      const id = generateId()
      const newToast = { ...toast, id, duration: toast.duration ?? 5000 }
      toasts = [...toasts, newToast]
      notify()
      
      if (newToast.duration && newToast.duration > 0) {
        setTimeout(() => {
          toasts = toasts.filter(t => t.id !== id)
          notify()
        }, newToast.duration)
      }
      
      return id
    },
    removeToast: (id: string) => {
      toasts = toasts.filter(t => t.id !== id)
      notify()
    },
    clearToasts: () => {
      toasts = []
      notify()
    }
  }
}

const toastStore = createToastStore()

export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>(toastStore.getToasts())

  useEffect(() => {
    return toastStore.subscribe(setToasts)
  }, [])

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    return toastStore.addToast(toast)
  }, [])

  const removeToast = useCallback((id: string) => {
    toastStore.removeToast(id)
  }, [])

  const clearToasts = useCallback(() => {
    toastStore.clearToasts()
  }, [])

  return { toasts, addToast, removeToast, clearToasts }
}

export function ToastProvider({ children }: { children?: React.ReactNode }) {
  const { toasts, removeToast } = useToasts()

  return (
    <div>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none" aria-live="polite" aria-label="Notifications">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            toast={toast}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </div>
  )
}

function Toast({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const [progress, setProgress] = useState(100)

  useEffect(() => {
    if (!toast.duration || toast.duration <= 0) return

    const interval = setInterval(() => {
      setProgress(prev => {
        const next = prev - (100 / (toast.duration! / 50))
        if (next <= 0) {
          return 0
        }
        return next
      })
    }, 50)

    return () => clearInterval(interval)
  }, [toast.duration, onClose])

  const icons = {
    success: <CheckCircle className="w-5 h-5 text-success-600 dark:text-success-400" />,
    error: <AlertCircle className="w-5 h-5 text-error-600 dark:text-error-400" />,
    warning: <AlertTriangle className="w-5 h-5 text-warning-600 dark:text-warning-400" />,
    info: <Info className="w-5 h-5 text-primary-600 dark:text-primary-400" />,
  }

  const colors = {
    success: 'border-success-200 bg-success-50 text-success-900 dark:bg-success-900/30 dark:text-success-100',
    error: 'border-error-200 bg-error-50 text-error-900 dark:bg-error-900/30 dark:text-error-100',
    warning: 'border-warning-200 bg-warning-50 text-warning-900 dark:bg-warning-900/30 dark:text-warning-100',
    info: 'border-primary-200 bg-primary-50 text-primary-900 dark:bg-primary-900/30 dark:text-primary-100',
  }

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border p-4 shadow-xl max-w-sm w-full animate-slide-in pointer-events-auto',
        colors[toast.type]
      )}
      role="alert"
      aria-live="polite"
    >
      <div className="flex-shrink-0 mt-0.5">
        {icons[toast.type]}
      </div>
      <div className="flex-1 min-w-0 mr-3">
        <p className="font-medium text-sm">{toast.title}</p>
        {toast.message && (
          <p className="text-sm opacity-90 mt-0.5">{toast.message}</p>
        )}
        {toast.action && (
          <button
            onClick={() => {
              toast.action?.onClick()
              onClose()
            }}
            className="mt-2 text-sm font-medium underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-current focus:ring-offset-2"
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        onClick={onClose}
        className="flex-shrink-0 p-1 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4 opacity-50 hover:opacity-100" aria-hidden="true" />
      </button>
      <div
        className="absolute bottom-0 left-0 h-0.5 rounded-b-xl transition-all duration-75 ease-linear"
        style={{ width: `${progress}%`, backgroundColor: 'currentColor', opacity: 0.3 }}
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Toast timeout"
      />
    </div>
  )
}

export const Toaster = ToastProvider