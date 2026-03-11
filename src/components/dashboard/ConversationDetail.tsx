import { Loader2, User, Bot, Paperclip, Check, Square } from 'lucide-react'
import type { ConversationDetailResponse } from '@/lib/types'

interface ConversationDetailProps {
  data: ConversationDetailResponse | null
  loading: boolean
  error?: string | null
  /** UUIDs of currently selected files (all selected by default) */
  selectedFileUuids?: Set<string>
  /** Called when user toggles a file */
  onToggleFile?: (fileUuid: string) => void
  /** Toggle all files on/off */
  onToggleAllFiles?: () => void
  allFilesSelected?: boolean
}

export function ConversationDetail({
  data,
  loading,
  error,
  selectedFileUuids,
  onToggleFile,
  onToggleAllFiles,
  allFilesSelected
}: ConversationDetailProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-muted-foreground">
        <Loader2 size={13} className="animate-spin" />
        <span className="text-xs">Loading conversation...</span>
      </div>
    )
  }

  if (error) {
    return (
      <p className="py-2 text-xs text-destructive">{error}</p>
    )
  }

  if (!data) return null

  const hasFileSelection = selectedFileUuids !== undefined && onToggleFile

  return (
    <div className="flex flex-col gap-3 pt-2">
      {/* Messages */}
      {data.messages.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
            Messages ({data.messages.length})
          </p>
          <div className="max-h-48 overflow-y-auto rounded-lg bg-secondary/30 p-2">
            {data.messages.map((msg, i) => (
              <div key={i} className="flex items-start gap-2 py-1">
                <span className="mt-0.5 shrink-0 text-muted-foreground">
                  {msg.sender === 'human' ? <User size={11} /> : <Bot size={11} />}
                </span>
                <p className="min-w-0 text-xs text-muted-foreground leading-relaxed">
                  {msg.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Files */}
      {data.files.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
              Files ({data.files.length})
            </p>
            {hasFileSelection && data.files.length > 1 && onToggleAllFiles && (
              <button
                onClick={onToggleAllFiles}
                className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                {allFilesSelected ? 'Deselect all' : 'Select all'}
              </button>
            )}
          </div>
          <div className="flex flex-col gap-1">
            {data.files.map((file, i) => {
              const isSelected = hasFileSelection
                ? selectedFileUuids.has(file.file_uuid)
                : true

              return (
                <button
                  key={i}
                  onClick={hasFileSelection ? () => onToggleFile(file.file_uuid) : undefined}
                  className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-left transition-colors ${
                    hasFileSelection
                      ? isSelected
                        ? 'bg-primary/10 text-foreground hover:bg-primary/15'
                        : 'bg-secondary/30 text-muted-foreground/50 hover:bg-secondary/50'
                      : 'bg-secondary/50 text-muted-foreground cursor-default'
                  }`}
                >
                  {hasFileSelection && (
                    <span className="shrink-0">
                      {isSelected
                        ? <Check size={11} className="text-primary" />
                        : <Square size={11} className="text-muted-foreground/40" />
                      }
                    </span>
                  )}
                  <Paperclip size={10} className="shrink-0" />
                  <span className="truncate">{file.name}</span>
                  <span className="shrink-0 rounded bg-secondary px-1 py-px text-[9px]">{file.kind}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {data.messages.length === 0 && data.files.length === 0 && (
        <p className="py-2 text-xs text-muted-foreground/60">No messages or files found</p>
      )}
    </div>
  )
}
