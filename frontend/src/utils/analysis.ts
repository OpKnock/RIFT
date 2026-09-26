import type { DemoPayload } from '@/services/api'

export interface Scored {
  nominal: number
  worst: number
}

export function paretoFront(items: Scored[]): boolean[] {
  return items.map((item, i) =>
    !items.some((other, j) => {
      if (i === j) return false
      return other.nominal <= item.nominal && other.worst <= item.worst &&
        (other.nominal < item.nominal || other.worst < item.worst)
    })
  )
}

export function scoreStats(scores: number[]): { min: number; max: number; mean: number; count: number } | null {
  if (scores.length === 0) return null
  const sum = scores.reduce((a, b) => a + b, 0)
  return { min: Math.min(...scores), max: Math.max(...scores), mean: sum / scores.length, count: scores.length }
}

export function equivalentGroups(policies: Array<Record<string, number>>): number[][] {
  const groups: number[][] = []
  const seen = new Array(policies.length).fill(false)
  for (let i = 0; i < policies.length; i++) {
    if (seen[i]) continue
    const group = [i]
    seen[i] = true
    for (let j = i + 1; j < policies.length; j++) {
      if (!seen[j] && JSON.stringify(policies[j]) === JSON.stringify(policies[i])) {
        group.push(j)
        seen[j] = true
      }
    }
    if (group.length > 1) groups.push(group)
  }
  return groups
}

export function confidenceFor(method: string): string {
  const m = method.toLowerCase()
  if (m.includes('exact')) return 'Optimal for the stated objective — exhaustive enumeration.'
  if (m.includes('cvar')) return 'Approximate — tail-sampled simulator output with reported energy.'
  if (m.includes('qaoa') || m.includes('simulator')) return 'Approximate — simulator output with reported energy and gap.'
  if (m.includes('heuristic')) return 'Approximate — heuristic output, gap reported where measurable.'
  return 'See reported energy and gap.'
}

export function bestNominal(robust: DemoPayload['robust']): number | null {
  if (robust.length === 0) return null
  let best = 0
  for (let i = 1; i < robust.length; i++) {
    if (robust[i].score < robust[best].score) best = i
  }
  return best
}

export function bestWorstCase(robust: DemoPayload['robust']): number | null {
  if (robust.length === 0) return null
  let best = 0
  for (let i = 1; i < robust.length; i++) {
    if (robust[i].worst_case_score < robust[best].worst_case_score) best = i
  }
  return best
}
