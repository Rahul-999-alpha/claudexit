import { Loader2, Brain, FileText, MessageSquare } from 'lucide-react'
import type { ProjectDetailResponse } from '@/lib/types'

interface ProjectDetailProps {
  data: ProjectDetailResponse | null
  loading: boolean
  error?: string | null
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}

export function ProjectDetail({ data, loading, error }: ProjectDetailProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-muted-foreground">
        <Loader2 size={13} className="animate-spin" />
        <span className="text-xs">Loading project details...</span>
      </div>
    )
  }

  if (error) {
    return <p className="py-2 text-xs text-destructive">{error}</p>
  }

  if (!data) return null

  const hasContent = data.memory || data.knowledge_docs.length > 0 || data.conversations.length > 0

  return (
    <div className="flex flex-col gap-3 pt-2">
      {/* Memory */}
      {data.memory && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <Brain size={11} className="text-muted-foreground/60" />
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
              Project Memory
            </p>
          </div>
          <pre className="max-h-32 overflow-y-auto rounded-lg bg-secondary/30 p-2 text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {data.memory}
          </pre>
        </div>
      )}

      {/* Knowledge Docs */}
      {data.knowledge_docs.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <FileText size={11} className="text-muted-foreground/60" />
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
              Knowledge ({data.knowledge_docs.length})
            </p>
          </div>
          <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
            {data.knowledge_docs.map((doc, i) => (
              <div
                key={i}
                className="rounded-md bg-secondary/30 px-2.5 py-1.5"
              >
                <p className="text-xs font-medium text-foreground">{doc.file_name}</p>
                {doc.content_preview && (
                  <p className="mt-0.5 text-[11px] text-muted-foreground/70 line-clamp-2">
                    {doc.content_preview}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conversations */}
      {data.conversations.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <MessageSquare size={11} className="text-muted-foreground/60" />
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
              Conversations ({data.conversations.length})
            </p>
          </div>
          <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
            {data.conversations.map((conv) => (
              <div
                key={conv.uuid}
                className="flex items-center gap-2 rounded-md bg-secondary/30 px-2.5 py-1.5"
              >
                <span className="min-w-0 flex-1 truncate text-xs text-foreground">
                  {conv.name || 'Untitled'}
                </span>
                <span className="shrink-0 text-[10px] text-muted-foreground/60">
                  {formatDate(conv.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!hasContent && (
        <p className="py-2 text-xs text-muted-foreground/60">No project data found</p>
      )}
    </div>
  )
}
