import { useState } from 'react'
import { api } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import { Loader2, CheckCircle2, XCircle, Plug } from 'lucide-react'

export function StepConnect() {
  const { connectResult, setConnectResult, setStep } = useWizardStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConnect = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.connect()
      setConnectResult(result)
      if (result.status === 'connected') {
        // Auto-advance after a brief moment
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

  const isConnected = connectResult?.status === 'connected'

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

      {!isConnected && !loading && (
        <button
          onClick={handleConnect}
          className="rounded-lg bg-primary px-8 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Connect
        </button>
      )}

      {loading && (
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 size={20} className="animate-spin" />
          <span className="text-sm">Detecting Claude Desktop and extracting session...</span>
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
          <div className="rounded-lg bg-secondary p-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground mb-1">Troubleshooting:</p>
            <ul className="list-disc pl-4 space-y-1">
              <li>Make sure the Claude Desktop app is installed</li>
              <li>Open Claude Desktop and log in at least once</li>
              <li>Try opening a conversation in Claude Desktop first</li>
              <li>If session expired, close and reopen Claude Desktop</li>
            </ul>
          </div>
          <button
            onClick={handleConnect}
            className="rounded-lg bg-secondary px-6 py-2 text-sm text-foreground hover:bg-accent transition-colors"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  )
}
