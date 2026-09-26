import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export interface HealthStatus {
  status: string
  engine: string
  version: string
  quantum_backend: string
  persistence: { configured: boolean }
  billing: { configured: boolean; provider: string }
}

export interface EngineMeta {
  engine: string
  engine_version: string
  quantum_backend: string
  capabilities: string[]
  optimizers: string[]
  backends: string[]
  limits: {
    max_policy_variables: number
    max_perturbations: number
    max_futures: number
    max_tree_depth: number
    max_payload_bytes: number
    max_name_length: number
    max_qubo_variables: number
    scenario_bounds: Record<string, [number, number]>
  }
  auth: { service_token_configured: boolean }
}

export interface DemoParams {
  crowd?: number
  smoke?: number
  corridor_capacity?: number
  block_b?: boolean
}

export interface RobustAssessment {
  policy: Record<string, number>
  score: number
  worst_case_score: number
  robustness_gap: number
  feasible_under_all: boolean
  worst_perturbation: Record<string, number>
}

export interface OptimizerResult {
  assignment: Record<string, number>
  energy: number
  method: string
  alpha?: number
}

export interface DemoPayload {
  scenario: {
    name: string
    initial_state: Record<string, number>
    interventions: Record<string, number[]>
  }
  futures: Array<{ policy: Record<string, number>; state: Record<string, number>; score: number; valid: boolean }>
  robust: RobustAssessment[]
  robust_optimization: {
    classical: OptimizerResult
    qaoa: OptimizerResult
    cvar_qaoa: OptimizerResult
  }
  multivariable: {
    variables: string[]
    policy_count: number
    exact: OptimizerResult
    qaoa_projection: OptimizerResult & { approximation: boolean; objective: string }
    projection_error: { max_absolute_gap: number; mean_absolute_gap: number }
    top_policies: Array<{ assignment: Record<string, number>; nominal_cost: number; robust_cost: number; feasible: boolean; worst_perturbation: Record<string, number> }>
  }
  benchmark: Array<{ method: string; energy: number; assignment: Record<string, number>; runtime_ms: number; note: string }>
  guardian: {
    passed: boolean
    checks: Array<{ passed: boolean; violations: string[] }>
    scope: string
    policy: Record<string, number>
  }
  reproducibility: {
    engine_version: string
    backend: string
    perturbations: Array<Record<string, number>>
    policy_variables: string[]
    note: string
  }
  future_tree: Array<{
    id: string
    parent_id: string | null
    depth: number
    policy: Record<string, number>
    score: number
    valid: boolean
    label: string
  }>
  causal_graph: {
    nodes: string[]
    edges: Array<{ cause: string; effect: string; strength: number }>
  }
  uncertainty: { risk_entropy: number }
}

export interface MonitorSnapshot {
  monitor: Record<string, unknown>
  alerts: Array<{ rule: string; firing: boolean; reason: string }>
}

export interface ExperimentCreate {
  name: string
  description?: string
  scenario_name?: string
  initial_state?: Record<string, number>
  perturbations?: Array<Record<string, number>>
  policy_variables?: string[]
  optimizer?: string
  backend?: string
  seed?: number | null
}

function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: string; detail?: string } | undefined
    if (data?.detail) return `${data.error || 'request_failed'}: ${data.detail}`
    if (data?.error) return data.error
    if (error.response) return `Server responded ${error.response.status}`
    return 'Server unreachable. Is the RIFT API running on :8080?'
  }
  return fallback
}

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 60000,
      headers: { 'Content-Type': 'application/json' },
    })

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => Promise.reject(error)
    )
  }

  async getHealth(): Promise<HealthStatus> {
    const response = await this.client.get<HealthStatus>('/health')
    return response.data
  }

  async getMeta(): Promise<EngineMeta> {
    const response = await this.client.get<EngineMeta>('/meta')
    return response.data
  }

  async runDemo(params: DemoParams = {}): Promise<DemoPayload> {
    const query: Record<string, string> = {}
    if (params.crowd !== undefined) query.crowd = String(params.crowd)
    if (params.smoke !== undefined) query.smoke = String(params.smoke)
    if (params.corridor_capacity !== undefined) query.corridor_capacity = String(params.corridor_capacity)
    if (params.block_b) query.block_b = '1'
    const response = await this.client.get<DemoPayload>('/demo', { params: query })
    return response.data
  }

  async getTwinDemo(day: number): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>('/twin/demo', { params: { t: day } })
    return response.data
  }

  async getTwinEvidence(): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>('/twin/evidence')
    return response.data
  }

  async getMonitor(): Promise<MonitorSnapshot> {
    const response = await this.client.get<MonitorSnapshot>('/ops/monitor')
    return response.data
  }

  async createExperiment(spec: ExperimentCreate): Promise<Record<string, unknown>> {
    const response = await this.client.post<Record<string, unknown>>('/experiments', spec)
    return response.data
  }

  async getExperiment(id: string): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>(`/experiments/${id}`)
    return response.data
  }

  async getRun(id: string): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>(`/runs/${id}`)
    return response.data
  }

  async listRuns(experimentId: string): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>(`/experiments/${experimentId}/runs`)
    return response.data
  }

  async submitReview(review: { action: string; evidence_id: string; reviewer_id: string; rationale?: string; supersedes?: string | null }): Promise<Record<string, unknown>> {
    const response = await this.client.post<Record<string, unknown>>('/twin/reviews', review)
    return response.data
  }

  async listReviews(): Promise<{ stats: Record<string, unknown>; reviews: Array<Record<string, unknown>> }> {
    const response = await this.client.get<{ stats: Record<string, unknown>; reviews: Array<Record<string, unknown>> }>('/twin/reviews')
    return response.data
  }

  async getProspectiveStats(): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>('/twin/prospective')
    return response.data
  }

  async getBillingStatus(): Promise<{ configured: boolean; provider: string }> {
    const response = await this.client.get<{ configured: boolean; provider: string }>('/billing/status')
    return response.data
  }

  async getEntitlement(): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>('/billing/entitlement')
    return response.data
  }

  getToken(): string | null {
    return localStorage.getItem('auth_token')
  }

  setToken(token: string): void {
    localStorage.setItem('auth_token', token)
  }

  clearToken(): void {
    localStorage.removeItem('auth_token')
  }
}

export const api = new ApiClient()
export default api
export { apiErrorMessage }
