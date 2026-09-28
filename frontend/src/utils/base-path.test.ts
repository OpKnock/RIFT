import { describe, expect, it } from 'vitest'
import { joinBase, appPath } from './base-path'

describe('joinBase', () => {
  it('joins base and absolute path with one slash', () => {
    expect(joinBase('/app', '/dashboard')).toBe('/app/dashboard')
  })

  it('accepts relative paths', () => {
    expect(joinBase('/app', 'dashboard')).toBe('/app/dashboard')
  })

  it('keeps root base intact', () => {
    expect(joinBase('/', '/dashboard')).toBe('/dashboard')
  })

  it('strips trailing slashes from base', () => {
    expect(joinBase('/app/', '/runs/abc')).toBe('/app/runs/abc')
  })

  it('maps root path to the base with trailing slash', () => {
    expect(joinBase('/app', '/')).toBe('/app/')
  })
})

describe('appPath', () => {
  it('always yields an absolute in-app path', () => {
    expect(appPath('/docs')).toMatch(/^\/.*\/docs$/)
    expect(appPath('settings')).toContain('/settings')
  })
})
