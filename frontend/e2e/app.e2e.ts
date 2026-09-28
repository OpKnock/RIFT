import { test, expect } from '@playwright/test'

// Production-image contract: the API serves the built React bundle
// under /app (vite base + router basename), / redirects there, and the
// HTML references only /app/ assets so favicon/manifest/scripts resolve.
test('root redirects to the canonical /app/ entry', async ({ request }) => {
  const res = await request.get('/', { maxRedirects: 0 });
  expect(res.status()).toBe(302);
  expect(res.headers()['location']).toBe('/app/');
});

test('/app/ serves the bundle with /app/ asset references', async ({ page }) => {
  const failed: string[] = [];
  page.on('response', (r) => {
    if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
  });
  const res = await page.goto('/app/');
  expect(res?.status()).toBe(200);
  const html = await page.content();
  expect(html).toContain('/app/assets/');
  expect(html).toContain('/app/manifest.webmanifest');
  expect(failed).toEqual([]);
});

test('deep links fall back to index.html (SPA)', async ({ page }) => {
  for (const path of ['/app/dashboard', '/app/runs/some-id']) {
    const res = await page.goto(path);
    expect(res?.status()).toBe(200);
    expect(await page.content()).toContain('<div id="root">');
  }
});

test('PWA assets resolve under /app/', async ({ request }) => {
  const icon = await request.get('/app/rift.svg');
  expect(icon.status()).toBe(200);
  expect(icon.headers()['content-type']).toContain('svg');
  const manifest = await request.get('/app/manifest.webmanifest');
  expect(manifest.status()).toBe(200);
  const body = await manifest.json();
  expect(body.start_url).toBe('/app/dashboard');
  expect(body.scope).toBe('/app/');
});

test('HTML responses carry the production CSP (fonts allowed)', async ({ request }) => {
  const res = await request.get('/app/');
  const csp = res.headers()['content-security-policy'] || '';
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain('https://fonts.googleapis.com');
  expect(csp).toContain('https://fonts.gstatic.com');
});

test('API is reachable same-origin', async ({ request }) => {
  const res = await request.get('/api/health');
  expect(res.status()).toBe(200);
  expect((await res.json()).status).toBe('ok');
});
