'use client'

import { Loader2, Sparkles, Database, FlaskConical, Shield } from 'lucide-react'

interface LoadingScreenProps {
  message?: string
  subtitle?: string
  showBrand?: boolean
}

export function LoadingScreen({
  message = 'Loading RIFT...',
  subtitle = 'Initializing counterfactual decision engine',
  showBrand = true,
}: LoadingScreenProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 dark:bg-secondary-950 px-4">
      <div className="max-w-md w-full text-center">
        {showBrand && (
          <div className="mb-8">
            <div className="mx-auto w-20 h-20 rounded-xl bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center mb-6 shadow-lg shadow-primary-500/25">
              <span className="text-2xl font-bold text-white">R</span>
            </div>
            <h1 className="text-3xl font-bold text-secondary-900 dark:text-white mb-2">RIFT</h1>
            <p className="text-secondary-600 dark:text-secondary-400">
              Counterfactual Decision Intelligence
            </p>
          </div>
        )}

        <div className="bg-white dark:bg-secondary-900 rounded-xl border border-secondary-200 dark:border-secondary-700 p-8 shadow-xl">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="relative w-12 h-12">
              <Loader2 className="w-full h-12 text-primary-600 dark:text-primary-400 animate-spin" aria-hidden="true" />
              <Sparkles className="absolute inset-0 w-8 h-8 text-primary-400/50 animate-pulse" aria-hidden="true" />
            </div>
          </div>

          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-2">
            {message}
          </h2>
          <p className="text-secondary-600 dark:text-secondary-400 mb-8">
            {subtitle}
          </p>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <Database className="w-6 h-6 mx-auto text-primary-600 dark:text-primary-400 mb-2" aria-hidden="true" />
              <p className="text-xs text-secondary-600 dark:text-secondary-400">State Vector</p>
            </div>
            <div className="p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <FlaskConical className="w-6 h-6 mx-auto text-primary-600 dark:text-primary-400 mb-2" aria-hidden="true" />
              <p className="text-xs text-secondary-600 dark:text-secondary-400">Counterfactuals</p>
            </div>
            <div className="p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <Shield className="w-6 h-6 mx-auto text-primary-600 dark:text-primary-400 mb-2" aria-hidden="true" />
              <p className="text-xs text-secondary-600 dark:text-secondary-400">Guardian</p>
            </div>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-center gap-4 text-xs text-secondary-500 dark:text-secondary-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary-600 animate-pulse" aria-hidden="true" />
            <span>Initializing core engine</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary-600 animate-pulse" style={{ animationDelay: '200ms' }} aria-hidden="true" />
            <span>Loading scenarios</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary-600 animate-pulse" style={{ animationDelay: '400ms' }} aria-hidden="true" />
            <span>Preparing Guardian</span>
          </span>
        </div>
      </div>
    </div>
  )
}