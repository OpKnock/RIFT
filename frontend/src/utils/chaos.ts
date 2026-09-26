export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export interface FuzzCell {
  crowd: number
  smoke: number
  capacity: number
}

export function fuzzParams(
  seed: number,
  count: number,
  bounds: { crowd: [number, number]; smoke: [number, number]; corridor_capacity: [number, number] }
): FuzzCell[] {
  const rand = mulberry32(seed)
  const cells: FuzzCell[] = []
  for (let i = 0; i < count; i++) {
    const pick = (lo: number, hi: number) => lo + rand() * (hi - lo)
    cells.push({
      crowd: Math.round(pick(bounds.crowd[0], bounds.crowd[1])),
      smoke: Math.round(pick(bounds.smoke[0], bounds.smoke[1]) * 10) / 10,
      capacity: Math.round(pick(bounds.corridor_capacity[0], bounds.corridor_capacity[1])),
    })
  }
  return cells
}

export function classifyDisturbance(p: Record<string, number>): 'independent' | 'compound' {
  return Object.keys(p).length > 1 ? 'compound' : 'independent'
}

export function groupFailureModes(
  items: Array<{ worst_perturbation: Record<string, number>; feasible_under_all: boolean }>
): Array<{ perturbation: string; count: number }> {
  const counts = new Map<string, number>()
  for (const item of items) {
    if (item.feasible_under_all) continue
    const key = JSON.stringify(item.worst_perturbation)
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([perturbation, count]) => ({ perturbation, count }))
    .sort((a, b) => b.count - a.count)
}

export function survivalRate(feasible: number, total: number): number | null {
  if (total === 0) return null
  return feasible / total
}
