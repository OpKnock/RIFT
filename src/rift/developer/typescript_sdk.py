"""TypeScript/JavaScript SDK Generator for RIFT API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TSConfig:
    """TypeScript SDK generation config."""
    output_dir: Path
    api_base_url: str = "http://localhost:8080"
    package_name: str = "@rift/sdk"
    package_version: str = "1.0.0"
    generate_react_hooks: bool = True
    generate_tests: bool = True


class TypeScriptSDKGenerator:
    """Generate TypeScript SDK from OpenAPI spec or Python SDK."""

    def __init__(self, config: TSConfig):
        self.config = config
        self.output_dir = config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> dict[str, str]:
        """Generate all SDK files. Returns dict of file_path -> content."""
        files = {}

        files["package.json"] = self._generate_package_json()
        files["tsconfig.json"] = self._generate_tsconfig()
        files["src/index.ts"] = self._generate_main_index()
        files["src/config.ts"] = self._generate_config()
        files["src/types.ts"] = self._generate_types()
        files["src/client.ts"] = self._generate_client()
        files["src/api/health.ts"] = self._generate_health_api()
        files["src/api/meta.ts"] = self._generate_meta_api()
        files["src/api/demo.ts"] = self._generate_demo_api()
        files["src/api/experiments.ts"] = self._generate_experiments_api()
        files["src/api/twin.ts"] = self._generate_twin_api()
        files["src/api/operations.ts"] = self._generate_operations_api()
        files["src/api/explainability.ts"] = self._generate_explainability_api()
        files["src/api/billing.ts"] = self._generate_billing_api()
        files["src/hooks/useExperiments.ts"] = self._generate_use_experiments_hook()
        files["src/hooks/useTwin.ts"] = self._generate_use_twin_hook()
        files["src/hooks/useMonitor.ts"] = self._generate_use_monitor_hook()
        files["src/errors.ts"] = self._generate_errors()
        files["README.md"] = self._generate_readme()

        if self.config.generate_tests:
            files["tests/client.test.ts"] = self._generate_client_tests()
            files["tests/api.test.ts"] = self._generate_api_tests()

        return files

    def write_all(self) -> list[Path]:
        """Write all generated files to disk."""
        files = self.generate()
        written = []
        for rel_path, content in files.items():
            path = self.output_dir / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            written.append(path)
        return written

    def _generate_package_json(self) -> str:
        return json.dumps({
            "name": self.config.package_name,
            "version": self.config.package_version,
            "description": "RIFT API TypeScript SDK",
            "main": "dist/index.js",
            "module": "dist/index.mjs",
            "types": "dist/index.d.ts",
            "exports": {
                ".": {
                    "import": "./dist/index.mjs",
                    "require": "./dist/index.js",
                    "types": "./dist/index.d.ts"
                }
            },
            "scripts": {
                "build": "tsc && tsc -m ESNext --outDir dist/esm && mv dist/esm dist/index.mjs",
                "test": "vitest run",
                "lint": "eslint src --ext .ts",
                "prepublishOnly": "npm run build && npm test"
            },
            "keywords": ["rift", "api", "sdk", "optimization", "digital-twin"],
            "author": "RIFT Team",
            "license": "AGPL-3.0-or-later",
            "peerDependencies": {
                "zod": "^3.22.0"
            },
            "devDependencies": {
                "typescript": "^5.3.0",
                "vitest": "^1.0.0",
                "eslint": "^8.56.0",
                "@typescript-eslint/eslint-plugin": "^6.19.0",
                "@typescript-eslint/parser": "^6.19.0",
                "zod": "^3.22.0"
            },
            "engines": {
                "node": ">=18.0.0"
            }
        }, indent=2)

    def _generate_tsconfig(self) -> str:
        return json.dumps({
            "compilerOptions": {
                "target": "ES2022",
                "module": "NodeNext",
                "moduleResolution": "NodeNext",
                "lib": ["ES2022"],
                "declaration": True,
                "declarationMap": True,
                "sourceMap": True,
                "outDir": "./dist",
                "rootDir": "./src",
                "strict": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
                "forceConsistentCasingInFileNames": True,
                "resolveJsonModule": True,
                "isolatedModules": True,
                "noEmit": False
            },
            "include": ["src/**/*"],
            "exclude": ["node_modules", "dist", "tests"]
        }, indent=2)

    def _generate_main_index(self) -> str:
        return '''export { RiftClient, createClient } from './client';
export { RiftAsyncClient, createAsyncClient } from './client';
export * from './types';
export * from './errors';
export * from './config';

// React hooks (optional)
export { useExperiments, useExperiment, useCreateExperiment } from './hooks/useExperiments';
export { useTwin, useTwinDemo } from './hooks/useTwin';
export { useMonitor } from './hooks/useMonitor';
'''

    def _generate_config(self) -> str:
        return '''import { z } from 'zod';

export const RiftConfigSchema = z.object({
  baseUrl: z.string().url().default('http://localhost:8080'),
  apiKey: z.string().optional(),
  jwtToken: z.string().optional(),
  timeout: z.number().positive().default(30000),
  maxRetries: z.number().int().nonnegative().default(3),
  retryDelay: z.number().positive().default(1000),
  verifySsl: z.boolean().default(true),
});

export type RiftConfig = z.infer<typeof RiftConfigSchema>;

export const defaultConfig: RiftConfig = {
  baseUrl: 'http://localhost:8080',
  timeout: 30000,
  maxRetries: 3,
  retryDelay: 1000,
  verifySsl: true,
};

export function createConfig(overrides: Partial<RiftConfig> = {}): RiftConfig {
  return RiftConfigSchema.parse({ ...defaultConfig, ...overrides });
}
'''

    def _generate_types(self) -> str:
        return '''import { z } from 'zod';

// Health & Meta
export const HealthStatusSchema = z.object({
  status: z.string(),
  engine: z.string(),
  version: z.string(),
  quantum_backend: z.string(),
  persistence: z.object({ configured: z.boolean() }),
  billing: z.object({ configured: z.boolean(), provider: z.string() }),
});
export type HealthStatus = z.infer<typeof HealthStatusSchema>;

export const EngineMetaSchema = z.object({
  engine: z.string(),
  engine_version: z.string(),
  quantum_backend: z.string(),
  capabilities: z.array(z.string()),
  optimizers: z.array(z.string()),
  backends: z.array(z.string()),
  limits: z.record(z.unknown()),
  auth: z.object({ service_token_configured: z.boolean() }),
});
export type EngineMeta = z.infer<typeof EngineMetaSchema>;

// Demo
export const DemoParamsSchema = z.object({
  crowd: z.number().int().optional(),
  smoke: z.number().optional(),
  corridor_capacity: z.number().optional(),
  block_b: z.boolean().optional(),
});
export type DemoParams = z.infer<typeof DemoParamsSchema>;

export const RobustAssessmentSchema = z.object({
  policy: z.record(z.number()),
  score: z.number(),
  worst_case_score: z.number(),
  robustness_gap: z.number(),
  feasible_under_all: z.boolean(),
  worst_perturbation: z.record(z.number()),
});
export type RobustAssessment = z.infer<typeof RobustAssessmentSchema>;

export const OptimizerResultSchema = z.object({
  assignment: z.record(z.number()),
  energy: z.number(),
  method: z.string(),
  alpha: z.number().optional(),
});
export type OptimizerResult = z.infer<typeof OptimizerResultSchema>;

export const DemoResultSchema = z.object({
  scenario: z.object({
    name: z.string(),
    initial_state: z.record(z.number()),
    interventions: z.record(z.array(z.number())),
  }),
  futures: z.array(z.object({
    policy: z.record(z.number()),
    state: z.record(z.number()),
    score: z.number(),
    valid: z.boolean(),
  })),
  robust: z.array(RobustAssessmentSchema),
  robust_optimization: z.object({
    classical: OptimizerResultSchema,
    qaoa: OptimizerResultSchema,
    cvar_qaoa: OptimizerResultSchema,
  }),
  multivariable: z.object({
    variables: z.array(z.string()),
    policy_count: z.number(),
    exact: OptimizerResultSchema,
    qaoa_projection: z.object({
      ...OptimizerResultSchema.shape,
      approximation: z.boolean(),
      objective: z.string(),
    }),
    projection_error: z.object({
      max_absolute_gap: z.number(),
      mean_absolute_gap: z.number(),
    }),
    top_policies: z.array(z.object({
      assignment: z.record(z.number()),
      nominal_cost: z.number(),
      robust_cost: z.number(),
      feasible: z.boolean(),
      worst_perturbation: z.record(z.number()),
    })),
  }),
  benchmark: z.array(z.object({
    method: z.string(),
    energy: z.number(),
    assignment: z.record(z.number()),
    runtime_ms: z.number(),
    note: z.string(),
  })),
  guardian: z.object({
    passed: z.boolean(),
    checks: z.array(z.object({ passed: z.boolean(), violations: z.array(z.string()) })),
    scope: z.string(),
    policy: z.record(z.number()),
  }),
  reproducibility: z.object({
    engine_version: z.string(),
    backend: z.string(),
    perturbations: z.array(z.record(z.number())),
    policy_variables: z.array(z.string()),
    note: z.string(),
  }),
  future_tree: z.array(z.object({
    id: z.string(),
    parent_id: z.string().nullable(),
    depth: z.number(),
    policy: z.record(z.number()),
    score: z.number(),
    valid: z.boolean(),
    label: z.string(),
  })),
  causal_graph: z.object({
    nodes: z.array(z.string()),
    edges: z.array(z.object({ cause: z.string(), effect: z.string(), strength: z.number() })),
  }),
  uncertainty: z.object({ risk_entropy: z.number() }),
});
export type DemoResult = z.infer<typeof DemoResultSchema>;

// Experiments
export const ExperimentSpecSchema = z.object({
  name: z.string(),
  scenario_name: z.string().default('smart-building-emergency'),
  initial_state: z.record(z.number()).optional(),
  perturbations: z.array(z.record(z.number())).optional(),
  policy_variables: z.array(z.string()).optional(),
  optimizer: z.enum(['exact', 'qaoa-expectation', 'qaoa-cvar']).default('exact'),
  backend: z.enum(['statevector-simulator', 'none']).default('statevector-simulator'),
  seed: z.number().int().optional(),
  description: z.string().optional(),
});
export type ExperimentSpec = z.infer<typeof ExperimentSpecSchema>;

export const ExperimentSchema = z.object({
  id: z.string(),
  name: z.string(),
  scenario_name: z.string(),
  status: z.string(),
  created_at: z.string(),
  spec: ExperimentSpecSchema,
  versions: z.array(z.record(z.unknown())).optional(),
  runs: z.array(z.record(z.unknown())).optional(),
});
export type Experiment = z.infer<typeof ExperimentSchema>;

// Runs
export const RunSchema = z.object({
  id: z.string(),
  experiment_id: z.string(),
  optimizer: z.string(),
  metrics: z.record(z.unknown()),
  result: z.record(z.unknown()).nullable(),
  seed: z.number().int().nullable(),
  status: z.string(),
  created_at: z.string(),
});
export type Run = z.infer<typeof RunSchema>;

// Comparison
export const ComparisonSchema = z.object({
  comparison_id: z.string(),
  type: z.enum(['optimizer', 'model', 'perturbation', 'robustness', 'regression']),
  baseline_id: z.string(),
  candidate_ids: z.array(z.string()),
  metrics: z.record(z.object({
    baseline: z.number(),
    candidates: z.record(z.number()),
    diff: z.record(z.number()),
  })),
  summary: z.string(),
  created_at: z.string(),
});
export type Comparison = z.infer<typeof ComparisonSchema>;

// Templates
export const ExperimentTemplateSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  spec: ExperimentSpecSchema,
  version: z.string(),
  created_at: z.string(),
  created_by: z.string(),
  tags: z.array(z.string()),
  is_public: z.boolean(),
});
export type ExperimentTemplate = z.infer<typeof ExperimentTemplateSchema>;

// Digital Twin
export const TwinSnapshotSchema = z.object({
  day_index: z.number(),
  patient_id: z.string(),
  state: z.record(z.unknown()),
  risk: z.record(z.unknown()),
  guardian: z.record(z.unknown()),
  futures: z.record(z.unknown()),
  trajectories: z.array(z.record(z.unknown())),
  provenance: z.record(z.unknown()),
});
export type TwinSnapshot = z.infer<typeof TwinSnapshotSchema>;

export const TwinEvidenceSchema = z.object({
  patient_id: z.string(),
  day_index: z.number(),
  risk: z.record(z.unknown()),
  robustness: z.record(z.unknown()),
  guardian: z.record(z.unknown()),
  futures: z.record(z.unknown()),
  trajectories: z.array(z.record(z.unknown())),
  decision_table: z.record(z.unknown()),
  reasons: z.array(z.string()),
  provenance: z.record(z.unknown()),
});
export type TwinEvidence = z.infer<typeof TwinEvidenceSchema>;

// Operations
export const IncidentSchema = z.object({
  id: z.string(),
  type: z.string(),
  severity: z.string(),
  title: z.string(),
  description: z.string(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  acknowledged_at: z.string().nullable(),
  resolved_at: z.string().nullable(),
  closed_at: z.string().nullable(),
  owner: z.string().nullable(),
  trigger_alert_id: z.string().nullable(),
  affected_decision_ids: z.array(z.string()),
  guardian_findings: z.array(z.record(z.unknown())),
  timeline: z.array(z.object({
    timestamp: z.string(),
    actor: z.string(),
    action: z.string(),
    note: z.string(),
    metadata: z.record(z.unknown()),
  })),
  tags: z.array(z.string()),
  metadata: z.record(z.unknown()),
});
export type Incident = z.infer<typeof IncidentSchema>;

export const DecisionSchema = z.object({
  id: z.string(),
  scenario_id: z.string(),
  policy: z.record(z.number()),
  proposed_by: z.string(),
  proposed_at: z.string(),
  status: z.string(),
  guardian_verdict: z.record(z.unknown()).nullable(),
  approved_by: z.string().nullable(),
  approved_at: z.string().nullable(),
  rejected_by: z.string().nullable(),
  rejected_at: z.string().nullable(),
  overridden_by: z.string().nullable(),
  overridden_at: z.string().nullable(),
  executed_at: z.string().nullable(),
  expired_at: z.string().nullable(),
  execution_result: z.record(z.unknown()).nullable(),
  linked_incident_id: z.string().nullable(),
  review_requested_by: z.string().nullable(),
  review_requested_at: z.string().nullable(),
  timeline: z.array(z.object({
    timestamp: z.string(),
    actor: z.string(),
    action: z.string(),
    note: z.string(),
    guardian_verdict: z.record(z.unknown()).nullable(),
    metadata: z.record(z.unknown()),
  })),
  metadata: z.record(z.unknown()),
});
export type Decision = z.infer<typeof DecisionSchema>;

// Explainability
export const ExplainabilityAuditSchema = z.object({
  records: z.array(z.object({
    record_id: z.string(),
    timestamp: z.string(),
    record_type: z.string(),
    actor: z.string(),
    payload: z.record(z.unknown()),
    previous_hash: z.string().nullable(),
    hash: z.string(),
  })),
});
export type ExplainabilityAudit = z.infer<typeof ExplainabilityAuditSchema>;

// Billing
export const BillingStatusSchema = z.object({
  configured: z.boolean(),
  provider: z.string(),
});
export type BillingStatus = z.infer<typeof BillingStatusSchema>;

export const EntitlementSchema = z.record(z.unknown());
export type Entitlement = z.infer<typeof EntitlementSchema>;

// Pagination
export const PaginatedResponseSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number(),
    page: z.number(),
    page_size: z.number(),
    has_more: z.boolean(),
  });

// API Error
export const ApiErrorSchema = z.object({
  error: z.string(),
  detail: z.string().optional(),
  request_id: z.string().optional(),
});
export type ApiError = z.infer<typeof ApiErrorSchema>;
'''

    def _generate_client(self) -> str:
        return '''import { RiftConfig, defaultConfig, createConfig } from './config';
import { RiftError, RiftAuthenticationError, RiftRateLimitError } from './errors';
import type { HealthStatus, EngineMeta, DemoParams, DemoResult, Experiment, ExperimentSpec, Run, Comparison, ExperimentTemplate, TwinSnapshot, TwinEvidence, Incident, Decision, BillingStatus, Entitlement, ExplainabilityAudit } from './types';

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE' | 'PUT' | 'PATCH';
  body?: unknown;
  params?: Record<string, string>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export class RiftClient {
  private config: RiftConfig;
  private abortController: AbortController | null = null;

  constructor(config: Partial<RiftConfig> = {}) {
    this.config = createConfig(config);
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = new URL(path, this.config.baseUrl);
    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` },
      ...this.config.jwtToken && { 'Authorization': `Bearer ${this.config.jwtToken}` },
      ...options.headers,
    };

    this.abortController = new AbortController();
    const timeoutId = setTimeout(() => this.abortController?.abort(), this.config.timeout);

    try {
      const response = await fetch(url.toString(), {
        method: options.method || 'GET',
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: this.abortController.signal,
        credentials: 'omit',
      });

      clearTimeout(timeoutId);

      if (response.status === 401) {
        throw new RiftAuthenticationError('Authentication failed');
      }
      if (response.status === 429) {
        const retryAfter = parseFloat(response.headers.get('Retry-After') || String(this.config.retryDelay / 1000));
        throw new RiftRateLimitError('Rate limit exceeded', retryAfter);
      }
      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new RiftError(error.detail || error.error || 'Request failed', response.status);
      }

      if (response.status === 204) {
        return undefined as T;
      }
      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof RiftError) throw error;
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new RiftError('Request aborted');
      }
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new RiftError('Network error: unable to reach server');
      }
      throw error;
    } finally {
      this.abortController = null;
    }
  }

  // Health & Meta
  async health(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/api/health');
  }

  async meta(): Promise<EngineMeta> {
    return this.request<EngineMeta>('/api/meta');
  }

  // Demo
  async runDemo(params?: DemoParams): Promise<DemoResult> {
    const query = new URLSearchParams();
    if (params?.crowd !== undefined) query.set('crowd', String(params.crowd));
    if (params?.smoke !== undefined) query.set('smoke', String(params.smoke));
    if (params?.corridor_capacity !== undefined) query.set('corridor_capacity', String(params.corridor_capacity));
    if (params?.block_b) query.set('block_b', '1');
    return this.request<DemoResult>('/api/demo', { params: Object.fromEntries(query) });
  }

  // Experiments
  async createExperiment(spec: ExperimentSpec): Promise<Experiment> {
    return this.request<Experiment>('/api/experiments', { method: 'POST', body: spec });
  }

  async getExperiment(id: string): Promise<Experiment> {
    return this.request<Experiment>(`/api/experiments/${id}`);
  }

  async listExperiments(status?: string, limit = 100): Promise<Experiment[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (status) params.set('status', status);
    return this.request<Experiment[]>(`/api/experiments?${params.toString()}`);
  }

  async deleteExperiment(id: string): Promise<void> {
    await this.request(`/api/experiments/${id}`, { method: 'DELETE' });
  }

  async createExperimentVersion(id: string, spec: ExperimentSpec, version: number, description = ''): Promise<any> {
    return this.request(`/api/experiments/${id}/versions`, { method: 'POST', body: { spec, version, description } });
  }

  async getExperimentVersions(id: string): Promise<any[]> {
    return this.request<any[]>(`/api/experiments/${id}/versions`);
  }

  // Runs
  async createRun(experimentId: string, optimizer: string, metrics: Record<string, unknown>, result?: Record<string, unknown>, seed?: number): Promise<any> {
    return this.request(`/api/experiments/${experimentId}/runs`, { method: 'POST', body: { optimizer, metrics, result, seed } });
  }

  async getRun(id: string): Promise<any> {
    return this.request(`/api/runs/${id}`);
  }

  async listRuns(experimentId: string): Promise<any[]> {
    return this.request<any[]>(`/api/experiments/${experimentId}/runs`);
  }

  // Comparisons
  async compare(type: string, baselineId: string, candidateIds: string[]): Promise<Comparison> {
    return this.request<Comparison>('/api/experiments/compare', { method: 'POST', body: { type, baseline_id: baselineId, candidate_ids: candidateIds } });
  }

  // Templates
  async listTemplates(): Promise<ExperimentTemplate[]> {
    return this.request<ExperimentTemplate[]>('/api/experiments/templates');
  }

  async getTemplate(id: string): Promise<ExperimentTemplate> {
    return this.request<ExperimentTemplate>(`/api/experiments/templates/${id}`);
  }

  async createTemplate(name: string, spec: ExperimentSpec, description = '', version = '1.0.0', tags?: string[], isPublic = false): Promise<ExperimentTemplate> {
    return this.request<ExperimentTemplate>('/api/experiments/templates', { method: 'POST', body: { name, spec, description, version, tags, is_public: isPublic } });
  }

  // Benchmarks
  async listBenchmarks(): Promise<any[]> {
    return this.request<any[]>('/api/experiments/benchmarks');
  }

  // Evidence
  async getEvidence(experimentId: string): Promise<any[]> {
    return this.request<any[]>(`/api/experiments/${experimentId}/evidence`);
  }

  // Export/Import
  async exportExperiment(id: string): Promise<any> {
    return this.request(`/api/experiments/${id}/export`);
  }

  async importExperiment(package_: any, name?: string): Promise<any> {
    return this.request('/api/experiments/import', { method: 'POST', body: { package: package_, name } });
  }

  // Replay
  async replayExperiment(id: string): Promise<any> {
    return this.request(`/api/experiments/${id}/replay`);
  }

  // Snapshots
  async getSnapshot(experimentId: string): Promise<any> {
    return this.request(`/api/experiments/${experimentId}/snapshots`);
  }

  // Digital Twin
  async getTwinDemo(day: number): Promise<TwinSnapshot> {
    return this.request<TwinSnapshot>('/api/twin/demo', { params: { t: String(day) } });
  }

  async getTwinEvidence(): Promise<TwinEvidence> {
    return this.request<TwinEvidence>('/api/twin/evidence');
  }

  // Operations
  async getMonitor(): Promise<any> {
    return this.request('/api/ops/monitor');
  }

  async getIncidents(status?: string, severity?: string, type?: string): Promise<Incident[]> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (severity) params.set('severity', severity);
    if (type) params.set('type', type);
    return this.request<Incident[]>(`/api/operations/incidents?${params.toString()}`);
  }

  async createIncident(data: { type: string; severity: string; title: string; description: string; trigger_alert_id?: string; tags?: string[] }): Promise<Incident> {
    return this.request<Incident>('/api/operations/incidents', { method: 'POST', body: data });
  }

  async incidentAction(id: string, action: string, note: string): Promise<Incident> {
    return this.request<Incident>(`/api/operations/incidents/${id}/action`, { method: 'POST', body: { action, note } });
  }

  async getDecisions(status?: string, scenarioId?: string): Promise<Decision[]> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (scenarioId) params.set('scenario_id', scenarioId);
    return this.request<Decision[]>(`/api/operations/decisions?${params.toString()}`);
  }

  async decisionAction(id: string, action: string, note: string): Promise<Decision> {
    return this.request<Decision>(`/api/operations/decisions/${id}/action`, { method: 'POST', body: { action, note } });
  }

  // Explainability
  async getExplainabilityAudit(): Promise<ExplainabilityAudit> {
    return this.request<ExplainabilityAudit>('/api/explainability/audit');
  }

  async getExplainabilityEvidence(): Promise<any> {
    return this.request('/api/explainability/evidence');
  }

  // Billing
  async getBillingStatus(): Promise<BillingStatus> {
    return this.request<BillingStatus>('/api/billing/status');
  }

  async getEntitlement(): Promise<Entitlement> {
    return this.request<Entitlement>('/api/billing/entitlement');
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.request(path, options) as Promise<T>;
  }
}

export function createClient(config: Partial<RiftConfig> = {}): RiftClient {
  return new RiftClient(config);
}

// Async iterator for streaming
export async function* streamExperiments(client: RiftClient, status?: string): AsyncIterableIterator<Experiment> {
  let page = 1;
  const pageSize = 100;
  while (true) {
    const experiments = await client.listExperiments(status, pageSize);
    if (experiments.length === 0) break;
    for (const exp of experiments) yield exp;
    page++;
  }
}
'''

    def _generate_health_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { HealthStatus } from '../types';

export const healthApi = {
  async get(client: RiftClient): Promise<HealthStatus> {
    return client.health();
  },
};
'''

    def _generate_meta_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { EngineMeta } from '../types';

export const metaApi = {
  async get(client: RiftClient): Promise<EngineMeta> {
    return client.meta();
  },
};
'''

    def _generate_demo_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { DemoParams, DemoResult } from '../types';

export const demoApi = {
  async run(client: RiftClient, params?: DemoParams): Promise<DemoResult> {
    return client.runDemo(params);
  },
};
'''

    def _generate_experiments_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { Experiment, ExperimentSpec, Run, Comparison, ExperimentTemplate } from '../types';

export const experimentsApi = {
  async create(client: RiftClient, spec: ExperimentSpec): Promise<Experiment> {
    return client.createExperiment(spec);
  },
  async get(client: RiftClient, id: string): Promise<Experiment> {
    return client.getExperiment(id);
  },
  async list(client: RiftClient, status?: string, limit = 100): Promise<Experiment[]> {
    return client.listExperiments(status, limit);
  },
  async delete(client: RiftClient, id: string): Promise<void> {
    return client.deleteExperiment(id);
  },
  async createVersion(client: RiftClient, id: string, spec: ExperimentSpec, version: number, description?: string): Promise<any> {
    return client.createExperimentVersion(id, spec, version, description);
  },
  async getVersions(client: RiftClient, id: string): Promise<any[]> {
    return client.getExperimentVersions(id);
  },
  // Runs
  async createRun(client: RiftClient, experimentId: string, optimizer: string, metrics: Record<string, unknown>, result?: Record<string, unknown>, seed?: number): Promise<Run> {
    return client.createRun(experimentId, optimizer, metrics, result, seed);
  },
  async getRun(client: RiftClient, id: string): Promise<Run> {
    return client.getRun(id);
  },
  async listRuns(client: RiftClient, experimentId: string): Promise<Run[]> {
    return client.listRuns(experimentId);
  },
  // Comparison
  async compare(client: RiftClient, type: string, baselineId: string, candidateIds: string[]): Promise<Comparison> {
    return client.compare(type, baselineId, candidateIds);
  },
  // Templates
  async listTemplates(client: RiftClient): Promise<ExperimentTemplate[]> {
    return client.listTemplates();
  },
  async getTemplate(client: RiftClient, id: string): Promise<ExperimentTemplate> {
    return client.getTemplate(id);
  },
  async createTemplate(client: RiftClient, name: string, spec: ExperimentSpec, description?: string, version?: string, tags?: string[], isPublic?: boolean): Promise<ExperimentTemplate> {
    return client.createTemplate(name, spec, description, version, tags, isPublic);
  },
  // Benchmarks
  async listBenchmarks(client: RiftClient): Promise<any[]> {
    return client.listBenchmarks();
  },
  // Evidence
  async getEvidence(client: RiftClient, experimentId: string): Promise<any[]> {
    return client.getEvidence(experimentId);
  },
  // Export/Import
  async export(client: RiftClient, id: string): Promise<any> {
    return client.exportExperiment(id);
  },
  async import(client: RiftClient, pkg: any, name?: string): Promise<any> {
    return client.importExperiment(pkg, name);
  },
  // Replay
  async replay(client: RiftClient, id: string): Promise<any> {
    return client.replayExperiment(id);
  },
  // Snapshots
  async getSnapshot(client: RiftClient, experimentId: string): Promise<any> {
    return client.getSnapshot(experimentId);
  },
};
'''

    def _generate_twin_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { TwinSnapshot, TwinEvidence } from '../types';

export const twinApi = {
  async getDemo(client: RiftClient, day: number): Promise<TwinSnapshot> {
    return client.getTwinDemo(day);
  },
  async getEvidence(client: RiftClient): Promise<TwinEvidence> {
    return client.getTwinEvidence();
  },
};
'''

    def _generate_operations_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { Incident, Decision } from '../types';

export const operationsApi = {
  async getMonitor(client: RiftClient): Promise<any> {
    return client.getMonitor();
  },
  async getIncidents(client: RiftClient, status?: string, severity?: string, type?: string): Promise<Incident[]> {
    return client.getIncidents(status, severity, type);
  },
  async createIncident(client: RiftClient, data: { type: string; severity: string; title: string; description: string; trigger_alert_id?: string; tags?: string[] }): Promise<Incident> {
    return client.createIncident(data);
  },
  async incidentAction(client: RiftClient, id: string, action: string, note: string): Promise<Incident> {
    return client.incidentAction(id, action, note);
  },
  async getDecisions(client: RiftClient, status?: string, scenarioId?: string): Promise<Decision[]> {
    return client.getDecisions(status, scenarioId);
  },
  async decisionAction(client: RiftClient, id: string, action: string, note: string): Promise<Decision> {
    return client.decisionAction(id, action, note);
  },
};
'''

    def _generate_explainability_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { ExplainabilityAudit } from '../types';

export const explainabilityApi = {
  async getAudit(client: RiftClient): Promise<ExplainabilityAudit> {
    return client.getExplainabilityAudit();
  },
  async getEvidence(client: RiftClient): Promise<any> {
    return client.getExplainabilityEvidence();
  },
};
'''

    def _generate_billing_api(self) -> str:
        return '''import { RiftClient } from '../client';
import type { BillingStatus, Entitlement } from '../types';

export const billingApi = {
  async getStatus(client: RiftClient): Promise<BillingStatus> {
    return client.getBillingStatus();
  },
  async getEntitlement(client: RiftClient): Promise<Entitlement> {
    return client.getEntitlement();
  },
};
'''

    def _generate_use_experiments_hook(self) -> str:
        return '''import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createClient, RiftClient } from '../client';
import type { Experiment, ExperimentSpec, ExperimentTemplate } from '../types';

const defaultClient = new RiftClient();

export function useExperiments(status?: string, limit = 100, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['experiments', status, limit],
    queryFn: () => client.listExperiments(status, limit),
    staleTime: 30000,
  });
}

export function useExperiment(id: string, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['experiment', id],
    queryFn: () => client.getExperiment(id),
    enabled: !!id,
    staleTime: 30000,
  });
}

export function useCreateExperiment(client: RiftClient = defaultClient) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (spec: ExperimentSpec) => client.createExperiment(spec),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
    },
  });
}

export function useExperimentTemplates(client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['experimentTemplates'],
    queryFn: () => client.listTemplates(),
    staleTime: 60000,
  });
}
'''

    def _generate_use_twin_hook(self) -> str:
        return '''import { useQuery } from '@tanstack/react-query';
import { RiftClient } from '../client';
import type { TwinSnapshot, TwinEvidence } from '../types';

const defaultClient = new RiftClient();

export function useTwinDemo(day: number, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['twinDemo', day],
    queryFn: () => client.getTwinDemo(day),
    enabled: day >= 0,
    staleTime: 60000,
  });
}

export function useTwinEvidence(client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['twinEvidence'],
    queryFn: () => client.getTwinEvidence(),
    staleTime: 60000,
  });
}

export function useTwinReplay(day: number, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['twinReplay', day],
    queryFn: async () => {
      // Replay would re-run the twin up to the given day
      return client.getTwinDemo(day);
    },
    enabled: day >= 0,
  });
}
'''

    def _generate_use_monitor_hook(self) -> str:
        return '''import { useQuery } from '@tanstack/react-query';
import { RiftClient } from '../client';

const defaultClient = new RiftClient();

export function useMonitor(pollInterval = 5000, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['monitor'],
    queryFn: () => client.getMonitor(),
    refetchInterval: pollInterval,
    staleTime: 1000,
  });
}

export function useIncidents(status?: string, severity?: string, type?: string, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['incidents', status, severity, type],
    queryFn: () => client.getIncidents(status, severity, type),
    refetchInterval: 10000,
    staleTime: 5000,
  });
}

export function useDecisions(status?: string, scenarioId?: string, client: RiftClient = defaultClient) {
  return useQuery({
    queryKey: ['decisions', status, scenarioId],
    queryFn: () => client.getDecisions(status, scenarioId),
    refetchInterval: 10000,
    staleTime: 5000,
  });
}
'''

    def _generate_errors(self) -> str:
        return '''export class RiftError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number,
    public readonly response?: unknown
  ) {
    super(message);
    this.name = 'RiftError';
  }
}

export class RiftAuthenticationError extends RiftError {
  constructor(message = 'Authentication failed') {
    super(message, 401);
    this.name = 'RiftAuthenticationError';
  }
}

export class RiftRateLimitError extends RiftError {
  constructor(message = 'Rate limit exceeded', public readonly retryAfter?: number) {
    super(message, 429);
    this.name = 'RiftRateLimitError';
  }
}

export class RiftValidationError extends RiftError {
  constructor(message: string, public readonly details?: unknown) {
    super(message, 422);
    this.name = 'RiftValidationError';
  }
}

export class RiftNotFoundError extends RiftError {
  constructor(resource: string) {
    super(\`\${resource} not found\`, 404);
    this.name = 'RiftNotFoundError';
  }
}

export function isRiftError(error: unknown): error is RiftError {
  return error instanceof RiftError;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof RiftError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Unknown error';
}
'''

    def _generate_readme(self) -> str:
        return f'''# @rift/sdk

TypeScript/JavaScript SDK for the RIFT API.

## Installation

```bash
npm install @rift/sdk zod
# or
yarn add @rift/sdk zod
```

## Quick Start

```typescript
import {{ createClient, RiftClient }} from '@rift/sdk';

const client = createClient({{
  baseUrl: 'http://localhost:8080',
  apiKey: 'your-api-key',
}});

// Run a demo
const result = await client.runDemo({{ crowd: 100, smoke: 10 }});
console.log(result.guardian);

// Create an experiment
const experiment = await client.createExperiment({{
  name: 'my-experiment',
  scenario_name: 'smart-building-emergency',
  perturbations: [{{ smoke: 5 }}, {{ crowd: 50 }}],
  policy_variables: ['route_a', 'route_c', 'stairwell_b'],
  optimizer: 'exact',
  backend: 'statevector-simulator',
  seed: 42,
}});
```

## React Hooks

```tsx
import {{ useExperiments, useTwinDemo, useMonitor }} from '@rift/sdk/hooks';

function Dashboard() {{
  const {{ data: experiments }} = useExperiments();
  const {{ data: twin }} = useTwinDemo(5);
  const {{ data: monitor }} = useMonitor(5000);

  return (
    <div>
      <h1>Experiments: {{experiments?.length}}</h1>
      <h2>Twin Risk: {{twin?.risk?.risk}}</h2>
    </div>
  );
}}
```

## Configuration

```typescript
const client = createClient({{
  baseUrl: 'https://api.rift.example.com',
  apiKey: process.env.RIFT_API_KEY,
  timeout: 30000,
  maxRetries: 3,
  retryDelay: 1000,
}});
```

## Error Handling

```typescript
import {{ RiftError, RiftAuthenticationError, RiftRateLimitError }} from '@rift/sdk';

try {{
  const result = await client.runDemo({{ crowd: 100 }});
}} catch (error) {{
  if (error instanceof RiftAuthenticationError) {{
    // Handle auth error
  }} else if (error instanceof RiftRateLimitError) {{
    // Wait error.retryAfter seconds
  }} else if (error instanceof RiftError) {{
    // Handle other API errors
  }}
}}
```

## License

AGPL-3.0-or-later
'''
'''

    def _generate_client_tests(self) -> str:
        return '''import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RiftClient, RiftError, RiftAuthenticationError, RiftRateLimitError } from '../src/client';

describe('RiftClient', () => {
  let client: RiftClient;
  const mockFetch = vi.fn();
  global.fetch = mockFetch;

  beforeEach(() => {
    mockFetch.mockReset();
    client = new RiftClient({ baseUrl: 'http://localhost:8080', apiKey: 'test-key' });
  });

  it('should create client with config', () => {
    expect(client).toBeDefined();
  });

  it('should handle successful response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', engine: 'rift' }),
    });

    const result = await client.health();
    expect(result.status).toBe('ok');
  });

  it('should throw on 401', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ error: 'unauthorized' }),
    });

    await expect(client.health()).rejects.toThrow(RiftAuthenticationError);
  });

  it('should throw on 429', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      headers: new Map([['Retry-After', '5']]),
      json: async () => ({ error: 'rate limited' }),
    });

    await expect(client.health()).rejects.toThrow(RiftRateLimitError);
  });

  it('should throw on network error', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(client.health()).rejects.toThrow(RiftError);
  });
});
'''

    def _generate_api_tests(self) -> str:
        return '''import { describe, it, expect, vi } from 'vitest';
import { RiftClient } from '../src/client';

describe('RiftClient API methods', () => {
  let client: RiftClient;
  const mockFetch = vi.fn();
  global.fetch = mockFetch;

  beforeEach(() => {
    mockFetch.mockReset();
    client = new RiftClient({ baseUrl: 'http://localhost:8080' });
  });

  it('runDemo builds correct query params', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ scenario: {}, futures: [], robust: [] }),
    });

    await client.runDemo({ crowd: 100, smoke: 10, block_b: true });

    const call = mockFetch.mock.calls[0];
    const url = new URL(call[0]);
    expect(url.searchParams.get('crowd')).toBe('100');
    expect(url.searchParams.get('smoke')).toBe('10');
    expect(url.searchParams.get('block_b')).toBe('1');
  });

  it('createExperiment sends correct body', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 'exp-123', name: 'test' }),
    });

    await client.createExperiment({
      name: 'test',
      scenario_name: 'smart-building-emergency',
      optimizer: 'exact',
    });

    const call = mockFetch.mock.calls[0];
    expect(call[1]?.method).toBe('POST');
    const body = JSON.parse(call[1]?.body as string);
    expect(body.name).toBe('test');
    expect(body.optimizer).toBe('exact');
  });
});
'''