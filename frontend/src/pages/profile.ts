export const PROFILE_KEY = 'rift-profile-name'

export function readDisplayName(): string {
  try {
    return localStorage.getItem(PROFILE_KEY) || ''
  } catch {
    return ''
  }
}

export function writeDisplayName(name: string): void {
  try {
    if (name.trim()) {
      localStorage.setItem(PROFILE_KEY, name.trim())
    } else {
      localStorage.removeItem(PROFILE_KEY)
    }
  } catch {
    /* storage unavailable */
  }
}
