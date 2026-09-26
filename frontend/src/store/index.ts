import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { Scenario, Experiment, Run, User, Organization } from '@/types'

interface AppState {
  // UI State
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void

  // Theme
  theme: 'light' | 'dark' | 'system'
  setTheme: (theme: 'light' | 'dark' | 'system') => void

  // Data
  currentScenario: Scenario | null
  setCurrentScenario: (scenario: Scenario | null) => void

  currentExperiment: Experiment | null
  setCurrentExperiment: (experiment: Experiment | null) => void

  currentRun: Run | null
  setCurrentRun: (run: Run | null) => void

  // User
  user: User | null
  setUser: (user: User | null) => void

  organization: Organization | null
  setOrganization: (org: Organization | null) => void

  // Notifications
  unreadNotifications: number
  setUnreadNotifications: (count: number) => void

  // Loading states
  globalLoading: boolean
  setGlobalLoading: (loading: boolean) => void

  // Reset
  reset: () => void
}

const initialState = {
  sidebarOpen: true,
  theme: 'system' as const,
  currentScenario: null,
  currentExperiment: null,
  currentRun: null,
  user: null,
  organization: null,
  unreadNotifications: 0,
  globalLoading: false,
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialState,

      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      setTheme: (theme) => set({ theme }),

      setCurrentScenario: (scenario) => set({ currentScenario: scenario }),
      setCurrentExperiment: (experiment) => set({ currentExperiment: experiment }),
      setCurrentRun: (run) => set({ currentRun: run }),

      setUser: (user) => set({ user }),
      setOrganization: (org) => set({ organization: org }),

      setUnreadNotifications: (count) => set({ unreadNotifications: count }),

      setGlobalLoading: (loading) => set({ globalLoading: loading }),

      reset: () => set(initialState),
    }),
    {
      name: 'rift-app-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        theme: state.theme,
        user: state.user,
        organization: state.organization,
      }),
    }
  )
)

// Scenario store for builder
interface ScenarioBuilderState {
  scenario: Partial<import('@/types').Scenario> | null
  setScenario: (scenario: Partial<import('@/types').Scenario> | null) => void
  updateField: <K extends keyof import('@/types').Scenario>(field: K, value: import('@/types').Scenario[K]) => void
  reset: () => void
}

export const useScenarioBuilderStore = create<ScenarioBuilderState>()(
  persist(
    (set) => ({
      scenario: null,
      setScenario: (scenario) => set({ scenario }),
      updateField: (field, value) =>
        set((state) => ({
          scenario: state.scenario ? { ...state.scenario, [field]: value } : null,
        })),
      reset: () => set({ scenario: null }),
    }),
    {
      name: 'rift-scenario-builder',
      storage: createJSONStorage(() => sessionStorage),
    }
  )
)

// Simulation store
interface SimulationStore {
  currentRun: import('@/types').Run | null
  progress: import('@/types').SimulationProgress | null
  logs: import('@/types').LogEntry[]
  setCurrentRun: (run: import('@/types').Run | null) => void
  setProgress: (progress: import('@/types').SimulationProgress | null) => void
  addLog: (log: import('@/types').LogEntry) => void
  clearLogs: () => void
  reset: () => void
}

export const useSimulationStore = create<SimulationStore>()(
  persist(
    (set) => ({
      currentRun: null,
      progress: null,
      logs: [],
      setCurrentRun: (run) => set({ currentRun: run }),
      setProgress: (progress) => set({ progress }),
      addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
      clearLogs: () => set({ logs: [] }),
      reset: () => set({ currentRun: null, progress: null, logs: [] }),
    }),
    {
      name: 'rift-simulation',
      storage: createJSONStorage(() => sessionStorage),
    }
  )
)

// UI store for modals, drawers, etc.
interface UIStore {
  modals: Record<string, boolean>
  drawers: Record<string, boolean>
  toasts: Array<{ id: string; type: 'success' | 'error' | 'warning' | 'info'; title: string; message?: string }>
  openModal: (id: string) => void
  closeModal: (id: string) => void
  openDrawer: (id: string) => void
  closeDrawer: (id: string) => void
  addToast: (toast: { type: 'success' | 'error' | 'warning' | 'info'; title: string; message?: string }) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIStore>()(
  (set) => ({
    modals: {},
    drawers: {},
    toasts: [],
    openModal: (id) => set((state) => ({ modals: { ...state.modals, [id]: true } })),
    closeModal: (id) => set((state) => ({ modals: { ...state.modals, [id]: false } })),
    openDrawer: (id) => set((state) => ({ drawers: { ...state.drawers, [id]: true } })),
    closeDrawer: (id) => set((state) => ({ drawers: { ...state.drawers, [id]: false } })),
    addToast: (toast) =>
      set((state) => ({
        toasts: [...state.toasts, { ...toast, id: `${Date.now()}-${Math.random()}` }],
      })),
    removeToast: (id) =>
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      })),
  })
)