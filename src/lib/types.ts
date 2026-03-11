// ─── Legacy types (kept for backward compatibility with old export flow) ────

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

// ─── Wizard step ─────────────────────────────────────────────────────────────

export type WizardStep = 'connect_source' | 'connect_destination' | 'dashboard'

// ─── v1.0.0 Dashboard types ──────────────────────────────────────────────────

export interface DashboardStats {
  total_conversations: number
  total_projects: number
  total_knowledge_docs: number
  total_files: number
}

export interface DashboardProject {
  uuid: string
  name: string
  description?: string
  doc_count: number
  created_at?: string
  is_private?: boolean
  [key: string]: unknown  // allow extra Claude API fields
}

export interface DashboardConversation {
  uuid: string
  name: string
  created_at: string
  model?: string
  summary?: string
  project_uuid?: string
  num_files?: number
}

export interface DashboardResponse {
  global_memory: string | null
  project_memories: Record<string, string>  // project_uuid -> memory text
  projects: DashboardProject[]
  standalone_conversations: DashboardConversation[]
  all_conversation_uuids: string[]           // all conv UUIDs for file count scan
  stats: DashboardStats
}

// ─── v1.0.0 Migration request types ─────────────────────────────────────────

export interface HandoverOptions {
  template: string
  include_files: boolean
}

export interface MigrateMemoryRequest {
  scope: 'global' | 'project'
  project_uuid?: string
}

export interface MigrateProjectRequest {
  project_uuid: string
  migrate_conversations: boolean
  handover_options?: HandoverOptions | null
}

export interface MigrateConversationRequest {
  conversation_uuid: string
  project_uuid?: string | null  // dest project UUID
  handover_options: HandoverOptions
}

export interface MigrateJobResponse {
  job_id: string
}

export interface MigrateProgress {
  job_id: string
  status: 'running' | 'complete' | 'error'
  item_type: 'memory' | 'project' | 'conversation'
  item_name: string
  stage: string
  current_step: string
  steps_total: number
  steps_done: number
  errors: { item: string; error: string }[]
  result: Record<string, unknown>
}

// ─── Per-item export request types ───────────────────────────────────────────

export interface ExportItemConfig {
  output_dir: string
  format: 'json' | 'md' | 'both'
  download_files: boolean
  include_thinking: boolean
  file_uuids?: string[] | null  // if set, only download these files
}

export interface ExportConversationRequest {
  conversation_uuid: string
  config: ExportItemConfig
}

export interface ExportProjectRequest {
  project_uuid: string
  config: ExportItemConfig
}

export interface ExportBatchRequest {
  item_keys: string[]
  config: ExportItemConfig
}

// ─── Per-item state (tracked in Zustand store) ───────────────────────────────

export type ItemStatus = 'idle' | 'running' | 'done' | 'failed'

export interface ItemMigrationState {
  status: ItemStatus
  operation?: 'export' | 'migrate'
  jobId?: string
  destUuid?: string
  error?: string
}

// ─── v1.0.10 Dashboard detail types ─────────────────────────────────────────

export interface FileCountsResponse {
  counts: Record<string, number>
  total: number
}

export interface ConversationMessage {
  sender: string
  text: string
}

export interface ConversationFile {
  file_uuid: string
  name: string
  kind: string
}

export interface ConversationDetailResponse {
  messages: ConversationMessage[]
  files: ConversationFile[]
}

export interface KnowledgeDoc {
  file_name: string
  content_preview: string
}

export interface ProjectConversationSummary {
  uuid: string
  name: string
  created_at: string
  message_count: number
}

export interface ProjectDetailResponse {
  memory: string | null
  knowledge_docs: KnowledgeDoc[]
  conversations: ProjectConversationSummary[]
}
