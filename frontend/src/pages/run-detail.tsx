import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function RunDetail() {
  const { id } = useParams()
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(`/api/runs/${id}`)
        if (!res.ok) throw new Error(`Server responded ${res.status}`)
        const body = await res.json()
        if (!cancelled) setData(body.data ?? body)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load run.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [id])

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold font-mono text-secondary-900 dark:text-white">{id}</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">Live data from <code className="font-mono text-sm">GET /api/runs/{'{id}'}</code>.</p>
      </div>
      <Card>
        <div className="p-6">
          {loading && <p className="text-sm text-secondary-500">Loading…</p>}
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {!loading && !error && <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(data, null, 2)}</pre>}
          <div className="mt-4"><Link to="/runs"><Button variant="outline">Back to Runs</Button></Link></div>
        </div>
      </Card>
    </div>
  )
}
