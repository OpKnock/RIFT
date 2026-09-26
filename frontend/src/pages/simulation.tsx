import { useEffect, useState } from 'react'
import { Play, Loader2, CheckCircle, XCircle } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage, type DemoPayload, type EngineMeta } from '@/services/api'

export function Simulation() {
  const [meta, setMeta] = useState<EngineMeta | null>(null)
  const [metaError, setMetaError] = useState<string | null>(null)
  const [crowd, setCrowd] = useState('1200')
  const [smoke, setSmoke] = useState('4')
  const [capacity, setCapacity] = useState('60')
  const [blockB, setBlockB] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DemoPayload | null>(null)
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    api.getMeta()
      .then((m) => { if (!cancelled) setMeta(m) })
      .catch((e) => { if (!cancelled) setMetaError(apiErrorMessage(e, 'Failed to load engine metadata.')) })
    return () => { cancelled = true }
  }, [])

  const bounds = meta?.limits.scenario_bounds
  const clamp = (raw: string, lo: number, hi: number): number | null => {
    const v = Number(raw)
    if (!Number.isFinite(v) || v < lo || v > hi) return null
    return v
  }

  const handleRun = async () => {
    setError(null)
    setResult(null)
    if (!bounds) { setError('Engine metadata not loaded yet.'); return }
    const c = clamp(crowd, bounds.crowd[0], bounds.crowd[1])
    const s = clamp(smoke, bounds.smoke[0], bounds.smoke[1])
    const k = clamp(capacity, bounds.corridor_capacity[0], bounds.corridor_capacity[1])
    if (c === null || s === null || k === null) {
      setError(`Inputs out of engine bounds: crowd [${bounds.crowd}], smoke [${bounds.smoke}], capacity [${bounds.corridor_capacity}].`)
      return
    }
    setRunning(true)
    const t0 = performance.now()
    try {
      const payload = await api.runDemo({ crowd: c, smoke: s, corridor_capacity: k, block_b: blockB })
      setResult(payload)
      setElapsedMs(Math.round(performance.now() - t0))
    } catch (e) {
      setError(apiErrorMessage(e, 'Simulation failed.'))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Simulation</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Executes the real engine via <code className="font-mono text-sm">GET /api/demo</code> — smart-building emergency, deterministic.
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
            <Button onClick={handleRun} disabled={running || !meta} className="w-full">
              {running ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Running…</>) : (<><Play className="w-4 h-4 mr-2" />Run Simulation</>)}
            </Button>
            {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <div className="p-6">
            <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-4">Result</h2>
            {!result && !running && <p className="text-sm text-secondary-500">Configure the initial state and run. The engine response appears here with method labels.</p>}
            {running && <p className="text-sm text-secondary-500">Executing… (synchronous engine call, timed locally)</p>}
            {result && (
              <div className="space-y-5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={result.guardian.passed ? 'success' : 'error'}>
                    {result.guardian.passed ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                    Guardian {result.guardian.passed ? 'PASSED' : 'FAILED'}
                  </Badge>
                  <span className="text-xs text-secondary-500">{result.guardian.scope}</span>
                  {elapsedMs !== null && <span className="text-xs text-secondary-500 font-mono">round-trip {elapsedMs} ms</span>}
                </div>
                <div>
                  <h3 className="font-medium text-secondary-900 dark:text-white mb-2">Robust ranking</h3>
                  {result.robust.length === 0 && (
                    <p className="text-sm text-secondary-500">No feasible policies under the declared perturbations for this initial state. Adjust the inputs or inspect the Guardian checks.</p>
                  )}
                  {result.robust.length > 0 && (
                  <div className="table-container">
                    <table className="table">
                      <thead><tr><th>Policy</th><th>Nominal</th><th>Worst case</th><th>Gap</th><th>Feasible</th></tr></thead>
                      <tbody>
                        {result.robust.map((r, i) => (
                          <tr key={i}>
                            <td className="font-mono text-xs">{JSON.stringify(r.policy)}</td>
                            <td className="font-mono">{r.score.toFixed(2)}</td>
                            <td className="font-mono">{r.worst_case_score.toFixed(2)}</td>
                            <td className="font-mono">{r.robustness_gap.toFixed(2)}</td>
                            <td>{r.feasible_under_all ? 'yes' : 'no'}</td>
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
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
