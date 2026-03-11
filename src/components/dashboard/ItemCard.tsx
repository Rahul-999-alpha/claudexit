import { useState } from 'react'
import { Loader2, CheckCircle2, XCircle, Plus, Check, ChevronDown, BookmarkCheck, Undo2 } from 'lucide-react'
import { useWizardStore } from '@/stores/wizard'
import { api } from '@/lib/api'
import type { ItemMigrationState } from '@/lib/types'

// Stable fallback — same reference every call, so Zustand's Object.is check is stable
const IDLE_STATE: ItemMigrationState = { status: 'idle' }

interface ItemCardProps {
  itemKey: string
  icon: React.ReactNode
  title: string
  subtitle?: string
  metadata?: string
  actions: ('Export' | 'Migrate' | 'Both')[]
  destConnected: boolean
  onExport?: () => void
  onMigrate?: () => void
  onBoth?: () => void
  // Expandable
  expandable?: boolean
  onExpand?: () => void
  expandContent?: React.ReactNode
  // Queue
  queueable?: boolean
}

export function ItemCard({
  itemKey,
  icon,
  title,
  subtitle,
  metadata,
  actions,
  destConnected,
  onExport,
  onMigrate,
  onBoth,
  expandable = false,
  onExpand,
  expandContent,
  queueable = false
}: ItemCardProps) {
  const state = useWizardStore((s) => s.migrationStates[itemKey] ?? IDLE_STATE)
  const job = useWizardStore((s) => s.activeJobs[state.jobId ?? ''])
  const isSelected = useWizardStore((s) => s.selectedItems.includes(itemKey))
  const toggleQueueItem = useWizardStore((s) => s.toggleQueueItem)

  const [expanded, setExpanded] = useState(false)

  const setMigrationState = useWizardStore((s) => s.setMigrationState)

  const isRunning = state.status === 'running'
  const isDone = state.status === 'done'
  const isFailed = state.status === 'failed'

  const handleMarkMigrated = async () => {
    try {
      await api.markMigrated(itemKey)
      setMigrationState(itemKey, { status: 'done' })
    } catch {
      // ignore
    }
  }

  const handleUnmark = async () => {
    try {
      await api.unmarkMigrated(itemKey)
      setMigrationState(itemKey, { status: 'idle' })
    } catch {
      // ignore
    }
  }

  const borderClass = isRunning
    ? 'border-amber-500/30'
    : isDone
    ? 'border-green-500/30'
    : isFailed
    ? 'border-red-500/30'
    : isSelected
    ? 'border-primary/40'
    : 'border-border'

  const progress =
    job && job.steps_total > 0
      ? Math.round((job.steps_done / job.steps_total) * 100)
      : 0

  const truncatedDestUuid =
    state.destUuid
      ? state.destUuid.length > 12
        ? state.destUuid.slice(0, 8) + '…'
        : state.destUuid
      : null

  const handleToggleExpand = () => {
    const next = !expanded
    setExpanded(next)
    if (next && onExpand) onExpand()
  }

  return (
    <div
      className={`rounded-xl border ${borderClass} bg-card p-4 flex flex-col gap-2 hover:border-border/80 transition-colors`}
    >
      {/* Main row */}
      <div className="flex items-start gap-3">
        {/* Queue toggle */}
        {queueable && (
          <button
            onClick={() => toggleQueueItem(itemKey)}
            className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border transition-colors ${
              isSelected
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border text-muted-foreground hover:border-foreground/30'
            }`}
          >
            {isSelected ? <Check size={12} /> : <Plus size={12} />}
          </button>
        )}

        {/* Icon */}
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
          {icon}
        </div>

        {/* Text */}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{title}</p>
          {subtitle && (
            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{subtitle}</p>
          )}
          {metadata && (
            <p className="mt-1 text-xs text-muted-foreground/70">{metadata}</p>
          )}
        </div>

        {/* Status badge */}
        <div className="shrink-0">
          {isRunning && (
            <div className="flex items-center gap-1.5 text-amber-400">
              <Loader2 size={13} className="animate-spin" />
              <span className="text-xs font-medium">
                {state.operation === 'export' ? 'Exporting...' : 'Migrating...'}
              </span>
            </div>
          )}
          {isDone && (
            <div className="flex flex-col items-end gap-0.5">
              <div className="flex items-center gap-1.5 text-green-400">
                <CheckCircle2 size={13} />
                <span className="text-xs font-medium">Done</span>
              </div>
              {truncatedDestUuid && (
                <span className="text-[10px] text-muted-foreground/60">{truncatedDestUuid}</span>
              )}
            </div>
          )}
          {isFailed && (
            <div
              className="flex items-center gap-1.5 text-red-400 cursor-default"
              title={state.error ?? 'Migration failed'}
            >
              <XCircle size={13} />
              <span className="text-xs font-medium">Failed</span>
            </div>
          )}
        </div>

        {/* Expand toggle */}
        {expandable && (
          <button
            onClick={handleToggleExpand}
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronDown
              size={14}
              className={`transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            />
          </button>
        )}

        {/* Action buttons */}
        <div className="flex shrink-0 items-center gap-1.5">
          {actions.includes('Export') && (
            <button
              onClick={onExport}
              disabled={isRunning}
              className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Export
            </button>
          )}
          {actions.includes('Migrate') && (
            <button
              onClick={onMigrate}
              disabled={isRunning || isDone || !destConnected}
              className="rounded-md bg-secondary px-2.5 py-1 text-xs text-foreground hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Migrate
            </button>
          )}
          {actions.includes('Both') && (
            <button
              onClick={onBoth}
              disabled={isRunning || !destConnected}
              className="rounded-md border border-border px-2.5 py-1 text-xs text-foreground hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Both
            </button>
          )}
          {/* Mark as Migrated (idle items) / Unmark (done items) */}
          {!isRunning && !isDone && destConnected && (
            <button
              onClick={handleMarkMigrated}
              title="Mark as already migrated"
              className="rounded-md border border-border px-1.5 py-1 text-muted-foreground hover:text-green-400 hover:border-green-500/30 transition-colors"
            >
              <BookmarkCheck size={13} />
            </button>
          )}
          {isDone && (
            <button
              onClick={handleUnmark}
              title="Unmark — allow re-migration"
              className="rounded-md border border-border px-1.5 py-1 text-muted-foreground hover:text-amber-400 hover:border-amber-500/30 transition-colors"
            >
              <Undo2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expandable && expanded && expandContent && (
        <div className="border-t border-border/50 pt-2">
          {expandContent}
        </div>
      )}

      {/* Progress bar — shown only while running */}
      {isRunning && (
        <div className="flex flex-col gap-1">
          <div className="h-1 w-full rounded-full bg-primary/20">
            <div
              className="h-1 rounded-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {job && (
            <p className="text-[10px] text-muted-foreground/70">
              {job.steps_done}/{job.steps_total} — {job.current_step}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
