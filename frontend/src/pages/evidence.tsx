import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage } from '@/services/api'

interface TwinSnapshot {
  day_index?: number
  risk?: { risk?: number; event_predicted?: boolean; calibration?: string; model?: string; uncertainty?: number }
  guardian?: { display_allowed?: boolean; action?: string }
  provenance?: Record<string, unknown>
  meta?: { dataset?: string; safety?: string; engine_version?: string }
}

export function Evidence() {
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [day, setDay] = useState(5)
  const [twin, setTwin] = useState<TwinSnapshot | null>(null)
  const [twinLoading, setTwinLoading] = useState(false)
  const [twinError, setTwinError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.getTwinEvidence()
      .then((body) => { if (!cancelled) setData(body) })
      .catch((e) => { if (!cancelled) setError(apiErrorMessage(e, 'Failed to load evidence.')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setTwinLoading(true)
    setTwinError(null)
    api.getTwinDemo(day)
      .then((body) => { if (!cancelled) setTwin(body as TwinSnapshot) })
      .catch((e) => { if (!cancelled) setTwinError(apiErrorMessage(e, 'Failed to load twin snapshot.')) })
      .finally(() => { if (!cancelled) setTwinLoading(false) })
    return () => { cancelled = true }
  }, [day])

  const download = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'rift-evidence.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Evidence</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">Live bundle from <code className="font-mono text-sm">GET /api/twin/evidence</code>. Synthetic demo data — not clinical validation.</p>
        </div>
        <Button variant="outline" onClick={download} disabled={!data}>Export JSON</Button>
      </div>

      <Card>
        <div className="p-6 space-y-3">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Patient-twin replay (live)</h2>
          <p className="text-sm text-secondary-500">Snapshots from <code className="font-mono text-sm">GET /api/twin/demo?t=</code> — replay days 0–13, same deterministic series the bundle was built on.</p>
          <label className="block text-sm text-secondary-700 dark:text-secondary-300">
            Replay day: <span className="font-mono font-medium">{day}</span>
            <input type="range" min={0} max={13} value={day} onChange={(e) => setDay(Number(e.target.value))} className="w-full mt-1" aria-label="Replay day" />
          </label>
          {twinLoading && <p className="text-sm text-secondary-500">Loading day {day}…</p>}
          {twinError && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{twinError}</p>}
          {!twinLoading && !twinError && twin && (
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div><dt className="text-secondary-500">24h risk</dt><dd className="font-mono text-lg">{typeof twin.risk?.risk === 'number' ? twin.risk.risk.toFixed(3) : '—'}</dd></div>
              <div><dt className="text-secondary-500">Event predicted</dt><dd className="font-mono">{String(twin.risk?.event_predicted ?? '—')}</dd></div>
              <div><dt className="text-secondary-500">Guardian</dt><dd><Badge variant={twin.guardian?.display_allowed ? 'success' : 'error'}>{twin.guardian?.action || (twin.guardian?.display_allowed ? 'ALLOW' : 'WITHHOLD')}</Badge></dd></div>
              <div><dt className="text-secondary-500">Calibration</dt><dd className="font-mono text-xs">{twin.risk?.calibration || '—'}</dd></div>
              <div className="sm:col-span-2"><dt className="text-secondary-500">Dataset (source)</dt><dd className="text-xs">{twin.meta?.dataset || '—'}</dd></div>
              <div className="sm:col-span-2"><dt className="text-secondary-500">Safety</dt><dd className="text-xs">{twin.meta?.safety || '—'}</dd></div>
            </dl>
          )}
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-3">Frozen evidence bundle</h2>
          {loading && <p className="text-sm text-secondary-500">Loading evidence…</p>}
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {!loading && !error && <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(data, null, 2)}</pre>}
        </div>
      </Card>
    </div>
  )
}
