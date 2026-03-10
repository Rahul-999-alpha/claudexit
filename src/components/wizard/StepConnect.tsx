import { useState } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import { Loader2, CheckCircle2, XCircle, Plug, Globe } from 'lucide-react'

export function StepConnect() {
  const { connectResult, setConnectResult, setStep } = useWizardStore()
  const [loading, setLoading] = useState(false)
  const [loadingBrowser, setLoadingBrowser] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConnect = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.connect()
      setConnectResult(result)
      if (result.status === 'connected') {
        setTimeout(() => setStep('preview'), 600)
      } else {
        setError(result.error || 'Connection failed')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to connect to backend')
    } finally {
      setLoading(false)
    }
  }

  const handleBrowserLogin = async () => {
    setLoadingBrowser(true)
    setError(null)
    try {
      const cookies = await window.electronAPI.loginWithBrowser()
      if (!cookies) {
        setError('Login window was closed before completing login.')
        return
      }
      const result = await api.connectWithCookies(cookies)
      setConnectResult(result)
      if (result.status === 'connected') {
        setTimeout(() => setStep('preview'), 600)
      } else {
        setError(result.error || 'Connection failed')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Browser login failed')
    } finally {
      setLoadingBrowser(false)
    }
  }

  const isConnected = connectResult?.status === 'connected'
  const isLoading = loading || loadingBrowser

  return (
    <div className="flex flex-col items-center justify-center gap-6 pt-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary">
          <Plug size={28} className="text-primary" />
        </div>
        <h2 className="text-2xl font-semibold">Connect to Claude Desktop</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          claudexit will detect your Claude Desktop installation and securely
          extract your session to access your conversations and projects.
        </p>
      </div>

      {!isConnected && !isLoading && !error && (
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleConnect}
            className="rounded-lg bg-primary px-8 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Connect
          </button>
          <button
            onClick={handleBrowserLogin}
            className="flex items-center gap-2 rounded-lg bg-secondary px-6 py-2 text-sm text-foreground hover:bg-accent transition-colors"
          >
            <Globe size={14} />
            Login with Browser
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 size={20} className="animate-spin" />
          <span className="text-sm">
            {loadingBrowser
              ? 'Waiting for browser login...'
              : 'Detecting Claude Desktop and extracting session...'}
          </span>
        </div>
      )}

      {isConnected && (
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle2 size={20} />
            <span className="text-sm font-medium">Connected</span>
          </div>
          <div className="text-xs text-muted-foreground">
            Organization: {connectResult.org_id}
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
          <div className="flex gap-2">
            <button
              onClick={handleConnect}
              className="rounded-lg bg-secondary px-6 py-2 text-sm text-foreground hover:bg-accent transition-colors"
            >
              Retry
            </button>
            <button
              onClick={handleBrowserLogin}
              className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Globe size={14} />
              Login with Browser
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
