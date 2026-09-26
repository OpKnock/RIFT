import { Link } from 'react-router-dom'

export function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="border-t border-secondary-200 dark:border-secondary-700 mt-8">
      <div className="px-4 lg:px-6 py-6 max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="text-sm text-secondary-500">
            <p>© {year} RIFT — research prototype. Engine v1.0.0.</p>
            <p className="mt-1">Synthetic demo data. Decision support only — never autonomous care.</p>
          </div>
          <nav className="flex flex-wrap gap-x-4 gap-y-2 text-sm" aria-label="Footer">
            <Link to="/docs" className="text-secondary-600 hover:underline dark:text-secondary-400">Documentation</Link>
            <Link to="/faq" className="text-secondary-600 hover:underline dark:text-secondary-400">FAQ</Link>
            <Link to="/legal/privacy" className="text-secondary-600 hover:underline dark:text-secondary-400">Privacy</Link>
            <Link to="/legal/terms" className="text-secondary-600 hover:underline dark:text-secondary-400">Terms</Link>
            <Link to="/legal/cookies" className="text-secondary-600 hover:underline dark:text-secondary-400">Cookies</Link>
            <a href="https://github.com/OpKnock/RIFT" target="_blank" rel="noopener noreferrer" className="text-secondary-600 hover:underline dark:text-secondary-400">GitHub</a>
          </nav>
        </div>
      </div>
    </footer>
  )
}
