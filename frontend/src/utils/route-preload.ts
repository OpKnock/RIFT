/**
 * Route chunk preloading: after first paint, fetch every lazily-loaded
 * page chunk during idle time so later navigations never hit a Suspense
 * fallback (no more fullscreen loading screen on every click).
 */
export function preloadAllRoutes(loaders: Array<() => Promise<unknown>>): Promise<void> {
  return Promise.allSettled(loaders.map((load) => load())).then(() => undefined);
}

/** Run a callback when the browser is idle (fallback: soon after). */
export function onIdle(callback: () => void): () => void {
  if (typeof requestIdleCallback !== 'undefined') {
    const id = requestIdleCallback(() => callback());
    return () => cancelIdleCallback(id);
  }
  const id = window.setTimeout(callback, 800);
  return () => window.clearTimeout(id);
}
