import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, apiErrorMessage } from '@/services/api'

const POLL_MS = 10000

type IncidentType = 'alert_firing' | 'guardian_withhold' | 'prediction_anomaly' | 'data_quality' | 'model_drift' | 'decision_failure' | 'manual'
type IncidentSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info'

interface Incident {
  id: string
  type: string
  severity: string
  title: string
  description: string
  status: string
  created_at: string
  updated_at: string
  acknowledged_at: string | null
  resolved_at: string | null
  closed_at: string | null
  owner: string | null
  trigger_alert_id: string | null
  affected_decision_ids: string[]
  guardian_findings: any[]
  timeline: Array<{ timestamp: string; actor: string; action: string; note: string; metadata: any }>
  tags: string[]
  metadata: any
}

interface Decision {
  id: string
  scenario_id: string
  policy: Record<string, number>
  proposed_by: string
  proposed_at: string
  status: string
  guardian_verdict: any
  approved_by: string | null
  approved_at: string | null
  rejected_by: string | null
  rejected_at: string | null
  overridden_by: string | null
  overridden_at: string | null
  executed_at: string | null
  expired_at: string | null
  execution_result: any
  linked_incident_id: string | null
  review_requested_by: string | null
  review_requested_at: string | null
  timeline: Array<{ timestamp: string; actor: string; action: string; note: string; guardian_verdict: any; metadata: any }>
  metadata: any
}

export function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'incidents' | 'decisions'>('incidents')
  const [filters, setFilters] = useState({ status: '', severity: '', type: '' })
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [selectedDecision, setSelectedDecision] = useState<Decision | null>(null)
  const [newIncident, setNewIncident] = useState({ title: '', description: '', type: 'manual' as IncidentType, severity: 'medium' as IncidentSeverity, tags: '' })
  const [creating, setCreating] = useState(false)

  const fetchIncidents = async () => {
    try {
      const data = await api.getIncidents(filters)
      setIncidents(data)
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to load incidents'))
    }
  }

  const fetchDecisions = async () => {
    try {
      const data = await api.getDecisions()
      setDecisions(data)
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to load decisions'))
    }
  }

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      await Promise.all([fetchIncidents(), fetchDecisions()])
      if (!cancelled) setLoading(false)
    }
    load()
    const timer = setInterval(load, POLL_MS)
    return () => { cancelled = true; clearInterval(timer) }
  }, [filters])

  const createIncident = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await api.createIncident({
        ...newIncident,
        tags: newIncident.tags.split(',').map(t => t.trim()).filter(Boolean),
      })
      setNewIncident({ title: '', description: '', type: 'manual', severity: 'medium', tags: '' })
      await fetchIncidents()
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to create incident'))
    } finally {
      setCreating(false)
    }
  }

  const incidentAction = async (incident: Incident, action: string, note: string) => {
    try {
      await api.incidentAction(incident.id, action, note)
      await fetchIncidents()
      if (selectedIncident?.id === incident.id) setSelectedIncident(null)
    } catch (e) {
      setError(apiErrorMessage(e, `Failed to ${action} incident`))
    }
  }

  const decisionAction = async (decision: Decision, action: string, note: string) => {
    try {
      await api.decisionAction(decision.id, action, note)
      await fetchDecisions()
      if (selectedDecision?.id === decision.id) setSelectedDecision(null)
    } catch (e) {
      setError(apiErrorMessage(e, `Failed to ${action} decision`))
    }
  }

  const severityColor = (s: string): 'error' | 'warning' | 'secondary' => {
    const colors: Record<string, 'error' | 'warning' | 'secondary'> = {
      critical: 'error', high: 'error', medium: 'warning', low: 'secondary', info: 'secondary'
    }
    return colors[s] || 'secondary'
  }

  const statusColor = (s: string): 'error' | 'warning' | 'secondary' | 'success' => {
    const colors: Record<string, 'error' | 'warning' | 'secondary' | 'success'> = {
      open: 'error', acknowledged: 'warning', investigating: 'secondary', resolved: 'success', closed: 'secondary'
    }
    return colors[s] || 'secondary'
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Live Operations</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Incident lifecycle and decision approval workflow. Polls every 10s.
        </p>
      </div>

      {error && <div className="p-3 rounded-lg bg-error-50 dark:bg-error-900/20 border border-error-200 dark:border-error-800 text-error-600 dark:text-error-400" role="alert">{error}</div>}

      <Tabs value={activeTab} onValueChange={(v: string) => setActiveTab(v as 'incidents' | 'decisions')} className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="incidents">Incidents ({incidents.length})</TabsTrigger>
          <TabsTrigger value="decisions">Decisions ({decisions.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="incidents" className="space-y-4">
          {/* Filters */}
          <Card>
            <div className="p-4 flex flex-wrap gap-4">
              <select value={filters.status} onChange={(e) => setFilters(f => ({ ...f, status: e.target.value }))} className="w-40 px-3 py-2 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800 text-sm">
                <option value="">All</option>
                <option value="open">Open</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="investigating">Investigating</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
              <select value={filters.severity} onChange={(e) => setFilters(f => ({ ...f, severity: e.target.value }))} className="w-40 px-3 py-2 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800 text-sm">
                <option value="">All</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </select>
              <select value={filters.type} onChange={(e) => setFilters(f => ({ ...f, type: e.target.value }))} className="w-48 px-3 py-2 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800 text-sm">
                <option value="">All</option>
                <option value="alert_firing">Alert Firing</option>
                <option value="guardian_withhold">Guardian Withhold</option>
                <option value="prediction_anomaly">Prediction Anomaly</option>
                <option value="data_quality">Data Quality</option>
                <option value="model_drift">Model Drift</option>
                <option value="decision_failure">Decision Failure</option>
                <option value="manual">Manual</option>
              </select>
            </div>
          </Card>

{/* Create Incident */}
          <Card>
            <form onSubmit={createIncident} className="p-4 space-y-3">
              <h3 className="font-medium text-secondary-900 dark:text-white">Create Incident</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Input placeholder="Title" value={newIncident.title} onChange={e => setNewIncident(n => ({ ...n, title: e.target.value }))} required />
                <select value={newIncident.type} onChange={(e) => setNewIncident(n => ({ ...n, type: e.target.value as IncidentType }))} className="px-3 py-2 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800 text-sm">
                  <option value="alert_firing">Alert Firing</option>
                  <option value="guardian_withhold">Guardian Withhold</option>
                  <option value="prediction_anomaly">Prediction Anomaly</option>
                  <option value="data_quality">Data Quality</option>
                  <option value="model_drift">Model Drift</option>
                  <option value="decision_failure">Decision Failure</option>
                  <option value="manual">Manual</option>
                </select>
                <select value={newIncident.severity} onChange={(e) => setNewIncident(n => ({ ...n, severity: e.target.value as IncidentSeverity }))} className="px-3 py-2 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800 text-sm">
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                  <option value="info">Info</option>
                </select>
                <Input placeholder="Tags (comma-separated)" value={newIncident.tags} onChange={e => setNewIncident(n => ({ ...n, tags: e.target.value }))} />
              </div>
              <textarea placeholder="Description" value={newIncident.description} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNewIncident(n => ({ ...n, description: e.target.value }))} rows={2} className="w-full px-3 py-2 rounded border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-800 text-sm" />
              <Button type="submit" disabled={creating}>{creating ? 'Creating...' : 'Create Incident'}</Button>
            </form>
          </Card>

          {/* Incident List */}
          <Card>
            <div className="p-4">
              {loading && <p className="text-sm text-secondary-500">Loading incidents…</p>}
              {!loading && incidents.length === 0 && <p className="text-sm text-secondary-500">No incidents found.</p>}
              {!loading && incidents.length > 0 && (
                <div className="space-y-2">
                  {incidents.map(inc => (
                    <div
                      key={inc.id}
                      className={`p-3 rounded-lg border transition-colors cursor-pointer ${
                        selectedIncident?.id === inc.id
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/20'
                          : 'border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800/50'
                      }`}
                      onClick={() => setSelectedIncident(selectedIncident?.id === inc.id ? null : inc)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={severityColor(inc.severity)}>{inc.severity.toUpperCase()}</Badge>
                            <Badge variant={statusColor(inc.status)}>{inc.status.replace('_', ' ').toUpperCase()}</Badge>
                            <Badge variant="secondary">{inc.type.replace('_', ' ').toUpperCase()}</Badge>
                            <span className="font-mono text-xs text-secondary-500">{inc.id}</span>
                          </div>
                          <h4 className="font-medium text-secondary-900 dark:text-white mt-1">{inc.title}</h4>
                          <p className="text-sm text-secondary-600 dark:text-secondary-400 mt-1 truncate">{inc.description}</p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-secondary-500">
                            <span>Created: {new Date(inc.created_at).toLocaleString()}</span>
                            {inc.owner && <span>Owner: {inc.owner}</span>}
                            {inc.trigger_alert_id && <span>Alert: {inc.trigger_alert_id}</span>}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          {inc.affected_decision_ids.length > 0 && (
                            <Badge variant="secondary">{inc.affected_decision_ids.length} decisions</Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          {/* Incident Detail */}
          {selectedIncident && (
            <Card>
              <div className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-secondary-900 dark:text-white">{selectedIncident.title}</h3>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedIncident(null)}>Close</Button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                  <div><span className="text-secondary-500">ID:</span> <span className="font-mono ml-2">{selectedIncident.id}</span></div>
                  <div><span className="text-secondary-500">Status:</span> <Badge variant={statusColor(selectedIncident.status)} className="ml-2">{selectedIncident.status}</Badge></div>
                  <div><span className="text-secondary-500">Severity:</span> <Badge variant={severityColor(selectedIncident.severity)} className="ml-2">{selectedIncident.severity}</Badge></div>
                  <div><span className="text-secondary-500">Type:</span> <Badge variant="secondary" className="ml-2">{selectedIncident.type}</Badge></div>
                  <div className="sm:col-span-2"><span className="text-secondary-500">Created:</span> <span className="font-mono ml-2">{new Date(selectedIncident.created_at).toLocaleString()}</span></div>
                  <div className="sm:col-span-2"><span className="text-secondary-500">Owner:</span> <span className="font-mono ml-2">{selectedIncident.owner || '—'}</span></div>
                </div>
                <div className="space-y-2">
                  <h4 className="font-medium">Description</h4>
                  <p className="text-sm text-secondary-600 dark:text-secondary-400">{selectedIncident.description}</p>
                </div>
                {selectedIncident.guardian_findings.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="font-medium">Guardian Findings</h4>
                    <div className="space-y-1">
{selectedIncident.guardian_findings.map((f: { action: string; rule_id: string; message: string }, i: number) => (
                <Badge key={i} variant={(f.action === 'WITHHOLD' ? 'error' : 'warning') as 'error' | 'warning'} className="mr-1">
                  {f.rule_id}: {f.message}
                </Badge>
              ))}
                    </div>
                  </div>
                )}
                {selectedIncident.affected_decision_ids.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="font-medium">Linked Decisions</h4>
                    <div className="flex flex-wrap gap-1">
                      {selectedIncident.affected_decision_ids.map((d: string) => (
                        <Badge key={d} variant="secondary">{d}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                <div className="space-y-2">
                  <h4 className="font-medium">Timeline</h4>
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {selectedIncident.timeline.map((e: any, i: number) => (
                      <div key={`${e.timestamp}-${i}`} className="text-xs p-2 rounded bg-secondary-100 dark:bg-secondary-800/50">
                        <span className="font-mono text-secondary-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
                        <Badge variant="secondary" className="mx-1">{e.action}</Badge>
                        <span className="text-secondary-700 dark:text-secondary-300">{e.note}</span>
                        {e.actor && <span className="text-secondary-500 ml-2">by {e.actor}</span>}
                      </div>
                    ))}
                  </div>
                </div>
                {selectedIncident.status === 'open' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => incidentAction(selectedIncident, 'acknowledge', prompt('Acknowledgment note:') || '')}>Acknowledge</Button>
                  </div>
                )}
                {selectedIncident.status === 'acknowledged' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => incidentAction(selectedIncident, 'investigate', prompt('Investigation note:') || '')}>Investigate</Button>
                    <Button variant="ghost" size="sm" onClick={() => incidentAction(selectedIncident, 'resolve', prompt('Resolution note:') || '')}>Resolve</Button>
                  </div>
                )}
                {selectedIncident.status === 'investigating' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => incidentAction(selectedIncident, 'resolve', prompt('Resolution note:') || '')}>Resolve</Button>
                  </div>
                )}
                {selectedIncident.status === 'resolved' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => incidentAction(selectedIncident, 'close', 'Incident closed')}>Close</Button>
                    <Button variant="ghost" size="sm" onClick={() => incidentAction(selectedIncident, 'reopen', prompt('Reopen reason:') || '')}>Reopen</Button>
                  </div>
                )}
              </div>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="decisions" className="space-y-4">
          <Card>
            <div className="p-4">
              {loading && <p className="text-sm text-secondary-500">Loading decisions…</p>}
              {!loading && decisions.length === 0 && <p className="text-sm text-secondary-500">No decisions found.</p>}
              {!loading && decisions.length > 0 && (
                <div className="space-y-2">
                  {decisions.map(dec => (
                    <div
                      key={dec.id}
                      className={`p-3 rounded-lg border transition-colors cursor-pointer ${
                        selectedDecision?.id === dec.id
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/20'
                          : 'border-secondary-200 dark:border-secondary-700 hover:bg-secondary-50 dark:hover:bg-secondary-800/50'
                      }`}
                      onClick={() => setSelectedDecision(selectedDecision?.id === dec.id ? null : dec)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={
                              dec.status === 'approved' ? 'success' :
                              dec.status === 'rejected' ? 'error' :
                              dec.status === 'overridden' ? 'warning' :
                              dec.status === 'under_review' ? 'secondary' :
                              'secondary'
                            }>{dec.status.toUpperCase()}</Badge>
                            <Badge variant="secondary">{dec.scenario_id}</Badge>
                            <span className="font-mono text-xs text-secondary-500">{dec.id}</span>
                          </div>
                          <p className="font-mono text-xs text-secondary-600 dark:text-secondary-400 mt-1">
                            Policy: {JSON.stringify(dec.policy)}
                          </p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-secondary-500">
                            <span>Proposed by: {dec.proposed_by}</span>
                            <span>{new Date(dec.proposed_at).toLocaleString()}</span>
                            {dec.linked_incident_id && <span className="text-warning-600">Linked to incident: {dec.linked_incident_id}</span>}
                          </div>
                        </div>
                        {dec.guardian_verdict && (
                          <Badge variant={dec.guardian_verdict.action === 'WITHHOLD' ? 'error' : dec.guardian_verdict.action === 'WARN' ? 'warning' : 'success'}>
                            Guardian: {dec.guardian_verdict.action}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          {selectedDecision && (
            <Card>
              <div className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-secondary-900 dark:text-white">Decision {selectedDecision.id}</h3>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedDecision(null)}>Close</Button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                  <div><span className="text-secondary-500">Status:</span> <Badge variant={
                    selectedDecision.status === 'approved' ? 'success' :
                    selectedDecision.status === 'rejected' ? 'error' :
                    selectedDecision.status === 'overridden' ? 'warning' : 'secondary'
                  } className="ml-2">{selectedDecision.status}</Badge></div>
                  <div><span className="text-secondary-500">Scenario:</span> <span className="font-mono ml-2">{selectedDecision.scenario_id}</span></div>
                  <div className="sm:col-span-2"><span className="text-secondary-500">Proposed:</span> <span className="font-mono ml-2">{new Date(selectedDecision.proposed_at).toLocaleString()}</span></div>
                </div>
                <div className="space-y-2">
                  <h4 className="font-medium">Policy</h4>
                  <pre className="text-xs overflow-x-auto bg-secondary-100 dark:bg-secondary-800 p-2 rounded">{JSON.stringify(selectedDecision.policy, null, 2)}</pre>
                </div>
                {selectedDecision.guardian_verdict && (
                  <div className="space-y-2">
                    <h4 className="font-medium">Guardian Verdict</h4>
                    <div className="flex items-center gap-2">
                      <Badge variant={
                        selectedDecision.guardian_verdict.action === 'WITHHOLD' ? 'error' :
                        selectedDecision.guardian_verdict.action === 'WARN' ? 'warning' : 'success'
                      }>{selectedDecision.guardian_verdict.action}</Badge>
                      <span className="text-sm text-secondary-600 dark:text-secondary-400">
                        {selectedDecision.guardian_verdict.display_allowed ? 'Display allowed' : 'Display WITHHELD'}
                      </span>
                    </div>
                    {selectedDecision.guardian_verdict.rejections.length > 0 && (
                      <div className="space-y-1">
                        {selectedDecision.guardian_verdict.rejections.map((r: string, i: number) => (
                          <Badge key={i} variant="error" className="mr-1">REJECTION: {r}</Badge>
                        ))}
                      </div>
                    )}
                    {selectedDecision.guardian_verdict.flags.length > 0 && (
                      <div className="space-y-1">
                        {selectedDecision.guardian_verdict.flags.map((f: string, i: number) => (
                          <Badge key={i} variant="warning" className="mr-1">FLAG: {f}</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                <div className="space-y-2">
                  <h4 className="font-medium">Timeline</h4>
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {selectedDecision.timeline.map((e: any, i: number) => (
                      <div key={`${e.timestamp}-${i}`} className="text-xs p-2 rounded bg-secondary-100 dark:bg-secondary-800/50">
                        <span className="font-mono text-secondary-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
                        <Badge variant="secondary" className="mx-1">{e.action}</Badge>
                        <span className="text-secondary-700 dark:text-secondary-300">{e.note}</span>
                        {e.actor && <span className="text-secondary-500 ml-2">by {e.actor}</span>}
                      </div>
                    ))}
                  </div>
                </div>
                {/* Decision Actions */}
                {selectedDecision.status === 'pending' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => decisionAction(selectedDecision, 'accept', prompt('Approval note:') || '')}>Accept</Button>
                    <Button variant="outline" size="sm" onClick={() => decisionAction(selectedDecision, 'reject', prompt('Rejection note:') || '')}>Reject</Button>
                    <Button variant="ghost" size="sm" onClick={() => decisionAction(selectedDecision, 'request_review', prompt('Review request note:') || '')}>Request Review</Button>
                  </div>
                )}
                {selectedDecision.status === 'rejected' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => decisionAction(selectedDecision, 'override', prompt('Override justification (required):') || '')}>Override</Button>
                  </div>
                )}
                {selectedDecision.status === 'approved' && (
                  <div className="flex gap-2 pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => decisionAction(selectedDecision, 'execute', 'Decision executed')}>Execute</Button>
                  </div>
                )}
              </div>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}