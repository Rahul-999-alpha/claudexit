import { useWizardStore } from '@/stores/wizard'
import { cn } from '@/lib/utils'
import {
  FolderOpen,
  ArrowRight,
  ArrowLeft,
  MessageSquare,
  FileText,
  Brain,
  Download,
  BookOpen,
  Sparkles
} from 'lucide-react'

function Toggle({
  checked,
  onChange,
  icon: Icon,
  label,
  description
}: {
  checked: boolean
  onChange: (v: boolean) => void
  icon: React.ElementType
  label: string
  description: string
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        'flex items-start gap-3 rounded-lg border p-3 text-left transition-colors w-full',
        checked
          ? 'border-primary/50 bg-primary/5'
          : 'border-border bg-card hover:border-border/80'
      )}
    >
      <div
        className={cn(
          'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
          checked ? 'border-primary bg-primary' : 'border-muted-foreground'
        )}
      >
        {checked && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path
              d="M1 4L3.5 6.5L9 1"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Icon size={14} className="text-primary shrink-0" />
          <span className="text-sm font-medium">{label}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
    </button>
  )
}

export function StepConfigure() {
  const { exportConfig, updateConfig, setStep } = useWizardStore()

  const handleSelectDir = async () => {
    if (!window.electronAPI) return
    const dir = await window.electronAPI.selectDirectory()
    if (dir) updateConfig({ output_dir: dir })
  }

  const canProceed = exportConfig.output_dir.length > 0

  return (
    <div className="flex flex-col gap-5">
      <div className="text-center">
        <h2 className="text-xl font-semibold">Configure Export</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Choose what to export and where to save it
        </p>
      </div>

      {/* Output directory */}
      <div className="rounded-lg bg-card border border-border p-4">
        <div className="text-sm font-medium mb-2 flex items-center gap-2">
          <FolderOpen size={14} className="text-primary" />
          Output Directory
        </div>
        <div className="flex gap-2">
          <div className="flex-1 rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground truncate">
            {exportConfig.output_dir || 'No directory selected'}
          </div>
          <button
            onClick={handleSelectDir}
            className="shrink-0 rounded-md bg-secondary px-4 py-2 text-xs font-medium hover:bg-accent transition-colors"
          >
            Browse
          </button>
        </div>
      </div>

      {/* Export options */}
      <div className="grid grid-cols-2 gap-2">
        <Toggle
          checked={exportConfig.export_conversations}
          onChange={(v) => updateConfig({ export_conversations: v })}
          icon={MessageSquare}
          label="Conversations"
          description="All chat conversations"
        />
        <Toggle
          checked={exportConfig.export_projects}
          onChange={(v) => updateConfig({ export_projects: v })}
          icon={BookOpen}
          label="Projects & Knowledge"
          description="Project docs & structure"
        />
        <Toggle
          checked={exportConfig.download_files}
          onChange={(v) => updateConfig({ download_files: v })}
          icon={Download}
          label="Download Files"
          description="PDFs, images from chats"
        />
        <Toggle
          checked={exportConfig.export_memory}
          onChange={(v) => updateConfig({ export_memory: v })}
          icon={Brain}
          label="Memory"
          description="Your Claude memory"
        />
        <Toggle
          checked={exportConfig.include_thinking}
          onChange={(v) => updateConfig({ include_thinking: v })}
          icon={Sparkles}
          label="Thinking Blocks"
          description="Include reasoning steps"
        />
        <Toggle
          checked={exportConfig.generate_migration}
          onChange={(v) => updateConfig({ generate_migration: v })}
          icon={FileText}
          label="Migration Prompt"
          description="For account migration"
        />
      </div>

      {/* Format selector */}
      <div className="rounded-lg bg-card border border-border p-4">
        <div className="text-sm font-medium mb-2">Export Format</div>
        <div className="flex gap-2">
          {(['both', 'json', 'md'] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => updateConfig({ format: fmt })}
              className={cn(
                'flex-1 rounded-md px-3 py-2 text-xs font-medium transition-colors',
                exportConfig.format === fmt
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              )}
            >
              {fmt === 'both' ? 'JSON + Markdown' : fmt === 'json' ? 'JSON Only' : 'Markdown Only'}
            </button>
          ))}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          onClick={() => setStep('preview')}
          className="flex items-center gap-2 rounded-lg bg-secondary px-5 py-2.5 text-sm hover:bg-accent transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>
        <button
          onClick={() => canProceed && setStep('export')}
          disabled={!canProceed}
          className={cn(
            'flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-medium transition-colors',
            canProceed
              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
              : 'bg-secondary text-muted-foreground cursor-not-allowed'
          )}
        >
          Start Export
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
