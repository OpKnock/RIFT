import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage, type EngineMeta } from '@/services/api'

export function Scenarios() {
  const [meta, setMeta] = useState<EngineMeta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api.getMeta()
      .then((m) => { if (!cancelled) setMeta(m) })
      .catch((e) => { if (!cancelled) setError(apiErrorMessage(e, 'Failed to load engine metadata.')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Scenarios</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">
            The engine supports exactly one scenario type today (<code className="font-mono text-sm">smart-building-emergency</code>).
            Anything else would be fake — so this list comes from <code className="font-mono text-sm">GET /api/meta</code>.
          </p>
        </div>
        <Link to="/scenarios/new"><Button><Plus className="w-4 h-4 mr-2" />New Scenario</Button></Link>
      </div>

      {loading && <p className="text-sm text-secondary-500">Loading…</p>}
      {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
      {!loading && !error && meta && (
        <Card>
          <div className="p-6 space-y-3">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-secondary-900 dark:text-white font-mono">smart-building-emergency</h2>
              <Badge variant="secondary">engine-built-in</Badge>
            </div>
            <div>
              <h3 className="text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1">Bounded state variables</h3>
              <ul className="text-sm font-mono space-y-1">
                {Object.entries(meta.limits.scenario_bounds).map(([k, [lo, hi]]) => (
                  <li key={k}>{k} <span className="text-secondary-500">[{lo}, {hi}]</span></li>
                ))}
              </ul>
            </div>
            <div className="text-sm text-secondary-500">
              Optimizers <span className="font-mono">{meta.optimizers.join(', ')}</span> · backends <span className="font-mono">{meta.backends.join(', ')}</span> · max {meta.limits.max_policy_variables} policy variables, {meta.limits.max_perturbations} perturbations.
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
