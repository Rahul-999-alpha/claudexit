import { useState, useEffect } from 'react'
import { Minus, Square, X, Copy } from 'lucide-react'

export function TitleBar() {
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    const check = async () => {
      if (window.electronAPI) {
        setMaximized(await window.electronAPI.isMaximized())
      }
    }
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  const handleMinimize = () => window.electronAPI?.minimize()
  const handleMaximize = async () => {
    window.electronAPI?.maximize()
    if (window.electronAPI) {
      setMaximized(await window.electronAPI.isMaximized())
    }
  }
  const handleClose = () => window.electronAPI?.close()

  return (
    <div className="drag-region flex h-8 items-center justify-between border-b border-border bg-background px-3 select-none">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground tracking-wider uppercase">
          claudexit
        </span>
      </div>

      <div className="no-drag flex items-center">
        <button
          onClick={handleMinimize}
          className="flex h-8 w-10 items-center justify-center text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <Minus size={14} />
        </button>
        <button
          onClick={handleMaximize}
          className="flex h-8 w-10 items-center justify-center text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          {maximized ? <Copy size={12} /> : <Square size={12} />}
        </button>
        <button
          onClick={handleClose}
          className="flex h-8 w-10 items-center justify-center text-muted-foreground hover:bg-red-500 hover:text-white transition-colors"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}
