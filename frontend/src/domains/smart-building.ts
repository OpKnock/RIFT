import type { DomainDriver, DomainParams } from '@/domains/types'

export function defaultParams(): DomainParams {
  return { crowd: 1200, smoke: 4, capacity: 60, blockB: false }
}

export const driver: DomainDriver = {
  id: 'smart-building-emergency',
  scenarioName: 'smart-building-emergency',
  label: 'Smart-building emergency',

  fields: (bounds) => [
    { key: 'crowd', label: 'Crowd', min: bounds.crowd[0], max: bounds.crowd[1] },
    { key: 'smoke', label: 'Smoke', min: bounds.smoke[0], max: bounds.smoke[1] },
    { key: 'capacity', label: 'Corridor capacity', min: bounds.corridor_capacity[0], max: bounds.corridor_capacity[1] },
  ],

  defaults: defaultParams,

  templates: () => [
    { name: 'Evening rush', desc: 'High occupancy, moderate smoke, exit B open.', params: { crowd: 2500, smoke: 6, capacity: 80, blockB: false } },
    { name: 'Night low occupancy', desc: 'Sparse crowd, light smoke, full capacity.', params: { crowd: 300, smoke: 2, capacity: 60, blockB: false } },
    { name: 'Blocked exit drill', desc: 'Moderate crowd with corridor B closed.', params: { crowd: 1200, smoke: 4, capacity: 60, blockB: true } },
  ],

  toQuery: (params) => {
    const q: Record<string, string> = {
      crowd: String(params.crowd),
      smoke: String(params.smoke),
      corridor_capacity: String(params.capacity),
    }
    if (params.blockB) q.block_b = '1'
    return q
  },
}
