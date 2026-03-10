import { create } from 'zustand'
import type {
  WizardStep,
  ConnectResponse,
  PreviewResponse,
  ExportConfig,
  ExportProgress
} from '@/lib/types'

interface WizardState {
  // Current step
  step: WizardStep
  setStep: (step: WizardStep) => void

  // Step 1: Connect
  connectResult: ConnectResponse | null
  setConnectResult: (result: ConnectResponse | null) => void

  // Step 2: Preview
  previewData: PreviewResponse | null
  setPreviewData: (data: PreviewResponse | null) => void

  // Step 3: Configure
  exportConfig: ExportConfig
  updateConfig: (partial: Partial<ExportConfig>) => void

  // Step 4: Export
  exportJobId: string | null
  setExportJobId: (id: string | null) => void
  exportProgress: ExportProgress | null
  setExportProgress: (progress: ExportProgress | null) => void

  // Reset
  reset: () => void
}

const defaultConfig: ExportConfig = {
  output_dir: '',
  export_conversations: true,
  export_projects: true,
  download_files: true,
  include_thinking: true,
  export_memory: true,
  format: 'both',
  generate_migration: false
}

export const useWizardStore = create<WizardState>((set) => ({
  step: 'connect',
  setStep: (step) => set({ step }),

  connectResult: null,
  setConnectResult: (connectResult) => set({ connectResult }),

  previewData: null,
  setPreviewData: (previewData) => set({ previewData }),

  exportConfig: { ...defaultConfig },
  updateConfig: (partial) =>
    set((state) => ({ exportConfig: { ...state.exportConfig, ...partial } })),

  exportJobId: null,
  setExportJobId: (exportJobId) => set({ exportJobId }),
  exportProgress: null,
  setExportProgress: (exportProgress) => set({ exportProgress }),

  reset: () =>
    set({
      step: 'connect',
      connectResult: null,
      previewData: null,
      exportConfig: { ...defaultConfig },
      exportJobId: null,
      exportProgress: null
    })
}))
