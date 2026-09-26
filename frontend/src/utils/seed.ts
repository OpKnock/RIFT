import { config } from '@/config'

export function parseSeed(raw: string): { ok: true; value: number | null } | { ok: false; error: string } {
  const trimmed = raw.trim()
  if (trimmed === '') return { ok: true, value: null }
  if (!/^-?\d+$/.test(trimmed)) {
    return { ok: false, error: 'Seed must be an integer (or empty for none).' }
  }
  const value = Number(trimmed)
  if (!Number.isSafeInteger(value) || Math.abs(value) > config.maxSeed) {
    return { ok: false, error: `Seed must satisfy abs <= 2^62 (server rule).` }
  }
  return { ok: true, value }
}
