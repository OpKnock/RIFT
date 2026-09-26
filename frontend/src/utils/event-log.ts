export interface AppEvent {
  time: string
  kind: 'simulation' | 'approval' | 'sweep' | 'system'
  detail: string
}

const KEY = 'rift-event-log'
const MAX = 100

export function readEvents(): AppEvent[] {
  try {
    const raw = localStorage.getItem(KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function logEvent(kind: AppEvent['kind'], detail: string): AppEvent[] {
  const entry: AppEvent = { time: new Date().toISOString(), kind, detail }
  const next = [entry, ...readEvents()].slice(0, MAX)
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* storage unavailable: caller still gets the in-memory list */
  }
  return next
}
