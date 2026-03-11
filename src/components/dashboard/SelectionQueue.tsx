import { X, Download, ArrowRightLeft } from 'lucide-react'
import { useWizardStore } from '@/stores/wizard'

interface SelectionQueueProps {
  destConnected: boolean
  onExportSelected: (keys: string[]) => void
  onMigrateSelected: (keys: string[]) => void
}

export function SelectionQueue({ destConnected, onExportSelected, onMigrateSelected }: SelectionQueueProps) {
  const selectedItems = useWizardStore((s) => s.selectedItems)
  const toggleQueueItem = useWizardStore((s) => s.toggleQueueItem)
  const clearQueue = useWizardStore((s) => s.clearQueue)

  if (selectedItems.length === 0) return null

  // Parse display names from keys
  const items = selectedItems.map((key) => {
    const [type, ...rest] = key.split(':')
    const uuid = rest.join(':')
    return { key, type, uuid, label: `${type === 'project' ? 'Project' : 'Conversation'} ${uuid.slice(0, 8)}…` }
  })

  return (
    <div className="flex w-72 shrink-0 flex-col border-l border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">Queue</h3>
          <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
            {selectedItems.length}
          </span>
        </div>
        <button
          onClick={clearQueue}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Item list */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <div className="flex flex-col gap-1.5">
          {items.map((item) => (
            <div
              key={item.key}
              className="flex items-center gap-2 rounded-lg bg-secondary/50 px-3 py-2"
            >
              <span className="min-w-0 flex-1 truncate text-xs text-foreground">
                {item.label}
              </span>
              <button
                onClick={() => toggleQueueItem(item.key)}
                className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2 border-t border-border p-4">
        <button
          onClick={() => onExportSelected(selectedItems)}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Download size={13} />
          Export Selected
        </button>
        <button
          onClick={() => onMigrateSelected(selectedItems)}
          disabled={!destConnected}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ArrowRightLeft size={13} />
          Migrate Selected
        </button>
      </div>
    </div>
  )
}
