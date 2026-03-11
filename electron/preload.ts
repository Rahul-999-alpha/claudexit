import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),

  // File system
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  openPath: (path: string) => ipcRenderer.invoke('open-path', path),

  // Browser login
  loginWithBrowser: (partition?: string) => ipcRenderer.invoke('login-with-browser', partition),

  // Platform info
  platform: process.platform
})

declare global {
  interface Window {
    electronAPI: {
      minimize: () => void
      maximize: () => void
      close: () => void
      isMaximized: () => Promise<boolean>
      selectDirectory: () => Promise<string | null>
      openPath: (path: string) => Promise<void>
      loginWithBrowser: (partition?: string) => Promise<Record<string, string> | null>
      platform: string
    }
  }
}
