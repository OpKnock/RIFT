import { defineConfig } from '@playwright/test'

// Browser E2E against the PRODUCTION image (API serving the built
// bundle under /app). Run in CI after `docker build` + `docker run`:
//   npx playwright test -c playwright.config.ts
// Override the target with E2E_BASE_URL when running ad hoc.
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  timeout: 30000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:8080',
  },
})
