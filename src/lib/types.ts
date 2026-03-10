export interface ConnectResponse {
  status: 'connected' | 'error'
  org_id?: string
  session_preview?: string
  error?: string
}

export interface PreviewStats {
  total_conversations: number
  total_projects: number
  total_files_referenced: number
}

export interface PreviewResponse {
  memory: string | null
  projects: ProjectInfo[]
  conversations: ConversationInfo[]
  stats: PreviewStats
}

export interface ProjectInfo {
  uuid: string
  name: string
  description?: string
  is_private?: boolean
  created_at?: string
}

export interface ConversationInfo {
  uuid: string
  name: string
  created_at: string
  model?: string
  summary?: string
  project_uuid?: string
  num_files?: number
}

export interface ExportConfig {
  output_dir: string
  export_conversations: boolean
  export_projects: boolean
  download_files: boolean
  include_thinking: boolean
  export_memory: boolean
  format: 'json' | 'md' | 'both'
  generate_migration: boolean
}

export interface ExportProgress {
  job_id: string
  status: 'running' | 'complete' | 'error'
  stage: string
  current_item: string
  conversations_total: number
  conversations_done: number
  files_total: number
  files_done: number
  knowledge_total: number
  knowledge_done: number
  errors: { item: string; error: string }[]
  output_dir: string
}

export interface MigrateResponse {
  path: string
  char_count: number
}

export type WizardStep = 'connect' | 'preview' | 'configure' | 'export' | 'complete'
