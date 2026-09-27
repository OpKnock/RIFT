import { useEffect, useRef, useState } from 'react'

export interface StreamEvent {
  topic: string
  data: unknown
}

interface Options {
  topics: string[]
  onEvent: (event: StreamEvent) => void
  enabled?: boolean
}

const STREAM_URL = `${import.meta.env.VITE_API_URL || '/api'}/events/stream`

/**
 * Server-Sent Events subscription with silent polling fallback.
 *
 * EventSource carries cookies (HttpOnly session works) but not the
 * localStorage bearer token, so on authenticated-non-cookie setups the
 * stream 401s and callers must keep their polling interval as backup.
 * Returns `live` so UIs can show which transport is active.
 */
export function useEventStream({ topics, onEvent, enabled = true }: Options): boolean {
  const [live, setLive] = useState(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent
  const topicKey = topics.join(',')

  useEffect(() => {
    const list = topicKey.split(',').map((t) => t.trim()).filter(Boolean)
    if (!enabled || list.length === 0 || typeof EventSource === 'undefined') {
      setLive(false)
      return
    }
    const url = `${STREAM_URL}?topics=${encodeURIComponent(list.join(','))}`
    let source: EventSource | null = null
    try {
      source = new EventSource(url)
    } catch {
      setLive(false)
      return
    }
    source.onopen = () => setLive(true)
    source.onerror = () => setLive(false)
    source.addEventListener('message', (e: MessageEvent) => {
      try {
        const parsed = JSON.parse((e as MessageEvent).data as string) as StreamEvent
        if (parsed && typeof parsed.topic === 'string') onEventRef.current(parsed)
      } catch {
        /* malformed frame: ignore, polling covers gaps */
      }
    })
    return () => {
      setLive(false)
      source?.close()
    }
  }, [enabled, topicKey])

  return live
}
