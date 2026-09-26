import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, apiErrorMessage } from '@/services/api'

export function Experiments() {
  const [name, setName] = useState('')
  const [fetchId, setFetchId] = useState('')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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
            <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(result, null, 2)}</pre>
          )}
        </div>
      </Card>
    </div>
  )
}
