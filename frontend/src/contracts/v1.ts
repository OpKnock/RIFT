import { z } from 'zod'

export const CONTRACT_VERSION = 'v1'

const MAX_SEED = 2 ** 62

export const seedSchema = z.number().int().refine((s) => Math.abs(s) <= MAX_SEED, {
  message: `seed must be an integer with abs <= 2^62`,
})

export const demoParamsSchema = z.object({
  crowd: z.number().finite(),
  smoke: z.number().finite(),
  corridor_capacity: z.number().finite(),
  block_b: z.boolean(),
})

export const perturbationSchema = z.record(z.string(), z.number().finite()).refine(
  (p) => Object.keys(p).length > 0 && Object.keys(p).every((k) => k.trim().length > 0),
  { message: 'each perturbation must be a non-empty object with numeric amounts' }
)

export const experimentSpecSchema = z.object({
  name: z.string().trim().min(1, 'name is required').max(200),
  scenario_name: z.string().default('smart-building-emergency'),
  initial_state: z.record(z.string(), z.number().finite()).default({}),
  perturbations: z.array(perturbationSchema).max(32).default([]),
  policy_variables: z.array(z.string().trim().min(1).max(64)).max(16).default([]),
  optimizer: z.enum(['exact', 'qaoa-expectation', 'qaoa-cvar']).default('exact'),
  backend: z.enum(['statevector-simulator', 'none']).default('statevector-simulator'),
  seed: seedSchema.nullable().default(null),
  description: z.string().max(2000).default(''),
})

export type ExperimentSpecV1 = z.infer<typeof experimentSpecSchema>

export const reviewSchema = z.object({
  action: z.enum(['ACCEPT', 'REJECT', 'OVERRIDE', 'REQUEST_REVIEW']),
  evidence_id: z.string().trim().min(1, 'evidence_id is required'),
  reviewer_id: z.string().trim().min(1, 'reviewer_id is required'),
  rationale: z.string().default(''),
  supersedes: z.string().nullable().default(null),
})

export type ReviewV1 = z.infer<typeof reviewSchema>

export function formatZodError(error: z.ZodError): string {
  return error.issues.map((i) => `${i.path.join('.') || 'value'}: ${i.message}`).join('; ')
}
