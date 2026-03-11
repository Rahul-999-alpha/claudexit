import { useState, useEffect } from 'react'
import { X, AlertTriangle } from 'lucide-react'
import type { DashboardProject, DashboardConversation, DashboardResponse } from '@/lib/types'

interface HandoverConfirmOptions {
  template?: string
  include_files: boolean
  migrate_conversations?: boolean
}

interface HandoverModalProps {
  open: boolean
  onClose: () => void
  mode: 'project' | 'conversation' | 'memory'
  item: DashboardProject | DashboardConversation | null
  dashboardData: DashboardResponse | null
  onConfirm: (opts: HandoverConfirmOptions) => void
}

function isConversation(
  item: DashboardProject | DashboardConversation | null
): item is DashboardConversation {
  return item != null && 'summary' in item
}

function buildDefaultTemplate(title: string): string {
  return `[HANDOVER] Continuing conversation: "${title}"

Please acknowledge this continuation and pick up where we left off. Review the conversation history to understand the context.

Note: This conversation was migrated from a previous Claude account.`
}

export function HandoverModal({
  open,
  onClose,
  mode,
  item,
  onConfirm
}: HandoverModalProps) {
  const [template, setTemplate] = useState('')
  const [includeFiles, setIncludeFiles] = useState(true)
  const [migrateConversations, setMigrateConversations] = useState(true)

  // Reset state whenever the modal opens with a new item
  useEffect(() => {
    if (open) {
      if (mode === 'conversation' && isConversation(item)) {
        setTemplate(buildDefaultTemplate(item.name || 'Untitled Conversation'))
      } else {
        setTemplate('')
      }
      setIncludeFiles(true)
      setMigrateConversations(true)
    }
  }, [open, mode, item])

  if (!open) return null

  const handleConfirm = () => {
    onConfirm({
      template: template || undefined,
      include_files: includeFiles,
      migrate_conversations: migrateConversations
    })
    onClose()
  }

  const itemName = item?.name || 'Untitled'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="relative flex w-full max-w-lg flex-col gap-4 rounded-2xl border border-border bg-background p-6 mx-4 shadow-xl">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <X size={15} />
        </button>

        {/* ── Memory mode ── */}
        {mode === 'memory' && (
          <>
            <div>
              <h2 className="text-base font-semibold text-foreground">Migrate Memory</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Global memory</p>
            </div>

            <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
              <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-400" />
              <p className="text-xs text-muted-foreground leading-relaxed">
                Memory updates can take up to 24 hours to appear in Claude as it&apos;s processed
                during the daily synthesis cycle.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={onClose}
                className="rounded-lg bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Migrate Memory
              </button>
            </div>
          </>
        )}

        {/* ── Conversation mode ── */}
        {mode === 'conversation' && (
          <>
            <div>
              <h2 className="text-base font-semibold text-foreground">Migrate Conversation</h2>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{itemName}</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-foreground">Handover Message</label>
              <textarea
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                rows={7}
                className="w-full resize-none rounded-lg border border-border bg-secondary px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none transition-colors"
                placeholder="Enter a handover message..."
              />
              <p className="text-[10px] text-muted-foreground/60">
                This message is injected at the start of the migrated conversation to provide
                context to Claude.
              </p>
            </div>

            <label className="flex cursor-pointer items-center gap-2.5 text-sm text-foreground">
              <input
                type="checkbox"
                checked={includeFiles}
                onChange={(e) => setIncludeFiles(e.target.checked)}
                className="h-3.5 w-3.5 rounded accent-primary"
              />
              Include uploaded files
            </label>

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={onClose}
                className="rounded-lg bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Start Migration
              </button>
            </div>
          </>
        )}

        {/* ── Project mode ── */}
        {mode === 'project' && (
          <>
            <div>
              <h2 className="text-base font-semibold text-foreground">Migrate Project</h2>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{itemName}</p>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              This will recreate the project, copy all knowledge docs, and inject a handover
              message into each conversation.
            </p>

            <div className="flex flex-col gap-2.5">
              <label className="flex cursor-pointer items-center gap-2.5 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={migrateConversations}
                  onChange={(e) => setMigrateConversations(e.target.checked)}
                  className="h-3.5 w-3.5 rounded accent-primary"
                />
                Migrate conversations
              </label>

              {migrateConversations && (
                <label className="ml-5 flex cursor-pointer items-center gap-2.5 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={includeFiles}
                    onChange={(e) => setIncludeFiles(e.target.checked)}
                    className="h-3.5 w-3.5 rounded accent-primary"
                  />
                  Include files in handovers
                </label>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={onClose}
                className="rounded-lg bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Start Migration
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
