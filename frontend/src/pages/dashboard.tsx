import { GitBranch, Play, Database, FlaskConical, Scale, AlertTriangle, CheckCircle, AlertCircle, XCircle, Loader2, Info } from 'lucide-react'
import { cn } from '@/utils/cn'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const stats = [
  { name: 'Active Scenarios', value: '12', change: '+2', delta: 2, icon: GitBranch, color: 'primary' },
  { name: 'Completed Runs', value: '147', change: '+12', delta: 12, icon: Database, color: 'success' },
  { name: 'Active Experiments', value: '3', change: '+0', delta: 0, icon: FlaskConical, color: 'primary' },
  { name: 'Avg Agreement', value: '87%', change: '+3%', delta: 3, icon: Scale, color: 'warning' },
]

const recentRuns = [
  { id: 'run-001', scenario: 'Cardiac Strain v2.1', status: 'completed', duration: '2m 34s', agreement: '87%', started: '2 hours ago' },
  { id: 'run-002', scenario: 'Sepsis Challenge v1.0', status: 'running', duration: '1m 12s', agreement: '—', started: '5 min ago' },
  { id: 'run-003', scenario: 'MIT-BIH Arrhythmia', status: 'completed', duration: '4m 12s', agreement: '92%', started: '1 day ago' },
  { id: 'run-004', scenario: 'FANTASIA Normal Sinus', status: 'failed', duration: '45s', agreement: '—', started: '3 days ago' },
  { id: 'run-005', scenario: 'CHFDB Heart Failure', status: 'completed', duration: '3m 18s', agreement: '78%', started: '1 week ago' },
]

const alerts = [
  { type: 'warning', message: 'Phase 11 hardware run completed - advantage comparison pending', time: '2 hours ago' },
  { type: 'info', message: 'New PhysioNet datasets ingested: NSRDB, FANTASIA, EDB, LTAFDB, QTDB', time: '4 hours ago' },
  { type: 'success', message: 'Calibration methods updated: Isotonic & Beta regression added', time: '1 day ago' },
  { type: 'warning', message: 'Sample adequacy below threshold for external validation (5/54 events)', time: '2 days ago' },
]

export function Dashboard() {
  const statusColors = {
    completed: { bg: 'bg-success-100 dark:bg-success-900/30', text: 'text-success-700 dark:text-success-300', icon: CheckCircle },
    running: { bg: 'bg-primary-100 dark:bg-primary-900/30', text: 'text-primary-700 dark:text-primary-300', icon: Loader2 },
    failed: { bg: 'bg-error-100 dark:bg-error-900/30', text: 'text-error-700 dark:text-error-300', icon: XCircle },
    pending: { bg: 'bg-warning-100 dark:bg-warning-900/30', text: 'text-warning-700 dark:text-warning-300', icon: AlertCircle },
  } as const

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Dashboard</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">
            Counterfactual Decision Intelligence Platform — Research Prototype
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm">
            <GitBranch className="w-4 h-4 mr-2" />
            New Scenario
          </Button>
          <Button>
            <Play className="w-4 h-4 mr-2" />
            Run Simulation
          </Button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.name} className="card-hover">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-secondary-600 dark:text-secondary-400">{stat.name}</p>
                <p className="text-3xl font-bold text-secondary-900 dark:text-white mt-1">{stat.value}</p>
                {stat.delta !== 0 && (
                  <p className={cn(
                    'text-sm mt-1',
                    stat.delta > 0 ? 'text-success-600 dark:text-success-400' : 'text-error-600 dark:text-error-400'
                  )}>
                    {stat.change} vs last period
                  </p>
                )}
              </div>
              <div className={cn(
                'p-3 rounded-xl',
                stat.color === 'primary' && 'bg-primary-100 dark:bg-primary-900/30',
                stat.color === 'success' && 'bg-success-100 dark:bg-success-900/30',
                stat.color === 'warning' && 'bg-warning-100 dark:bg-warning-900/30',
                stat.color === 'error' && 'bg-error-100 dark:bg-error-900/30'
              )}>
                {stat.icon && <stat.icon className={cn('w-6 h-6', 
                  stat.color === 'primary' && 'text-primary-600',
                  stat.color === 'success' && 'text-success-600',
                  stat.color === 'warning' && 'text-warning-600',
                  stat.color === 'error' && 'text-error-600'
                )} aria-hidden="true" />}
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Runs */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-secondary-900 dark:text-white">Recent Runs</h2>
            <Button variant="ghost" size="sm" onClick={() => window.location.href = '/runs'}>
              View All
            </Button>
          </div>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Scenario</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Agreement</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => {
                  const status = statusColors[run.status as keyof typeof statusColors] || statusColors.pending
                  return (
                    <tr key={run.id}>
                      <td className="font-mono text-sm">{run.id}</td>
                      <td className="font-medium">{run.scenario}</td>
                      <td>
                        <Badge className={cn(status.bg, status.text)}>
                          <status.icon className="w-3 h-3 mr-1.5" aria-hidden="true" />
                          {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="font-mono text-sm">{run.duration}</td>
                      <td className="font-mono">{run.agreement}</td>
                      <td className="text-secondary-500 dark:text-secondary-400">{run.started}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Alerts & Quick Actions */}
        <Card>
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-4">Alerts & Notifications</h2>
          <div className="space-y-3">
            {alerts.map((alert, index) => (
              <div key={index} className={cn(
                'flex items-start gap-3 p-3 rounded-lg border',
                alert.type === 'warning' && 'border-warning-200 bg-warning-50 dark:border-warning-800 dark:bg-warning-900/30',
                alert.type === 'error' && 'border-error-200 bg-error-50 dark:border-error-800 dark:bg-error-900/30',
                alert.type === 'success' && 'border-success-200 bg-success-50 dark:border-success-800 dark:bg-success-900/30',
                alert.type === 'info' && 'border-primary-200 bg-primary-50 dark:border-primary-800 dark:bg-primary-900/30',
              )}>
                <div className="flex-shrink-0 mt-0.5">
                  {alert.type === 'warning' && <AlertTriangle className="w-5 h-5 text-warning-600 dark:text-warning-400" />}
                  {alert.type === 'error' && <AlertCircle className="w-5 h-5 text-error-600 dark:text-error-400" />}
                  {alert.type === 'success' && <CheckCircle className="w-5 h-5 text-success-600 dark:text-success-400" />}
                  {alert.type === 'info' && <Info className="w-5 h-5 text-primary-600 dark:text-primary-400" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-secondary-900 dark:text-white">{alert.message}</p>
                  <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-0.5">{alert.time}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Quick Actions Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="card-hover group">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors">
              <GitBranch className="w-6 h-6 text-primary-600 dark:text-primary-400" aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-semibold text-secondary-900 dark:text-white">New Scenario</h3>
              <p className="text-sm text-secondary-500 dark:text-secondary-400">Create a new scenario</p>
            </div>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-primary-100 dark:bg-primary-900/30 group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors">
              <Play className="w-6 h-6 text-primary-600 dark:text-primary-400" aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-semibold text-secondary-900 dark:text-white">Run Simulation</h3>
              <p className="text-sm text-secondary-500 dark:text-secondary-400">Execute a simulation</p>
            </div>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-success-100 dark:bg-success-900/30 group-hover:bg-success-200 dark:group-hover:bg-success-800/50 transition-colors">
              <Scale className="w-6 h-6 text-success-600 dark:text-success-400" aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-semibold text-secondary-900 dark:text-white">View Evidence</h3>
              <p className="text-sm text-secondary-500 dark:text-secondary-400">Review evidence bundles</p>
            </div>
          </div>
        </Card>

        <Card className="card-hover group">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-warning-100 dark:bg-warning-900/30 group-hover:bg-warning-200 dark:group-hover:bg-warning-800/50 transition-colors">
              <FlaskConical className="w-6 h-6 text-warning-600 dark:text-warning-400" aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-semibold text-secondary-900 dark:text-white">New Experiment</h3>
              <p className="text-sm text-secondary-500 dark:text-secondary-400">Design an experiment</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}