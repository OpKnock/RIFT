import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface RunRow {
  id: string
  experiment_id?: string
  status?: string
  backend?: string
  seed?: number
}

export function Runs() {
  const [runs, setRuns] = useState<RunRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/api/ops/monitor')
        if (!res.ok) throw new Error(`Server responded ${res.status}`)
        const body = await res.json()
        const list: RunRow[] = body?.data?.recent_runs || body?.recent_runs || []
        if (!cancelled) setRuns(Array.isArray(list) ? list : [])
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load runs.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Runs</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">Live data from <code className="font-mono text-sm">GET /api/ops/monitor</code>.</p>
        </div>
        <Link to="/simulation"><Button>New Run</Button></Link>
      </div>
      <Card>
        <div className="p-6">
          {loading && <p className="text-sm text-secondary-500">Loading runs…</p>}
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {!loading && !error && runs.length === 0 && (
            <p className="text-sm text-secondary-500">No runs reported by the server yet. Run a simulation to create one.</p>
          )}
          {!loading && !error && runs.length > 0 && (
            <div className="table-container">
              <table className="table">
                <thead><tr><th>Run ID</th><th>Experiment</th><th>Status</th><th>Backend</th><th></th></tr></thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td className="font-mono text-sm">{r.id}</td>
                      <td className="font-mono text-sm">{r.experiment_id || '—'}</td>
                      <td><Badge variant="secondary">{r.status || 'unknown'}</Badge></td>
                      <td className="font-mono text-sm">{r.backend || '—'}</td>
                      <td className="text-right"><Link className="text-primary-600 hover:underline text-sm" to={`/runs/${r.id}`}>View</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
