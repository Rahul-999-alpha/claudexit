import { cn } from '@/lib/utils'
import { useWizardStore } from '@/stores/wizard'
import type { WizardStep } from '@/lib/types'
import { Check } from 'lucide-react'

const STEPS: { key: WizardStep; label: string }[] = [
  { key: 'connect_source', label: 'Source' },
  { key: 'connect_destination', label: 'Destination' },
  { key: 'dashboard', label: 'Migrate' },
]

function StepIndicator() {
  const currentStep = useWizardStore((s) => s.step)
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep)

  return (
    <div className="flex items-center justify-center gap-1 py-4 px-6">
      {STEPS.map((step, i) => {
        const isComplete = i < currentIndex
        const isCurrent = i === currentIndex

        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-all',
                  isComplete && 'bg-primary text-primary-foreground',
                  isCurrent && 'bg-primary text-primary-foreground ring-2 ring-primary/30 ring-offset-1 ring-offset-background',
                  !isComplete && !isCurrent && 'bg-secondary text-muted-foreground'
                )}
              >
                {isComplete ? <Check size={14} /> : i + 1}
              </div>
              <span
                className={cn(
                  'text-xs',
                  isCurrent ? 'text-foreground font-medium' : 'text-muted-foreground'
                )}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  'mx-2 h-px w-8 transition-colors mb-5',
                  i < currentIndex ? 'bg-primary' : 'bg-border'
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function WizardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <StepIndicator />
      <div className="flex-1 overflow-y-auto px-6 pb-6">{children}</div>
    </div>
  )
}
