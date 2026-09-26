'use client'

import { useState, useEffect } from 'react'
import { Cookie, ChevronDown, ChevronUp, Shield, Palette } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface CookiePreferences {
  essential: boolean
  preferences: boolean
}

const COOKIE_CONSENT_KEY = 'rift_cookie_consent'
const COOKIE_PREFERENCES_KEY = 'rift_cookie_preferences'

const defaultPreferences: CookiePreferences = {
  essential: true,
  preferences: true,
}

export function CookieConsentBanner() {
  const [showBanner, setShowBanner] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [preferences, setPreferences] = useState<CookiePreferences>(defaultPreferences)

  useEffect(() => {
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY)
    setShowBanner(consent !== 'accepted' && consent !== 'rejected')
    const raw = localStorage.getItem(COOKIE_PREFERENCES_KEY)
    if (raw) {
      try {
        setPreferences(JSON.parse(raw))
      } catch {
        setPreferences(defaultPreferences)
      }
    }
  }, [])

  const persist = (prefs: CookiePreferences, consent: string) => {
    localStorage.setItem(COOKIE_PREFERENCES_KEY, JSON.stringify(prefs))
    localStorage.setItem(COOKIE_CONSENT_KEY, consent)
    setPreferences(prefs)
    setShowBanner(false)
    setShowDetails(false)
  }

  const acceptAll = () => persist({ essential: true, preferences: true }, 'accepted')
  const rejectOptional = () => persist({ essential: true, preferences: false }, 'rejected')
  const savePreferences = () => persist(preferences, 'accepted')

  if (!showBanner && !showDetails) {
    return (
      <button
        onClick={() => setShowDetails(true)}
        className="fixed bottom-4 right-4 z-40 p-2 rounded-full bg-white dark:bg-secondary-900 shadow-lg border border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800 transition-all"
        aria-label="Cookie preferences"
      >
        <Cookie className="w-5 h-5 text-secondary-600 dark:text-secondary-400" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 md:bottom-6 md:left-auto md:right-6 md:w-96 animate-slide-up">
      <div className="bg-white dark:bg-secondary-900 rounded-xl border border-secondary-200 dark:border-secondary-700 shadow-xl p-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex-shrink-0">
            <Cookie className="w-5 h-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-secondary-900 dark:text-white mb-1">Cookie Preferences</h3>
            <p className="text-sm text-secondary-600 dark:text-secondary-400">
              Essential cookies keep the site working. Optional preference cookies remember settings like theme.
            </p>
          </div>
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex-shrink-0 p-1 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors"
            aria-label={showDetails ? 'Show less' : 'Show details'}
          >
            {showDetails ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>

        {showDetails && (
          <div className="mt-4 pt-4 border-t border-secondary-200 dark:border-secondary-700 space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Shield className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                  <span className="font-medium text-secondary-900 dark:text-white">Essential Cookies</span>
                </div>
                <span className="text-xs text-secondary-500 dark:text-secondary-400">Always Active</span>
              </div>
              <p className="text-xs text-secondary-500 dark:text-secondary-400">
                Authentication, security, basic functionality. Cannot be disabled.
              </p>
            </div>
            <div>
              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-2">
                  <Palette className="w-5 h-5 text-secondary-600 dark:text-secondary-400" />
                  <span className="font-medium text-secondary-900 dark:text-white">Preference Cookies</span>
                </div>
                <input
                  type="checkbox"
                  checked={preferences.preferences}
                  onChange={(e) => setPreferences((prev) => ({ ...prev, preferences: e.target.checked }))}
                  className="w-5 h-5 rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                />
              </label>
              <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1 ml-7">
                Remembers theme, sidebar state, view mode.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={savePreferences} className="flex-1">
                Save Choices
              </Button>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 pt-4 mt-4 border-t border-secondary-200 dark:border-secondary-700">
          <Button variant="secondary" onClick={rejectOptional} className="flex-1">
            Reject Optional
          </Button>
          <Button onClick={acceptAll} className="flex-1">
            Accept All
          </Button>
        </div>
      </div>
    </div>
  )
}
