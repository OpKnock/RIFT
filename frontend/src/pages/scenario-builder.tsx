import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/input'
import { api, apiErrorMessage, type EngineMeta } from '@/services/api'

export function ScenarioBuilder() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [meta, setMeta] = useState<EngineMeta | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [crowd, setCrowd] = useState('1200')
  const [smoke, setSmoke] = useState('4')
  const [capacity, setCapacity] = useState('60')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<unknown>(null)

  useEffect(() => {
    let cancelled = false
    api.getMeta()
      .then((m) => { if (!cancelled) setMeta(m) })
      .catch(() => { if (!cancelled) setMeta(null) })
    return () => { cancelled = true }
  }, [])

  const handleSave = async () => {
    setError(null)
    setCreated(null)
    if (!name.trim()) {
      setError('Scenario name is required.')
      return
    }
    const bounds = meta?.limits.scenario_bounds
    const initial_state: Record<string, number> = {}
    if (bounds) {
      for (const [key, raw] of [['crowd', crowd], ['smoke', smoke], ['corridor_capacity', capacity]] as const) {
        const v = Number(raw)
        const [lo, hi] = bounds[key]
        if (!Number.isFinite(v) || v < lo || v > hi) {
          setError(`${key} must be within [${lo}, ${hi}].`)
          return
        }
        initial_state[key] = v
      }
    }
    setSaving(true)
    try {
      const row = await api.createExperiment({
        name,
        description,
        scenario_name: 'smart-building-emergency',
        initial_state,
        perturbations: [],
        policy_variables: [],
        optimizer: 'exact',
        backend: 'statevector-simulator',
        seed: 42,
      })
      setCreated(row)
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to save scenario.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">
          {id ? 'Edit Scenario' : 'New Scenario'}
        </h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Saved via the real <code className="font-mono text-sm">POST /api/experiments</code> against the one supported scenario (<code className="font-mono text-sm">smart-building-emergency</code>).
          Bounds come from <code className="font-mono text-sm">GET /api/meta</code>. Without Supabase the server answers 503 — shown below, not hidden.
        </p>
      </div>
      <Card>
        <div className="p-6 space-y-4">
          <Input label="Scenario name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Evening rush, Block B closed" />
          <Textarea label="Description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What decision does this scenario test?" rows={3} />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input label="Crowd" type="number" value={crowd} onChange={(e) => setCrowd(e.target.value)} />
            <Input label="Smoke" type="number" value={smoke} onChange={(e) => setSmoke(e.target.value)} />
            <Input label="Corridor capacity" type="number" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
          </div>
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {created !== null && !error && (
            <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(created, null, 2)}</pre>
          )}
          <div className="flex gap-3">
            <Button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save Scenario'}</Button>
            <Button variant="outline" onClick={() => navigate('/scenarios')}>Cancel</Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
