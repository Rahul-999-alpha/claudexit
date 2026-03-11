import { Component, type ReactNode } from 'react'
import { TitleBar } from '@/components/layout/TitleBar'
import { WizardLayout } from '@/components/layout/WizardLayout'
import { StepConnectSource } from '@/components/wizard/StepConnectSource'
import { StepConnectDestination } from '@/components/wizard/StepConnectDestination'
import { Dashboard } from '@/components/dashboard/Dashboard'
import { useWizardStore } from '@/stores/wizard'

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-sm font-medium text-destructive">Render error</p>
          <pre className="max-w-lg overflow-auto rounded-lg bg-secondary p-4 text-left text-xs text-muted-foreground">
            {this.state.error.message}
            {'\n'}
            {this.state.error.stack}
          </pre>
          <p className="text-xs text-muted-foreground">Press F12 to open DevTools for more details.</p>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const step = useWizardStore((s) => s.step)

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TitleBar />
      <ErrorBoundary>
        {step === 'dashboard' ? (
          <Dashboard />
        ) : (
          <WizardLayout>
            {step === 'connect_source' && <StepConnectSource />}
            {step === 'connect_destination' && <StepConnectDestination />}
          </WizardLayout>
        )}
      </ErrorBoundary>
    </div>
  )
}
