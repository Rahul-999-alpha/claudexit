import type {
  ConnectResponse,
  PreviewResponse,
  ExportConfig,
  ExportProgress,
  MigrateResponse
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
    })
}

export function createExportWebSocket(jobId: string): WebSocket {
  return new WebSocket(`ws://127.0.0.1:8020/api/export/stream/${jobId}`)
}
