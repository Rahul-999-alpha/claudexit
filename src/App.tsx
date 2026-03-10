import { TitleBar } from '@/components/layout/TitleBar'
import { WizardLayout } from '@/components/layout/WizardLayout'
import { StepConnect } from '@/components/wizard/StepConnect'
import { StepPreview } from '@/components/wizard/StepPreview'
import { StepConfigure } from '@/components/wizard/StepConfigure'
import { StepExport } from '@/components/wizard/StepExport'
import { StepComplete } from '@/components/wizard/StepComplete'
import { useWizardStore } from '@/stores/wizard'

function WizardRouter() {
  const step = useWizardStore((s) => s.step)

  switch (step) {
    case 'connect':
      return <StepConnect />
    case 'preview':
      return <StepPreview />
    case 'configure':
      return <StepConfigure />
    case 'export':
      return <StepExport />
    case 'complete':
      return <StepComplete />
  }
}

export default function App() {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TitleBar />
      <WizardLayout>
        <WizardRouter />
      </WizardLayout>
    </div>
  )
}
