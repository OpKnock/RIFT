/**
 * Slim indeterminate progress bar pinned to the viewport top.
 * Used as the Suspense fallback AFTER boot, so route changes feel
 * instant instead of flashing the fullscreen loading screen.
 */
export function RouteProgress() {
  return (
    <div className="fixed top-0 left-0 right-0 z-50 h-1" role="progressbar" aria-label="Loading page">
      <div className="h-full w-1/3 bg-primary-600 dark:bg-primary-400 rounded-r-full animate-[route-progress_1s_ease-in-out_infinite]" />
      <style>{`@keyframes route-progress { 0% { margin-left: -33%; } 100% { margin-left: 100%; } }`}</style>
    </div>
  )
}
