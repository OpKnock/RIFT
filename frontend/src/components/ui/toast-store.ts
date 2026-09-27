import { useState, useEffect, useCallback } from 'react'
import type { Toast } from './toaster'

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
