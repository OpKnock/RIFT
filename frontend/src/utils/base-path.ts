// Base-aware navigation for the production sub-path deployment.
//
// The bundle is served under /app (vite `base` + BrowserRouter `basename`),
// so full-page navigations (window.location.href) must be prefixed.
// In-page <Link>/<Navigate> already respect the router basename and are
// unaffected. Derives the prefix from vite's BASE_URL so it tracks config.
const BASE = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');

export function appPath(path: string): string {
  return `${BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

export function goApp(path: string): void {
  window.location.href = appPath(path);
}
