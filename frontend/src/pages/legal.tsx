import { Shield, FileText, Clock, Lock, Globe, Database, User, Settings, Cookie } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function Legal() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Legal & Compliance</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Legal documents, compliance information, and data protection
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Shield className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Privacy Policy</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              How we collect, use, and protect your data in compliance with GDPR, DPDP, and other regulations.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/privacy'}>
              Read Policy
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <FileText className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Terms of Service</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              Terms and conditions governing your use of RIFT platform and services.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/terms'}>
              Read Terms
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Cookie className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Cookie Policy</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              How we use cookies and similar technologies on our platform.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/cookies'}>
              Read Policy
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Lock className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Data Processing Addendum</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              Standard contractual clauses for data processing under GDPR Article 28.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/dpa'}>
              View DPA
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Globe className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Subprocessors</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              List of subprocessors and third-party services we use.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/subprocessors'}>
              View List
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Database className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Data Retention</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              Our data retention schedules and deletion policies.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/retention'}>
              View Policy
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <User className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Data Subject Rights</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              How to exercise your rights under GDPR, DPDP, and other regulations.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/rights'}>
              Learn More
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Settings className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Security Practices</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              Our security measures, certifications, and incident response procedures.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/security'}>
              View Details
            </Button>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="p-6">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors mb-4">
              <Clock className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            </div>
            <h3 className="font-semibold text-secondary-900 dark:text-white text-lg mb-2">Data Retention Schedule</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              Detailed retention periods for different data categories.
            </p>
            <Button variant="outline" size="sm" onClick={() => window.location.href = '/legal/retention-schedule'}>
              View Schedule
            </Button>
          </div>
        </Card>
      </div>

      <div className="mt-8">
        <h2 className="text-2xl font-bold text-secondary-900 dark:text-white mb-4">Quick Links</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Button variant="outline" onClick={() => window.location.href = '/legal/privacy'}>
            <Shield className="w-4 h-4 mr-2" />
            Privacy Policy
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/terms'}>
            <FileText className="w-4 h-4 mr-2" />
            Terms of Service
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/cookies'}>
            <Cookie className="w-4 h-4 mr-2" />
            Cookie Policy
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/dpa'}>
            <Lock className="w-4 h-4 mr-2" />
            DPA
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/subprocessors'}>
            <Globe className="w-4 h-4 mr-2" />
            Subprocessors
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/retention'}>
            <Database className="w-4 h-4 mr-2" />
            Retention Policy
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/rights'}>
            <User className="w-4 h-4 mr-2" />
            Data Rights
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/legal/security'}>
            <Settings className="w-4 h-4 mr-2" />
            Security
          </Button>
        </div>
      </div>
    </div>
  )
}