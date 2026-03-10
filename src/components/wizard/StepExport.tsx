import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import { useExportProgress } from '@/hooks/useExportProgress'
import { cn } from '@/lib/utils'
import { Loader2, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'

function ProgressBar({ value, max, className }: { value: number; max: number; className?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className={cn('h-2 w-full rounded-full bg-secondary overflow-hidden', className)}>
      <div
        className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function StepExport() {
  const { exportConfig, exportJobId, setExportJobId, exportProgress } = useWizardStore()
  const [started, setStarted] = useState(false)
  const [errorsExpanded, setErrorsExpanded] = useState(false)

  // Connect WebSocket for live progress
  useExportProgress(exportJobId)

  // Start export on mount
  useEffect(() => {
    if (started) return
    setStarted(true)

    const startExport = async () => {
      try {
        const { job_id } = await api.exportStart(exportConfig)
        setExportJobId(job_id)
      } catch (e) {
        console.error('Failed to start export:', e)
      }
    }
    startExport()
  }, [started, exportConfig, setExportJobId])

  const p = exportProgress
  const isRunning = p?.status === 'running'
  const totalDone = (p?.conversations_done || 0) + (p?.knowledge_done || 0) + (p?.files_done || 0)
  const totalAll = (p?.conversations_total || 0) + (p?.knowledge_total || 0) + (p?.files_total || 0)

  return (
    <div className="flex flex-col items-center gap-6 pt-8">
      <div className="text-center">
        <h2 className="text-xl font-semibold">
          {isRunning ? 'Exporting...' : p?.status === 'error' ? 'Export Failed' : 'Starting Export...'}
        </h2>
        {p?.current_item && (
          <p className="mt-2 text-sm text-muted-foreground max-w-md truncate">{p.current_item}</p>
        )}
      </div>

      {/* Main progress */}
      <div className="w-full max-w-lg space-y-4">
        <ProgressBar value={totalDone} max={totalAll || 1} />

        {/* Counters */}
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-lg bg-card border border-border p-3">
            <div className="text-lg font-bold">
              {p?.conversations_done || 0}
              <span className="text-muted-foreground font-normal">/{p?.conversations_total || 0}</span>
            </div>
            <div className="text-xs text-muted-foreground">Conversations</div>
          </div>
          <div className="rounded-lg bg-card border border-border p-3">
            <div className="text-lg font-bold">
              {p?.knowledge_done || 0}
              <span className="text-muted-foreground font-normal">/{p?.knowledge_total || 0}</span>
            </div>
            <div className="text-xs text-muted-foreground">Knowledge Docs</div>
          </div>
          <div className="rounded-lg bg-card border border-border p-3">
            <div className="text-lg font-bold">
              {p?.files_done || 0}
              <span className="text-muted-foreground font-normal">/{p?.files_total || 0}</span>
            </div>
            <div className="text-xs text-muted-foreground">Files</div>
          </div>
        </div>

        {/* Stage indicator */}
        {isRunning && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 size={14} className="animate-spin" />
            <span className="text-xs capitalize">{p?.stage || 'starting'}</span>
          </div>
        )}

        {/* Errors */}
        {p && p.errors.length > 0 && (
          <div className="rounded-lg bg-card border border-destructive/30 p-3">
            <button
              onClick={() => setErrorsExpanded(!errorsExpanded)}
              className="flex w-full items-center gap-2 text-left"
            >
              <AlertTriangle size={14} className="text-destructive" />
              <span className="text-xs font-medium text-destructive flex-1">
                {p.errors.length} error{p.errors.length !== 1 ? 's' : ''}
              </span>
              {errorsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            {errorsExpanded && (
              <div className="mt-2 max-h-32 overflow-y-auto space-y-1">
                {p.errors.map((err, i) => (
                  <div key={i} className="text-xs text-muted-foreground">
                    <span className="text-foreground">{err.item}:</span> {err.error}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
