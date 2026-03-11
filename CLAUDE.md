# CLAUDE.md — claudexit

## What This Is

claudexit is an Electron desktop app (React 18 + FastAPI) that exports conversations, projects, knowledge files, memory, and uploaded files from the Claude Desktop app on Windows. Two modes: (1) Legacy wizard — 5-step flow: Connect → Preview → Configure → Export → Complete. (2) Dashboard mode (v1.0.0+) — connect source/destination accounts, browse a full dashboard of projects and conversations with per-item export, selective file picking, batch export, and account-to-account migration.

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
- **Two auth methods**: (1) Auto-detect: DPAPI cookie extraction from Claude Desktop's Chromium data dir (searches 12 candidate paths across `%APPDATA%` and `%LOCALAPPDATA%`). Kills the Network Service subprocess to bypass exclusive file lock, copies the DB, service auto-restarts. (2) Browser login: Opens an Electron BrowserWindow to claude.ai/login, polls for `sessionKey` cookie, passes cookies directly to the backend.
- **Org ID resolution**: The `lastActiveOrg` cookie may not exist on all installs. If missing, the API client auto-fetches the org ID from `GET /api/organizations`.
- **Export pipeline**: Async background tasks with WebSocket progress streaming. Supports full-account export, per-conversation export (with file selection), per-project export, and batch export of selected items.
- **Dashboard mode** (v1.0.0+): Source + destination account connection → interactive dashboard with expandable project/conversation cards, per-item export and migration, Select All (per-section + global), selection queue sidebar for batch operations.
- **Single-user desktop app**: No auth, no persistence, no multi-tenancy.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Backend ready check |
| POST | /api/connect | Extract cookies via DPAPI, verify session |
| POST | /api/connect/cookies | Accept cookies directly (browser login) |
| POST | /api/connect/destination | Connect destination account for migration |
| GET | /api/preview | List projects, conversations, memory |
| GET | /api/dashboard | Full dashboard data (projects, convs, memories, stats) |
| POST | /api/dashboard/file-counts | Scan conversations for file counts |
| GET | /api/dashboard/conversation/{uuid} | Conversation messages + files list |
| GET | /api/dashboard/project/{uuid} | Project memory, knowledge docs, conversations |
| POST | /api/export/start | Start full-account export job |
| POST | /api/export/conversation | Export single conversation (with file selection) |
| POST | /api/export/project | Export single project + its conversations |
| POST | /api/export/batch | Batch export selected items |
| GET | /api/export/status/{job_id} | Poll progress |
| WS | /api/export/stream/{job_id} | Live progress WebSocket |
| POST | /api/migrate | Generate migration prompt |
| POST | /api/migrate/memory | Migrate memory (global or project) |
| POST | /api/migrate/project | Migrate project + conversations |
| POST | /api/migrate/conversation | Migrate single conversation |
| GET | /api/migrate/status/{job_id} | Poll migration progress |
| WS | /api/migrate/stream/{job_id} | Live migration progress WebSocket |

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
| Legacy wizard steps | `src/components/wizard/Step*.tsx` |
| Dashboard (main view) | `src/components/dashboard/Dashboard.tsx` |
| Item card (project/conv) | `src/components/dashboard/ItemCard.tsx` |
| Selection queue sidebar | `src/components/dashboard/SelectionQueue.tsx` |
| Conversation detail | `src/components/dashboard/ConversationDetail.tsx` |
| Project detail viewer | `src/components/dashboard/ProjectDetail.tsx` |
| Cookie extraction | `backend/app/services/cookies.py` |
| Claude API client | `backend/app/services/claude_api.py` |
| Export pipeline | `backend/app/services/exporter.py` |
| Migration service | `backend/app/services/migration.py` |
| Utility functions | `backend/app/utils.py` |
| Pydantic models | `backend/app/models.py` |
| FastAPI entry | `backend/app/main.py` |
| Dashboard router | `backend/app/routers/dashboard.py` |
| Export router | `backend/app/routers/export.py` |
| Connect router | `backend/app/routers/connect.py` |
| Migrate router | `backend/app/routers/migrate.py` |

## Common Gotchas

- **DPAPI**: Windows-only. The cookie extraction uses Windows CryptUnprotectData. Won't work on macOS/Linux.
- **Chromium file lock**: Claude Desktop's Network Service holds an exclusive lock (no `FILE_SHARE_READ`) on the Cookies DB. The code kills the Network Service, copies the file, and Chromium auto-restarts it. Direct SQLite readonly mode and `shutil.copy2` both fail while the lock is held.
- **Claude Desktop path varies**: Different install methods (Store, MSI, enterprise) put data in different paths. The code searches 12 candidates across `%APPDATA%` and `%LOCALAPPDATA%`. If auto-detect fails, the browser login fallback bypasses this entirely.
- **`lastActiveOrg` cookie missing**: Some installs don't set this cookie. The API client auto-resolves the org ID from `GET /api/organizations` on first use.
- **Cloudflare TLS fingerprinting**: `httpx` gets 403'd by Cloudflare on claude.ai. The API client uses `urllib.request` (via `asyncio.to_thread`) which has a compatible TLS fingerprint.
- **FastAPI trailing slashes**: Use `@router.get("")` not `@router.get("/")` — the prefix adds the path.
- **PyInstaller**: Must use `upx=False`. UPX corrupts DLLs on Windows.
- **Port 8020**: Chosen to avoid conflicts with Briefinator (8000), Sprintinator (8010).
- **Module-level state**: The connect router stores cookies and API client at module level. Single-user desktop app, so this is fine.

## Git

SSH remote uses `github.com-rahul` alias. Repo: `Rahul-999-alpha/claudexit`.
