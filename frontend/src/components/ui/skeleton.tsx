/**
 * Loading skeletons: reserved-space pulse blocks so pages don't flash
 * from blank to content (or blank to error) on first load.
 */
export function SkeletonLines({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-label="Loading" role="status">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-secondary-200 dark:bg-secondary-700 animate-pulse"
          style={{ width: `${92 - i * 13}%` }}
        />
      ))}
    </div>
  )
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-secondary-200 dark:border-secondary-700 p-6 space-y-3" aria-label="Loading" role="status">
      <div className="h-5 w-1/3 rounded bg-secondary-200 dark:bg-secondary-700 animate-pulse" />
      <SkeletonLines rows={3} />
    </div>
  )
}
