import { useEffect, useRef, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, apiErrorMessage } from '@/services/api'
import { readEvents, type AppEvent } from '@/utils/event-log'
import { SOURCE_DEFS, MQTT_NOTE, type SourceProbe } from '@/utils/sources'

const POLL_MS = 5000

export function Runs() {
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null)
  const [alerts, setAlerts] = useState<Array<{ rule: string; firing: boolean; reason: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [billing, setBilling] = useState<{ configured: boolean; provider: string } | null>(null)
  const [entitlement, setEntitlement] = useState<unknown>(null)
  const [entitlementError, setEntitlementError] = useState<string | null>(null)
  const [notifState, setNotifState] = useState<string>(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission)
  const [events, setEvents] = useState<AppEvent[]>(() => readEvents())
  const [paused, setPaused] = useState(false)
  const [probes, setProbes] = useState<Record<string, SourceProbe>>({})
  const [probing, setProbing] = useState(false)
  const seenFiring = useRef<Set<string>>(new Set())
  const pausedRef = useRef(false)
  pausedRef.current = paused

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
    if (!paused) load()
    api.getBillingStatus()
      .then((b) => { if (!cancelled) setBilling(b) })
      .catch(() => { if (!cancelled) setBilling(null) })
    const timer = window.setInterval(() => {
      if (!pausedRef.current) load()
    }, POLL_MS)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [paused])

  const probeAll = async () => {
    setProbing(true)
    const out: Record<string, SourceProbe> = {}
    const checks: Array<[string, () => Promise<unknown>]> = [
      ['health', () => api.getHealth()],
      ['meta', () => api.getMeta()],
      ['demo', () => api.runDemo({})],
      ['twin-demo', () => api.getTwinDemo(0)],
      ['twin-evidence', () => api.getTwinEvidence()],
      ['monitor', () => api.getMonitor()],
      ['reviews', () => api.listReviews()],
    ]
    for (const [key, fn] of checks) {
      const t0 = performance.now()
      try {
        await fn()
        out[key] = { key, ok: true, latencyMs: Math.round(performance.now() - t0), checkedAt: new Date().toISOString(), detail: null }
      } catch (e) {
        out[key] = { key, ok: false, latencyMs: Math.round(performance.now() - t0), checkedAt: new Date().toISOString(), detail: apiErrorMessage(e, 'probe failed') }
      }
      setProbes({ ...out })
    }
    setProbing(false)
  }

  const checkEntitlement = async () => {
    setEntitlement(null)
    setEntitlementError(null)
    try {
      setEntitlement(await api.getEntitlement())
    } catch (e) {
      setEntitlementError(apiErrorMessage(e, 'Entitlement check failed.'))
    }
  }

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
        <div className="mt-2 flex gap-2">
          <Button variant={paused ? 'outline' : 'secondary'} size="sm" onClick={() => setPaused(!paused)}>
            {paused ? 'Resume polling (end outage drill)' : 'Pause polling (outage drill)'}
          </Button>
        </div>
        {paused && (
          <p className="text-sm text-warning-600 dark:text-warning-400 mt-2" role="status">
            Outage drill active: subscriber polling paused. Counters freeze; on resume the next poll catches up. No data is fabricated while paused.
          </p>
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
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Per-route traffic (live counters)</h2>
                {(() => {
                  const routes = (snapshot?.routes || {}) as Record<string, { requests: number; failures: number; p50_ms: number | null; p95_ms: number | null }>
                  const entries = Object.entries(routes)
                  if (entries.length === 0) return <p className="text-sm text-secondary-500">No requests recorded yet in this server process.</p>
                  return (
                    <div className="table-container">
                      <table className="table">
                        <thead><tr><th>Route</th><th>Requests</th><th>Failures</th><th>p50 ms</th><th>p95 ms</th></tr></thead>
                        <tbody>
                          {entries.map(([route, s]) => (
                            <tr key={route}>
                              <td className="font-mono text-xs">{route}</td>
                              <td className="font-mono">{s.requests}</td>
                              <td className="font-mono">{s.failures}</td>
                              <td className="font-mono">{s.p50_ms === null ? '—' : s.p50_ms.toFixed(1)}</td>
                              <td className="font-mono">{s.p95_ms === null ? '—' : s.p95_ms.toFixed(1)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                })()}
              </div>
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Source registry + heartbeat</h2>
                <p className="text-sm text-secondary-500 mb-2">
                  Every upstream this UI consumes, with on-demand heartbeat (latency + ok/fail measured live here).
                  Freshness and reliability below are client-observed at probe time — not server telemetry. Experiments are write-gated (no safe probe exists), shown as such.
                </p>
                <div className="mb-3">
                  <Button variant="outline" size="sm" onClick={probeAll} disabled={probing}>
                    {probing ? 'Probing…' : 'Probe all sources'}
                  </Button>
                </div>
                <div className="table-container mb-2">
                  <table className="table">
                    <thead><tr><th>Source</th><th>Target</th><th>Auth</th><th>Heartbeat</th><th>Freshness</th><th>Quality notes</th></tr></thead>
                    <tbody>
                      {SOURCE_DEFS.map((s) => {
                        const p = probes[s.key]
                        return (
                          <tr key={s.key}>
                            <td className="font-medium text-sm">{s.label}<br /><span className="font-mono text-xs text-secondary-500">{s.kind}</span></td>
                            <td className="font-mono text-xs">{s.target}</td>
                            <td className="text-xs">{s.auth}</td>
                            <td>
                              {!p && <span className="text-xs text-secondary-500">not probed</span>}
                              {p && <Badge variant={p.ok ? 'success' : 'error'}>{p.ok ? `ok · ${p.latencyMs} ms` : 'FAIL'}</Badge>}
                            </td>
                            <td className="font-mono text-xs">{p?.checkedAt ? new Date(p.checkedAt).toLocaleTimeString() : '—'}</td>
                            <td className="text-xs max-w-xs">{p?.detail || s.qualityNotes}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-secondary-500">{MQTT_NOTE}</p>
              </div>
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Usage metering (live counters)</h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm mb-3">
                  {[
                    ['Requests', (snapshot?.requests_total as number | undefined) ?? '—'],
                    ['Failure rate', typeof snapshot?.failure_rate === 'number' ? (snapshot.failure_rate as number).toFixed(3) : '—'],
                    ['Predictions', (snapshot?.prediction_count as number | undefined) ?? '—'],
                    ['Uptime (s)', typeof snapshot?.uptime_s === 'number' ? Math.round(snapshot.uptime_s as number) : '—'],
                  ].map(([label, value]) => (
                    <div key={label} className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                      <p className="text-xs text-secondary-500">{label}</p>
                      <p className="font-mono font-medium">{value}</p>
                    </div>
                  ))}
                </div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Billing</h2>
                <p className="text-sm text-secondary-500 mb-2">
                  Provider <span className="font-mono">{billing?.provider || '…'}</span> · {billing ? (billing.configured ? 'configured' : 'not configured (disabled by default)') : 'loading…'}
                </p>
                <div className="flex gap-2 mb-2">
                  <Button variant="outline" size="sm" onClick={checkEntitlement}>Check entitlement</Button>
                </div>
                {entitlementError && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{entitlementError}</p>}
                {entitlement !== null && !entitlementError && (
                  <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(entitlement, null, 2)}</pre>
                )}
                <p className="text-xs text-secondary-500 mt-2">Subscriptions and checkout require operator credentials — the server answers 503 without them. No payment flow is faked here.</p>
              </div>
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Raw snapshot</h2>
                <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(snapshot, null, 2)}</pre>
              </div>
              <div>
                <h2 className="font-medium text-secondary-900 dark:text-white mb-2">Event history (this browser only)</h2>
                {events.length === 0 && <p className="text-sm text-secondary-500">No local events yet — runs, approvals, and sweeps are recorded here.</p>}
                {events.length > 0 && (
                  <ul className="space-y-1 text-sm max-h-64 overflow-y-auto">
                    {events.map((e, i) => (
                      <li key={`${e.time}-${i}`} className="flex gap-2 items-center">
                        <span className="font-mono text-xs text-secondary-500 whitespace-nowrap">{new Date(e.time).toLocaleTimeString()}</span>
                        <Badge variant="secondary">{e.kind}</Badge>
                        <span className="text-secondary-700 dark:text-secondary-300">{e.detail}</span>
                        {e.params && (
                          <button
                            className="text-primary-600 hover:underline text-sm whitespace-nowrap"
                            onClick={() => {
                              try {
                                localStorage.setItem('rift-replay-params', JSON.stringify(e.params))
                              } catch {
                                /* storage unavailable */
                              }
                              window.location.href = '/simulation'
                            }}
                          >
                            Load in Simulation
                          </button>
                        )}
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
