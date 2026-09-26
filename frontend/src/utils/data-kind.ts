export type DataKind = 'synthetic' | 'simulated' | 'real' | 'validated' | 'experimental'

const LABELS: Record<DataKind, string> = {
  synthetic: 'synthetic',
  simulated: 'simulated',
  real: 'real',
  validated: 'validated',
  experimental: 'experimental',
}

export function labelOf(kind: DataKind): string {
  return LABELS[kind]
}

export function detectTwinKind(dataset: string | undefined): DataKind {
  const text = (dataset || '').toLowerCase()
  if (text.includes('not clinically validated') || text.includes('synthetic')) return 'synthetic'
  if (text.includes('validated')) return 'validated'
  return 'experimental'
}

export function detectEngineKind(): DataKind {
  return 'simulated'
}
