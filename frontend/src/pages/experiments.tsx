import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ExperimentRow {
  id: string
  name?: string
  status?: string
}

export function Experiments() {
  const [items, setItems] = useState<ExperimentRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/experiments')
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      const body = await res.json()
      const list = body?.data ?? body ?? []
      setItems(Array.isArray(list) ? list : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load experiments.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const create = async () => {
    if (!name.trim()) { setError('Experiment name is required.'); return }
    setError(null)
    try {
      const res = await fetch('/api/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      setName('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create experiment.')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Experiments</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">Live data from <code className="font-mono text-sm">GET / POST /api/experiments</code>.</p>
      </div>
      <Card>
        <div className="p-6 space-y-4">
          <div className="flex gap-3">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="New experiment name" />
            <Button onClick={create}>Create</Button>
          </div>
          {loading && <p className="text-sm text-secondary-500">Loading…</p>}
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {!loading && !error && items.length === 0 && <p className="text-sm text-secondary-500">No experiments yet.</p>}
          {!loading && !error && items.length > 0 && (
            <ul className="divide-y divide-secondary-100 dark:divide-secondary-800">
              {items.map((x) => (
                <li key={x.id} className="py-3 flex items-center justify-between">
                  <div><p className="font-medium font-mono text-sm">{x.id}</p><p className="text-sm text-secondary-500">{x.name || 'Untitled'}</p></div>
                  <Link className="text-primary-600 hover:underline text-sm" to={`/simulation`}>Open in Simulation</Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  )
}
