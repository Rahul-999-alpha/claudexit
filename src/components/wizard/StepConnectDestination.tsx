import { useState } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import { Loader2, CheckCircle2, XCircle, Upload, Globe } from 'lucide-react'

export function StepConnectDestination() {
  const { destConnectResult, setDestConnectResult, setStep } = useWizardStore()
  const [loadingBrowser, setLoadingBrowser] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleBrowserLogin = async () => {
    setLoadingBrowser(true)
    setError(null)
    try {
      const cookies = await (window as any).electronAPI?.loginWithBrowser()
      if (!cookies) {
        setError('Login window was closed before completing login.')
        return
      }
      const result = await api.connectDestination(cookies)
      setDestConnectResult(result)
      if (result.status === 'connected') {
        setTimeout(() => setStep('dashboard'), 600)
      } else {
        setError(result.error || 'Connection failed')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Browser login failed')
    } finally {
      setLoadingBrowser(false)
    }
  }

  const isConnected = destConnectResult?.status === 'connected'

  return (
    <div className="flex flex-col items-center justify-center gap-6 pt-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary">
          <Upload size={28} className="text-primary" />
        </div>
        <h2 className="text-2xl font-semibold">Connect Destination Account</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Sign in to the Claude account where you want to migrate your conversations
          and projects.
        </p>
      </div>

      {!isConnected && !loadingBrowser && !error && (
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleBrowserLogin}
            className="flex items-center gap-2 rounded-lg bg-primary px-8 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Globe size={14} />
            Login with Browser
          </button>
          <p className="max-w-xs text-center text-xs text-muted-foreground">
            This should be a DIFFERENT account from your source. You can log in to any
            Claude account via browser.
          </p>
          <button
            onClick={() => setStep('dashboard')}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip — export only
          </button>
        </div>
      )}

      {loadingBrowser && (
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 size={20} className="animate-spin" />
          <span className="text-sm">Waiting for browser login...</span>
        </div>
      )}

      {isConnected && (
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2 text-blue-400">
            <CheckCircle2 size={20} />
            <span className="text-sm font-medium">Connected</span>
          </div>
          <div className="text-xs text-muted-foreground">
            Organization: {destConnectResult.org_id}
          </div>
          <div className="text-xs text-blue-400/70">
            Ready to write to this account
          </div>
        </div>
      )}

      {error && (
        <div className="flex max-w-md flex-col items-center gap-3">
          <div className="flex items-center gap-2 text-destructive">
            <XCircle size={20} />
            <span className="text-sm font-medium">Connection Failed</span>
          </div>
          <p className="text-center text-xs text-muted-foreground">{error}</p>
          <button
            onClick={handleBrowserLogin}
            className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Globe size={14} />
            Try Again
          </button>
        </div>
      )}

      <button
        onClick={() => setStep('connect_source')}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
      >
        Back to source account
      </button>
    </div>
  )
}
