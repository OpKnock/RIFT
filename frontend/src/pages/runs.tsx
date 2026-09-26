import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage } from '@/services/api'

export function Runs() {
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null)
  const [alerts, setAlerts] = useState<Array<{ rule: string; firing: boolean; reason: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.getMonitor()
      .then((m) => {
        if (cancelled) return
        setSnapshot((m.monitor || {}) as Record<string, unknown>)
        setAlerts(m.alerts || [])
      })
      .catch((e) => { if (!cancelled) setError(apiErrorMessage(e, 'Failed to load monitor.')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Operations</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Live telemetry from <code className="font-mono text-sm">GET /api/ops/monitor</code>. Per-run listing requires persistence (Supabase); without it the server answers 503 — shown honestly, not faked.
        </p>
      </div>
      <Card>
        <div className="p-6">
          {loading && <p className="text-sm text-secondary-500">Loading monitor…</p>}
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {!loading && !error && (
            <div className="space-y-4">
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Alerts</h2>
                {alerts.length === 0 && <p className="text-sm text-secondary-500">No alert rules evaluated.</p>}
                <ul className="space-y-2">
                  {alerts.map((a) => (
                    <li key={a.rule} className="flex items-center gap-2 text-sm">
                      <Badge variant={a.firing ? 'error' : 'secondary'}>{a.firing ? 'FIRING' : 'ok'}</Badge>
                      <span className="font-mono">{a.rule}</span>
                      <span className="text-secondary-500">{a.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Snapshot</h2>
                <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(snapshot, null, 2)}</pre>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
