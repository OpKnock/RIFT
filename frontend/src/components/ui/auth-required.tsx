import { Link } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

/**
 * Professional empty state for 401s: the server requires authentication
 * and this browser has none. Points at Settings → API Token instead of
 * dumping a raw error banner.
 */
export function AuthRequired({ resource }: { resource: string }) {
  return (
    <Card>
      <div className="p-6 flex items-start gap-4">
        <div className="shrink-0 rounded-lg bg-secondary-100 dark:bg-secondary-800 p-2.5">
          <KeyRound className="w-5 h-5 text-secondary-500" aria-hidden />
        </div>
        <div className="space-y-2">
          <h2 className="font-semibold text-secondary-900 dark:text-white">Authentication required</h2>
          <p className="text-sm text-secondary-600 dark:text-secondary-400">
            This server gates {resource} behind authentication, and this browser isn&apos;t signed in.
            Add your service token once — it&apos;s exchanged for an HttpOnly session cookie, never stored in plain text.
          </p>
          <Link to="/settings?tab=api">
            <Button size="sm">Open API token settings</Button>
          </Link>
        </div>
      </div>
    </Card>
  )
}
