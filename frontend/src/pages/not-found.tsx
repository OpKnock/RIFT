import { Home, ArrowLeft, FileQuestion } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 dark:bg-secondary-950 px-4">
      <div className="max-w-md w-full text-center py-12">
        <div className="mb-8">
          <div className="mx-auto w-24 h-24 rounded-full bg-secondary-100 dark:bg-secondary-800 flex items-center justify-center mb-6">
            <FileQuestion className="w-12 h-12 text-secondary-400 dark:text-secondary-500" />
          </div>
          <h1 className="text-4xl font-bold text-secondary-900 dark:text-white mb-2">404</h1>
          <h2 className="text-2xl font-semibold text-secondary-700 dark:text-secondary-300 mb-4">Page Not Found</h2>
          <p className="text-secondary-600 dark:text-secondary-400 mb-8 max-w-md mx-auto">
            Sorry, we couldn't find the page you're looking for. It might have been moved, deleted, or never existed.
          </p>
        </div>

        <div className="space-y-4">
          <Button onClick={() => window.location.href = '/dashboard'} className="w-full sm:w-auto">
            <Home className="w-4 h-4 mr-2" />
            Go to Dashboard
          </Button>
          <Button variant="outline" onClick={() => window.history.back()} className="w-full sm:w-auto">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Go Back
          </Button>
        </div>

        <div className="mt-10 pt-8 border-t border-secondary-200 dark:border-secondary-700">
          <p className="text-secondary-500 dark:text-secondary-400 text-sm mb-4">Popular Pages</p>
          <div className="grid grid-cols-2 gap-3">
            <Link to="/dashboard" className="p-3 rounded-lg border border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800 transition-colors text-left">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 text-primary-600 dark:text-primary-400">📊</span>
                <span className="font-medium text-secondary-900 dark:text-white">Dashboard</span>
              </div>
              <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">Overview & metrics</p>
            </Link>
            <Link to="/scenarios" className="p-3 rounded-lg border border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800 transition-colors text-left">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 text-primary-600 dark:text-primary-400">🧪</span>
                <span className="font-medium text-secondary-900 dark:text-white">Scenarios</span>
              </div>
              <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">Manage scenarios</p>
            </Link>
            <Link to="/simulation" className="p-3 rounded-lg border border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800 transition-colors text-left">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 text-primary-600 dark:text-primary-400">▶️</span>
                <span className="font-medium text-secondary-900 dark:text-white">Simulation</span>
              </div>
              <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">Run simulations</p>
            </Link>
            <Link to="/runs" className="p-3 rounded-lg border border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800 transition-colors text-left">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 text-primary-600 dark:text-primary-400">📊</span>
                <span className="font-medium text-secondary-900 dark:text-white">Runs</span>
              </div>
              <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">Run history</p>
            </Link>
          </div>
        </div>

        <div className="mt-8 text-center">
          <p className="text-secondary-500 dark:text-secondary-400 text-sm">
            Still can't find what you're looking for?
            <a href="mailto:support@rift.dev" className="underline hover:no-underline text-primary-600 dark:text-primary-400 ml-1">
              Contact support
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}