import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import {
  Loader2,
  MessageSquare,
  FolderOpen,
  Brain,
  FileText,
  ChevronDown,
  ChevronRight,
  ArrowRight
} from 'lucide-react'

export function StepPreview() {
  const { previewData, setPreviewData, setStep } = useWizardStore()
  const [loading, setLoading] = useState(!previewData)
  const [error, setError] = useState<string | null>(null)
  const [memoryExpanded, setMemoryExpanded] = useState(false)

  useEffect(() => {
    if (previewData) return
    const fetchPreview = async () => {
      try {
        const data = await api.preview()
        setPreviewData(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load preview')
      } finally {
        setLoading(false)
      }
    }
    fetchPreview()
  }, [previewData, setPreviewData])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 pt-16">
        <Loader2 size={24} className="animate-spin text-primary" />
        <span className="text-sm text-muted-foreground">Loading your account data...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 pt-16">
        <p className="text-sm text-destructive">{error}</p>
        <button
          onClick={() => { setError(null); setLoading(true); setPreviewData(null) }}
          className="rounded-lg bg-secondary px-4 py-2 text-sm hover:bg-accent transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!previewData) return null

  const { stats, memory, projects, conversations } = previewData

  // Group conversations by project
  const projMap = new Map(projects.map((p) => [p.uuid, p.name]))
  const grouped = new Map<string, number>()
  grouped.set('(No Project)', 0)
  for (const p of projects) grouped.set(p.name, 0)
  for (const c of conversations) {
    const pName = c.project_uuid ? projMap.get(c.project_uuid) || '(No Project)' : '(No Project)'
    grouped.set(pName, (grouped.get(pName) || 0) + 1)
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="text-center">
        <h2 className="text-xl font-semibold">Your Account</h2>
        <p className="text-sm text-muted-foreground mt-1">Here's what we found</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-card border border-border p-4 text-center">
          <MessageSquare size={20} className="mx-auto mb-2 text-primary" />
          <div className="text-2xl font-bold">{stats.total_conversations}</div>
          <div className="text-xs text-muted-foreground">Conversations</div>
        </div>
        <div className="rounded-lg bg-card border border-border p-4 text-center">
          <FolderOpen size={20} className="mx-auto mb-2 text-primary" />
          <div className="text-2xl font-bold">{stats.total_projects}</div>
          <div className="text-xs text-muted-foreground">Projects</div>
        </div>
        <div className="rounded-lg bg-card border border-border p-4 text-center">
          <FileText size={20} className="mx-auto mb-2 text-primary" />
          <div className="text-2xl font-bold">{stats.total_files_referenced}</div>
          <div className="text-xs text-muted-foreground">Files Referenced</div>
        </div>
      </div>

      {/* Memory */}
      {memory && (
        <div className="rounded-lg bg-card border border-border p-4">
          <button
            onClick={() => setMemoryExpanded(!memoryExpanded)}
            className="flex w-full items-center gap-2 text-left"
          >
            <Brain size={16} className="text-primary" />
            <span className="text-sm font-medium flex-1">Memory</span>
            <span className="text-xs text-muted-foreground mr-2">
              {memory.length.toLocaleString()} chars
            </span>
            {memoryExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {memoryExpanded && (
            <pre className="mt-3 max-h-48 overflow-y-auto rounded bg-secondary p-3 text-xs text-muted-foreground whitespace-pre-wrap">
              {memory}
            </pre>
          )}
        </div>
      )}

      {/* Projects breakdown */}
      {projects.length > 0 && (
        <div className="rounded-lg bg-card border border-border p-4">
          <div className="text-sm font-medium mb-3 flex items-center gap-2">
            <FolderOpen size={16} className="text-primary" />
            Projects
          </div>
          <div className="space-y-1">
            {Array.from(grouped.entries()).map(([name, count]) =>
              count > 0 ? (
                <div
                  key={name}
                  className="flex items-center justify-between rounded px-2 py-1.5 text-xs"
                >
                  <span className="text-foreground">{name}</span>
                  <span className="text-muted-foreground">
                    {count} conversation{count !== 1 ? 's' : ''}
                  </span>
                </div>
              ) : null
            )}
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={() => setStep('configure')}
          className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Configure Export
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
