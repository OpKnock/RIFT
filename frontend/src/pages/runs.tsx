import { useEffect, useRef, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, apiErrorMessage } from '@/services/api'
import { readEvents, type AppEvent } from '@/utils/event-log'

const POLL_MS = 5000

export function Runs() {
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null)
  const [alerts, setAlerts] = useState<Array<{ rule: string; firing: boolean; reason: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notifState, setNotifState] = useState<string>(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)
  const [events, setEvents] = useState<AppEvent[]>(() => readEvents())
  const seenFiring = useRef<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    const load = () => {
      api.getMonitor()
        .then((m) => {
          if (cancelled) return
          setSnapshot((m.monitor || {}) as Record<string, unknown>)
          const next = m.alerts || []
          setAlerts(next)
          for (const a of next) {
            if (a.firing && !seenFiring.current.has(a.rule)) {
              seenFiring.current.add(a.rule)
              if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
                try {
                  new Notification(`RIFT alert: ${a.rule}`, { body: a.reason })
                } catch {
                  /* notification display failed: list below still shows it */
                }
              }
            }
          }
          setEvents(readEvents())
        })
        .catch((e) => { if (!cancelled) setError(apiErrorMessage(e, 'Failed to load monitor.')) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }
    load()
    const timer = window.setInterval(load, POLL_MS)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [])

  const enableNotifications = async () => {
    if (typeof Notification === 'undefined') return
    try {
      const result = await Notification.requestPermission()
      setNotifState(result)
    } catch {
      setNotifState('denied')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Operations</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Live telemetry from <code className="font-mono text-sm">GET /api/ops/monitor</code>, polled every 5 s (client polling — the server offers no push channel).
          Per-run listing requires persistence (Supabase); without it the server answers 503 — shown honestly, not faked.
        </p>
        {notifState !== 'granted' && notifState !== 'unsupported' && (
          <div className="mt-2">
            <Button variant="outline" size="sm" onClick={enableNotifications}>Enable browser notifications for firing alerts</Button>
          </div>
        )}
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
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Event history (this browser only)</h2>
                {events.length === 0 && <p className="text-sm text-secondary-500">No local events yet — runs, approvals, and sweeps are recorded here.</p>}
                {events.length > 0 && (
                  <ul className="space-y-1 text-sm max-h-64 overflow-y-auto">
                    {events.map((e, i) => (
                      <li key={`${e.time}-${i}`} className="flex gap-2">
                        <span className="font-mono text-xs text-secondary-500 whitespace-nowrap">{new Date(e.time).toLocaleTimeString()}</span>
                        <Badge variant="secondary">{e.kind}</Badge>
                        <span className="text-secondary-700 dark:text-secondary-300">{e.detail}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
