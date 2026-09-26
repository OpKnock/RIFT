import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function Evidence() {
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/api/twin/evidence')
        if (!res.ok) throw new Error(`Server responded ${res.status}`)
        const body = await res.json()
        if (!cancelled) setData(body.data ?? body)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load evidence.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const download = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'rift-evidence.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Evidence</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">Live bundle from <code className="font-mono text-sm">GET /api/twin/evidence</code>. Synthetic demo data — not clinical validation.</p>
        </div>
        <Button variant="outline" onClick={download} disabled={!data}>Export JSON</Button>
      </div>
      <Card>
        <div className="p-6">
          {loading && <p className="text-sm text-secondary-500">Loading evidence…</p>}
          {error && <p className="text-sm text-error-600 dark:text-error-400" role="alert">{error}</p>}
          {!loading && !error && <pre className="text-xs overflow-x-auto bg-secondary-50 dark:bg-secondary-800 p-4 rounded-lg">{JSON.stringify(data, null, 2)}</pre>}
        </div>
      </Card>
    </div>
  )
}
