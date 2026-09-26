import { useState } from 'react'
import { Search, LayoutDashboard, List, Eye, Edit, Copy, Plus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/input'

const statusBadges = {
  validated: { variant: 'success' as const, label: 'Validated' },
  draft: { variant: 'secondary' as const, label: 'Draft' },
  archived: { variant: 'outline' as const, label: 'Archived' },
}

const mockScenarios = [
  { id: 'scn-001', name: 'Cardiac Strain v2.1', description: '24h cardiac-strain risk prediction', variables: 8, perturbations: 3, status: 'validated', updated: '2 hours ago' },
  { id: 'scn-002', name: 'Sepsis Challenge v1.0', description: 'ICU sepsis onset prediction', variables: 6, perturbations: 2, status: 'draft', updated: '1 day ago' },
  { id: 'scn-003', name: 'MIT-BIH Arrhythmia', description: 'Arrhythmia classification from ECG', variables: 10, perturbations: 4, status: 'validated', updated: '1 week ago' },
  { id: 'scn-004', name: 'FANTASIA Normal Sinus', description: 'Normal sinus rhythm baseline', variables: 5, perturbations: 1, status: 'archived', updated: '2 weeks ago' },
  { id: 'scn-005', name: 'CHFDB Heart Failure', description: 'Heart failure progression model', variables: 8, perturbations: 3, status: 'validated', updated: '3 days ago' },
]

export function Scenarios() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'validated' | 'draft' | 'archived'>('all')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  const filteredScenarios = mockScenarios.filter((scenario) => {
    const matchesSearch = scenario.name.toLowerCase().includes(search.toLowerCase()) ||
      scenario.description.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || scenario.status === filter
    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Scenarios</h1>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1">
            Manage and create counterfactual scenarios
          </p>
        </div>
        <Button onClick={() => console.log('New scenario')}>
          <Plus className="w-4 h-4 mr-2" />
          New Scenario
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search scenarios..."
            className="w-full pl-10 pr-4 py-2 text-sm bg-secondary-50 dark:bg-secondary-800 border border-secondary-200 dark:border-secondary-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
        <Select
          value={filter}
          onChange={(e) => setFilter(e.target.value as any)}
          options={[
            { value: 'all', label: 'All Status' },
            { value: 'validated', label: 'Validated' },
            { value: 'draft', label: 'Draft' },
            { value: 'archived', label: 'Archived' },
          ]}
        />
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setViewMode('grid')} className={viewMode === 'grid' ? 'bg-primary-50 dark:bg-primary-900/30' : ''}>
            <LayoutDashboard className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setViewMode('list')} className={viewMode === 'list' ? 'bg-primary-50 dark:bg-primary-900/30' : ''}>
            <List className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Scenarios Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredScenarios.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} />
          ))}
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Variables</th>
                <th>Perturbations</th>
                <th>Status</th>
                <th>Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {mockScenarios.map((scenario) => (
                <tr key={scenario.id} className="hover:bg-secondary-50 dark:hover:bg-secondary-800/50">
                  <td className="font-medium">{scenario.name}</td>
                  <td className="text-secondary-600 dark:text-secondary-400 max-w-xs truncate">{scenario.description}</td>
                  <td className="font-mono">{scenario.variables}</td>
                  <td className="font-mono">{scenario.perturbations}</td>
                  <td>
                    <Badge variant={statusBadges[scenario.status as keyof typeof statusBadges].variant}>
                      {statusBadges[scenario.status as keyof typeof statusBadges].label}
                    </Badge>
                  </td>
                  <td className="text-secondary-500 dark:text-secondary-400">{scenario.updated}</td>
                  <td className="text-right">
                    <button className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors" aria-label="Edit">
                      <Edit className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ScenarioCard({ scenario }: { scenario: typeof mockScenarios[0] }) {
  const status = statusBadges[scenario.status as keyof typeof statusBadges]

  return (
    <div className="card-hover p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-secondary-900 dark:text-white text-lg">{scenario.name}</h3>
          <p className="text-secondary-600 dark:text-secondary-400 mt-1 text-sm">{scenario.description}</p>
        </div>
        <Badge variant={status.variant}>{status.label}</Badge>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4 text-center">
        <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
          <p className="text-2xl font-bold text-secondary-900 dark:text-white">{mockScenarios.find(s => s.id === mockScenarios[0].id)?.variables || 8}</p>
          <p className="text-xs text-secondary-500 dark:text-secondary-400">Variables</p>
        </div>
        <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
          <p className="text-2xl font-bold text-secondary-900 dark:text-white">{scenario.perturbations}</p>
          <p className="text-xs text-secondary-500 dark:text-secondary-400">Perturbations</p>
        </div>
        <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
          <p className="text-2xl font-bold text-secondary-900 dark:text-white">{scenario.status === 'validated' ? '✓' : '—'}</p>
          <p className="text-xs text-secondary-500 dark:text-secondary-400">Validated</p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-secondary-100 dark:border-secondary-800">
        <span className="text-xs text-secondary-500 dark:text-secondary-400">Updated {scenario.updated}</span>
        <div className="flex items-center gap-2">
          <button className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors" aria-label="View">
            <Eye className="w-4 h-4" />
          </button>
          <button className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors" aria-label="Edit">
            <Edit className="w-4 h-4" />
          </button>
          <button className="p-2 rounded-lg text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800 transition-colors" aria-label="Duplicate">
            <Copy className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

