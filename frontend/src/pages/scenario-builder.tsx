import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/input'

export function ScenarioBuilder() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [name, setName] = useState(id ? `Scenario ${id}` : '')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    setError(null)
    if (!name.trim()) {
      setError('Scenario name is required.')
      return
    }
    setSaving(true)
    try {
      const res = await fetch('/api/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, scenario: { name, initial_state: {} } }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.error || `Server responded ${res.status}`)
      }
      navigate('/experiments')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save scenario.')
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
          Saved via the real <code className="font-mono text-sm">POST /api/experiments</code> endpoint.
        </p>
      </div>
      <Card>
        <div className="p-6 space-y-4">
          <Input label="Scenario name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cardiac Strain v2.2" />
          <Textarea label="Description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What decision does this scenario test?" rows={4} />
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          <div className="flex gap-3">
            <Button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save Scenario'}</Button>
            <Button variant="outline" onClick={() => navigate('/scenarios')}>Cancel</Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
