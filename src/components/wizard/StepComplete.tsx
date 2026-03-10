import { useState } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import {
  CheckCircle2,
  FolderOpen,
  FileText,
  RotateCcw,
  MessageSquare,
  Download,
  BookOpen,
  AlertTriangle,
  Loader2
} from 'lucide-react'

export function StepComplete() {
  const { exportProgress, exportConfig, reset } = useWizardStore()
  const [migrating, setMigrating] = useState(false)
  const [migrateResult, setMigrateResult] = useState<{ path: string; char_count: number } | null>(
    null
  )

  const p = exportProgress
  const hasErrors = (p?.errors.length || 0) > 0

  const handleOpenFolder = () => {
    if (p?.output_dir && window.electronAPI) {
      window.electronAPI.openPath(p.output_dir)
    }
  }

  const handleMigrate = async () => {
    if (!p?.output_dir) return
    setMigrating(true)
    try {
      const result = await api.migrate(p.output_dir)
      setMigrateResult(result)
    } catch (e) {
      console.error('Migration failed:', e)
    } finally {
      setMigrating(false)
    }
  }

  const handleExportAgain = () => {
    reset()
  }

  return (
    <div className="flex flex-col items-center gap-6 pt-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-500/10">
          <CheckCircle2 size={28} className="text-green-400" />
        </div>
        <h2 className="text-xl font-semibold">Export Complete</h2>
        {hasErrors && (
          <div className="flex items-center gap-1.5 text-xs text-amber-400">
            <AlertTriangle size={12} />
            {p!.errors.length} item{p!.errors.length !== 1 ? 's' : ''} had errors
          </div>
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 w-full max-w-md">
        <div className="rounded-lg bg-card border border-border p-3 text-center">
          <MessageSquare size={16} className="mx-auto mb-1 text-primary" />
          <div className="text-lg font-bold">{p?.conversations_done || 0}</div>
          <div className="text-xs text-muted-foreground">Conversations</div>
        </div>
        <div className="rounded-lg bg-card border border-border p-3 text-center">
          <BookOpen size={16} className="mx-auto mb-1 text-primary" />
          <div className="text-lg font-bold">{p?.knowledge_done || 0}</div>
          <div className="text-xs text-muted-foreground">Knowledge Docs</div>
        </div>
        <div className="rounded-lg bg-card border border-border p-3 text-center">
          <Download size={16} className="mx-auto mb-1 text-primary" />
          <div className="text-lg font-bold">{p?.files_done || 0}</div>
          <div className="text-xs text-muted-foreground">Files</div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex flex-col gap-2 w-full max-w-sm">
        <button
          onClick={handleOpenFolder}
          className="flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <FolderOpen size={16} />
          Open Export Folder
        </button>

        {exportConfig.generate_migration && !migrateResult && (
          <button
            onClick={handleMigrate}
            disabled={migrating}
            className="flex items-center justify-center gap-2 rounded-lg bg-secondary px-6 py-3 text-sm font-medium hover:bg-accent transition-colors"
          >
            {migrating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <FileText size={16} />
            )}
            Generate Migration Prompt
          </button>
        )}

        {migrateResult && (
          <div className="rounded-lg bg-card border border-border p-3 text-center">
            <div className="text-xs text-muted-foreground">Migration prompt saved</div>
            <div className="text-sm font-medium mt-1">
              {migrateResult.char_count.toLocaleString()} characters
            </div>
          </div>
        )}

        <button
          onClick={handleExportAgain}
          className="flex items-center justify-center gap-2 rounded-lg bg-secondary px-6 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <RotateCcw size={16} />
          Export Again
        </button>
      </div>
    </div>
  )
}
