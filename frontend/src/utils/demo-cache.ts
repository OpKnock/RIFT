import type { DemoPayload } from '@/services/api'

const PREFIX = 'rift-demo-cache:'
const MAX_ENTRIES = 30

export function demoCacheKey(params: { crowd: number; smoke: number; capacity: number; blockB: boolean }, engineVersion: string): string {
  return `${PREFIX}${engineVersion}:${params.crowd}|${params.smoke}|${params.capacity}|${params.blockB ? 1 : 0}`
}

export function readDemoCache(key: string): DemoPayload | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as DemoPayload
    if (!parsed || typeof parsed !== 'object' || !('guardian' in parsed)) return null
    return parsed
  } catch {
    return null
  }
}

export function writeDemoCache(key: string, payload: DemoPayload): void {
  try {
    localStorage.setItem(key, JSON.stringify(payload))
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith(PREFIX)) keys.push(k)
    }
    if (keys.length > MAX_ENTRIES) {
      localStorage.removeItem(keys[0])
    }
  } catch {
    /* storage unavailable: caching silently skipped */
  }
}

export function clearDemoCache(): number {
  let removed = 0
  try {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith(PREFIX)) keys.push(k)
    }
    for (const k of keys) {
      localStorage.removeItem(k)
      removed += 1
    }
  } catch {
    /* ignore */
  }
  return removed
}
