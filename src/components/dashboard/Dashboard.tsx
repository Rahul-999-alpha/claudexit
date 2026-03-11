import { useEffect, useState, useCallback, useRef } from 'react'
import { Brain, FolderOpen, MessageSquare, Loader2, RefreshCw, RotateCcw, CheckSquare } from 'lucide-react'
import { api, createMigrateWebSocket, createExportWebSocket } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import { ItemCard } from './ItemCard'
import { SelectionQueue } from './SelectionQueue'
import { ConversationDetail } from './ConversationDetail'
import { ProjectDetail } from './ProjectDetail'
import { HandoverModal } from './HandoverModal'
import type {
  DashboardProject,
  DashboardConversation,
  MigrateProgress,
  HandoverOptions,
  ConversationDetailResponse,
  ProjectDetailResponse
} from '@/lib/types'

// ─── Modal state ─────────────────────────────────────────────────────────────

interface ModalState {
  open: boolean
  mode: 'project' | 'conversation' | 'memory'
  item: DashboardProject | DashboardConversation | null
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
    return `${Math.floor(diffDays / 365)}y ago`
  } catch {
    return iso
  }
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max) + '…'
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({
  icon,
  label,
  count,
  onSelectAll,
  allSelected
}: {
  icon: React.ReactNode
  label: string
  count?: number
  onSelectAll?: () => void
  allSelected?: boolean
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <span className="text-muted-foreground">{icon}</span>
      <h2 className="text-sm font-semibold text-foreground">{label}</h2>
      {count !== undefined && (
        <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground">
          {count}
        </span>
      )}
      {onSelectAll && (
        <button
          onClick={onSelectAll}
          className="ml-auto text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {allSelected ? 'Deselect All' : 'Select All'}
        </button>
      )}
    </div>
  )
}

// ─── Stats chip ───────────────────────────────────────────────────────────────

function StatChip({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1">
      <span className="text-xs font-semibold text-foreground">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export function Dashboard() {
  const {
    dashboardData,
    setDashboardData,
    dashboardLoading,
    setDashboardLoading,
    setMigrationState,
    setJobProgress,
    clearJob,
    sourceConnectResult,
    destConnectResult,
    setStep,
    reset,
    selectedItems,
    selectAll,
    deselectAll
  } = useWizardStore()

  const [error, setError] = useState<string | null>(null)
  const [modal, setModal] = useState<ModalState>({
    open: false,
    mode: 'memory',
    item: null
  })

  // Show coming-soon toast
  const [toastMsg, setToastMsg] = useState<string | null>(null)

  // File count scan
  const [fileCountsLoading, setFileCountsLoading] = useState(false)
  const [fileCounts, setFileCounts] = useState<Record<string, number> | null>(null)
  const [totalFiles, setTotalFiles] = useState<number | null>(null)
  const fileCountsScanned = useRef(false)

  // Conversation detail cache
  const [convDetails, setConvDetails] = useState<Record<string, ConversationDetailResponse>>({})
  const [convLoading, setConvLoading] = useState<Record<string, boolean>>({})
  const [convErrors, setConvErrors] = useState<Record<string, string>>({})

  // Per-conversation file selection (uuid -> Set of selected file_uuids)
  const [convFileSelection, setConvFileSelection] = useState<Record<string, Set<string>>>({})

  // Project detail cache
  const [projDetails, setProjDetails] = useState<Record<string, ProjectDetailResponse>>({})
  const [projLoading, setProjLoading] = useState<Record<string, boolean>>({})
  const [projErrors, setProjErrors] = useState<Record<string, string>>({})

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 3000)
  }

  // ── Load dashboard data ──────────────────────────────────────────────────

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true)
    setError(null)
    try {
      const data = await api.getDashboard()
      setDashboardData(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load account data')
    } finally {
      setDashboardLoading(false)
    }
  }, [setDashboardData, setDashboardLoading])

  useEffect(() => {
    if (!dashboardData) {
      loadDashboard()
    }
  }, [dashboardData, loadDashboard])

  // ── Background file count scan ──────────────────────────────────────────

  useEffect(() => {
    if (!dashboardData || fileCountsScanned.current) return
    fileCountsScanned.current = true

    const convUuids = dashboardData.all_conversation_uuids ?? dashboardData.standalone_conversations.map((c) => c.uuid)
    if (convUuids.length === 0) return

    setFileCountsLoading(true)
    api
      .getFileCounts(convUuids)
      .then((res) => {
        setFileCounts(res.counts)
        setTotalFiles(res.total)
      })
      .catch(() => {
        // Silently fail — file counts are non-critical
      })
      .finally(() => setFileCountsLoading(false))
  }, [dashboardData])

  // ── Fetch conversation detail ────────────────────────────────────────────

  const fetchConversationDetail = useCallback(async (uuid: string) => {
    if (convDetails[uuid] || convLoading[uuid]) return
    setConvLoading((prev) => ({ ...prev, [uuid]: true }))
    try {
      const data = await api.getConversationDetail(uuid)
      setConvDetails((prev) => ({ ...prev, [uuid]: data }))
      // Auto-select all files
      if (data.files.length > 0) {
        setConvFileSelection((prev) => ({
          ...prev,
          [uuid]: new Set(data.files.map((f) => f.file_uuid))
        }))
      }
    } catch (e) {
      setConvErrors((prev) => ({
        ...prev,
        [uuid]: e instanceof Error ? e.message : 'Failed to load'
      }))
    } finally {
      setConvLoading((prev) => ({ ...prev, [uuid]: false }))
    }
  }, [convDetails, convLoading])

  // ── Fetch project detail ────────────────────────────────────────────────

  const fetchProjectDetail = useCallback(async (uuid: string) => {
    if (projDetails[uuid] || projLoading[uuid]) return
    setProjLoading((prev) => ({ ...prev, [uuid]: true }))
    try {
      const data = await api.getProjectDetail(uuid)
      setProjDetails((prev) => ({ ...prev, [uuid]: data }))
    } catch (e) {
      setProjErrors((prev) => ({
        ...prev,
        [uuid]: e instanceof Error ? e.message : 'Failed to load'
      }))
    } finally {
      setProjLoading((prev) => ({ ...prev, [uuid]: false }))
    }
  }, [projDetails, projLoading])

  // ── Job tracking via WebSocket ────────────────────────────────────────────

  const trackJob = useCallback(
    (itemKey: string, jobId: string) => {
      setMigrationState(itemKey, { status: 'running', jobId })

      const ws = createMigrateWebSocket(jobId)

      ws.onmessage = (e) => {
        try {
          const progress: MigrateProgress = JSON.parse(e.data as string)
          setJobProgress(jobId, progress)

          if (progress.status === 'complete') {
            const destUuid = progress.result?.dest_uuid as string | undefined
            setMigrationState(itemKey, { status: 'done', jobId, destUuid })
            clearJob(jobId)
            ws.close()
          } else if (progress.status === 'error') {
            const firstError = progress.errors?.[0]?.error ?? 'Migration failed'
            setMigrationState(itemKey, { status: 'failed', jobId, error: firstError })
            clearJob(jobId)
            ws.close()
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        setMigrationState(itemKey, {
          status: 'failed',
          jobId,
          error: 'WebSocket connection error'
        })
        clearJob(jobId)
      }
    },
    [setMigrationState, setJobProgress, clearJob]
  )

  // ── Export job tracking via WebSocket ─────────────────────────────────────

  const trackExportJob = useCallback(
    (itemKey: string, jobId: string) => {
      setMigrationState(itemKey, { status: 'running', operation: 'export', jobId })

      const ws = createExportWebSocket(jobId)

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data as string)
          if (data.keepalive) return

          if (data.status === 'complete') {
            setMigrationState(itemKey, { status: 'done', operation: 'export', jobId })
            ws.close()
          } else if (data.status === 'error') {
            const firstError = data.errors?.[0]?.error ?? 'Export failed'
            setMigrationState(itemKey, { status: 'failed', operation: 'export', jobId, error: firstError })
            ws.close()
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        setMigrationState(itemKey, {
          status: 'failed',
          operation: 'export',
          jobId,
          error: 'WebSocket connection error'
        })
      }
    },
    [setMigrationState]
  )

  // ── Export handlers ──────────────────────────────────────────────────────

  const handleExportConversation = async (conv: DashboardConversation) => {
    const dir = await window.electronAPI.selectDirectory()
    if (!dir) return

    // If user has expanded and deselected some files, pass the selection
    const selectedFiles = convFileSelection[conv.uuid]
    const detail = convDetails[conv.uuid]
    const hasCustomSelection = selectedFiles && detail && selectedFiles.size < detail.files.length
    const fileUuids = hasCustomSelection ? [...selectedFiles] : null

    const key = `conv:${conv.uuid}`
    try {
      const { job_id } = await api.exportConversation({
        conversation_uuid: conv.uuid,
        config: { output_dir: dir, format: 'both', download_files: true, include_thinking: true, file_uuids: fileUuids }
      })
      trackExportJob(key, job_id)
    } catch (e) {
      setMigrationState(key, {
        status: 'failed',
        operation: 'export',
        error: e instanceof Error ? e.message : 'Export failed'
      })
    }
  }

  const handleExportProject = async (project: DashboardProject) => {
    const dir = await window.electronAPI.selectDirectory()
    if (!dir) return

    const key = `project:${project.uuid}`
    try {
      const { job_id } = await api.exportProject({
        project_uuid: project.uuid,
        config: { output_dir: dir, format: 'both', download_files: true, include_thinking: true }
      })
      trackExportJob(key, job_id)
    } catch (e) {
      setMigrationState(key, {
        status: 'failed',
        operation: 'export',
        error: e instanceof Error ? e.message : 'Export failed'
      })
    }
  }

  // ── Migration handlers ────────────────────────────────────────────────────

  const handleMigrateMemory = async () => {
    try {
      const { job_id } = await api.migrateMemory({ scope: 'global' })
      trackJob('memory:global', job_id)
    } catch (e) {
      setMigrationState('memory:global', {
        status: 'failed',
        error: e instanceof Error ? e.message : 'Failed to start migration'
      })
    }
  }

  const handleMigrateProject = async (
    project: DashboardProject,
    opts: { include_files: boolean; migrate_conversations?: boolean }
  ) => {
    const key = `project:${project.uuid}`
    const handoverOptions: HandoverOptions | null = opts.migrate_conversations
      ? { template: '', include_files: opts.include_files }
      : null

    try {
      const { job_id } = await api.migrateProject({
        project_uuid: project.uuid,
        migrate_conversations: opts.migrate_conversations ?? true,
        handover_options: handoverOptions
      })
      trackJob(key, job_id)
    } catch (e) {
      setMigrationState(key, {
        status: 'failed',
        error: e instanceof Error ? e.message : 'Failed to start migration'
      })
    }
  }

  const handleMigrateConversation = async (
    conv: DashboardConversation,
    opts: { template?: string; include_files: boolean }
  ) => {
    const key = `conv:${conv.uuid}`
    try {
      const { job_id } = await api.migrateConversation({
        conversation_uuid: conv.uuid,
        project_uuid: conv.project_uuid ?? null,
        handover_options: {
          template: opts.template ?? '',
          include_files: opts.include_files
        }
      })
      trackJob(key, job_id)
    } catch (e) {
      setMigrationState(key, {
        status: 'failed',
        error: e instanceof Error ? e.message : 'Failed to start migration'
      })
    }
  }

  // ── Modal handlers ────────────────────────────────────────────────────────

  const openProjectModal = (project: DashboardProject) => {
    setModal({ open: true, mode: 'project', item: project })
  }

  const openConversationModal = (conv: DashboardConversation) => {
    setModal({ open: true, mode: 'conversation', item: conv })
  }

  const closeModal = () => {
    setModal((m) => ({ ...m, open: false }))
  }

  const handleModalConfirm = (opts: {
    template?: string
    include_files: boolean
    migrate_conversations?: boolean
  }) => {
    if (modal.mode === 'memory') {
      handleMigrateMemory()
    } else if (modal.mode === 'project' && modal.item) {
      handleMigrateProject(modal.item as DashboardProject, opts)
    } else if (modal.mode === 'conversation' && modal.item) {
      handleMigrateConversation(modal.item as DashboardConversation, opts)
    }
  }

  // ── Selection queue handlers ──────────────────────────────────────────────

  const handleExportSelected = async (keys: string[]) => {
    const dir = await window.electronAPI.selectDirectory()
    if (!dir) return

    try {
      const { job_id } = await api.exportBatch({
        item_keys: keys,
        config: { output_dir: dir, format: 'both', download_files: true, include_thinking: true }
      })
      // Track on each item
      for (const key of keys) {
        setMigrationState(key, { status: 'running', operation: 'export', jobId: job_id })
      }
      // Track via WebSocket — update all items when done
      const ws = createExportWebSocket(job_id)
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data as string)
          if (data.keepalive) return
          if (data.status === 'complete') {
            for (const key of keys) {
              setMigrationState(key, { status: 'done', operation: 'export', jobId: job_id })
            }
            ws.close()
          } else if (data.status === 'error') {
            const firstError = data.errors?.[0]?.error ?? 'Export failed'
            for (const key of keys) {
              setMigrationState(key, { status: 'failed', operation: 'export', jobId: job_id, error: firstError })
            }
            ws.close()
          }
        } catch {
          // ignore
        }
      }
      ws.onerror = () => {
        for (const key of keys) {
          setMigrationState(key, { status: 'failed', operation: 'export', error: 'WebSocket error' })
        }
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Batch export failed')
    }
  }

  const handleMigrateSelected = (_keys: string[]) => {
    showToast('Bulk migrate coming soon')
  }

  // ── Select All helpers ──────────────────────────────────────────────────

  const projectKeys = dashboardData?.projects.map((p) => `project:${p.uuid}`) ?? []
  const convKeys = dashboardData?.standalone_conversations.map((c) => `conv:${c.uuid}`) ?? []
  const allKeys = [...projectKeys, ...convKeys]

  const allProjectsSelected = projectKeys.length > 0 && projectKeys.every((k) => selectedItems.includes(k))
  const allConvsSelected = convKeys.length > 0 && convKeys.every((k) => selectedItems.includes(k))
  const allItemsSelected = allKeys.length > 0 && allKeys.every((k) => selectedItems.includes(k))

  const toggleSelectAllProjects = () => {
    if (allProjectsSelected) deselectAll(projectKeys)
    else selectAll(projectKeys)
  }

  const toggleSelectAllConvs = () => {
    if (allConvsSelected) deselectAll(convKeys)
    else selectAll(convKeys)
  }

  const toggleSelectAllGlobal = () => {
    if (allItemsSelected) deselectAll(allKeys)
    else selectAll(allKeys)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const stats = dashboardData?.stats
  const hasDest = destConnectResult?.status === 'connected'

  const migrateOrPrompt = (fn: () => void) =>
    hasDest ? fn : () => showToast('Connect a destination account to migrate')

  // Resolve file count for display
  const displayFileCount = totalFiles !== null ? totalFiles : stats?.total_files ?? 0

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      {/* ── No-destination banner ── */}
      {!hasDest && (
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-amber-500/20 bg-amber-500/5 px-6 py-2">
          <span className="text-xs text-amber-400/80">Export only — no destination account connected. Migrate buttons are disabled.</span>
          <button
            onClick={() => setStep('connect_destination')}
            className="rounded-md bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-400 hover:bg-amber-500/20 transition-colors"
          >
            Connect destination
          </button>
        </div>
      )}
      {/* ── Sticky header ── */}
      <div className="flex shrink-0 items-center gap-3 border-b border-border bg-background px-6 py-3">
        {/* Left: title + account info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold text-foreground">claudexit dashboard</span>
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground/60">
            {sourceConnectResult?.org_id && (
              <span>src: {truncate(sourceConnectResult.org_id, 20)}</span>
            )}
            {sourceConnectResult?.org_id && destConnectResult?.org_id && (
              <span className="text-border">→</span>
            )}
            {destConnectResult?.org_id && (
              <span>dest: {truncate(destConnectResult.org_id, 20)}</span>
            )}
          </div>
        </div>

        {/* Center: stats chips */}
        {stats && (
          <div className="flex items-center gap-1.5">
            <StatChip value={stats.total_conversations} label="conversations" />
            <StatChip value={stats.total_projects} label="projects" />
            <StatChip value={stats.total_knowledge_docs} label="docs" />
            <StatChip
              value={fileCountsLoading ? '...' : displayFileCount}
              label="files"
            />
          </div>
        )}

        {/* Right: Select All + Start Over */}
        {dashboardData && allKeys.length > 0 && (
          <button
            onClick={toggleSelectAllGlobal}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <CheckSquare size={12} />
            {allItemsSelected ? 'Deselect All' : 'Select All'}
          </button>
        )}
        <button
          onClick={reset}
          className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <RotateCcw size={12} />
          Start Over
        </button>
      </div>

      {/* ── Loading state ── */}
      {dashboardLoading && (
        <div className="flex flex-1 items-center justify-center gap-3 text-muted-foreground">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-sm">Loading your account data...</span>
        </div>
      )}

      {/* ── Error state ── */}
      {!dashboardLoading && error && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={loadDashboard}
            className="flex items-center gap-1.5 rounded-lg bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors"
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      {/* ── Content + Queue sidebar ── */}
      {!dashboardLoading && !error && dashboardData && (
        <div className="flex flex-1 overflow-hidden">
          {/* Main scrollable content */}
          <div className="flex-1 overflow-y-auto px-6 pt-4 pb-8">

            {/* Section 1: Memory */}
            {dashboardData.global_memory && (
              <section className="mb-8">
                <SectionHeader icon={<Brain size={15} />} label="Memory" />
                <ItemCard
                  itemKey="memory:global"
                  icon={<Brain size={15} />}
                  title="Global Memory"
                  subtitle={truncate(dashboardData.global_memory, 120)}
                  destConnected={hasDest}
                  actions={['Migrate']}
                  onMigrate={migrateOrPrompt(() => setModal({ open: true, mode: 'memory', item: null }))}
                  expandable
                  expandContent={
                    <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed">
                      {dashboardData.global_memory}
                    </pre>
                  }
                />
              </section>
            )}

            {/* Section 2: Projects */}
            {dashboardData.projects.length > 0 && (
              <section className="mb-8">
                <SectionHeader
                  icon={<FolderOpen size={15} />}
                  label="Projects"
                  count={dashboardData.projects.length}
                  onSelectAll={toggleSelectAllProjects}
                  allSelected={allProjectsSelected}
                />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {dashboardData.projects.map((project) => {
                    const subtitleParts: string[] = [
                      `${project.doc_count} knowledge doc${project.doc_count !== 1 ? 's' : ''}`
                    ]
                    if (project.description) {
                      subtitleParts.push(truncate(project.description, 60))
                    }
                    return (
                      <ItemCard
                        key={project.uuid}
                        itemKey={`project:${project.uuid}`}
                        icon={<FolderOpen size={15} />}
                        title={project.name}
                        subtitle={subtitleParts.join(' · ')}
                        metadata={project.created_at ? formatDate(project.created_at) : undefined}
                        destConnected={hasDest}
                        actions={['Export', 'Migrate', 'Both']}
                        onExport={() => handleExportProject(project)}
                        onMigrate={migrateOrPrompt(() => openProjectModal(project))}
                        onBoth={async () => { await handleExportProject(project); if (hasDest) openProjectModal(project) }}
                        queueable
                        expandable
                        onExpand={() => fetchProjectDetail(project.uuid)}
                        expandContent={
                          <ProjectDetail
                            data={projDetails[project.uuid] ?? null}
                            loading={projLoading[project.uuid] ?? false}
                            error={projErrors[project.uuid]}
                          />
                        }
                      />
                    )
                  })}
                </div>
              </section>
            )}

            {/* Section 3: Conversations */}
            {dashboardData.standalone_conversations.length > 0 && (
              <section>
                <SectionHeader
                  icon={<MessageSquare size={15} />}
                  label="Conversations"
                  count={dashboardData.standalone_conversations.length}
                  onSelectAll={toggleSelectAllConvs}
                  allSelected={allConvsSelected}
                />
                <div className="flex flex-col gap-2">
                  {dashboardData.standalone_conversations.map((conv) => {
                    const fileCount = fileCounts?.[conv.uuid] ?? conv.num_files ?? 0
                    const metaParts: string[] = [formatDate(conv.created_at)]
                    if (fileCount > 0) {
                      metaParts.push(`${fileCount} file${fileCount !== 1 ? 's' : ''}`)
                    } else if (fileCountsLoading) {
                      metaParts.push('... files')
                    }
                    return (
                      <ItemCard
                        key={conv.uuid}
                        itemKey={`conv:${conv.uuid}`}
                        icon={<MessageSquare size={15} />}
                        title={conv.name || 'Untitled Conversation'}
                        subtitle={conv.summary ? truncate(conv.summary, 100) : undefined}
                        metadata={metaParts.join(' · ')}
                        destConnected={hasDest}
                        actions={['Export', 'Migrate', 'Both']}
                        onExport={() => handleExportConversation(conv)}
                        onMigrate={migrateOrPrompt(() => openConversationModal(conv))}
                        onBoth={async () => { await handleExportConversation(conv); if (hasDest) openConversationModal(conv) }}
                        queueable
                        expandable
                        onExpand={() => fetchConversationDetail(conv.uuid)}
                        expandContent={
                          <ConversationDetail
                            data={convDetails[conv.uuid] ?? null}
                            loading={convLoading[conv.uuid] ?? false}
                            error={convErrors[conv.uuid]}
                            selectedFileUuids={convFileSelection[conv.uuid]}
                            onToggleFile={(fid) => {
                              setConvFileSelection((prev) => {
                                const current = prev[conv.uuid] ?? new Set<string>()
                                const next = new Set(current)
                                if (next.has(fid)) next.delete(fid)
                                else next.add(fid)
                                return { ...prev, [conv.uuid]: next }
                              })
                            }}
                            onToggleAllFiles={() => {
                              const detail = convDetails[conv.uuid]
                              if (!detail) return
                              const current = convFileSelection[conv.uuid] ?? new Set<string>()
                              const allSelected = detail.files.every((f) => current.has(f.file_uuid))
                              setConvFileSelection((prev) => ({
                                ...prev,
                                [conv.uuid]: allSelected
                                  ? new Set<string>()
                                  : new Set(detail.files.map((f) => f.file_uuid))
                              }))
                            }}
                            allFilesSelected={
                              convDetails[conv.uuid]
                                ? convDetails[conv.uuid].files.every((f) =>
                                    (convFileSelection[conv.uuid] ?? new Set()).has(f.file_uuid)
                                  )
                                : true
                            }
                          />
                        }
                      />
                    )
                  })}
                </div>
              </section>
            )}
          </div>

          {/* Selection queue sidebar */}
          <SelectionQueue
            destConnected={hasDest}
            onExportSelected={handleExportSelected}
            onMigrateSelected={handleMigrateSelected}
          />
        </div>
      )}

      {/* ── Toast ── */}
      {toastMsg && (
        <div className="pointer-events-none fixed bottom-4 left-1/2 -translate-x-1/2 rounded-lg bg-secondary border border-border px-4 py-2 text-xs text-foreground shadow-lg">
          {toastMsg}
        </div>
      )}

      {/* ── HandoverModal ── */}
      <HandoverModal
        open={modal.open}
        onClose={closeModal}
        mode={modal.mode}
        item={modal.item}
        dashboardData={dashboardData}
        onConfirm={handleModalConfirm}
      />
    </div>
  )
}
