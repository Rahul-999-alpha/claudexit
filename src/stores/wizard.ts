import { create } from 'zustand'
import type {
  WizardStep,
  ConnectResponse,
  DashboardResponse,
  MigrateProgress,
  ItemMigrationState
} from '@/lib/types'

interface WizardState {
  // Navigation
  step: WizardStep
  setStep: (step: WizardStep) => void

  // Step 1: Connect Source
  sourceConnectResult: ConnectResponse | null
  setSourceConnectResult: (result: ConnectResponse | null) => void

  // Step 2: Connect Destination
  destConnectResult: ConnectResponse | null
  setDestConnectResult: (result: ConnectResponse | null) => void

  // Step 3: Dashboard
  dashboardData: DashboardResponse | null
  setDashboardData: (data: DashboardResponse | null) => void
  dashboardLoading: boolean
  setDashboardLoading: (v: boolean) => void

  // Per-item migration state
  // Key format: "memory:global", "memory:{project_uuid}", "project:{uuid}", "conv:{uuid}"
  migrationStates: Record<string, ItemMigrationState>
  setMigrationState: (key: string, state: ItemMigrationState) => void
  getMigrationState: (key: string) => ItemMigrationState
  loadPersistedHistory: (items: Record<string, { status: string; dest_uuid: string | null }>) => void

  // Active migration jobs (jobId -> MigrateProgress)
  activeJobs: Record<string, MigrateProgress>
  setJobProgress: (jobId: string, progress: MigrateProgress) => void
  clearJob: (jobId: string) => void

  // Import mode
  importMode: boolean
  importDir: string | null
  setImportMode: (mode: boolean, dir?: string | null) => void

  // Output dir for local exports
  outputDir: string
  setOutputDir: (dir: string) => void

  // Selection queue (dashboard sidebar)
  selectedItems: string[]        // item keys: "project:{uuid}", "conv:{uuid}"
  toggleQueueItem: (key: string) => void
  selectAll: (keys: string[]) => void
  deselectAll: (keys: string[]) => void
  clearQueue: () => void

  // Reset everything
  reset: () => void
}

export const useWizardStore = create<WizardState>((set, get) => ({
  step: 'connect_source',
  setStep: (step) => set({ step }),

  sourceConnectResult: null,
  setSourceConnectResult: (sourceConnectResult) => set({ sourceConnectResult }),

  destConnectResult: null,
  setDestConnectResult: (destConnectResult) => set({ destConnectResult }),

  dashboardData: null,
  setDashboardData: (dashboardData) => set({ dashboardData }),
  dashboardLoading: false,
  setDashboardLoading: (dashboardLoading) => set({ dashboardLoading }),

  migrationStates: {},
  setMigrationState: (key, state) =>
    set((s) => ({ migrationStates: { ...s.migrationStates, [key]: state } })),
  getMigrationState: (key) => get().migrationStates[key] ?? { status: 'idle' },
  loadPersistedHistory: (items) => {
    const states: Record<string, ItemMigrationState> = {}
    for (const [key, val] of Object.entries(items)) {
      if (val.status === 'done') {
        states[key] = { status: 'done', destUuid: val.dest_uuid ?? undefined }
      }
    }
    set((s) => ({ migrationStates: { ...s.migrationStates, ...states } }))
  },

  activeJobs: {},
  setJobProgress: (jobId, progress) =>
    set((s) => ({ activeJobs: { ...s.activeJobs, [jobId]: progress } })),
  clearJob: (jobId) =>
    set((s) => {
      const activeJobs = { ...s.activeJobs }
      delete activeJobs[jobId]
      return { activeJobs }
    }),

  importMode: false,
  importDir: null,
  setImportMode: (importMode, dir = null) => set({ importMode, importDir: dir ?? null }),

  outputDir: '',
  setOutputDir: (outputDir) => set({ outputDir }),

  selectedItems: [],
  toggleQueueItem: (key) =>
    set((s) => ({
      selectedItems: s.selectedItems.includes(key)
        ? s.selectedItems.filter((k) => k !== key)
        : [...s.selectedItems, key]
    })),
  selectAll: (keys) =>
    set((s) => {
      const existing = new Set(s.selectedItems)
      for (const k of keys) existing.add(k)
      return { selectedItems: [...existing] }
    }),
  deselectAll: (keys) =>
    set((s) => {
      const toRemove = new Set(keys)
      return { selectedItems: s.selectedItems.filter((k) => !toRemove.has(k)) }
    }),
  clearQueue: () => set({ selectedItems: [] }),

  reset: () =>
    set({
      step: 'connect_source',
      sourceConnectResult: null,
      destConnectResult: null,
      dashboardData: null,
      dashboardLoading: false,
      migrationStates: {},
      activeJobs: {},
      importMode: false,
      importDir: null,
      outputDir: '',
      selectedItems: []
    })
}))
