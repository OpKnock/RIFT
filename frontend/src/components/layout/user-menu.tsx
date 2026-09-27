'use client'

import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Settings, LogOut, Key, Shield } from 'lucide-react'
import { cn } from '@/utils/cn'
import { api } from '@/services/api'
import { readDisplayName } from '@/pages/profile'

interface UserMenuProps {
  user?: {
    name: string
    email: string
    avatar?: string
    role: string
  }
}

const FALLBACK_USER = { name: 'Research User', email: 'research@rift.dev', role: 'Researcher' }

export function UserMenu({ user }: UserMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  // Identity is the operator's local display profile when set; the
  // hardcoded fallback is clearly labeled and never sent to the server
  // as an authenticated principal.
  const profileName = readDisplayName()
  const effectiveUser = user || (profileName
    ? { name: profileName, email: 'research@rift.dev', role: 'Researcher (local profile)' }
    : FALLBACK_USER)

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
          {effectiveUser.name}
        </span>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 w-56 origin-top-right rounded-xl border border-secondary-200 bg-white py-1 shadow-lg dark:border-secondary-700 dark:bg-secondary-900 animate-fade-in"
          role="menu"
          aria-orientation="vertical"
        >
          <div className="px-3 py-2 border-b border-secondary-100 dark:border-secondary-800">
            <p className="text-sm font-medium text-secondary-900 dark:text-white">{effectiveUser.name}</p>
            <p className="text-xs text-secondary-500 dark:text-secondary-400 truncate">{effectiveUser.email}</p>
            <p className="text-xs text-primary-600 dark:text-primary-400 mt-0.5">{effectiveUser.role}</p>
          </div>

          <div className="py-1" role="none">
            <button
              className={cn(
                'flex items-center gap-3 w-full px-3 py-2 text-sm text-secondary-700 dark:text-secondary-300',
                'hover:bg-secondary-100 dark:hover:bg-secondary-800',
                'transition-colors'
              )}
              role="menuitem"
              onClick={() => { setOpen(false); navigate('/settings?tab=profile') }}
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
              onClick={() => { setOpen(false); navigate('/settings?tab=api') }}
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
              onClick={() => { setOpen(false); navigate('/settings?tab=security') }}
            >
              <Shield className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span>Security</span>
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
            onClick={() => { void api.logout(); setOpen(false); navigate('/dashboard', { replace: true }) }}
          >
            <LogOut className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            <span>Sign out (destroys server session)</span>
          </button>
        </div>
      )}
    </div>
  )
}