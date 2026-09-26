import { useEffect, useState } from 'react'
import { User, Shield, Bell, Palette, Key, Globe, Database, Moon, Sun, Monitor, Save } from 'lucide-react'
import { cn } from '@/utils/cn'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useTheme } from '@/components/providers/theme-provider'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { readUtm } from '@/hooks/use-utm'
import { api, apiErrorMessage, type HealthStatus, type EngineMeta } from '@/services/api'

const PROFILE_KEY = 'rift-profile-name'

export function Settings() {
  const { resolvedTheme, setTheme } = useTheme()
  const [activeTab, setActiveTab] = useState('profile')
  const [displayName, setDisplayName] = useState(() => {
    try {
      return localStorage.getItem(PROFILE_KEY) || ''
    } catch {
      return ''
    }
  })
  const [savedTick, setSavedTick] = useState(false)
  const [tokenInput, setTokenInput] = useState('')
  const [hasToken, setHasToken] = useState(() => api.getToken() !== null)
  const [confirmClear, setConfirmClear] = useState(false)
  const [utm] = useState(() => readUtm())
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [meta, setMeta] = useState<EngineMeta | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [pollAlerts, setPollAlerts] = useState(() => {
    try {
      return localStorage.getItem('rift-poll-alerts') !== 'off'
    } catch {
      return true
    }
  })

  useEffect(() => {
    let cancelled = false
    Promise.all([api.getHealth(), api.getMeta()])
      .then(([h, m]) => {
        if (cancelled) return
        setHealth(h)
        setMeta(m)
      })
      .catch((e) => { if (!cancelled) setStatusError(apiErrorMessage(e, 'Engine unreachable.')) })
    return () => { cancelled = true }
  }, [])

  const saveProfile = () => {
    try {
      if (displayName.trim()) {
        localStorage.setItem(PROFILE_KEY, displayName.trim())
      } else {
        localStorage.removeItem(PROFILE_KEY)
      }
      setSavedTick(true)
      window.setTimeout(() => setSavedTick(false), 2000)
    } catch {
      /* storage unavailable */
    }
  }

  const saveToken = () => {
    if (!tokenInput.trim()) return
    api.setToken(tokenInput.trim())
    setTokenInput('')
    setHasToken(true)
  }

  const clearToken = () => {
    api.clearToken()
    setHasToken(false)
  }

  const togglePollAlerts = (on: boolean) => {
    setPollAlerts(on)
    try {
      localStorage.setItem('rift-poll-alerts', on ? 'on' : 'off')
    } catch {
      /* storage unavailable */
    }
  }

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'api', label: 'API Token', icon: Key },
    { id: 'integrations', label: 'Integrations', icon: Globe },
    { id: 'data', label: 'Data & Privacy', icon: Database },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-6 px-4 sm:px-6 lg:px-8">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Settings</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">Local preferences plus live server security posture. Nothing here pretends to manage server-side accounts.</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4 md:grid-cols-7 gap-1 p-1 bg-secondary-100 dark:bg-secondary-800 rounded-lg">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="flex items-center gap-2 px-3 py-2">
              <tab.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="profile" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Display name (this browser)</h2>
              <p className="text-sm text-secondary-500">Used to pre-fill reviewer IDs on approvals. Stored only here — the server never sees it except inside review payloads you submit.</p>
              <Input label="Display name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. operator-1" />
              <div className="flex items-center gap-3">
                <Button onClick={saveProfile}><Save className="w-4 h-4 mr-2" />Save{savedTick ? 'd ✓' : ''}</Button>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Server security posture (live)</h2>
              {statusError && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{statusError}</p>}
              {health && meta && !statusError && (
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div><dt className="text-secondary-500">Auth mode</dt><dd className="font-mono">{meta.auth.service_token_configured ? 'service-token (bearer-gated)' : 'open dev mode (no gate)'}</dd></div>
                  <div><dt className="text-secondary-500">Persistence</dt><dd className="font-mono">{health.persistence.configured ? 'configured' : 'not configured'}</dd></div>
                  <div><dt className="text-secondary-500">Billing</dt><dd className="font-mono">{health.billing.configured ? 'configured' : 'not configured'} ({health.billing.provider})</dd></div>
                  <div><dt className="text-secondary-500">Engine</dt><dd className="font-mono">v{health.version} · {health.quantum_backend}</dd></div>
                </dl>
              )}
              <div className="text-sm text-secondary-500 space-y-1 pt-2 border-t border-secondary-100 dark:border-secondary-800">
                <p>MFA, secret rotation, SSO, and per-user accounts are operator duties — this UI cannot manage them because the server exposes no such endpoints.</p>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Firing-alert notifications</h2>
              <p className="text-sm text-secondary-500">Controls the browser notifications offered on the Operations page. Stored locally; nothing is sent anywhere.</p>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-secondary-900 dark:text-white">Notify on firing alerts</p>
                  <p className="text-sm text-secondary-500 dark:text-secondary-400">Requires browser permission, granted on the Operations page.</p>
                </div>
                <Switch checked={pollAlerts} onChange={() => togglePollAlerts(!pollAlerts)} aria-label="Notify on firing alerts" />
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Theme</h2>
              <div className="grid grid-cols-3 gap-4">
                {(['light', 'dark', 'system'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTheme(t)}
                    aria-pressed={(resolvedTheme === t) || (t === 'system' && resolvedTheme !== 'light' && resolvedTheme !== 'dark')}
                    className={cn(
                      'p-4 rounded-xl border-2 transition-all',
                      'hover:border-primary-400 dark:hover:border-primary-500',
                      'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      'bg-white dark:bg-secondary-900'
                    )}
                  >
                    <div className="text-center">
                      <div className="w-16 h-16 mx-auto rounded-xl mb-3 bg-secondary-100 dark:bg-secondary-800 flex items-center justify-center">
                        {t === 'light' && <Sun className="w-8 h-8 text-yellow-500" />}
                        {t === 'dark' && <Moon className="w-8 h-8 text-blue-400" />}
                        {t === 'system' && <Monitor className="w-8 h-8 text-secondary-600" />}
                      </div>
                      <p className="font-medium text-secondary-900 dark:text-white capitalize">{t}</p>
                    </div>
                  </button>
                ))}
              </div>
              <p className="text-sm text-secondary-500">Currently resolved: <span className="font-mono">{resolvedTheme}</span></p>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="api" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Service-token (this browser)</h2>
              <p className="text-sm text-secondary-500">
                When the operator sets <code className="font-mono">RIFT_API_TOKEN</code> on the server, paste the same token here to call gated endpoints
                (<code className="font-mono">/metrics</code>, <code className="font-mono">/api/ops/monitor</code>). Stored only in this browser. Status: {hasToken ? <Badge variant="success">token set</Badge> : <Badge variant="secondary">no token</Badge>}
              </p>
              <div className="flex gap-3">
                <Input type="password" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} placeholder="Paste service token" aria-label="Service token" />
                <Button onClick={saveToken} disabled={!tokenInput.trim()}>Save</Button>
                {hasToken && <Button variant="outline" onClick={clearToken}>Clear</Button>}
              </div>
              <p className="text-sm text-secondary-500">Server-side keys, rotation, and per-user credentials are operator duties — no management endpoint exists.</p>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="integrations" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Integration status (live)</h2>
              {statusError && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{statusError}</p>}
              {health && !statusError && (
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <Badge variant={health.persistence.configured ? 'success' : 'secondary'}>{health.persistence.configured ? 'connected' : 'not configured'}</Badge>
                    <span>Supabase persistence — enables experiments, runs, and review durability</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Badge variant={health.billing.configured ? 'success' : 'secondary'}>{health.billing.configured ? 'connected' : 'not configured'}</Badge>
                    <span>Billing ({health.billing.provider}) — disabled by default</span>
                  </li>
                </ul>
              )}
              <p className="text-sm text-secondary-500">There is no connect/disconnect action here because the server exposes none — integrations are configured with server environment variables by the operator.</p>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="data" className="mt-6 space-y-6">
          <Card>
            <div className="p-6 space-y-4">
              <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Local data</h2>
              <p className="text-sm text-secondary-500">Export or clear what this browser holds (run history, event log, display name, cookie choices). Server-side data is operator-managed.</p>
              <div className="flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => {
                  const dump: Record<string, unknown> = {}
                  for (const k of ['rift-local-runs', 'rift-event-log', PROFILE_KEY, 'rift_cookie_preferences', 'rift-utm-first-touch']) {
                    try {
                      const raw = localStorage.getItem(k)
                      dump[k] = raw ? JSON.parse(raw) : null
                    } catch {
                      dump[k] = null
                    }
                  }
                  const blob = new Blob([JSON.stringify(dump, null, 2)], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'rift-local-data.json'
                  a.click()
                  URL.revokeObjectURL(url)
                }}>Export local data (JSON)</Button>
                <Button variant="outline" onClick={() => setConfirmClear(true)}>Clear local data</Button>
              </div>
              <p className="text-sm text-secondary-500">
                First-touch attribution: <span className="font-mono">{utm ? `utm_source=${utm.utm_source || '—'} utm_medium=${utm.utm_medium || '—'} utm_campaign=${utm.utm_campaign || '—'}` : 'no UTM parameters recorded'}</span>.
                Captured once from the landing URL, stored only here, included in the export above.
              </p>
              <ConfirmDialog
                open={confirmClear}
                title="Clear local data?"
                body="Removes run history, event log, and display name from this browser. This cannot be undone. Server-side data is unaffected."
                confirmLabel="Clear everything local"
                onCancel={() => setConfirmClear(false)}
                onConfirm={() => {
                  for (const k of ['rift-local-runs', 'rift-event-log', PROFILE_KEY]) {
                    try { localStorage.removeItem(k) } catch { /* ignore */ }
                  }
                  setDisplayName('')
                  setConfirmClear(false)
                }}
              />
              <p className="text-sm text-secondary-500">Account deletion and server-side retention are operator duties — see the deployment docs. Ledger backup procedure: copy the JSONL ledger files (see incident runbook).</p>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
