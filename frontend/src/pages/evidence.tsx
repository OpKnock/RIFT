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
        <div className="p-6 space-y-3">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Model lifecycle (from bundle)</h2>
          {(() => {
            const meta = (data as Record<string, unknown> | null)?.meta as Record<string, unknown> | undefined
            const model = meta?.model as Record<string, unknown> | undefined
            if (!data) return <p className="text-sm text-secondary-500">Loading…</p>
            if (!model) return <p className="text-sm text-secondary-500">No model block in this bundle.</p>
            const stages = ['research', 'candidate', 'validated', 'approved', 'deployed']
            const current = String(model.status || 'research')
            const currentIdx = Math.max(0, stages.indexOf(current))
            return (
              <div className="space-y-3 text-sm">
                <div className="flex flex-wrap items-center gap-1">
                  {stages.map((s, i) => (
                    <span key={s} className="flex items-center gap-1">
                      <Badge variant={i < currentIdx ? 'success' : i === currentIdx ? 'warning' : 'secondary'}>{s}</Badge>
                      {i < stages.length - 1 && <span className="text-secondary-400">→</span>}
                    </span>
                  ))}
                </div>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div><dt className="text-secondary-500">Model</dt><dd className="font-mono">{String(model.model_id || '—')}</dd></div>
                  <div><dt className="text-secondary-500">Deployment gate</dt><dd className="font-mono">{String(model.deployment_gate || '—')}</dd></div>
                  <div><dt className="text-secondary-500">Weights digest</dt><dd className="font-mono text-xs break-all">{String(model.weights_digest || '—')}</dd></div>
                  <div><dt className="text-secondary-500">Datasets</dt><dd className="font-mono text-xs">{Array.isArray(model.dataset_versions) ? model.dataset_versions.join(', ') : '—'}</dd></div>
                </dl>
                <p className="text-xs text-secondary-500">Promotion and rollback require evidence plus a human approver and happen operator-side — no promotion endpoint exists, so none is faked here. Drift detection runs in the evaluation pipeline; continuous real-world validation remains an external gate.</p>
              </div>
            )
          })()}
        </div>
      </Card>

      <Card>
        <div className="p-6 space-y-3">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Noise stress by severity (from bundle)</h2>
          <p className="text-sm text-secondary-500">Sensor-noise magnitudes vs agreement and uncertainty — the served severity ladder, not a client invention.</p>
          {(() => {
            const rows = (data as Record<string, unknown> | null)?.stress as { rows?: Array<{ noise_magnitude: number; days: number; agreement: number | null; mean_uncertainty: number | null }> } | undefined
            if (!data) return <p className="text-sm text-secondary-500">Loading…</p>
            if (!rows?.rows || rows.rows.length === 0) return <p className="text-sm text-secondary-500">No stress rows in this bundle.</p>
            return (
              <div className="table-container">
                <table className="table">
                  <thead><tr><th>Noise magnitude</th><th>Days</th><th>Agreement</th><th>Mean uncertainty</th></tr></thead>
                  <tbody>
                    {rows.rows.map((r, i) => (
                      <tr key={i}>
                        <td className="font-mono">{r.noise_magnitude}</td>
                        <td className="font-mono">{r.days}</td>
                        <td className="font-mono">{r.agreement === null ? '—' : r.agreement.toFixed(3)}</td>
                        <td className="font-mono">{r.mean_uncertainty === null ? '—' : r.mean_uncertainty.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          })()}
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
