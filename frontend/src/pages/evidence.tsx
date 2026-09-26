import { useEffect, useRef, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage } from '@/services/api'

interface TwinSnapshot {
  day_index?: number
  patient_id?: string
  risk?: {
    risk?: number
    event_predicted?: boolean
    calibration?: string
    model?: string
    uncertainty?: number
    input_quality?: number
    measurement_jitter?: number
    interval?: [number, number]
  }
  guardian?: { display_allowed?: boolean; action?: string }
  provenance?: Record<string, unknown>
  meta?: { dataset?: string; safety?: string; engine_version?: string }
  model_notes?: string
  state?: { data_quality?: number; stale_days?: number; provenance?: string }
  trajectories?: Array<{ policy: Record<string, number>; path: Array<{ day: number; risk: number }> }>
}

interface StoredSnapshot {
  id: string
  day: number
  time: string
  risk: number | null
  event: boolean | null
  guardian: string
  quality: number | null
  predictionId: string | null
}

interface ScanRow {
  day: number
  risk: number | null
  event: boolean | null
  guardian: string
  delta: number | null
  flagged: boolean
}

const SNAPS_KEY = 'rift-twin-snapshots'

function loadSnaps(): StoredSnapshot[] {
  try {
    const raw = localStorage.getItem(SNAPS_KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function Evidence() {
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [day, setDay] = useState(5)
  const [twin, setTwin] = useState<TwinSnapshot | null>(null)
  const [twinLoading, setTwinLoading] = useState(false)
  const [twinError, setTwinError] = useState<string | null>(null)
  const [snaps, setSnaps] = useState<StoredSnapshot[]>(() => loadSnaps())
  const [snapMsg, setSnapMsg] = useState<string | null>(null)
  const [compareIds, setCompareIds] = useState<[string, string]>(['', ''])
  const [scan, setScan] = useState<ScanRow[]>([])
  const [scanning, setScanning] = useState(false)
  const scanCancel = useRef(false)

  useEffect(() => () => { scanCancel.current = true }, [])

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

  const persistSnaps = (next: StoredSnapshot[]) => {
    setSnaps(next)
    try {
      localStorage.setItem(SNAPS_KEY, JSON.stringify(next))
    } catch {
      /* storage unavailable */
    }
  }

  const captureSnapshot = () => {
    if (!twin) return
    const entry: StoredSnapshot = {
      id: `${day}@${new Date().toISOString()}`,
      day,
      time: new Date().toISOString(),
      risk: typeof twin.risk?.risk === 'number' ? twin.risk.risk : null,
      event: typeof twin.risk?.event_predicted === 'boolean' ? twin.risk.event_predicted : null,
      guardian: twin.guardian?.action || (twin.guardian?.display_allowed ? 'ALLOW' : 'WITHHOLD'),
      quality: typeof twin.risk?.input_quality === 'number' ? twin.risk.input_quality : null,
      predictionId: typeof twin.provenance?.prediction_id === 'string' ? (twin.provenance.prediction_id as string) : null,
    }
    persistSnaps([entry, ...snaps].slice(0, 30))
    setSnapMsg(`Captured day ${day}. Snapshots live only in this browser.`)
  }

  const deleteSnap = (id: string) => {
    persistSnaps(snaps.filter((s) => s.id !== id))
  }

  const exportSnaps = () => {
    const blob = new Blob([JSON.stringify(snaps, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'rift-twin-snapshots.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const importSnaps = async (file: File | undefined) => {
    if (!file) return
    setSnapMsg(null)
    try {
      const parsed: unknown = JSON.parse(await file.text())
      const list = Array.isArray(parsed) ? parsed : [parsed]
      const valid: StoredSnapshot[] = []
      for (const item of list) {
        if (item && typeof item === 'object' && typeof (item as Record<string, unknown>).day === 'number') {
          const r = item as Record<string, unknown>
          valid.push({
            id: `imported@${new Date().toISOString()}@${valid.length}`,
            day: r.day as number,
            time: typeof r.time === 'string' ? r.time : new Date().toISOString(),
            risk: typeof r.risk === 'number' ? r.risk : null,
            event: typeof r.event === 'boolean' ? r.event : null,
            guardian: typeof r.guardian === 'string' ? r.guardian : 'unknown',
            quality: typeof r.quality === 'number' ? r.quality : null,
            predictionId: typeof r.predictionId === 'string' ? r.predictionId : null,
          })
        }
      }
      if (valid.length === 0) {
        setSnapMsg('Import rejected: no entries with a numeric day field.')
        return
      }
      persistSnaps([...valid.reverse(), ...snaps].slice(0, 30))
      setSnapMsg(`Imported ${valid.length} snapshot(s). Shape-checked (day + optional fields) on import.`)
    } catch {
      setSnapMsg('Import rejected: file is not valid JSON.')
    }
  }

  const runDivergenceScan = async () => {
    if (scanning) return
    setScanning(true)
    scanCancel.current = false
    const rows: ScanRow[] = []
    let prev: number | null = null
    for (let d = 0; d <= 13; d++) {
      if (scanCancel.current) break
      try {
        const body = (await api.getTwinDemo(d)) as TwinSnapshot
        const risk = typeof body.risk?.risk === 'number' ? body.risk.risk : null
        const delta = risk !== null && prev !== null ? risk - prev : null
        rows.push({
          day: d,
          risk,
          event: typeof body.risk?.event_predicted === 'boolean' ? body.risk.event_predicted : null,
          guardian: body.guardian?.action || (body.guardian?.display_allowed ? 'ALLOW' : 'WITHHOLD'),
          delta,
          flagged: delta !== null && Math.abs(delta) > 0.1,
        })
        if (risk !== null) prev = risk
      } catch {
        rows.push({ day: d, risk: null, event: null, guardian: 'error', delta: null, flagged: false })
      }
      setScan([...rows])
    }
    setScanning(false)
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
            <div className="space-y-4">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div><dt className="text-secondary-500">24h risk</dt><dd className="font-mono text-lg">{typeof twin.risk?.risk === 'number' ? twin.risk.risk.toFixed(3) : '—'}</dd></div>
                <div><dt className="text-secondary-500">Event predicted</dt><dd className="font-mono">{String(twin.risk?.event_predicted ?? '—')}</dd></div>
                <div><dt className="text-secondary-500">Guardian</dt><dd><Badge variant={twin.guardian?.display_allowed ? 'success' : 'error'}>{twin.guardian?.action || (twin.guardian?.display_allowed ? 'ALLOW' : 'WITHHOLD')}</Badge></dd></div>
                <div><dt className="text-secondary-500">Calibration</dt><dd className="font-mono text-xs">{twin.risk?.calibration || '—'}</dd></div>
                <div><dt className="text-secondary-500">Patient</dt><dd className="font-mono text-xs">{twin.patient_id || '—'}</dd></div>
                <div><dt className="text-secondary-500">Freshness / confidence</dt><dd className="font-mono text-xs">quality {twin.risk?.input_quality ?? '—'} · jitter {typeof twin.risk?.measurement_jitter === 'number' ? twin.risk.measurement_jitter.toFixed(3) : '—'} · uncertainty {typeof twin.risk?.uncertainty === 'number' ? twin.risk.uncertainty.toFixed(3) : '—'} · stale {twin.state?.stale_days ?? '—'}d</dd></div>
                <div className="sm:col-span-2"><dt className="text-secondary-500">Dataset (source)</dt><dd className="text-xs">{twin.meta?.dataset || '—'}</dd></div>
                <div className="sm:col-span-2"><dt className="text-secondary-500">Safety</dt><dd className="text-xs">{twin.meta?.safety || '—'}</dd></div>
                <div className="sm:col-span-2"><dt className="text-secondary-500">Provenance</dt><dd className="font-mono text-xs break-all">pred {String(twin.provenance?.prediction_id || '—').slice(0, 16)}… · model {String(twin.provenance?.model_id || '—')} · weights {String(twin.provenance?.weights_digest || '—').slice(0, 16)}… · {String(twin.provenance?.calibration_id || '')}</dd></div>
                <div className="sm:col-span-2"><dt className="text-secondary-500">Transition model</dt><dd className="text-xs">{twin.model_notes || '—'}</dd></div>
              </dl>

              {twin.trajectories && twin.trajectories.length > 0 && (
                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2 text-sm">Predicted trajectories (per policy)</h3>
                  <div className="table-container">
                    <table className="table">
                      <thead><tr><th>Policy</th><th>Day → risk path</th></tr></thead>
                      <tbody>
                        {twin.trajectories.slice(0, 6).map((t, i) => (
                          <tr key={i}>
                            <td className="font-mono text-xs">{JSON.stringify(t.policy)}</td>
                            <td className="font-mono text-xs">{t.path.map((p) => `${p.day}:${p.risk.toFixed(2)}`).join(' → ')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={captureSnapshot} disabled={twinLoading}>Capture snapshot (day {day})</Button>
                <Button variant="outline" size="sm" onClick={exportSnaps} disabled={snaps.length === 0}>Export snapshots</Button>
                <label className="text-sm px-3 py-1.5 rounded-lg border border-secondary-300 dark:border-secondary-600 cursor-pointer hover:bg-secondary-100 dark:hover:bg-secondary-800">
                  Import snapshots
                  <input type="file" accept="application/json" className="hidden" onChange={(e) => { importSnaps(e.target.files?.[0]); e.target.value = '' }} />
                </label>
              </div>
              {snapMsg && <p className="text-sm text-secondary-600 dark:text-secondary-400">{snapMsg}</p>}
              {snaps.length > 0 && (
                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2 text-sm">Snapshots (this browser only)</h3>
                  <ul className="space-y-1 text-sm">
                    {snaps.map((s) => (
                      <li key={s.id} className="flex items-center justify-between gap-2 font-mono text-xs p-2 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                        <span>day {s.day} · risk {s.risk === null ? '—' : s.risk.toFixed(3)} · {s.guardian}</span>
                        <button className="text-error-600 hover:underline" onClick={() => deleteSnap(s.id)}>Delete</button>
                      </li>
                    ))}
                  </ul>
                  {snaps.length >= 2 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                      {[0, 1].map((slot) => (
                        <div key={slot}>
                          <label className="label" htmlFor={`twin-compare-${slot}`}>Compare slot {slot === 0 ? 'A' : 'B'}</label>
                          <select id={`twin-compare-${slot}`} value={compareIds[slot]} onChange={(e) => setCompareIds(slot === 0 ? [e.target.value, compareIds[1]] : [compareIds[0], e.target.value])} className="input">
                            <option value="">—</option>
                            {snaps.map((s) => (
                              <option key={s.id} value={s.id}>day {s.day} · {s.risk === null ? '—' : s.risk.toFixed(3)}</option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  )}
                  {compareIds[0] && compareIds[1] && (() => {
                    const a = snaps.find((s) => s.id === compareIds[0])
                    const b = snaps.find((s) => s.id === compareIds[1])
                    if (!a || !b) return null
                    return (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm mt-3">
                        {[['A', a], ['B', b]].map(([label, s]) => {
                          const snap = s as StoredSnapshot
                          return (
                            <div key={label as string} className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 space-y-1">
                              <p className="font-medium">Slot {label as string} · day {snap.day}</p>
                              <p className="font-mono text-xs">risk {snap.risk === null ? '—' : snap.risk.toFixed(3)} · {snap.guardian} · quality {snap.quality ?? '—'}</p>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })()}
                </div>
              )}

              <div>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-medium text-secondary-900 dark:text-white text-sm">Divergence scan (days 0–13)</h3>
                  {!scanning && <Button variant="outline" size="sm" onClick={runDivergenceScan}>Run scan</Button>}
                  {scanning && <Button variant="ghost" size="sm" onClick={() => { scanCancel.current = true }}>Stop</Button>}
                </div>
                <p className="text-xs text-secondary-500 mb-2">Sequential live fetches; flags day-over-day risk jumps over 0.10. Cancellable.</p>
                {scan.length > 0 && (
                  <div className="table-container">
                    <table className="table">
                      <thead><tr><th>Day</th><th>Risk</th><th>Δ</th><th>Event</th><th>Guardian</th></tr></thead>
                      <tbody>
                        {scan.map((r) => (
                          <tr key={r.day} className={r.flagged ? 'bg-warning-50 dark:bg-warning-900/20' : ''}>
                            <td className="font-mono">{r.day}</td>
                            <td className="font-mono">{r.risk === null ? '—' : r.risk.toFixed(3)}</td>
                            <td className="font-mono">{r.delta === null ? '—' : (r.delta >= 0 ? '+' : '') + r.delta.toFixed(3)}</td>
                            <td className="font-mono">{r.event === null ? '—' : String(r.event)}</td>
                            <td><Badge variant={r.guardian === 'WITHHOLD' ? 'error' : 'secondary'}>{r.guardian}</Badge></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
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
