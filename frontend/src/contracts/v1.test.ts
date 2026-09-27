import { describe, expect, it } from 'vitest'
import {
  CONTRACT_VERSION,
  demoParamsSchema,
  experimentSpecSchema,
  formatZodError,
  perturbationSchema,
  reviewSchema,
  seedSchema,
} from './v1'

describe('contracts v1', () => {
  it('pins the contract version', () => {
    expect(CONTRACT_VERSION).toBe('v1')
  })

  it('accepts a valid demo params payload', () => {
    const out = demoParamsSchema.safeParse({ crowd: 100, smoke: 5, corridor_capacity: 50, block_b: false })
    expect(out.success).toBe(true)
  })

  it('rejects non-finite demo params', () => {
    expect(demoParamsSchema.safeParse({ crowd: NaN, smoke: 5, corridor_capacity: 50, block_b: false }).success).toBe(false)
  })

  it('accepts a minimal experiment spec with defaults', () => {
    const out = experimentSpecSchema.safeParse({ name: 'smoke' })
    expect(out.success).toBe(true)
    if (out.success) {
      expect(out.data.optimizer).toBe('exact')
      expect(out.data.scenario_name).toBe('smart-building-emergency')
    }
  })

  it('rejects unknown optimizers and empty perturbations', () => {
    expect(experimentSpecSchema.safeParse({ name: 'x', optimizer: 'quantum-magic' }).success).toBe(false)
    expect(perturbationSchema.safeParse({}).success).toBe(false)
    expect(perturbationSchema.safeParse({ smoke: 2 }).success).toBe(true)
  })

  it('enforces the seed bound shared with the backend', () => {
    expect(seedSchema.safeParse(2 ** 62).success).toBe(true)
    // NB: 2**62+2 is not representable in a double (rounds to 2**62),
    // so the out-of-range probe must be exactly representable.
    expect(seedSchema.safeParse(2 ** 63).success).toBe(false)
    expect(seedSchema.safeParse(1.5).success).toBe(false)
  })

  it('requires reviewer identity on reviews', () => {
    expect(reviewSchema.safeParse({ action: 'ACCEPT', evidence_id: 'ev', reviewer_id: '' }).success).toBe(false)
    expect(reviewSchema.safeParse({ action: 'ACCEPT', evidence_id: 'ev', reviewer_id: 'alice' }).success).toBe(true)
  })

  it('formats zod errors readably', () => {
    const out = experimentSpecSchema.safeParse({ name: '' })
    expect(out.success).toBe(false)
    if (!out.success) {
      expect(formatZodError(out.error)).toContain('name')
    }
  })
})
