import type {
  ConnectResponse,
  PreviewResponse,
  ExportConfig,
  ExportProgress,
  MigrateResponse,
  DashboardResponse,
  MigrateMemoryRequest,
  MigrateProjectRequest,
  MigrateConversationRequest,
  MigrateJobResponse,
  MigrateProgress,
  FileCountsResponse,
  ConversationDetailResponse,
  ProjectDetailResponse,
  ExportConversationRequest,
  ExportProjectRequest,
  ExportBatchRequest
} from './types'

const API_BASE = 'http://127.0.0.1:8020'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `Request failed: ${res.status}`)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  connect: () => request<ConnectResponse>('/api/connect', { method: 'POST' }),

  connectWithCookies: (cookies: Record<string, string>) =>
    request<ConnectResponse>('/api/connect/cookies', {
      method: 'POST',
      body: JSON.stringify({ cookies })
    }),

  preview: () => request<PreviewResponse>('/api/preview'),

  exportStart: (config: ExportConfig) =>
    request<{ job_id: string }>('/api/export/start', {
      method: 'POST',
      body: JSON.stringify(config)
    }),

  exportStatus: (jobId: string) =>
    request<ExportProgress>(`/api/export/status/${jobId}`),

  migrate: (outputDir: string) =>
    request<MigrateResponse>('/api/migrate', {
      method: 'POST',
      body: JSON.stringify({ output_dir: outputDir })
    }),

  // ─── v1.0.0 methods ──────────────────────────────────────────────────────

  connectDestination: (cookies: Record<string, string>) =>
    request<ConnectResponse>('/api/connect/destination', {
      method: 'POST',
      body: JSON.stringify({ cookies })
    }),

  getDashboard: () => request<DashboardResponse>('/api/dashboard'),

  migrateMemory: (req: MigrateMemoryRequest) =>
    request<MigrateJobResponse>('/api/migrate/memory', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  migrateProject: (req: MigrateProjectRequest) =>
    request<MigrateJobResponse>('/api/migrate/project', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  migrateConversation: (req: MigrateConversationRequest) =>
    request<MigrateJobResponse>('/api/migrate/conversation', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  getMigrateStatus: (jobId: string) =>
    request<MigrateProgress>(`/api/migrate/status/${jobId}`),

  getFileCounts: (uuids: string[]) =>
    request<FileCountsResponse>('/api/dashboard/file-counts', {
      method: 'POST',
      body: JSON.stringify({ uuids })
    }),

  getConversationDetail: (uuid: string) =>
    request<ConversationDetailResponse>(`/api/dashboard/conversation/${uuid}`),

  getProjectDetail: (uuid: string) =>
    request<ProjectDetailResponse>(`/api/dashboard/project/${uuid}`),

  // ─── Per-item export methods ───────────────────────────────────────────

  exportConversation: (req: ExportConversationRequest) =>
    request<{ job_id: string }>('/api/export/conversation', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  exportProject: (req: ExportProjectRequest) =>
    request<{ job_id: string }>('/api/export/project', {
      method: 'POST',
      body: JSON.stringify(req)
    }),

  exportBatch: (req: ExportBatchRequest) =>
    request<{ job_id: string }>('/api/export/batch', {
      method: 'POST',
      body: JSON.stringify(req)
    })
}

export function createExportWebSocket(jobId: string): WebSocket {
  return new WebSocket(`ws://127.0.0.1:8020/api/export/stream/${jobId}`)
}

export function createMigrateWebSocket(jobId: string): WebSocket {
  return new WebSocket(`ws://127.0.0.1:8020/api/migrate/stream/${jobId}`)
}
