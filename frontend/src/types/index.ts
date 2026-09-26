// RIFT Frontend Type Definitions

// Core domain types
export interface Scenario {
  id: string
  name: string
  description: string
  initialState: Record<string, number>
  transition: TransitionModel
  constraints: Constraint[]
  objective: ObjectiveFunction
  createdAt: string
  updatedAt: string
  version: string
  tags: string[]
  dataProvenance: DataProvenance
}

export interface TransitionModel {
  type: 'bounded' | 'linear' | 'custom'
  parameters: Record<string, number>
  bounds: Record<string, [number, number]>
  validated: boolean
  validationDate?: string
}

export interface Constraint {
  id: string
  type: 'hard' | 'soft'
  expression: string
  parameters: Record<string, number>
  severity: 'high' | 'medium' | 'low'
  description: string
}

export interface ObjectiveFunction {
  type: 'minimize' | 'maximize'
  expression: string
  variables: string[]
  weights?: Record<string, number>
  target?: number
}

export interface DataProvenance {
  source: 'synthetic' | 'real' | 'validated' | 'demo'
  sourceId?: string
  collectionDate?: string
  validationStatus: 'pending' | 'validated' | 'rejected'
  checksum?: string
  metadata: Record<string, unknown>
}

export interface Future {
  id: string
  policy: Record<string, number>
  trajectory: TrajectoryPoint[]
  nominalRisk: number
  worstCaseRisk: number
  feasibility: boolean
  uncertainty: number
  contributions: Contribution[]
}

export interface TrajectoryPoint {
  day: number
  state: Record<string, number>
  risk: number
  uncertainty: number
  interventions: Record<string, number>
}

export interface Contribution {
  factor: string
  value: number
  uncertainty: number
}

export interface ExperimentResult {
  candidates: Future[]
  bestPolicy: OptimizationResult
  verification: VerificationResult
  adversarialVerification: VerificationResult[]
  robustCandidates: RobustCandidate[]
  robustQubo: QUBO | null
  quantumPolicy: OptimizationResult | null
  cvarQuantumPolicy: OptimizationResult | null
  executionMetadata: ExecutionMetadata
}

export interface OptimizationResult {
  assignment: Record<string, number>
  energy: number
  method: 'exact' | 'qaoa-simulator' | 'qaoa-hardware' | 'heuristic' | 'cvar'
  fallbackUsed: boolean
  primaryError?: string
  probability?: number
  expectedEnergy?: number
}

export interface VerificationResult {
  passed: boolean
  findings: Finding[]
  stages: StageResult[]
  action: 'ALLOW' | 'WARN' | 'WITHHOLD'
  scope: string
}

export interface Finding {
  ruleId: string
  stage: 'INPUT' | 'STATE' | 'MODEL' | 'COUNTERFACTUAL' | 'OUTPUT' | 'DEPLOYMENT'
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  action: 'WITHHOLD' | 'WARN' | 'ALLOW'
  message: string
  evidence: Record<string, unknown>
}

export interface StageResult {
  stage: string
  passed: boolean
  findings: Finding[]
}

export interface RobustCandidate {
  policy: Record<string, number>
  nominalRisk: number
  worstCaseRisk: number
  robustnessGap: number
  feasibleUnderAll: boolean
}

export interface QUBO {
  variables: string[]
  linear: Record<string, number>
  quadratic: Record<string, number>
}

export interface ExecutionMetadata {
  executionId: string
  timestamp: string
  duration: number
  backend: 'exact' | 'qaoa-simulator' | 'qaoa-hardware' | 'heuristic'
  seed: number
  fingerprint: string
  gitCommit: string
  version: string
}

export interface RobustnessReport {
  perturbations: Perturbation[]
  ranking: PolicyRanking[]
  worstCaseSpread: number
  imputedFields: string[]
}

export interface Perturbation {
  id: string
  type: 'noise' | 'stale' | 'bias' | 'temporal' | 'correlated' | 'combined'
  magnitude: number
  parameters: Record<string, number>
}

export interface PolicyRanking {
  policy: Record<string, number>
  nominalRisk: number
  worstCaseRisk: number
  robustnessGap: number
  feasibleUnderAll: boolean
}

export interface EvidenceBundle {
  id: string
  version: string
  timestamp: string
  labels: Label[]
  outcomeRule: OutcomeRule
  calibration: CalibrationReport
  heldOut: HeldOutReport
  stressSweep: StressSweepReport
  externalValidation: ExternalValidationReport
  calibrationRepair: CalibrationRepairReport
  cohort: CohortReport
  confusion: ConfusionMatrix
  sampleAdequacy: AdequacyVerdict
  warnings: string[]
}

export interface Label {
  day: number
  predictedRisk: number
  realizedEvent: boolean
  predictedEvent: boolean
}

export interface OutcomeRule {
  description: string
  restingHrMin: number
  sleepMax: number
  hrvMax: number
}

export interface CalibrationReport {
  raw: CalibrationMetrics
  calibrated: CalibrationMetrics
  params: { a: number; b: number }
  fitDays: number
  testDays: number
}

export interface CalibrationMetrics {
  ece: number
  brier: number
  agreement: number
}

export interface HeldOutReport {
  daysEvaluated: number
  eventAgreement: number
  brier: number
  intervalCoverage: number
  sensitivity: number
  specificity: number
  meanOnsetLag: number
  outcomeRule: string
  calibrationWindow: string
  heldOutWindow: string
  perDay: Label[]
  confusion: ConfusionMatrix
}

export interface ConfusionMatrix {
  tp: number
  tn: number
  fp: number
  fn: number
}

export interface StressSweepReport {
  rows: StressRow[]
  uncertaintyResponds: boolean
}

export interface StressRow {
  noiseMagnitude: number
  agreement: number
  meanUncertainty: number
}

export interface ExternalValidationReport {
  sourceId: string
  status: 'complete' | 'insufficient'
  daysEvaluated: number
  events: number
  eventAgreement: number
  brierRaw: number
  brierCalibrated: number
  eceRaw: number
  eceCalibrated: number
  slopeIntercept: { slope: number; intercept: number }
  sampleAdequacy: AdequacyVerdict
  warnings: string[]
  perDay: Label[]
  confusion: ConfusionMatrix
  recalibrated: boolean
}

export interface CalibrationRepairReport {
  raw: CalibrationMetrics
  calibrated: CalibrationMetrics
  params: { a: number; b: number }
  fitDays: number
  testDays: number
}

export interface CohortReport {
  overall: CohortMetrics
  subgroups: Record<string, CohortMetrics>
}

export interface CohortMetrics {
  n: number
  agreement: number
  brier: number
  ece: number
  sensitivity: number
  specificity: number
}

export interface AdequacyVerdict {
  verdict: 'adequate' | 'limited' | 'insufficient'
  events: number
  nonEvents: number
  bar: string
}

export interface Experiment {
  id: string
  name: string
  description: string
  scenarioId: string
  parameters: ExperimentParameters
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: ExperimentResult
  createdAt: string
  updatedAt: string
  owner: string
  tags: string[]
}

export interface ExperimentParameters {
  perturbations: Perturbation[]
  objectives: ObjectiveFunction[]
  constraints: Constraint[]
  backends: ('exact' | 'qaoa-simulator' | 'qaoa-hardware')[]
  seeds: number[]
  replications: number
}

export interface Run {
  id: string
  experimentId: string
  scenarioId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: ExperimentResult
  startedAt: string
  completedAt?: string
  duration?: number
  seed: number
  backend: string
  fingerprint: string
  logs: LogEntry[]
}

export interface LogEntry {
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
  context?: Record<string, unknown>
}

export interface User {
  id: string
  name: string
  email: string
  avatar?: string
  role: 'admin' | 'researcher' | 'viewer'
  organizationId: string
  createdAt: string
  lastActiveAt: string
}

export interface Organization {
  id: string
  name: string
  slug: string
  ownerId: string
  plan: 'free' | 'pro' | 'enterprise'
  settings: OrganizationSettings
  createdAt: string
}

export interface OrganizationSettings {
  ssoEnabled: boolean
  ssoProvider?: string
  dataRetentionDays: number
  allowedDomains: string[]
  billingEmail: string
}

export interface ApiResponse<T> {
  data: T
  meta: {
    timestamp: string
    requestId: string
    version: string
  }
}

export interface PaginatedResponse<T> {
  data: T[]
  meta: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
}

export interface WebSocketMessage<T> {
  type: string
  payload: T
  timestamp: string
  requestId?: string
}

export interface SimulationProgress {
  runId: string
  stage: 'initializing' | 'generating_futures' | 'optimizing' | 'verifying' | 'complete' | 'failed'
  progress: number
  message: string
  currentStep?: string
  totalSteps?: number
  estimatedTimeRemaining?: number
  partialResults?: Partial<ExperimentResult>
}