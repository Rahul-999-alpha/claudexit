import { spawn, ChildProcess } from 'child_process'
import { join } from 'path'
import { is } from '@electron-toolkit/utils'

let backendProcess: ChildProcess | null = null
const BACKEND_PORT = 8020
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

export function getBackendUrl(): string {
  return BACKEND_URL
}

export function startBackend(): void {
  const backendDir = is.dev
    ? join(__dirname, '../../backend')
    : join(process.resourcesPath, 'backend')

  const cmd = is.dev ? 'python' : join(backendDir, 'claudexit-backend.exe')

  const args = is.dev
    ? ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)]
    : ['--host', '127.0.0.1', '--port', String(BACKEND_PORT)]

  console.log(`Starting backend: ${cmd} ${args.join(' ')}`)

  backendProcess = spawn(cmd, args, {
    cwd: backendDir,
    env: { ...process.env, PORT: String(BACKEND_PORT) },
    stdio: ['pipe', 'pipe', 'pipe']
  })

  backendProcess.stdout?.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`)
  })

  backendProcess.stderr?.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`)
  })

  backendProcess.on('error', (err) => {
    console.error('Failed to start backend:', err)
  })

  backendProcess.on('exit', (code) => {
    console.log(`Backend exited with code ${code}`)
    backendProcess = null
  })
}

export function stopBackend(): void {
  if (backendProcess) {
    console.log('Stopping backend...')
    backendProcess.kill('SIGTERM')
    setTimeout(() => {
      if (backendProcess) {
        backendProcess.kill('SIGKILL')
      }
    }, 3000)
  }
}

export async function waitForBackend(maxRetries = 30, delayMs = 500): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(`${BACKEND_URL}/health`)
      if (response.ok) {
        console.log('Backend is ready')
        return true
      }
    } catch {
      // Backend not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }
  return false
}
