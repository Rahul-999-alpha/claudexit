import { useState } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import { Loader2, CheckCircle2, XCircle, Download, Globe, FolderOpen } from 'lucide-react'

export function StepConnectSource() {
  const {
    sourceConnectResult,
    setSourceConnectResult,
    setStep,
    setDashboardData,
    setImportMode
  } = useWizardStore()
  const [loading, setLoading] = useState(false)
  const [loadingBrowser, setLoadingBrowser] = useState(false)
  const [loadingImport, setLoadingImport] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConnect = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.connect()
      setSourceConnectResult(result)
      if (result.status === 'connected') {
        setTimeout(() => setStep('connect_destination'), 600)
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
      const cookies = await (window as any).electronAPI?.loginWithBrowser('source')
      if (!cookies) {
        setError('Login window was closed before completing login.')
        return
      }
      const result = await api.connectWithCookies(cookies)
      setSourceConnectResult(result)
      if (result.status === 'connected') {
        setTimeout(() => setStep('connect_destination'), 600)
      } else {
        setError(result.error || 'Connection failed')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Browser login failed')
    } finally {
      setLoadingBrowser(false)
    }
  }

  const handleImportFromFolder = async () => {
    setLoadingImport(true)
    setError(null)
    try {
      const dir = await window.electronAPI?.selectDirectory()
      if (!dir) {
        setLoadingImport(false)
        return
      }

      const dashboardData = await api.importScan(dir)
      setImportMode(true, dir)
      setDashboardData(dashboardData)
      // Skip connect_destination, go straight to dashboard
      // User can connect destination later from the dashboard banner
      setStep('connect_destination')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to scan export folder')
    } finally {
      setLoadingImport(false)
    }
  }

  const isConnected = sourceConnectResult?.status === 'connected'
  const isLoading = loading || loadingBrowser || loadingImport

  return (
    <div className="flex flex-col items-center justify-center gap-6 pt-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary">
          <Download size={28} className="text-primary" />
        </div>
        <h2 className="text-2xl font-semibold">Connect Source Account</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          claudexit will detect your Claude Desktop installation and extract your session
          cookies to read your conversations and projects.
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

          <div className="mt-2 flex items-center gap-3 text-muted-foreground/40">
            <div className="h-px w-12 bg-border" />
            <span className="text-xs">or</span>
            <div className="h-px w-12 bg-border" />
          </div>

          <button
            onClick={handleImportFromFolder}
            className="flex items-center gap-2 rounded-lg border border-border px-6 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <FolderOpen size={14} />
            Import from Export Folder
          </button>
          <p className="max-w-xs text-center text-[10px] text-muted-foreground/50">
            Use a previous claudexit export folder as the source for migration
          </p>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 size={20} className="animate-spin" />
          <span className="text-sm">
            {loadingImport
              ? 'Scanning export folder...'
              : loadingBrowser
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
            {sourceConnectResult.account_email || sourceConnectResult.account_name || sourceConnectResult.org_id}
          </div>
          <div className="text-xs text-green-400/70">
            Ready to read from this account
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
          <button
            onClick={handleImportFromFolder}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <FolderOpen size={12} />
            Import from Export Folder
          </button>
        </div>
      )}
    </div>
  )
}
