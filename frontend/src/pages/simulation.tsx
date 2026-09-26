import { useState } from 'react'
import { Play, RefreshCw, ChevronDown, ChevronUp, Download, CheckCircle, Loader2, XCircle, AlertCircle } from 'lucide-react'
import { cn } from '@/utils/cn'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/input'

const mockRuns = [
  { id: 'run-001', scenario: 'Cardiac Strain v2.1', status: 'completed', duration: '2m 34s', agreement: '87%', backend: 'exact', seed: 42, started: '2 hours ago' },
  { id: 'run-002', scenario: 'Sepsis Challenge v1.0', status: 'running', duration: '1m 12s', agreement: '—', backend: 'qaoa-simulator', seed: 123, started: '5 min ago' },
  { id: 'run-003', scenario: 'MIT-BIH Arrhythmia', status: 'completed', duration: '4m 12s', agreement: '92%', backend: 'exact', seed: 7, started: '1 day ago' },
  { id: 'run-004', scenario: 'FANTASIA Normal Sinus', status: 'failed', duration: '45s', agreement: '—', backend: 'qaoa-simulator', seed: 42, started: '3 days ago' },
  { id: 'run-005', scenario: 'CHFDB Heart Failure', status: 'completed', duration: '3m 18s', agreement: '78%', backend: 'exact', seed: 99, started: '1 week ago' },
]

const backends = ['exact', 'qaoa-simulator', 'qaoa-hardware', 'heuristic']

export function Simulation() {
  const [scenarioId, setScenarioId] = useState('')
  const [backend, setBackend] = useState('exact')
  const [seed, setSeed] = useState(42)
  const [perturbations, setPerturbations] = useState('')
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentRun, setCurrentRun] = useState<typeof mockRuns[0] | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  const handleRun = () => {
    if (!scenarioId) return
    setRunning(true)
    setProgress(0)
    
    // Simulate progress
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) {
          clearInterval(interval)
          return 100
        }
        return prev + Math.random() * 15
      })
    }, 500)

    // Simulate completion
    setTimeout(() => {
      clearInterval(interval)
      setProgress(100)
      setRunning(false)
      setCurrentRun({
        id: `run-${Date.now()}`,
        scenario: mockRuns.find(s => s.id === scenarioId)?.scenario || 'Unknown',
        status: 'completed',
        duration: `${Math.floor(Math.random() * 3) + 1}m ${Math.floor(Math.random() * 60)}s`,
        agreement: `${Math.floor(Math.random() * 20) + 70}%`,
        backend,
        seed,
        started: 'Just now',
      })
    }, 3000)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Simulation</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">
            Run counterfactual simulations with CHAOS robustness testing
          </p>
        </div>
      </div>

      {/* Configuration Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration */}
        <Card className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-4">Simulation Configuration</h2>
          
          <div className="space-y-4">
            <div>
              <label className="label">Scenario</label>
              <Select
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
                options={[
                  { value: '', label: 'Select a scenario...' },
                  { value: 'scn-001', label: 'Cardiac Strain v2.1' },
                  { value: 'scn-002', label: 'Sepsis Challenge v1.0' },
                  { value: 'scn-003', label: 'MIT-BIH Arrhythmia' },
                  { value: 'scn-004', label: 'FANTASIA Normal Sinus' },
                  { value: 'scn-005', label: 'CHFDB Heart Failure' },
                ]}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Optimization Backend</label>
                <Select
                  value={backend}
                  onChange={(e) => setBackend(e.target.value)}
                  options={backends.map(b => ({ value: b, label: b.charAt(0).toUpperCase() + b.slice(1).replace('-', ' ') }))}
                />
              </div>

              <div>
                <label className="label">Random Seed</label>
                <Input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                  min={0}
                  max={2147483647}
                />
              </div>
            </div>

            <div>
              <label className="label">Perturbations (comma-separated)</label>
              <Input
                value={perturbations}
                onChange={(e) => setPerturbations(e.target.value)}
                placeholder="e.g., noise:0.05, stale:2, bias:hr:5"
              />
              <p className="text-xs text-secondary-500 dark:text-secondary-400 mt-1">
                Format: perturbation_type:parameter,perturbation_type:parameter
              </p>
            </div>

            <div className="flex items-center gap-4 pt-4 border-t border-secondary-100 dark:border-secondary-800">
              <Button 
                onClick={handleRun} 
                disabled={running || !scenarioId}
                className="flex-1"
              >
                {running ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Run Simulation
                  </>
                )}
              </Button>
              <Button variant="secondary" onClick={() => setShowHistory(!showHistory)}>
                {showHistory ? <ChevronUp className="w-4 h-4 mr-2" /> : <ChevronDown className="w-4 h-4 mr-2" />}
                {showHistory ? 'Hide History' : 'Show History'}
              </Button>
            </div>
          </div>
        </Card>

        {/* Progress Panel */}
        <Card>
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-white mb-4">Simulation Progress</h2>
          
          {running && (
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-secondary-600 dark:text-secondary-400">Progress</span>
                  <span className="font-mono font-medium">{progress}%</span>
                </div>
                <div className="h-2 bg-secondary-200 dark:bg-secondary-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-600 transition-all duration-300 ease-out"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                  <p className="text-xs text-secondary-500 dark:text-secondary-400">Backend</p>
                  <p className="font-medium capitalize">{backend}</p>
                </div>
                <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                  <p className="text-xs text-secondary-500 dark:text-secondary-400">Seed</p>
                  <p className="font-mono">{seed}</p>
                </div>
                <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                  <p className="text-xs text-secondary-500 dark:text-secondary-400">Perturbations</p>
                  <p className="font-mono text-xs truncate">{perturbations || 'none'}</p>
                </div>
                <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                  <p className="text-xs text-secondary-500 dark:text-secondary-400">Progress</p>
                  <p className="font-mono font-medium">{progress}%</p>
                </div>
              </div>
            </div>
          )}
          
          {currentRun && !running && (
            <div className="p-4 rounded-lg bg-success-50 dark:bg-success-900/30 border border-success-200 dark:border-success-800">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-success-800 dark:text-success-200">Simulation Complete</h3>
                <Badge variant="success">Completed</Badge>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm mb-4">
                <div>
                  <p className="text-xs text-secondary-500">Agreement</p>
                  <p className="font-mono font-medium text-lg">{currentRun.agreement}</p>
                </div>
                <div>
                  <p className="text-xs text-secondary-500">Duration</p>
                  <p className="font-mono">{currentRun.duration}</p>
                </div>
                <div>
                  <p className="text-xs text-secondary-500">Backend</p>
                  <p className="font-mono capitalize">{currentRun.backend}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => { setCurrentRun(null); }}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Run Again
                </Button>
                <Button variant="ghost" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  Export
                </Button>
              </div>
            </div>
          )}
          
          {showHistory && (
            <div className="mt-6">
              <h3 className="font-semibold text-secondary-900 dark:text-white mb-3">Run History</h3>
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Run ID</th>
                      <th>Scenario</th>
                      <th>Status</th>
                      <th>Duration</th>
                      <th>Agreement</th>
                      <th>Backend</th>
                      <th>Seed</th>
                      <th>Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mockRuns.map((run) => {
                      const status = statusColors[run.status as keyof typeof statusColors] || statusColors.pending
                      return (
                        <tr key={run.id} className="hover:bg-secondary-50 dark:hover:bg-secondary-800/50">
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
                          <td className="text-secondary-600 dark:text-secondary-400 capitalize">{run.backend}</td>
                          <td className="font-mono">{run.seed}</td>
                          <td className="text-secondary-500 dark:text-secondary-400">{run.started}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

const statusColors = {
  completed: { bg: 'bg-success-100 dark:bg-success-900/30', text: 'text-success-700 dark:text-success-300', icon: CheckCircle },
  running: { bg: 'bg-primary-100 dark:bg-primary-900/30', text: 'text-primary-700 dark:text-primary-300', icon: Loader2 },
  failed: { bg: 'bg-error-100 dark:bg-error-900/30', text: 'text-error-700 dark:text-error-300', icon: XCircle },
  pending: { bg: 'bg-warning-100 dark:bg-warning-900/30', text: 'text-warning-700 dark:text-warning-300', icon: AlertCircle },
} as const