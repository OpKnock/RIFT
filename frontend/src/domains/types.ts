export interface StateField {
  key: string
  label: string
  min: number
  max: number
}

export interface DomainParams {
  crowd: number
  smoke: number
  capacity: number
  blockB: boolean
}

export interface DomainTemplate {
  name: string
  desc: string
  params: DomainParams
}

export interface DomainDriver {
  id: string
  scenarioName: string
  label: string
  fields: (bounds: Record<string, [number, number]>) => StateField[]
  defaults: () => DomainParams
  templates: () => DomainTemplate[]
  toQuery: (params: DomainParams) => Record<string, string>
}

export const DOMAIN_REGISTRY: Array<{ id: string; note: string }> = [
  { id: 'smart-building-emergency', note: 'implemented: the one engine-supported scenario' },
]
