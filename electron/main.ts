import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { startBackend, stopBackend, waitForBackend } from './services/backend'

let mainWindow: BrowserWindow | null = null

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 640,
    minWidth: 700,
    minHeight: 550,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0D0D0D',
    show: false,
    resizable: true,
    webPreferences: {
      preload: join(__dirname, '../preload/preload.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.claudexit.app')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // IPC handlers
  ipcMain.on('window-minimize', () => mainWindow?.minimize())
  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.on('window-close', () => mainWindow?.close())
  ipcMain.handle('window-is-maximized', () => mainWindow?.isMaximized() ?? false)

  ipcMain.handle('select-directory', async () => {
    if (!mainWindow) return null
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory', 'createDirectory'],
      title: 'Select Export Directory'
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

  ipcMain.handle('open-path', async (_event, path: string) => {
    await shell.openPath(path)
  })

  ipcMain.handle('login-with-browser', async () => {
    return new Promise<Record<string, string> | null>((resolve) => {
      const loginWindow = new BrowserWindow({
        width: 900,
        height: 700,
        parent: mainWindow ?? undefined,
        modal: true,
        title: 'Log in to Claude',
        webPreferences: { nodeIntegration: false, contextIsolation: true }
      })

      loginWindow.setMenuBarVisibility(false)
      loginWindow.loadURL('https://claude.ai/login')

      // Poll for sessionKey cookie every second
      const interval = setInterval(async () => {
        try {
          const cookies = await loginWindow.webContents.session.cookies.get({
            url: 'https://claude.ai'
          })
          const hasSession = cookies.some((c) => c.name === 'sessionKey')
          if (hasSession) {
            clearInterval(interval)
            const cookieMap: Record<string, string> = {}
            for (const c of cookies) {
              cookieMap[c.name] = c.value
            }
            loginWindow.close()
            resolve(cookieMap)
          }
        } catch {
          // Window may have been closed
        }
      }, 1000)

      loginWindow.on('closed', () => {
        clearInterval(interval)
        resolve(null)
      })
    })
  })

  // Start FastAPI backend
  startBackend()
  const backendReady = await waitForBackend()
  if (!backendReady) {
    console.error('Failed to start backend')
  }

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('will-quit', () => {
  stopBackend()
})
