import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, apiErrorMessage } from '@/services/api'

interface EvidenceBundle {
  patient_id: string
  day_index: number
  risk: Record<string, any>
  robustness: Record<string, any>
  guardian: Record<string, any>
  futures: Record<string, any>
  trajectories: any[]
  decision_table: Record<string, any>
  reasons: string[]
  provenance: Record<string, any>
}

export function Explainability() {
  const [evidence, setEvidence] = useState<EvidenceBundle | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<string>('overview')
  const [auditLog, setAuditLog] = useState<any[]>([])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [ev, audit] = await Promise.all([
          api.getTwinEvidence(),
          api.getExplainabilityAudit().catch(() => ({ records: [] })),
        ])
        if (!cancelled) {
          setEvidence(ev as unknown as EvidenceBundle)
          setAuditLog(audit.records || [])
          setLoading(false)
        }
      } catch (e) {
        if (!cancelled) {
          setError(apiErrorMessage(e, 'Failed to load evidence'))
          setLoading(false)
        }
      }
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Explainability & Trust</h1>
        <p className="text-secondary-600 dark:text-secondary-400">Loading evidence bundle…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Explainability & Trust</h1>
        <div className="p-3 rounded-lg bg-error-50 dark:bg-error-900/20 border border-error-200 dark:border-error-800 text-error-600 dark:text-error-400" role="alert">
          {error}
        </div>
      </div>
    )
  }

  const e = evidence!

  const overview = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Decision Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Patient</p>
              <p className="font-mono font-medium">{e.patient_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Day</p>
              <p className="font-mono font-medium">{e.day_index}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Predicted Risk</p>
              <p className="font-mono font-medium">{(e.risk.risk * 100).toFixed(1)}%</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Uncertainty</p>
              <p className="font-mono font-medium">±{(e.risk.uncertainty * 100).toFixed(1)}%</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 sm:col-span-2">
              <p className="text-secondary-500">Risk Interval</p>
              <p className="font-mono font-medium">
                {(e.risk.interval[0] * 100).toFixed(1)}% – {(e.risk.interval[1] * 100).toFixed(1)}%
              </p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 sm:col-span-2">
              <p className="text-secondary-500">Guardian Action</p>
              <Badge variant={e.guardian.action === 'WITHHOLD' ? 'error' : e.guardian.action === 'WARN' ? 'warning' : 'success'} className="text-base">
                {e.guardian.action}
              </Badge>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Top Reasons</h2>
          <ul className="space-y-2">
            {e.reasons.map((r, i) => (
              <li key={i} className="text-sm text-secondary-700 dark:text-secondary-300 p-2 rounded bg-secondary-50 dark:bg-secondary-800/50">
                {r}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      {e.guardian.rejections.length > 0 && (
        <Card>
          <div className="p-6">
            <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Guardian Rejections</h2>
            <div className="space-y-1">
              {e.guardian.rejections.map((r: string, i: number) => (
                <Badge key={i} variant="error" className="mr-1">REJECTION: {r}</Badge>
              ))}
            </div>
          </div>
        </Card>
      )}

      {e.guardian.flags.length > 0 && (
        <Card>
          <div className="p-6">
            <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Guardian Flags</h2>
            <div className="space-y-1">
              {e.guardian.flags.map((f: string, i: number) => (
                <Badge key={i} variant="warning" className="mr-1">FLAG: {f}</Badge>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  )

  const assumptionExplorer = () => {
    const ranking = e.futures.robust_ranking || []
    return (
      <div className="space-y-4">
        <Card>
          <div className="p-6">
            <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Policy Assumptions</h2>
            {ranking.map((r: any, i: number) => (
              <div key={i} className="mb-4 p-4 rounded-lg bg-secondary-50 dark:bg-secondary-800/50 border">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={r.feasible_under_all ? 'success' : 'error'}>
                    {r.feasible_under_all ? 'Feasible' : 'Infeasible'}
                  </Badge>
                  <span className="font-mono">Policy: {JSON.stringify(r.policy)}</span>
                </div>
                <div className="text-sm space-y-1">
                  <p><span className="text-secondary-500">Nominal Risk: </span>{r.nominal_risk?.toFixed(3)}</p>
                  <p><span className="text-secondary-500">Worst-case Risk: </span>{r.worst_case_risk?.toFixed(3)}</p>
                  <details className="mt-2">
                    <summary className="text-secondary-600 dark:text-secondary-400 cursor-pointer">Assumption Ledger</summary>
                    <pre className="text-xs mt-2 p-2 bg-secondary-100 dark:bg-secondary-800 rounded overflow-x-auto">
                      {JSON.stringify(r.assumptions, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <div className="p-6">
            <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Imputed Fields</h2>
            <div className="flex flex-wrap gap-2">
              {(e.futures.imputed_fields || []).map((f: string, i: number) => (
                <Badge key={i} variant="secondary">{f}</Badge>
              ))}
            </div>
          </div>
        </Card>
      </div>
    )
  }

  const provenanceExplorer = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Prediction Provenance</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {Object.entries(e.provenance).map(([k, v]) => (
              <div key={k} className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
                <p className="text-secondary-500 font-mono text-xs">{k}</p>
                <p className="font-mono text-xs break-all">{typeof v === 'string' ? v : JSON.stringify(v)}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  )

  const modelExplorer = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Model & Version</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Model ID</p>
              <p className="font-mono">{e.provenance.model_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Weights Digest</p>
              <p className="font-mono break-all">{e.provenance.weights_digest}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Schema Version</p>
              <p className="font-mono">{e.provenance.schema_version}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Calibration</p>
              <p className="font-mono">{e.provenance.calibration_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Engine</p>
              <p className="font-mono">{e.provenance.engine}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Input Hash</p>
              <p className="font-mono break-all">{e.provenance.input_hash}</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )

  const evidenceExplorer = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Risk Record</h2>
          <pre className="text-xs overflow-x-auto bg-secondary-100 dark:bg-secondary-800 p-4 rounded">{JSON.stringify(e.risk, null, 2)}</pre>
        </div>
      </Card>
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Robustness</h2>
          <pre className="text-xs overflow-x-auto bg-secondary-100 dark:bg-secondary-800 p-4 rounded">{JSON.stringify(e.robustness, null, 2)}</pre>
        </div>
      </Card>
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Guardian Verdict</h2>
          <pre className="text-xs overflow-x-auto bg-secondary-100 dark:bg-secondary-800 p-4 rounded">{JSON.stringify(e.guardian, null, 2)}</pre>
        </div>
      </Card>
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Counterfactuals</h2>
          <pre className="text-xs overflow-x-auto bg-secondary-100 dark:bg-secondary-800 p-4 rounded">{JSON.stringify(e.futures, null, 2)}</pre>
        </div>
      </Card>
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Trajectories</h2>
          <pre className="text-xs overflow-x-auto bg-secondary-100 dark:bg-secondary-800 p-4 rounded">{JSON.stringify(e.trajectories, null, 2)}</pre>
        </div>
      </Card>
    </div>
  )

  const fingerprintViewer = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Execution Fingerprint</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Prediction ID</p>
              <p className="font-mono break-all">{e.provenance.prediction_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Model ID</p>
              <p className="font-mono">{e.provenance.model_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Weights Digest</p>
              <p className="font-mono break-all">{e.provenance.weights_digest}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Schema Version</p>
              <p className="font-mono">{e.provenance.schema_version}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Calibration ID</p>
              <p className="font-mono">{e.provenance.calibration_id}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Input Hash</p>
              <p className="font-mono break-all">{e.provenance.input_hash}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">EHR Hash</p>
              <p className="font-mono break-all">{e.provenance.ehr_hash}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary-50 dark:bg-secondary-800/50">
              <p className="text-secondary-500">Baseline Hash</p>
              <p className="font-mono break-all">{e.provenance.baseline_hash}</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )

  const guardianView = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Guardian Verification</h2>
          <div className="flex items-center gap-3 mb-4">
            <Badge variant={e.guardian.action === 'WITHHOLD' ? 'error' : e.guardian.action === 'WARN' ? 'warning' : 'success'} className="text-base">
              Action: {e.guardian.action}
            </Badge>
            <span className="text-sm text-secondary-600 dark:text-secondary-400">
              {e.guardian.display_allowed ? 'Display ALLOWED' : 'Display WITHHELD'}
            </span>
          </div>
          <div className="space-y-2">
            <h3 className="font-medium">Stage Gates</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(e.guardian.stages || {}).map(([stage, info]: [string, any]) => (
                <div key={stage} className={`p-3 rounded-lg ${info.passed ? 'bg-success-50 dark:bg-success-900/20' : 'bg-error-50 dark:bg-error-900/20'} border ${info.passed ? 'border-success-200' : 'border-error-200'}`}>
                  <div className="font-medium">{stage}</div>
                  <Badge variant={info.passed ? 'success' : 'error'}>
                    {info.passed ? 'PASSED' : 'FAILED'}
                  </Badge>
                  <div className="text-xs text-secondary-500 mt-1">
                    Rules: {info.rules?.join(', ') || 'none'}
                  </div>
                </div>
              ))}
            </div>
          </div>
          {e.guardian.findings && e.guardian.findings.length > 0 && (
            <div className="mt-4 space-y-2">
              <h3 className="font-medium">All Findings</h3>
              {e.guardian.findings.map((f: any, i: number) => (
                <Badge key={i} variant={f.action === 'WITHHOLD' ? 'error' : 'warning'} className="mr-1">
                  [{f.stage}] {f.rule_id}: {f.message}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )

  const auditTrail = () => (
    <div className="space-y-4">
      <Card>
        <div className="p-6">
          <h2 className="font-medium text-secondary-900 dark:text-white mb-4">Decision Audit Trail</h2>
          {auditLog.length === 0 ? (
            <p className="text-sm text-secondary-500">No audit records available.</p>
          ) : (
            <div className="max-h-96 overflow-y-auto space-y-2">
              {auditLog.map((r: any, i: number) => (
                <div key={i} className="text-xs p-3 rounded bg-secondary-100 dark:bg-secondary-800/50 border">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-mono text-secondary-500">{r.timestamp}</span>
                    <Badge variant="secondary">{r.record_type}</Badge>
                    <Badge variant="secondary">{r.actor}</Badge>
                    <span className="font-mono">{r.record_id}</span>
                  </div>
                  <pre className="text-xs overflow-x-auto">{JSON.stringify(r.payload, null, 2)}</pre>
                  <div className="flex items-center gap-2 mt-1 text-secondary-500">
                    <span>Hash: <span className="font-mono">{r.hash?.slice(0, 16)}…</span></span>
                    <span>Prev: <span className="font-mono">{r.previous_hash?.slice(0, 16)}…</span></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 dark:text-white">Explainability & Trust</h1>
        <p className="text-secondary-600 dark:text-secondary-400 mt-1">
          Complete decision reasoning, assumptions, provenance, evidence, and audit trail.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="assumptions">Assumptions</TabsTrigger>
          <TabsTrigger value="provenance">Provenance</TabsTrigger>
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="fingerprint">Fingerprint</TabsTrigger>
          <TabsTrigger value="guardian">Guardian</TabsTrigger>
          <TabsTrigger value="audit">Audit Trail</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">{overview()}</TabsContent>
        <TabsContent value="assumptions" className="space-y-4">{assumptionExplorer()}</TabsContent>
        <TabsContent value="provenance" className="space-y-4">{provenanceExplorer()}</TabsContent>
        <TabsContent value="model" className="space-y-4">{modelExplorer()}</TabsContent>
        <TabsContent value="evidence" className="space-y-4">{evidenceExplorer()}</TabsContent>
        <TabsContent value="fingerprint" className="space-y-4">{fingerprintViewer()}</TabsContent>
        <TabsContent value="guardian" className="space-y-4">{guardianView()}</TabsContent>
        <TabsContent value="audit" className="space-y-4">{auditTrail()}</TabsContent>
      </Tabs>
    </div>
  )
}