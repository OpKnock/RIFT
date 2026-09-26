import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api, apiErrorMessage } from '@/services/api'

type Row = Record<string, unknown>

const DIFF_FIELDS = ['name', 'status', 'optimizer', 'backend', 'seed', 'fingerprint', 'engine_version', 'user_id'] as const

function scalar(row: Row | null, field: string): string {
  if (!row) return '—'
  const v = row[field]
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

export function Experiments() {
  const [name, setName] = useState('')
  const [fetchId, setFetchId] = useState('')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [idA, setIdA] = useState('')
  const [idB, setIdB] = useState('')
  const [rowA, setRowA] = useState<Row | null>(null)
  const [rowB, setRowB] = useState<Row | null>(null)
  const [diffError, setDiffError] = useState<string | null>(null)
  const [diffBusy, setDiffBusy] = useState(false)

  const create = async () => {
    if (!name.trim()) { setError('Experiment name is required.'); return }
    setError(null)
    setResult(null)
    setBusy(true)
    try {
      const row = await api.createExperiment({ name })
      setResult(row)
      setName('')
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to create experiment.'))
    } finally {
      setBusy(false)
    }
  }

  const fetchOne = async () => {
    if (!fetchId.trim()) { setError('Experiment ID is required.'); return }
    setError(null)
    setResult(null)
    setBusy(true)
    try {
      const row = await api.getExperiment(fetchId.trim())
      setResult(row)
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to fetch experiment.'))
    } finally {
      setBusy(false)
    }
  }

  const compare = async () => {
    if (!idA.trim() || !idB.trim()) { setDiffError('Two experiment UUIDs are required.'); return }
    setDiffError(null)
    setRowA(null)
    setRowB(null)
    setDiffBusy(true)
    try {
      const [a, b] = await Promise.all([api.getExperiment(idA.trim()), api.getExperiment(idB.trim())])
      setRowA(a as Row)
      setRowB(b as Row)
    } catch (e) {
      setDiffError(apiErrorMessage(e, 'Failed to fetch experiments for comparison.'))
    } finally {
      setDiffBusy(false)
    }
  }

  const ownerOf = (row: unknown): string | null => {
    if (row && typeof row === 'object' && 'user_id' in (row as Row)) {
      const v = (row as Row)['user_id']
      return v === null || v === undefined ? null : String(v)
    }
    return null
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Experiments</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Real <code className="font-mono text-sm">POST /api/experiments</code> and <code className="font-mono text-sm">GET /api/experiments/{'{id}'}</code>.
          There is no list endpoint — and no persistence without Supabase (server answers 503). Both facts are shown, not hidden.
        </p>
      </div>
      <Card>
        <div className="p-6 space-y-4">
          <div className="flex gap-3">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="New experiment name" />
            <Button onClick={create} disabled={busy}>Create</Button>
          </div>
          <div className="flex gap-3">
            <Input value={fetchId} onChange={(e) => setFetchId(e.target.value)} placeholder="Experiment UUID to fetch" />
            <Button variant="outline" onClick={fetchOne} disabled={busy}>Fetch</Button>
          </div>
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {result !== null && !error && (
            <div className="space-y-2">
              {ownerOf(result) !== null && (
                <p className="text-sm">Owner: <span className="font-mono">{ownerOf(result)}</span> <span className="text-secondary-500">(per-row ownership, enforced server-side)</span></p>
              )}
              <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <div className="p-6 space-y-4">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Decision difference (two experiments)</h2>
          <p className="text-sm text-secondary-500">Fetches both rows and diffs versioned fields side by side. Requires persistence; 503 otherwise.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input value={idA} onChange={(e) => setIdA(e.target.value)} placeholder="Experiment UUID A" />
            <Input value={idB} onChange={(e) => setIdB(e.target.value)} placeholder="Experiment UUID B" />
          </div>
          <Button variant="outline" onClick={compare} disabled={diffBusy}>Compare</Button>
          {diffError && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{diffError}</p>}
          {rowA && rowB && !diffError && (
            <div className="table-container">
              <table className="table">
                <thead><tr><th>Field</th><th>A</th><th>B</th><th></th></tr></thead>
                <tbody>
                  {DIFF_FIELDS.map((f) => {
                    const a = scalar(rowA, f)
                    const b = scalar(rowB, f)
                    const same = a === b
                    return (
                      <tr key={f}>
                        <td className="font-mono text-xs">{f}</td>
                        <td className="font-mono text-xs">{a}</td>
                        <td className="font-mono text-xs">{b}</td>
                        <td><Badge variant={same ? 'secondary' : 'warning'}>{same ? 'same' : 'DIFFERS'}</Badge></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
