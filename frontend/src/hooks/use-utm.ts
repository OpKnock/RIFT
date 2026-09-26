import { useEffect } from 'react'

export interface UtmTouch {
  utm_source: string | null
  utm_medium: string | null
  utm_campaign: string | null
  first_seen: string
}

const KEY = 'rift-utm-first-touch'

export function readUtm(): UtmTouch | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as UtmTouch
    if (typeof parsed !== 'object' || parsed === null) return null
    return parsed
  } catch {
    return null
  }
}

export function useUtm(): void {
  useEffect(() => {
    try {
      if (localStorage.getItem(KEY) !== null) return
      const q = new URLSearchParams(window.location.search)
      const source = q.get('utm_source')
      const medium = q.get('utm_medium')
      const campaign = q.get('utm_campaign')
      if (source || medium || campaign) {
        const touch: UtmTouch = {
          utm_source: source,
          utm_medium: medium,
          utm_campaign: campaign,
          first_seen: new Date().toISOString(),
        }
        localStorage.setItem(KEY, JSON.stringify(touch))
      }
    } catch {
      /* storage or URL unavailable */
    }
  }, [])
}
