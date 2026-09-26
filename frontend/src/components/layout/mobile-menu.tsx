'use client'

import { useEffect } from 'react'
import { X, Monitor, GitBranch, Play, Database, FlaskConical, Scale, Settings, HelpCircle } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

interface MobileMenuProps {
  isOpen: boolean
  onClose: () => void
}

export function MobileMenu({ isOpen, onClose }: MobileMenuProps) {
  const location = useLocation()

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Mobile menu">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden="true" />
      <div className="absolute left-0 top-0 bottom-0 w-72 bg-white dark:bg-secondary-950 border-r border-secondary-200 dark:border-secondary-700 shadow-xl animate-slide-right">
        <div className="flex items-center justify-between h-16 px-4 border-b border-secondary-200 dark:border-secondary-700">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-600 text-white font-bold text-sm">
              R
            </div>
            <span className="font-semibold text-lg text-secondary-900 dark:text-white">RIFT</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800"
            aria-label="Close menu"
          >
            <X className="w-6 h-6" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1" aria-label="Mobile navigation">
          {[
            { name: 'Dashboard', href: '/dashboard', icon: Monitor },
            { name: 'Scenarios', href: '/scenarios', icon: GitBranch },
            { name: 'Simulation', href: '/simulation', icon: Play },
            { name: 'Runs', href: '/runs', icon: Database },
            { name: 'Experiments', href: '/experiments', icon: FlaskConical },
            { name: 'Evidence', href: '/evidence', icon: Scale },
            { name: 'Settings', href: '/settings', icon: Settings },
            { name: 'Docs', href: '/docs', icon: HelpCircle },
          ].map((item) => {
            const isActive = location.pathname === item.href || 
              (item.href !== '/' && location.pathname.startsWith(item.href + '/'))
            return (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-3 text-base font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700 font-medium dark:bg-primary-900/30 dark:text-primary-300'
                      : 'text-secondary-600 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800'
                  }`
                }
                aria-current={isActive ? 'page' : undefined}
              >
                <item.icon className="w-6 h-6 flex-shrink-0" aria-hidden="true" />
                <span>{item.name}</span>
              </NavLink>
            )}
          )}
        </nav>

        <div className="p-4 border-t border-secondary-200 dark:border-secondary-700">
          <p className="text-xs text-secondary-500 dark:text-secondary-400 text-center">
            RIFT v1.0.0 · Research Prototype
          </p>
        </div>
      </div>
    </div>
  )
}