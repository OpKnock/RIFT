import { useEffect, useRef, useState } from 'react'
import { MessageCircle, X, BookOpen, Bug, Mail } from 'lucide-react'

export function FloatingContact() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open ])

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open ])

  return (
    <div ref={ref} className="fixed bottom-4 right-4 z-40">
      {open && (
        <div className="mb-2 w-60 rounded-xl border border-secondary-200 bg-white p-2 shadow-xl dark:border-secondary-700 dark:bg-secondary-900" role="menu" aria-label="Contact options">
          <a href="/docs" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-secondary-100 dark:hover:bg-secondary-800" role="menuitem">
            <BookOpen className="w-4 h-4 text-secondary-500" />Documentation
          </a>
          <a href="mailto:support@rift.dev" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-secondary-100 dark:hover:bg-secondary-800" role="menuitem">
            <Mail className="w-4 h-4 text-secondary-500" />Email support
          </a>
          <a href="https://github.com/OpKnock/RIFT/issues/new" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-secondary-100 dark:hover:bg-secondary-800" role="menuitem">
            <Bug className="w-4 h-4 text-secondary-500" />Report an issue
          </a>
        </div>
      )}
      <button
        onClick={() => setOpen(!open)}
        className="p-3 rounded-full bg-primary-600 text-white shadow-lg hover:bg-primary-700 transition-colors"
        aria-expanded={open}
        aria-label={open ? 'Close contact menu' : 'Open contact menu'}
      >
        {open ? <X className="w-5 h-5" /> : <MessageCircle className="w-5 h-5" />}
      </button>
    </div>
  )
}
