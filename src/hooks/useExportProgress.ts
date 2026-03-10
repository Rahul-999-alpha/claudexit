import { useEffect, useRef } from 'react'
import { createExportWebSocket } from '@/lib/api'
import { useWizardStore } from '@/stores/wizard'
import type { ExportProgress } from '@/lib/types'

export function useExportProgress(jobId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const setExportProgress = useWizardStore((s) => s.setExportProgress)
  const setStep = useWizardStore((s) => s.setStep)

  useEffect(() => {
    if (!jobId) return

    const ws = createExportWebSocket(jobId)
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.keepalive) return

      const progress = data as ExportProgress
      setExportProgress(progress)

      if (progress.status === 'complete') {
        setStep('complete')
      }
    }

    ws.onerror = () => {
      // Fall back to polling if WebSocket fails
      console.warn('WebSocket error, connection lost')
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [jobId, setExportProgress, setStep])
}
