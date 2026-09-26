import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Play, FlaskConical, Scale, ArrowRight } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage, type HealthStatus, type EngineMeta } from '@/services/api'

export function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [meta, setMeta] = useState<EngineMeta | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.getHealth(), api.getMeta()])
      .then(([h, m]) => {
        if (cancelled) return
        setHealth(h)
        setMeta(m)
      })
      .catch((e) => { if (!cancelled) setError(apiErrorMessage(e, 'Engine unreachable.')) })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">RIFT</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Counterfactual decision intelligence — research prototype. Define a scenario, run futures, stress them, verify with Guardian.
        </p>
      </div>

      <Card>
        <div className="p-6 space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Engine</h2>
            {health && <Badge variant={health.status === 'ok' ? 'success' : 'error'}>{health.status}</Badge>}
          </div>
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {health && meta && !error && (
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div><dt className="text-secondary-500">Version</dt><dd className="font-mono">v{health.version}</dd></div>
              <div><dt className="text-secondary-500">Quantum backend</dt><dd className="font-mono">{health.quantum_backend}</dd></div>
              <div><dt className="text-secondary-500">Optimizers</dt><dd className="font-mono">{meta.optimizers.join(', ')}</dd></div>
              <div><dt className="text-secondary-500">Persistence</dt><dd className="font-mono">{health.persistence.configured ? 'configured' : 'not configured'}</dd></div>
            </dl>
          )}
          <div className="pt-2">
            <Link to="/simulation"><Button><Play className="w-4 h-4 mr-2" />Run a Simulation</Button></Link>
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-3">Where to go</h2>
          <ul className="space-y-2 text-sm">
            <li><Link to="/simulation" className="text-primary-600 hover:underline inline-flex items-center gap-1">Simulation <ArrowRight className="w-3 h-3" /></Link><span className="text-secondary-500"> — run the engine, see Guardian verdict</span></li>
            <li><Link to="/evidence" className="text-primary-600 hover:underline inline-flex items-center gap-1">Evidence <ArrowRight className="w-3 h-3" /></Link><span className="text-secondary-500"> — synthetic backtest bundle, adequacy labeled</span></li>
            <li><Link to="/experiments" className="text-primary-600 hover:underline inline-flex items-center gap-1">Experiments <FlaskConical className="w-3 h-3" /></Link><span className="text-secondary-500"> — versioned specs (needs persistence)</span></li>
            <li><Link to="/docs" className="text-primary-600 hover:underline inline-flex items-center gap-1">Documentation <ArrowRight className="w-3 h-3" /></Link><span className="text-secondary-500"> — repo docs index</span></li>
          </ul>
          <p className="text-xs text-secondary-500 mt-4 flex items-center gap-1"><Scale className="w-3 h-3" /> Synthetic demo data. Decision support only — never autonomous care, never clinically validated.</p>
        </div>
      </Card>
    </div>
  )
}
