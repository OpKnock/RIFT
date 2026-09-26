import { useEffect, useRef, useState } from 'react'
import { Play, Loader2, CheckCircle, XCircle, RotateCcw, ShieldCheck, Copy, Check } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { FutureTree3D } from '@/components/twin-3d'
import { logEvent } from '@/utils/event-log'
import { demoCacheKey, readDemoCache, writeDemoCache, clearDemoCache } from '@/utils/demo-cache'
import { api, apiErrorMessage, type DemoPayload, type EngineMeta } from '@/services/api'

interface RunParams {
  crowd: number
  smoke: number
  capacity: number
  blockB: boolean
}

interface HistoryEntry {
  key: string
  time: string
  params: RunParams
  guardianPassed: boolean
  robustCount: number
  classicalEnergy: number
  classicalMethod: string
}

interface SweepCell {
  crowd: number
  smoke: number
  guardianPassed: boolean | null
  robustCount: number | null
  error: string | null
}

const HISTORY_KEY = 'rift-local-runs'
const HISTORY_MAX = 20

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

function reasonFor(r: DemoPayload['robust'][number]): string {
  const parts: string[] = []
  parts.push(r.feasible_under_all ? 'Feasible under every declared perturbation.' : 'Rejected: infeasible under at least one perturbation.')
  parts.push(`Robustness gap ${r.robustness_gap.toFixed(2)}.`)
  const worst = Object.entries(r.worst_perturbation || {})
  if (worst.length > 0) {
    parts.push(`Worst perturbation: ${worst.map(([k, v]) => `${k}=${v}`).join(', ')}.`)
  }
  return parts.join(' ')
}

const DEFAULTS: RunParams = { crowd: 1200, smoke: 4, capacity: 60, blockB: false }

const TEMPLATES: Array<{ name: string; desc: string; params: RunParams }> = [
  { name: 'Evening rush', desc: 'High occupancy, moderate smoke, exit B open.', params: { crowd: 2500, smoke: 6, capacity: 80, blockB: false } },
  { name: 'Night low occupancy', desc: 'Sparse crowd, light smoke, full capacity.', params: { crowd: 300, smoke: 2, capacity: 60, blockB: false } },
  { name: 'Blocked exit drill', desc: 'Moderate crowd with corridor B closed.', params: { crowd: 1200, smoke: 4, capacity: 60, blockB: true } },
]

export function Simulation() {
  const [meta, setMeta] = useState<EngineMeta | null>(null)
  const [metaError, setMetaError] = useState<string | null>(null)
  const [crowd, setCrowd] = useState('1200')
  const [smoke, setSmoke] = useState('4')
  const [capacity, setCapacity] = useState('60')
  const [blockB, setBlockB] = useState(false)
  const [running, setRunning] = useState(false)
  const [phase, setPhase] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DemoPayload | null>(null)
  const [lastParams, setLastParams] = useState<RunParams | null>(null)
  const [sweeping, setSweeping] = useState(false)
  const [sweep, setSweep] = useState<SweepCell[]>([])
  const [reviewer, setReviewer] = useState('')
  const [rationale, setRationale] = useState('')
  const [reviewAction, setReviewAction] = useState('ACCEPT')
  const [reviewMsg, setReviewMsg] = useState<string | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [ranAt, setRanAt] = useState<string | null>(null)
  const [cacheHit, setCacheHit] = useState(false)
  const [copied, setCopied] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(() => loadHistory())
  const [compareIds, setCompareIds] = useState<[string, string]>(['', ''])
  const timerRef = useRef<number | null>(null)
  const sweepCancel = useRef(false)

  useEffect(() => {
    let cancelled = false
    api.getMeta()
      .then((m) => { if (!cancelled) setMeta(m) })
      .catch((e) => { if (!cancelled) setMetaError(apiErrorMessage(e, 'Failed to load engine metadata.')) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current)
      sweepCancel.current = true
    }
  }, [])

  const bounds = meta?.limits.scenario_bounds

  const parseInputs = (): RunParams | null => {
    if (!bounds) {
      setError('Engine metadata not loaded yet.')
      return null
    }
    const checks: Array<[string, string, number, number]> = [
      ['crowd', crowd, bounds.crowd[0], bounds.crowd[1]],
      ['smoke', smoke, bounds.smoke[0], bounds.smoke[1]],
      ['corridor_capacity', capacity, bounds.corridor_capacity[0], bounds.corridor_capacity[1]],
    ]
    const out: Record<string, number> = {}
    for (const [key, raw, lo, hi] of checks) {
      const v = Number(raw)
      if (!Number.isFinite(v) || v < lo || v > hi) {
        setError(`${key} must be within [${lo}, ${hi}].`)
        return null
      }
      out[key] = v
    }
    return { crowd: out.crowd, smoke: out.smoke, capacity: out.corridor_capacity, blockB }
  }

  const recordHistory = (params: RunParams, payload: DemoPayload) => {
    const entry: HistoryEntry = {
      key: `${params.crowd}|${params.smoke}|${params.capacity}|${params.blockB ? 1 : 0}|${payload.reproducibility.engine_version}`,
      time: new Date().toISOString(),
      params,
      guardianPassed: payload.guardian.passed,
      robustCount: payload.robust.length,
      classicalEnergy: payload.robust_optimization.classical.energy,
      classicalMethod: payload.robust_optimization.classical.method,
    }
    setHistory((prev) => {
      const next = [entry, ...prev.filter((h) => h.key !== entry.key)].slice(0, HISTORY_MAX)
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
      } catch {
        /* storage full or unavailable: history stays in memory */
      }
      return next
    })
  }

  const execute = async (params: RunParams): Promise<DemoPayload> => {
    const started = performance.now()
    setPhase('sending request')
    const key = demoCacheKey(params, meta?.engine_version || 'unknown')
    const cached = readDemoCache(key)
    if (cached) {
      setCacheHit(true)
      setPhase('rendering cached response')
      setElapsed(Math.round(performance.now() - started))
      return cached
    }
    setCacheHit(false)
    const payload = await api.runDemo({ crowd: params.crowd, smoke: params.smoke, corridor_capacity: params.capacity, block_b: params.blockB })
    writeDemoCache(key, payload)
    setPhase('rendering response')
    setElapsed(Math.round(performance.now() - started))
    return payload
  }

  const handleRun = async (paramsOverride?: RunParams) => {
    const params = paramsOverride || parseInputs()
    if (!params) return
    setError(null)
    setResult(null)
    setReviewMsg(null)
    setReviewError(null)
    setRunning(true)
    const t0 = performance.now()
    timerRef.current = window.setInterval(() => setElapsed(Math.round(performance.now() - t0)), 250)
    try {
      setPhase('executing engine')
      const payload = await execute(params)
      setResult(payload)
      setLastParams(params)
      setRanAt(new Date().toISOString())
      recordHistory(params, payload)
      logEvent('simulation', `run completed: crowd=${params.crowd} smoke=${params.smoke} guardian=${payload.guardian.passed ? 'PASSED' : 'FAILED'}`)
      setPhase('')
    } catch (e) {
      setError(apiErrorMessage(e, 'Simulation failed.'))
      logEvent('simulation', `run failed: ${apiErrorMessage(e, 'request failed')}`)
      setPhase('')
    } finally {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current)
        timerRef.current = null
      }
      setRunning(false)
    }
  }

  const handleReset = () => {
    setCrowd(String(DEFAULTS.crowd))
    setSmoke(String(DEFAULTS.smoke))
    setCapacity(String(DEFAULTS.capacity))
    setBlockB(DEFAULTS.blockB)
    setResult(null)
    setError(null)
    setReviewMsg(null)
    setReviewError(null)
    setElapsed(0)
    setPhase('')
    setRanAt(null)
    setCacheHit(false)
  }

  const stale =
    result !== null &&
    lastParams !== null &&
    (Number(crowd) !== lastParams.crowd ||
      Number(smoke) !== lastParams.smoke ||
      Number(capacity) !== lastParams.capacity ||
      blockB !== lastParams.blockB)

  const curlFor = (p: RunParams): string => {
    const q = new URLSearchParams({
      crowd: String(p.crowd),
      smoke: String(p.smoke),
      corridor_capacity: String(p.capacity),
    })
    if (p.blockB) q.set('block_b', '1')
    return `curl "http://127.0.0.1:8080/api/demo?${q.toString()}"`
  }

  const handleCopyCurl = async () => {
    if (!lastParams) return
    try {
      await navigator.clipboard.writeText(curlFor(lastParams))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const applyTemplate = (t: (typeof TEMPLATES)[number]) => {
    setCrowd(String(t.params.crowd))
    setSmoke(String(t.params.smoke))
    setCapacity(String(t.params.capacity))
    setBlockB(t.params.blockB)
    setError(null)
  }

  const handleBreak = async () => {
    if (!bounds || sweeping) return
    setSweep([])
    setSweeping(true)
    sweepCancel.current = false
    const crowds = [bounds.crowd[0], (bounds.crowd[0] + bounds.crowd[1]) / 2, bounds.crowd[1]]
    const smokes = [bounds.smoke[0], bounds.smoke[1]]
    const cells: SweepCell[] = []
    for (const c of crowds) {
      for (const s of smokes) {
        if (sweepCancel.current) break
        const params: RunParams = { crowd: Math.round(c), smoke: Math.round(s * 10) / 10, capacity: Number(capacity) || DEFAULTS.capacity, blockB }
        try {
          const payload = await api.runDemo({ crowd: params.crowd, smoke: params.smoke, corridor_capacity: params.capacity, block_b: params.blockB })
          cells.push({ crowd: params.crowd, smoke: params.smoke, guardianPassed: payload.guardian.passed, robustCount: payload.robust.length, error: null })
        } catch (e) {
          cells.push({ crowd: params.crowd, smoke: params.smoke, guardianPassed: null, robustCount: null, error: apiErrorMessage(e, 'request failed') })
        }
        setSweep([...cells])
      }
      if (sweepCancel.current) break
    }
    setSweeping(false)
    if (!sweepCancel.current) {
      const failed = cells.filter((c) => c.guardianPassed === false).length
      logEvent('sweep', `break-this-plan sweep finished: ${cells.length} cells, ${failed} Guardian failures`)
    }
  }

  const handleApprove = async () => {
    setReviewMsg(null)
    setReviewError(null)
    if (!result || !lastParams) {
      setReviewError('Run a simulation first.')
      return
    }
    if (!reviewer.trim()) {
      setReviewError('Reviewer ID is required — anonymous approvals are not auditable.')
      return
    }
    try {
      const row = await api.submitReview({
        action: reviewAction,
        evidence_id: `demo-run:${lastParams.crowd}|${lastParams.smoke}|${lastParams.capacity}|${lastParams.blockB ? 1 : 0}|${result.reproducibility.engine_version}`,
        reviewer_id: reviewer.trim(),
        rationale: rationale.trim(),
      })
      const rid = (row as Record<string, unknown>)['review_id']
      setReviewMsg(`Recorded ${reviewAction} · ${String(rid).slice(0, 12)}…`)
      logEvent('approval', `${reviewAction} recorded by ${reviewer.trim()} for current run`)
      setRationale('')
    } catch (e) {
      setReviewError(apiErrorMessage(e, 'Review rejected.'))
    }
  }

  const comparePair = compareIds[0] && compareIds[1]
    ? [history.find((h) => h.key === compareIds[0]), history.find((h) => h.key === compareIds[1])]
    : [undefined, undefined]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Simulation</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Executes the real engine via <code className="font-mono text-sm">GET /api/demo</code> — smart-building emergency.
          Decision content is deterministic for identical inputs (verified: only wall-clock timings vary).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <div className="p-6 space-y-4">
            <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Initial State</h2>
            {metaError && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{metaError}</p>}
            <Input label={`Crowd [${bounds ? `${bounds.crowd[0]}–${bounds.crowd[1]}` : '…'}]`} type="number" value={crowd} onChange={(e) => setCrowd(e.target.value)} />
            <Input label={`Smoke [${bounds ? `${bounds.smoke[0]}–${bounds.smoke[1]}` : '…'}]`} type="number" value={smoke} onChange={(e) => setSmoke(e.target.value)} />
            <Input label={`Corridor capacity [${bounds ? `${bounds.corridor_capacity[0]}–${bounds.corridor_capacity[1]}` : '…'}]`} type="number" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
            <label className="flex items-center gap-2 text-sm text-secondary-700 dark:text-secondary-300">
              <input type="checkbox" checked={blockB} onChange={(e) => setBlockB(e.target.checked)} className="h-4 w-4 rounded border-secondary-300 text-primary-600" />
              Block corridor B (+penalty)
            </label>
            {meta && (
              <div className="text-xs text-secondary-500 dark:text-secondary-400 space-y-1 pt-2 border-t border-secondary-100 dark:border-secondary-800">
                <p>Optimizers: <span className="font-mono">{meta.optimizers.join(', ')}</span></p>
                <p>Backend: <span className="font-mono">{meta.backends.join(', ')}</span></p>
                <p>Engine: <span className="font-mono">v{meta.engine_version}</span></p>
              </div>
            )}
            <div>
              <p className="text-xs font-medium text-secondary-500 dark:text-secondary-400 mb-2">Templates (local presets — engine supports one scenario type)</p>
              <div className="flex flex-wrap gap-2">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => applyTemplate(t)}
                    disabled={running}
                    title={t.desc}
                    className="text-xs px-2.5 py-1.5 rounded-lg border border-secondary-300 dark:border-secondary-600 hover:bg-secondary-100 dark:hover:bg-secondary-800 transition-colors disabled:opacity-50"
                  >
                    {t.name}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => handleRun()} disabled={running || !meta} className="flex-1">
                {running ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />{phase || 'Running…'} · {elapsed} ms</>) : (<><Play className="w-4 h-4 mr-2" />Run Simulation</>)}
              </Button>
              <Button variant="outline" onClick={handleReset} disabled={running} aria-label="Reset to defaults">
                <RotateCcw className="w-4 h-4" />
              </Button>
            </div>
            {lastParams && !running && (
              <Button variant="ghost" size="sm" onClick={() => handleRun(lastParams)} className="w-full">
                Replay exact inputs ({lastParams.crowd}, {lastParams.smoke}, {lastParams.capacity}{lastParams.blockB ? ', blocked' : ''})
              </Button>
            )}
            {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <div className="p-6">
            <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-4">Result</h2>
            {!result && !running && <p className="text-sm text-secondary-500">Configure the initial state and run. Guardian verdict, ranking with reasons, optimizer methods, and the 3D future tree appear here.</p>}
            {running && <p className="text-sm text-secondary-500">Engine executing… {elapsed} ms elapsed. No simulated progress — this timer measures the live request.</p>}
            {result && (
              <div className="space-y-5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={result.guardian.passed ? 'success' : 'error'}>
                    {result.guardian.passed ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                    Guardian {result.guardian.passed ? 'PASSED' : 'FAILED'}
                  </Badge>
                  <span className="text-xs text-secondary-500">{result.guardian.scope}</span>
                  <span className="text-xs text-secondary-500 font-mono">round-trip {elapsed} ms</span>
                  <span className="text-xs text-secondary-500">risk entropy {result.uncertainty.risk_entropy.toFixed(3)}</span>
                  {cacheHit && <Badge variant="secondary">CACHE HIT — identical inputs + engine version</Badge>}
                  <button
                    onClick={() => { clearDemoCache() }}
                    className="text-xs text-secondary-500 hover:underline"
                    title="Clears fingerprint-keyed demo cache in this browser"
                  >
                    Clear cache
                  </button>
                  <button onClick={handleCopyCurl} className="text-xs text-primary-600 hover:underline inline-flex items-center gap-1" aria-label="Copy as curl">
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}{copied ? 'Copied' : 'Copy as curl'}
                  </button>
                </div>
                {stale && (
                  <p className="text-sm text-warning-600 dark:text-warning-400 border border-warning-200 dark:border-warning-800 rounded-lg px-3 py-2" role="status">
                    Inputs changed since this result — it is stale. Re-run to recompute.
                  </p>
                )}
                {ranAt && !stale && (
                  <p className="text-xs text-secondary-500">Computed {new Date(ranAt).toLocaleTimeString()} · valid only for the exact inputs shown above.</p>
                )}
                {!result.guardian.passed && (
                  <div className="text-sm border border-error-200 dark:border-error-800 rounded-lg px-3 py-2 space-y-1" role="alert">
                    <p className="font-medium text-error-700 dark:text-error-300">Incident mode: Guardian withheld this result.</p>
                    <ul className="list-disc list-inside text-secondary-600 dark:text-secondary-400">
                      <li>Do not act on these numbers — display is frozen by policy.</li>
                      <li>Try the Break-this-plan sweep to find passing inputs, or adjust the initial state.</li>
                      <li>Record the outcome via Human approval below so the audit trail shows the decision.</li>
                    </ul>
                  </div>
                )}

                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2">3D future tree ({result.future_tree.length} nodes)</h3>
                  <FutureTree3D nodes={result.future_tree} />
                </div>

                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2">Robust ranking + reasons</h3>
                  {result.robust.length === 0 && (
                    <p className="text-sm text-secondary-500">No feasible policies under the declared perturbations for this initial state.</p>
                  )}
                  {result.robust.length > 0 && (
                    <div className="table-container">
                      <table className="table">
                        <thead><tr><th>Policy</th><th>Nominal</th><th>Worst case</th><th>Gap</th><th>Feasible</th><th>Reason</th></tr></thead>
                        <tbody>
                          {result.robust.map((r, i) => (
                            <tr key={i}>
                              <td className="font-mono text-xs">{JSON.stringify(r.policy)}</td>
                              <td className="font-mono">{r.score.toFixed(2)}</td>
                              <td className="font-mono">{r.worst_case_score.toFixed(2)}</td>
                              <td className="font-mono">{r.robustness_gap.toFixed(2)}</td>
                              <td>{r.feasible_under_all ? 'yes' : 'no'}</td>
                              <td className="text-xs max-w-xs">{reasonFor(r)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2">Optimizer comparison</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                    {[
                      { label: 'Exact (classical)', r: result.robust_optimization.classical },
                      { label: 'QAOA simulator', r: result.robust_optimization.qaoa },
                      { label: 'QAOA CVaR tail', r: result.robust_optimization.cvar_qaoa },
                    ].map((o) => (
                      <div key={o.label} className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                        <p className="font-medium">{o.label}</p>
                        <p className="font-mono">energy {o.r.energy.toFixed(3)}</p>
                        <p className="font-mono text-xs text-secondary-500">{o.r.method}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="text-xs text-secondary-500 space-y-1 pt-2 border-t border-secondary-100 dark:border-secondary-800">
                  <p>Reproducibility: engine v{result.reproducibility.engine_version} · backend <span className="font-mono">{result.reproducibility.backend}</span> · {result.reproducibility.note}</p>
                  <p>Benchmark notes:</p>
                  <ul className="list-disc list-inside">
                    {result.benchmark.map((b) => (
                      <li key={b.method}><span className="font-mono">{b.method}</span> — {b.note}</li>
                    ))}
                  </ul>
                </div>

                <div className="pt-2 border-t border-secondary-100 dark:border-secondary-800">
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2 flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4" /> Human approval
                  </h3>
                  {!result.guardian.passed && (
                    <p className="text-sm text-warning-600 dark:text-warning-400 mb-2">Guardian did not pass — approval is discouraged and will be recorded as such.</p>
                  )}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <Input label="Reviewer ID" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="e.g. operator-1" />
                    <div>
                      <label className="label" htmlFor="review-action">Action</label>
                      <select id="review-action" value={reviewAction} onChange={(e) => setReviewAction(e.target.value)} className="input">
                        <option value="ACCEPT">ACCEPT</option>
                        <option value="REJECT">REJECT</option>
                        <option value="OVERRIDE">OVERRIDE</option>
                        <option value="REQUEST_REVIEW">REQUEST REVIEW</option>
                      </select>
                    </div>
                    <Input label="Rationale (required to reject/override)" value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="Why this decision?" />
                  </div>
                  <div className="mt-3">
                    <Button variant="outline" onClick={handleApprove}>Record Decision</Button>
                  </div>
                  {reviewMsg && <p className="text-sm text-success-600 dark:text-success-400 mt-2">{reviewMsg}</p>}
                  {reviewError && <p className="text-sm text-error-600 dark:text-error-400 mt-2" role="alert">{reviewError}</p>}
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <div className="p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Break this plan</h2>
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleBreak} disabled={sweeping || !meta}>
                {sweeping ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sweeping…</>) : 'Run 3×2 Sweep'}
              </Button>
              {sweeping && <Button variant="ghost" onClick={() => { sweepCancel.current = true }}>Stop</Button>}
            </div>
          </div>
          <p className="text-sm text-secondary-500">Six real executions across crowd × smoke extremes (current capacity, current block flag). Capped, sequential, cancellable — finds inputs where Guardian fails.</p>
          {sweep.length > 0 && (
            <div className="table-container">
              <table className="table">
                <thead><tr><th>Crowd</th><th>Smoke</th><th>Guardian</th><th>Feasible policies</th><th></th></tr></thead>
                <tbody>
                  {sweep.map((c, i) => (
                    <tr key={i}>
                      <td className="font-mono">{c.crowd}</td>
                      <td className="font-mono">{c.smoke}</td>
                      <td>{c.guardianPassed === null ? <span className="text-error-600 text-sm">{c.error}</span> : <Badge variant={c.guardianPassed ? 'success' : 'error'}>{c.guardianPassed ? 'PASSED' : 'FAILED'}</Badge>}</td>
                      <td className="font-mono">{c.robustCount === null ? '—' : c.robustCount}</td>
                      <td className="text-right">
                        <button className="text-primary-600 hover:underline text-sm" onClick={() => { setCrowd(String(c.crowd)); setSmoke(String(c.smoke)); handleRun({ crowd: c.crowd, smoke: c.smoke, capacity: Number(capacity) || DEFAULTS.capacity, blockB }) }}>
                          Load
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <div className="p-6 space-y-3">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Local run history + compare</h2>
          <p className="text-sm text-secondary-500">Stored only in this browser (localStorage, max {HISTORY_MAX}). Server-side history requires persistence — see Experiments.</p>
          {history.length === 0 && <p className="text-sm text-secondary-500">No runs yet this session.</p>}
          {history.length > 0 && (
            <>
              <div className="table-container">
                <table className="table">
                  <thead><tr><th>Time</th><th>Inputs</th><th>Guardian</th><th>Policies</th><th>Energy</th><th>Method</th></tr></thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.key + h.time}>
                        <td className="text-xs">{new Date(h.time).toLocaleTimeString()}</td>
                        <td className="font-mono text-xs">{h.params.crowd}, {h.params.smoke}, {h.params.capacity}{h.params.blockB ? ', blocked' : ''}</td>
                        <td><Badge variant={h.guardianPassed ? 'success' : 'error'}>{h.guardianPassed ? 'PASSED' : 'FAILED'}</Badge></td>
                        <td className="font-mono">{h.robustCount}</td>
                        <td className="font-mono">{h.classicalEnergy.toFixed(2)}</td>
                        <td className="font-mono text-xs">{h.classicalMethod}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[0, 1].map((slot) => (
                  <div key={slot}>
                    <label className="label" htmlFor={`compare-${slot}`}>Compare slot {slot === 0 ? 'A' : 'B'}</label>
                    <select id={`compare-${slot}`} value={compareIds[slot]} onChange={(e) => setCompareIds(slot === 0 ? [e.target.value, compareIds[1]] : [compareIds[0], e.target.value])} className="input">
                      <option value="">—</option>
                      {history.map((h) => (
                        <option key={h.key + h.time} value={h.key}>{new Date(h.time).toLocaleTimeString()} · {h.params.crowd}/{h.params.smoke}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              {comparePair[0] && comparePair[1] && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  {comparePair.map((h, i) => h && (
                    <div key={i} className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 space-y-1">
                      <p className="font-medium">Slot {i === 0 ? 'A' : 'B'} · {new Date(h.time).toLocaleTimeString()}</p>
                      <p className="font-mono text-xs">inputs {h.params.crowd}, {h.params.smoke}, {h.params.capacity}{h.params.blockB ? ', blocked' : ''}</p>
                      <p>Guardian: <Badge variant={h.guardianPassed ? 'success' : 'error'}>{h.guardianPassed ? 'PASSED' : 'FAILED'}</Badge></p>
                      <p className="font-mono">policies {h.robustCount} · energy {h.classicalEnergy.toFixed(2)} ({h.classicalMethod})</p>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </Card>
    </div>
  )
}
