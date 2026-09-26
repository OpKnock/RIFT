export const EXPECTED_ENGINE_VERSION = '1.0.0'

export const config = {
  apiBase: import.meta.env.VITE_API_URL || '/api',
  env: import.meta.env.MODE,
  isDev: import.meta.env.DEV,
  monitorPollMs: 5000,
  localHistoryMax: 20,
  demoCacheMax: 30,
  eventLogMax: 100,
  requestTimeoutMs: 60000,
  maxSeed: 2 ** 62,
} as const

export type AppConfig = typeof config
