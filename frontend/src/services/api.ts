import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { ApiResponse, PaginatedResponse, WebSocketMessage, SimulationProgress, Scenario, Experiment, ExperimentParameters, Run, LogEntry, EvidenceBundle, User } from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

class ApiClient {
  private client: AxiosInstance
  private ws: WebSocket | null = null
  private progressCallbacks: Map<string, (progress: SimulationProgress) => void> = new Map()

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
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
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('auth_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // Scenario API
  async getScenarios(params?: { page?: number; pageSize?: number; search?: string }) {
    const response = await this.client.get<PaginatedResponse<Scenario>>('/scenarios', { params })
    return response.data
  }

  async getScenario(id: string) {
    const response = await this.client.get<ApiResponse<Scenario>>(`/scenarios/${id}`)
    return response.data
  }

  async createScenario(data: Partial<Scenario>) {
    const response = await this.client.post<ApiResponse<Scenario>>('/scenarios', data)
    return response.data
  }

  async updateScenario(id: string, data: Partial<Scenario>) {
    const response = await this.client.patch<ApiResponse<Scenario>>(`/scenarios/${id}`, data)
    return response.data
  }

  async deleteScenario(id: string) {
    await this.client.delete(`/scenarios/${id}`)
  }

  async cloneScenario(id: string, name: string) {
    const response = await this.client.post<ApiResponse<Scenario>>(`/scenarios/${id}/clone`, { name })
    return response.data
  }

  // Experiment API
  async getExperiments(params?: { page?: number; pageSize?: number; status?: string }) {
    const response = await this.client.get<PaginatedResponse<Experiment>>('/experiments', { params })
    return response.data
  }

  async getExperiment(id: string) {
    const response = await this.client.get<ApiResponse<Experiment>>(`/experiments/${id}`)
    return response.data
  }

  async createExperiment(data: Partial<Experiment>) {
    const response = await this.client.post<ApiResponse<Experiment>>('/experiments', data)
    return response.data
  }

  async runExperiment(id: string, parameters: ExperimentParameters) {
    const response = await this.client.post<ApiResponse<Run>>(`/experiments/${id}/run`, parameters)
    return response.data
  }

  // Run API
  async getRuns(params?: { page?: number; pageSize?: number; experimentId?: string }) {
    const response = await this.client.get<PaginatedResponse<Run>>('/runs', { params })
    return response.data
  }

  async getRun(id: string) {
    const response = await this.client.get<ApiResponse<Run>>(`/runs/${id}`)
    return response.data
  }

  async getRunLogs(id: string) {
    const response = await this.client.get<ApiResponse<LogEntry[]>>(`/runs/${id}/logs`)
    return response.data
  }

  async cancelRun(id: string) {
    await this.client.post(`/runs/${id}/cancel`)
  }

  // Evidence API
  async getEvidence(runId: string) {
    const response = await this.client.get<ApiResponse<EvidenceBundle>>(`/runs/${runId}/evidence`)
    return response.data
  }

  async exportEvidence(runId: string, format: 'json' | 'pdf' = 'json') {
    const response = await this.client.get(`/runs/${runId}/evidence/export`, {
      params: { format },
      responseType: format === 'pdf' ? 'blob' : 'json',
    })
    return response.data
  }

  // Scenario Builder API
  async validateScenario(scenario: Partial<Scenario>) {
    const response = await this.client.post<ApiResponse<{ valid: boolean; errors: string[] }>>(
      '/scenarios/validate',
      scenario
    )
    return response.data
  }

  async getScenarioTemplates() {
    const response = await this.client.get<ApiResponse<Scenario[]>>('/scenarios/templates')
    return response.data
  }

  // Health API
  async getHealth() {
    const response = await this.client.get<ApiResponse<{ status: string; version: string }>>('/health')
    return response.data
  }

  async getMetrics() {
    const response = await this.client.get('/metrics')
    return response.data
  }

  // WebSocket for real-time progress
  connectProgress(runId: string, callback: (progress: SimulationProgress) => void) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.close()
    }

    this.ws = new WebSocket(`${API_BASE_URL.replace('http', 'ws')}/ws/progress/${runId}`)

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage<SimulationProgress> = JSON.parse(event.data)
        if (message.type === 'progress') {
          callback(message.payload)
          this.progressCallbacks.get(runId)?.(message.payload)
        }
      } catch (error) {
        console.error('Failed to parse progress message:', error)
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    this.ws.onclose = () => {
      this.progressCallbacks.delete(runId)
    }
  }

  disconnectProgress() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  onProgress(runId: string, callback: (progress: SimulationProgress) => void) {
    this.progressCallbacks.set(runId, callback)
  }

  // Auth
  async login(email: string, password: string) {
    const response = await this.client.post<ApiResponse<{ token: string; user: User }>>('/auth/login', {
      email,
      password,
    })
    const { token } = response.data.data
    localStorage.setItem('auth_token', token)
    return response.data
  }

  async register(data: { name: string; email: string; password: string }) {
    const response = await this.client.post<ApiResponse<{ token: string; user: User }>>('/auth/register', data)
    const { token } = response.data.data
    localStorage.setItem('auth_token', token)
    return response.data
  }

  logout() {
    localStorage.removeItem('auth_token')
    window.location.href = '/login'
  }

  getToken() {
    return localStorage.getItem('auth_token')
  }

  isAuthenticated() {
    return !!this.getToken()
  }
}

export const api = new ApiClient()
export default api