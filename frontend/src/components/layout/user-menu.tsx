'use client'

import { useState, useRef, useEffect } from 'react'
import { User, Settings, LogOut, Key, Shield, Globe } from 'lucide-react'
import { cn } from '@/utils/cn'

interface UserMenuProps {
  user?: {
    name: string
    email: string
    avatar?: string
    role: string
  }
}

export function UserMenu({ user = { name: 'Research User', email: 'research@rift.dev', role: 'Researcher' } }: UserMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 p-1.5 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors"
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="User menu"
      >
        <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
          <User className="w-5 h-5 text-primary-600 dark:text-primary-400" aria-hidden="true" />
        </div>
        <span className="hidden sm:block text-sm font-medium text-secondary-700 dark:text-secondary-300">
          {user.name}
        </span>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 w-56 origin-top-right rounded-xl border border-secondary-200 bg-white py-1 shadow-lg dark:border-secondary-700 dark:bg-secondary-900 animate-fade-in"
          role="menu"
          aria-orientation="vertical"
        >
          <div className="px-3 py-2 border-b border-secondary-100 dark:border-secondary-800">
            <p className="text-sm font-medium text-secondary-900 dark:text-white">{user.name}</p>
            <p className="text-xs text-secondary-500 dark:text-secondary-400 truncate">{user.email}</p>
            <p className="text-xs text-primary-600 dark:text-primary-400 mt-0.5">{user.role}</p>
          </div>

          <div className="py-1" role="none">
            <button
              className={cn(
                'flex items-center gap-3 w-full px-3 py-2 text-sm text-secondary-700 dark:text-secondary-300',
                'hover:bg-secondary-100 dark:hover:bg-secondary-800',
                'transition-colors'
              )}
              role="menuitem"
            >
              <Settings className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span>Settings</span>
            </button>

            <button
              className={cn(
                'flex items-center gap-3 w-full px-3 py-2 text-sm text-secondary-700 dark:text-secondary-300',
                'hover:bg-secondary-100 dark:hover:bg-secondary-800',
                'transition-colors'
              )}
              role="menuitem"
            >
              <Key className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span>API Keys</span>
            </button>

            <button
              className={cn(
                'flex items-center gap-3 w-full px-3 py-2 text-sm text-secondary-700 dark:text-secondary-300',
                'hover:bg-secondary-100 dark:hover:bg-secondary-800',
                'transition-colors'
              )}
              role="menuitem"
            >
              <Shield className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span>Security</span>
            </button>

            <button
              className={cn(
                'flex items-center gap-3 w-full px-3 py-2 text-sm text-secondary-700 dark:text-secondary-300',
                'hover:bg-secondary-100 dark:hover:bg-secondary-800',
                'transition-colors'
              )}
              role="menuitem"
            >
              <Globe className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span>Language</span>
            </button>
          </div>

          <div className="border-t border-secondary-100 dark:border-secondary-800" role="none" />

          <button
            className={cn(
              'flex items-center gap-3 w-full px-3 py-2 text-sm text-error-600 dark:text-error-400',
              'hover:bg-error-50 dark:hover:bg-error-900/30',
              'transition-colors'
            )}
            role="menuitem"
            onClick={() => console.log('Sign out')}
          >
            <LogOut className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  )
}