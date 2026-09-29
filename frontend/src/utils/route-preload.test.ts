import { describe, expect, it, vi } from 'vitest'
import { preloadAllRoutes } from './route-preload'

describe('preloadAllRoutes', () => {
  it('warms every loader and resolves when done', async () => {
    const calls: string[] = []
    const loaders = [
      () => Promise.resolve('a').then((v) => { calls.push(v); return v }),
      () => Promise.resolve('b').then((v) => { calls.push(v); return v }),
    ]
    await preloadAllRoutes(loaders)
    expect(calls.sort()).toEqual(['a', 'b'])
  })

  it('survives individual chunk failures (allSettled)', async () => {
    const ok = vi.fn(() => Promise.resolve('ok'))
    const bad = vi.fn(() => Promise.reject(new Error('chunk 404')))
    await expect(preloadAllRoutes([ok, bad])).resolves.toBeUndefined()
    expect(ok).toHaveBeenCalled()
    expect(bad).toHaveBeenCalled()
  })

  it('handles an empty loader list', async () => {
    await expect(preloadAllRoutes([])).resolves.toBeUndefined()
  })
})
