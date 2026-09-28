// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useEventStream } from './use-event-stream'

type Listener = (e: { data: string }) => void

class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  opts: { withCredentials?: boolean }
  listeners = new Map<string, Listener[]>()
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  constructor(url: string, opts: { withCredentials?: boolean } = {}) {
    this.url = url
    this.opts = opts
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, fn: Listener) {
    const list = this.listeners.get(type) || []
    list.push(fn)
    this.listeners.set(type, list)
  }

  emit(type: string, data: string) {
    for (const fn of this.listeners.get(type) || []) fn({ data })
  }

  close() {
    this.closed = true
  }
}

describe('useEventStream', () => {
  beforeEach(() => {
    MockEventSource.instances = []
    vi.stubGlobal('EventSource', MockEventSource)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('subscribes with credentials and dispatches parsed events', () => {
    const onEvent = vi.fn()
    const { result } = renderHook(() =>
      useEventStream({ topics: ['incidents.lifecycle'], onEvent }),
    )
    expect(MockEventSource.instances).toHaveLength(1)
    const source = MockEventSource.instances[0]
    expect(source.url).toContain('topics=incidents.lifecycle')
    expect(source.opts.withCredentials).toBe(true)

    act(() => {
      source.onopen?.()
    })
    expect(result.current).toBe(true)

    act(() => {
      source.emit('message', JSON.stringify({ topic: 'incidents.lifecycle', data: {} }))
    })
    expect(onEvent).toHaveBeenCalledWith({ topic: 'incidents.lifecycle', data: {} })
  })

  it('ignores malformed frames and reports disconnected on error', () => {
    const onEvent = vi.fn()
    const { result } = renderHook(() =>
      useEventStream({ topics: ['a'], onEvent }),
    )
    const source = MockEventSource.instances[0]
    act(() => {
      source.emit('message', 'not-json{{{')
    })
    expect(onEvent).not.toHaveBeenCalled()
    act(() => {
      source.onerror?.()
    })
    expect(result.current).toBe(false)
  })

  it('closes the stream on unmount', () => {
    const { unmount } = renderHook(() =>
      useEventStream({ topics: ['a'], onEvent: () => undefined }),
    )
    const source = MockEventSource.instances[0]
    unmount()
    expect(source.closed).toBe(true)
  })
})
