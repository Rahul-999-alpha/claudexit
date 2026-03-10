# CLAUDE.md — claudexit

## What This Is

claudexit is an Electron desktop app (React 18 + FastAPI) that exports conversations, projects, knowledge files, memory, and uploaded files from the Claude Desktop app on Windows. Wizard-style UX with 5 steps: Connect, Preview, Configure, Export, Complete.

## Development Commands

```bash
# Install deps
npm install
cd backend && pip install -r requirements.txt && cd ..

# Run dev mode (Electron + backend)
npm run dev

# Build frontend
npx electron-vite build

# Build backend binary
cd backend && python -m PyInstaller claudexit-backend.spec --noconfirm

# Build Windows installer (full pipeline)
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
# Output: release/claudexit Setup {version}.exe
```

## Architecture

- **Backend runs as subprocess**: Electron spawns `claudexit-backend.exe` (PyInstaller) on port 8020. In dev, runs `python -m uvicorn`.
- **No database**: Pure export tool. State is in-memory only (cookies, API client, job progress).
- **Cookie extraction**: DPAPI decryption of Chromium cookies from `%APPDATA%/Claude/`. Works while Claude Desktop is running (kills the Chromium Network Service subprocess to bypass exclusive file lock, copies the DB, service auto-restarts).
- **Export pipeline**: Async background task with WebSocket progress streaming.
- **Single-user desktop app**: No auth, no persistence, no multi-tenancy.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Backend ready check |
| POST | /api/connect | Extract cookies, verify session |
| GET | /api/preview | List projects, conversations, memory |
| POST | /api/export/start | Start background export job |
| GET | /api/export/status/{job_id} | Poll progress |
| WS | /api/export/stream/{job_id} | Live progress WebSocket |
| POST | /api/migrate | Generate migration prompt |

## Key Files

| Area | Files |
|------|-------|
| Electron main | `electron/main.ts` |
| Backend launcher | `electron/services/backend.ts` |
| Preload (IPC) | `electron/preload.ts` |
| React app | `src/App.tsx` (wizard router) |
| API client | `src/lib/api.ts` |
| Types | `src/lib/types.ts` |
| Zustand store | `src/stores/wizard.ts` |
| WebSocket hook | `src/hooks/useExportProgress.ts` |
| Wizard steps | `src/components/wizard/Step*.tsx` |
| Cookie extraction | `backend/app/services/cookies.py` |
| Claude API client | `backend/app/services/claude_api.py` |
| Export pipeline | `backend/app/services/exporter.py` |
| Migration prompt | `backend/app/services/migration.py` |
| Utility functions | `backend/app/utils.py` |
| Pydantic models | `backend/app/models.py` |
| FastAPI entry | `backend/app/main.py` |

## Common Gotchas

- **DPAPI**: Windows-only. The cookie extraction uses Windows CryptUnprotectData. Won't work on macOS/Linux.
- **Chromium file lock**: Claude Desktop's Network Service holds an exclusive lock (no `FILE_SHARE_READ`) on the Cookies DB. The code kills the Network Service, copies the file, and Chromium auto-restarts it. Direct SQLite readonly mode and `shutil.copy2` both fail while the lock is held.
- **Cloudflare TLS fingerprinting**: `httpx` gets 403'd by Cloudflare on claude.ai. The API client uses `urllib.request` (via `asyncio.to_thread`) which has a compatible TLS fingerprint.
- **FastAPI trailing slashes**: Use `@router.get("")` not `@router.get("/")` — the prefix adds the path.
- **PyInstaller**: Must use `upx=False`. UPX corrupts DLLs on Windows.
- **Port 8020**: Chosen to avoid conflicts with Briefinator (8000), Sprintinator (8010).
- **Module-level state**: The connect router stores cookies and API client at module level. Single-user desktop app, so this is fine.

## Git

SSH remote uses `github.com-rahul` alias. Repo: `Rahul-999-alpha/claudexit`.
