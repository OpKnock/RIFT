'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { Search, Github, ExternalLink, Zap, Settings, HelpCircle, Monitor, GitBranch, Play as PlayIcon, Database as DatabaseIcon, FlaskConical as FlaskConicalIcon, Scale as ScaleIcon } from 'lucide-react'
import { cn } from '@/utils/cn'
import { useCommandPalette } from '@/hooks/use-command-palette'

interface Command {
  id: string
  label: string
  description: string
  icon?: React.ReactNode
  action: () => void
  category: string
  shortcut?: string
}

const commands: Command[] = [
  // Navigation
  { id: 'dashboard', label: 'Go to Dashboard', description: 'Open dashboard overview', icon: <Monitor className="w-4 h-4" />, action: () => window.location.href = '/dashboard', category: 'Navigation', shortcut: 'g d' },
  { id: 'scenarios', label: 'View Scenarios', description: 'Manage scenarios', icon: <GitBranch className="w-4 h-4" />, action: () => window.location.href = '/scenarios', category: 'Navigation', shortcut: 'g s' },
  { id: 'simulation', label: 'Run Simulation', description: 'Run a simulation', icon: <PlayIcon className="w-4 h-4" />, action: () => window.location.href = '/simulation', category: 'Navigation', shortcut: 'g r' },
  { id: 'runs', label: 'View Runs', description: 'View run history', icon: <DatabaseIcon className="w-4 h-4" />, action: () => window.location.href = '/runs', category: 'Navigation', shortcut: 'g r' },
  { id: 'experiments', label: 'Experiments', description: 'Manage experiments', icon: <FlaskConicalIcon className="w-4 h-4" />, action: () => window.location.href = '/experiments', category: 'Navigation', shortcut: 'g e' },
  { id: 'evidence', label: 'View Evidence', description: 'View evidence', icon: <ScaleIcon className="w-4 h-4" />, action: () => window.location.href = '/evidence', category: 'Navigation', shortcut: 'g e' },
  { id: 'settings', label: 'Settings', description: 'Open settings', icon: <Settings className="w-4 h-4" />, action: () => window.location.href = '/settings', category: 'Navigation', shortcut: 'g s' },
  { id: 'docs', label: 'Documentation', description: 'Open documentation', icon: <HelpCircle className="w-4 h-4" />, action: () => window.location.href = '/docs', category: 'Navigation', shortcut: 'g h' },

  // Actions
  { id: 'new-scenario', label: 'New Scenario', description: 'Create a new scenario', icon: <Zap className="w-4 h-4" />, action: () => window.location.href = '/scenarios/new', category: 'Actions', shortcut: 'n s' },
  { id: 'new-experiment', label: 'New Experiment', description: 'Create a new experiment', icon: <Zap className="w-4 h-4" />, action: () => window.location.href = '/experiments/new', category: 'Actions', shortcut: 'n e' },
  { id: 'run-simulation', label: 'Run Simulation', description: 'Execute a simulation', icon: <PlayIcon className="w-4 h-4" />, action: () => window.location.href = '/simulation', category: 'Actions', shortcut: 'r s' },

  // External
  { id: 'github', label: 'GitHub Repository', description: 'Open GitHub repo', icon: <Github className="w-4 h-4" />, action: () => window.open('https://github.com/OpKnock/RIFT', '_blank'), category: 'External', shortcut: 'g g' },
  { id: 'docs-external', label: 'Documentation', description: 'Open docs', icon: <ExternalLink className="w-4 h-4" />, action: () => window.open('https://github.com/OpKnock/RIFT', '_blank'), category: 'External', shortcut: 'd d' },
]

export function CommandPalette() {
  const { open, closeCommandPalette } = useCommandPalette()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }, [])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        useCommandPalette.getState().toggleCommandPalette()
      }
      if (event.key === 'Escape') {
        closeCommandPalette()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const filteredCommands = useMemo(() => {
    if (!query) return commands
    const lowerQuery = query.toLowerCase()
    return commands.filter(cmd =>
      cmd.label.toLowerCase().includes(lowerQuery) ||
      cmd.description.toLowerCase().includes(lowerQuery) ||
      cmd.category.toLowerCase().includes(lowerQuery) ||
      cmd.shortcut?.toLowerCase().includes(lowerQuery)
    )
  }, [query])

  const groupedCommands = useMemo(() => {
    const groups: Record<string, Command[]> = {}
    filteredCommands.forEach(cmd => {
      if (!groups[cmd.category]) groups[cmd.category] = []
      groups[cmd.category].push(cmd)
    })
    return groups
  }, [filteredCommands])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => Math.min(prev + 1, filteredCommands.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => Math.max(prev - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (filteredCommands[selectedIndex]) {
          filteredCommands[selectedIndex].action()
          closeCommandPalette()
          setQuery('')
          setSelectedIndex(0)
        }
        break
      case 'Escape':
        closeCommandPalette()
        setQuery('')
        setSelectedIndex(0)
        break
    }
  }

  const executeCommand = (cmd: Command) => {
    cmd.action()
    closeCommandPalette()
    setQuery('')
    setSelectedIndex(0)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-20" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 bg-black/50" onClick={() => closeCommandPalette()} aria-hidden="true" />
      <div className="relative w-full max-w-2xl mx-4 animate-slide-down">
        <div className="rounded-xl border border-secondary-200 bg-white shadow-xl dark:border-secondary-700 dark:bg-secondary-900 overflow-hidden">
          <div className="relative p-4">
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" aria-hidden="true" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a command or search..."
                  className="w-full pl-10 pr-4 py-3 text-sm bg-secondary-50 dark:bg-secondary-800 border border-secondary-200 dark:border-secondary-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  aria-label="Command palette search"
                  autoComplete="off"
                  spellCheck={false}
                />
                <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-0.5 text-xs text-secondary-400 bg-secondary-100 dark:bg-secondary-800 rounded">
                  <kbd className="px-1.5">⌘</kbd>+<kbd className="px-1.5">K</kbd>
                </kbd>
              </div>
            </div>
          </div>

          <div ref={listRef} className="max-h-96 overflow-y-auto">
            {Object.entries(groupedCommands).map(([category, cmds]) => (
                <div key={category} className="border-t border-secondary-100 dark:border-secondary-800">
                  <div className="px-4 py-2 text-xs font-semibold text-secondary-500 uppercase tracking-wider dark:text-secondary-400">
                    {category}
                  </div>
                  {cmds.map((cmd) => {
                    const globalIndex = commands.indexOf(cmd)
                    const isSelected = globalIndex === selectedIndex
                    return (
                      <button
                        key={cmd.id}
                        onClick={() => executeCommand(cmd)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                        className={cn(
                          'flex items-center gap-3 w-full px-4 py-2.5 text-sm transition-colors',
                          isSelected
                            ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                            : 'text-secondary-700 hover:bg-secondary-50 dark:text-secondary-300 dark:hover:bg-secondary-800'
                        )}
                        role="option"
                        aria-selected={isSelected}
                      >
                        <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center text-secondary-400 dark:text-secondary-500">
                          {cmd.icon}
                        </span>
                        <div className="flex-1 min-w-0">
                          <span className="font-medium truncate block">{cmd.label}</span>
                          <span className="text-xs text-secondary-500 dark:text-secondary-400 truncate block">{cmd.description}</span>
                        </div>
                        {cmd.shortcut && (
                          <kbd className="px-2 py-0.5 text-xs text-secondary-400 bg-secondary-100 dark:bg-secondary-800 rounded font-mono">
                            {cmd.shortcut.replace(' ', '+').toUpperCase()}
                          </kbd>
                        )}
                      </button>
                    )
                  })}
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}