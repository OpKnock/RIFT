export interface SourceDef {
  key: string
  label: string
  kind: 'api-endpoint' | 'dataset'
  target: string
  auth: string
  qualityNotes: string
}

export interface SourceProbe {
  key: string
  ok: boolean | null
  latencyMs: number | null
  checkedAt: string | null
  detail: string | null
}

export const SOURCE_DEFS: SourceDef[] = [
  { key: 'health', label: 'Engine health', kind: 'api-endpoint', target: 'GET /api/health', auth: 'open', qualityNotes: 'Liveness + version + persistence/billing flags.' },
  { key: 'meta', label: 'Engine metadata', kind: 'api-endpoint', target: 'GET /api/meta', auth: 'open', qualityNotes: 'Optimizers, backends, bounds. Source of client-side validation limits.' },
  { key: 'demo', label: 'Engine demo run', kind: 'api-endpoint', target: 'GET /api/demo', auth: 'open', qualityNotes: 'Bounds-checked inputs; 422 on violation. Deterministic decision content.' },
  { key: 'twin-demo', label: 'Twin snapshots', kind: 'api-endpoint', target: 'GET /api/twin/demo?t=', auth: 'open', qualityNotes: 'Days 0–13 only; 422 outside range. Carries quality, jitter, provenance.' },
  { key: 'twin-evidence', label: 'Evidence bundle', kind: 'api-endpoint', target: 'GET /api/twin/evidence', auth: 'open', qualityNotes: 'Frozen synthetic bundle with adequacy verdict.' },
  { key: 'monitor', label: 'Ops monitor', kind: 'api-endpoint', target: 'GET /api/ops/monitor', auth: 'open in dev; bearer-gated when token set', qualityNotes: 'Counters, alert evaluations. Polled — no server push exists.' },
  { key: 'experiments', label: 'Experiment store', kind: 'api-endpoint', target: 'POST/GET /api/experiments', auth: 'open in dev; ownership-checked', qualityNotes: 'Requires Supabase; 503 without it. UUID-validated IDs.' },
  { key: 'reviews', label: 'Review ledger', kind: 'api-endpoint', target: 'GET/POST /api/twin/reviews', auth: 'open in dev', qualityNotes: 'Append-only, hash-chained; rationale required to reject/override.' },
  { key: 'twin-series', label: 'Twin demo series', kind: 'dataset', target: 'synthetic 14-day series (seed 42)', auth: 'n/a (bundled)', qualityNotes: 'NOT clinically validated. Replay range 0–13 enforced server-side.' },
  { key: 'evidence-cohorts', label: 'Evidence cohorts', kind: 'dataset', target: 'synthetic 60-day + external series', auth: 'n/a (bundled)', qualityNotes: 'Sample-adequacy bar 100/100 events; current verdict served per bundle.' },
]

export const MQTT_NOTE =
  'MQTT / IoT ingestion is not served by this backend — no broker, topic, or device-auth endpoint exists. ' +
  'Device integration would be a backend project; nothing here pretends otherwise.'
