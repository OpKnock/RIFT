import { useEffect, useState } from 'react'
import { Outlet, NavLink, Link, useLocation } from 'react-router-dom'
import { Menu, Sun, Moon, Monitor, GitBranch, Play, Database, FlaskConical, Settings, Scale, ChevronLeft, ChevronRight, Bell, Github, AlertTriangle, Search } from 'lucide-react'
import { useTheme } from '@/components/providers/theme-provider'
import { cn } from '@/utils/cn'
import { MobileMenu } from './mobile-menu'
import { UserMenu } from './user-menu'
import { BackToTop } from '@/components/back-to-top'
import { FloatingContact } from '@/components/floating-contact'
import { ScrollProgress } from '@/components/scroll-progress'
import { Footer } from '@/components/layout/footer'
import { useRouteTitle } from '@/hooks/use-route-title'
import { useUtm } from '@/hooks/use-utm'
import { CommandPalette } from '@/components/ui/command-palette'
import { useCommandPalette } from '@/hooks/use-command-palette'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine)

  useEffect(() => {
    const goOnline = () => setOnline(true)
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])
  const location = useLocation()
  const { resolvedTheme, setTheme } = useTheme()
  const { openCommandPalette } = useCommandPalette()
  useRouteTitle()
  useUtm()

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen)

  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: Monitor, description: 'Overview & metrics' },
    { name: 'Scenarios', href: '/scenarios', icon: GitBranch, description: 'Manage scenarios' },
    { name: 'Simulation', href: '/simulation', icon: Play, description: 'Run simulations' },
    { name: 'Runs', href: '/runs', icon: Database, description: 'View run history' },
    { name: 'Experiments', href: '/experiments', icon: FlaskConical, description: 'Manage experiments' },
    { name: 'Evidence', href: '/evidence', icon: Scale, description: 'View evidence' },
    { name: 'Incidents', href: '/incidents', icon: AlertTriangle, description: 'Incident lifecycle' },
    { name: 'Explainability', href: '/explainability', icon: Search, description: 'Decision reasoning' },
    { name: 'Settings', href: '/settings', icon: Settings, description: 'Configuration' },
  ]

  return (
    <div className="min-h-screen bg-secondary-50 dark:bg-secondary-950">
      <ScrollProgress />
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-3 focus:py-2 focus:rounded-lg focus:bg-primary-600 focus:text-white text-sm"
      >
        Skip to content
      </a>
      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 h-screen bg-white dark:bg-secondary-950 border-r border-secondary-200 dark:border-secondary-700 transition-all duration-300',
          'flex flex-col',
          sidebarOpen ? 'w-64' : 'w-20',
          'lg:translate-x-0'
        )}
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-secondary-200 dark:border-secondary-700">
          <Link to="/dashboard" className="flex items-center gap-3" aria-label="RIFT home">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-600 text-white font-bold text-sm">
              R
            </div>
            {sidebarOpen && (
              <span className="font-semibold text-lg text-secondary-900 dark:text-white">
                RIFT
              </span>
            )}
          </Link>
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors"
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1" aria-label="Main navigation">
          {navItems.map((item) => {
            const isActive = location.pathname === item.href || 
              (item.href !== '/' && location.pathname.startsWith(item.href + '/'))
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-primary-50 text-primary-700 font-medium dark:bg-primary-900/30 dark:text-primary-300'
                      : 'text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900 dark:text-secondary-400 dark:hover:bg-secondary-800 dark:hover:text-secondary-100'
                  }`
                }
                aria-current={isActive ? 'page' : undefined}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                <span className="truncate">{item.name}</span>
              </NavLink>
            )}
          )}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-secondary-200 dark:border-secondary-700">
          <div className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-secondary-900 dark:text-white truncate">
                RIFT v1.0.0
              </p>
              <p className="text-xs text-secondary-500 dark:text-secondary-400 truncate">
                Research Prototype
              </p>
            </div>
            <a
              href="https://github.com/OpKnock/RIFT"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors"
              aria-label="GitHub Repository"
            >
              <Github className="w-5 h-5" aria-hidden="true" />
            </a>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main
        className={cn(
          'flex-1 min-h-screen transition-all duration-300',
          sidebarOpen ? 'lg:ml-64' : 'lg:ml-20'
        )}
      >
        {/* Top Bar */}
        <header className="sticky top-0 z-30 h-16 bg-white/80 dark:bg-secondary-950/80 backdrop-blur-lg border-b border-secondary-200 dark:border-secondary-700">
          <div className="flex items-center justify-between h-full px-4 lg:px-6">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800"
                aria-label="Open menu"
              >
                <Menu className="w-6 h-6" aria-hidden="true" />
              </button>

              {/* Command Palette Trigger */}
              <button
                onClick={openCommandPalette}
                className="flex-1 max-w-md lg:max-w-lg"
              >
                <CommandPalette />
              </button>
            </div>

            <div className="flex items-center gap-3">
              {/* Theme Toggle */}
              <button
                onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
                className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors"
                aria-label="Toggle theme"
              >
                {resolvedTheme === 'dark' ? (
                  <Sun className="w-5 h-5" aria-hidden="true" />
                ) : (
                  <Moon className="w-5 h-5" aria-hidden="true" />
                )}
              </button>

              {/* Alerts (live, evaluated server-side) */}
              <Link to="/runs" className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors" aria-label="Operations and alerts">
                <Bell className="w-5 h-5" aria-hidden="true" />
              </Link>

              {/* User Menu */}
              <UserMenu />
            </div>
          </div>
        </header>

        {!online && (
          <div className="px-4 lg:px-6 pt-4" role="alert">
            <p className="text-sm text-warning-600 dark:text-warning-400 border border-warning-200 dark:border-warning-800 rounded-lg px-3 py-2">
              Offline — the local engine is unreachable until connectivity returns. Previously loaded pages remain readable.
            </p>
          </div>
        )}

        {/* Page Content */}
        <div id="main-content" className="p-4 lg:p-6">
          <Outlet />
        </div>
        <Footer />
      </main>

      {/* Mobile Menu */}
      <MobileMenu isOpen={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />

      {/* Command Palette */}
      <CommandPalette />

      <BackToTop />
      <FloatingContact />
    </div>
  )
}