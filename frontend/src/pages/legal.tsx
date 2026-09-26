import { Shield, FileText, Cookie, Scale } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function Legal() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Legal & Compliance</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          The documents that actually exist in this project. No placeholder links — every button below opens a real page.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4 w-fit">
              <Shield className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Privacy Policy</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4 text-sm">
              Data collection, rights, retention, international transfers. Covers DPA terms, subprocessors, and retention schedules.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/privacy'}>
              Read Policy
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4 w-fit">
              <FileText className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Terms of Service</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4 text-sm">
              Research-prototype terms, disclaimers, liability limits, governing law.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/terms'}>
              Read Terms
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4 w-fit">
              <Cookie className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Cookie Policy</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4 text-sm">
              Essential-only cookies. No tracking, advertising, or third-party analytics.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/cookies'}>
              Read Policy
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4 w-fit">
              <Scale className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">License & Commercial Position</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4 text-sm">
              Code: <span className="font-mono">AGPL-3.0-or-later</span>. Data: no raw real-patient data committed — synthetic plus open-access public datasets only.
              Research prototype: no commercial deployment, no clinical validation, regulatory path external.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/docs'}>
              Read Docs Index
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
