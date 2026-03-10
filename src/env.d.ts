/// <reference types="vite/client" />

declare global {
  interface Window {
    electronAPI: {
      minimize: () => void
      maximize: () => void
      close: () => void
      isMaximized: () => Promise<boolean>
      selectDirectory: () => Promise<string | null>
      openPath: (path: string) => Promise<void>
      platform: string
    }
  }
}

export {}
