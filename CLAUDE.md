# CLAUDE.md — claudexit

## What This Is

claudexit is an Electron desktop app (React 18 + FastAPI) that exports conversations, projects, knowledge files, memory, and uploaded files from the Claude Desktop app on Windows. Two modes: (1) Legacy wizard — 5-step flow: Connect → Preview → Configure → Export → Complete. (2) Dashboard mode (v1.0.0+) — connect source/destination accounts, browse a full dashboard of projects and conversations with per-item export, selective file picking, batch export, and account-to-account migration. (3) Import mode (v1.1.0+) — import from a previous claudexit export folder for users who lost source account access.

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

# Version bump (updates package.json + backend/app/main.py)
npm run version:bump 1.2.0
```

## Architecture

- **Backend runs as subprocess**: Electron spawns `claudexit-backend.exe` (PyInstaller) on port 8020. In dev, runs `python -m uvicorn`.
- **No database**: Pure export tool. Migration state persisted to `%APPDATA%/claudexit/migration_state.json`.
- **Two auth methods**: (1) Auto-detect: DPAPI cookie extraction from Claude Desktop's Chromium data dir (searches 12 candidate paths across `%APPDATA%` and `%LOCALAPPDATA%`). Kills the Network Service subprocess to bypass exclusive file lock, copies the DB, service auto-restarts. (2) Browser login: Opens an Electron BrowserWindow to claude.ai/login, polls for `sessionKey` cookie, passes cookies directly to the backend.
- **Session isolation**: Destination browser login uses an ephemeral Electron partition (no `persist:` prefix) so it starts with a clean cookie jar — prevents auto-logging into the same account as source.
- **Org ID resolution**: The `lastActiveOrg` cookie may not exist on all installs. If missing, the API client auto-fetches the org ID from `GET /api/organizations`.
- **Account identity**: Email/name captured from the organizations API response during session verification. Displayed in dashboard header and connect screens (email > name > org_id fallback chain).
- **Export pipeline**: Async background tasks with WebSocket progress streaming. Supports full-account export, per-conversation export (with file selection), per-project export, and batch export of selected items.
- **Migration pipeline**: Creates conversations on destination, uploads files (two-step: wiggle + convert_document), sends handover prompt with SSE consumption. Rate-limited with exponential backoff.
- **Import mode** (v1.1.0+): `ImportSource` class duck-types the `ClaudeAPI` read interface, reading from a previous export folder on disk. Drop-in replacement for source in all read operations.
- **Dashboard mode** (v1.0.0+): Source + destination account connection → interactive dashboard with expandable project/conversation cards, per-item export and migration, Select All (per-section + global), selection queue sidebar for batch operations.
- **File logging**: Backend logs to `%APPDATA%/claudexit/backend.log` for post-mortem debugging.
- **Single-user desktop app**: No auth, no multi-tenancy.

## claude.ai Internal API Reference

All endpoints are under `https://claude.ai/api`. Auth requires ALL claude.ai cookies + User-Agent, Referer, Origin headers (sessionKey alone gives 403). Must use `urllib.request` — `httpx` gets 403'd by Cloudflare TLS fingerprinting.

### Read Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/organizations` | List orgs. Returns email, name, uuid. Used to resolve org_id |
| GET | `/organizations/{org}/chat_conversations` | List all conversations |
| GET | `/organizations/{org}/chat_conversations/{id}?tree=True&rendering_mode=messages` | Full conversation with messages, files, summary, model |
| GET | `/organizations/{org}/projects` | List projects |
| GET | `/organizations/{org}/projects/{id}/docs` | Project knowledge docs |
| GET | `/organizations/{org}/memory` | Global memory |
| GET | `/organizations/{org}/memory?project_uuid={id}` | Project-scoped memory |
| GET | `/{org}/files/{id}/{variant}` | Download file (variants: `document_pdf`, `preview`, `thumbnail`) |
| GET | `/account_profile` | Account profile info |

### Write Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/organizations/{org}/chat_conversations` | Create conversation. Body: `{uuid, name, is_temporary, model?, project_uuid?}` |
| POST | `/organizations/{org}/projects` | Create project. Body: `{name, description, is_private}` |
| POST | `/organizations/{org}/projects/{id}/docs` | Add knowledge doc. Body: `{file_name, content}` (text content as JSON) |
| POST | `/organizations/{org}/projects/{id}/sync` | Sync project after adding docs |
| PUT | `/organizations/{org}/memory/controls` | Write memory via controls array |
| POST | `/organizations/{org}/chat_conversations/{id}/completion` | Send message (SSE response) |

### File Upload (Two-Step Process)

Uploading files to conversations requires two API calls:

**Step 1: Upload raw file**
```
POST /organizations/{org}/conversations/{id}/wiggle/upload-file
Content-Type: multipart/form-data
Accept: */*
```
- **IMPORTANT**: Uses `/conversations/` NOT `/chat_conversations/`
- Returns: `{success, path, sanitized_name, size_bytes, file_kind, file_uuid, file_name}`
- `file_kind` is `"document"`, `"image"`, or `"blob"`
- `size_bytes` may be `null` — always fallback to actual byte length

**Step 2: Convert document (documents only, skip for images)**
```
POST /organizations/{org}/convert_document
Content-Type: multipart/form-data
Accept: */*
```
- Returns: `{file_name, file_size, file_type, extracted_content, path}`
- `extracted_content` is the full text extraction of the document
- Returns 415 for images — skip this step when `file_kind == "image"` or MIME starts with `image/`
- This response IS the attachment format for the completion request

**Step 3: Include in completion request**
```json
{
  "attachments": [
    {
      "file_name": "doc.pdf",
      "file_size": 12529,
      "file_type": "pdf",
      "extracted_content": "... full text ...",
      "path": "/mnt/user-data/uploads/doc.pdf"
    }
  ],
  "files": []
}
```
- **DO NOT** use `{"type": "tool_result", "file_uuid": "..."}` format — that doesn't work
- **`files` must be `[]`** (empty), not file UUID list
- **`file_size` must be an integer**, never null — Claude returns 400 otherwise

### Completion Endpoint Details

```
POST /organizations/{org}/chat_conversations/{id}/completion
Content-Type: application/json
Accept: text/event-stream
```
- Returns Server-Sent Events (SSE), NOT JSON — do not `json.loads()` the response
- Consume chunks until connection closes: `while chunk := resp.read(4096)`
- Timeout should be generous (180s) — Claude may take 10-15s to respond
- Body includes: `prompt`, `timezone`, `attachments`, `files: []`, `rendering_mode: "messages"`, `tools: []`, `personalized_styles: []`

### Conversation Data Structure

Top-level fields from `get_conversation()`:
- `uuid`, `name`, `summary` (rich auto-generated summary), `model` (e.g. "claude-haiku-4-5-20251001")
- `created_at`, `updated_at`, `settings` (web_search, mcp_tools config)
- `chat_messages[]` — each has: `sender` ("human"/"assistant"), `content` (string or content blocks array), `files_v2[]`, `created_at`

Content block types: `text`, `thinking`, `tool_use`, `tool_result`, `document`

### Rate Limiting

- Retryable codes: `429`, `529`, `500`, `502`, `503`
- Exponential backoff: 2s, 4s, 8s, 16s, 32s (5 retries max)
- Respect `Retry-After` header when present
- Inter-operation delays: 1.0s for creates/docs/memory, 1.5s for file uploads, 2.0s before handover completion, 3.0s between conversations in bulk migration

## API Endpoints (claudexit backend)

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
| POST | /api/import/scan | Scan export folder, return dashboard data (import mode) |
| POST | /api/migrate/memory | Migrate memory (global or project) |
| POST | /api/migrate/project | Migrate project + conversations |
| POST | /api/migrate/conversation | Migrate single conversation |
| GET | /api/migrate/handover-preview | Build enriched handover template for preview |
| GET | /api/migrate/history | Load persisted migration states |
| POST | /api/migrate/mark | Manually mark item as migrated |
| POST | /api/migrate/unmark | Remove migration record |
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
| Handover modal | `src/components/dashboard/HandoverModal.tsx` |
| Selection queue sidebar | `src/components/dashboard/SelectionQueue.tsx` |
| Conversation detail | `src/components/dashboard/ConversationDetail.tsx` |
| Project detail viewer | `src/components/dashboard/ProjectDetail.tsx` |
| Cookie extraction | `backend/app/services/cookies.py` |
| Claude API client | `backend/app/services/claude_api.py` |
| Export pipeline | `backend/app/services/exporter.py` |
| Migration service | `backend/app/services/migrator.py` |
| Import from folder | `backend/app/services/importer.py` |
| Migration persistence | `backend/app/services/persistence.py` |
| Utility functions | `backend/app/utils.py` |
| Pydantic models | `backend/app/models.py` |
| FastAPI entry | `backend/app/main.py` |
| Dashboard router | `backend/app/routers/dashboard.py` |
| Export router | `backend/app/routers/export.py` |
| Connect router | `backend/app/routers/connect.py` |
| Migrate router | `backend/app/routers/migrate_v2.py` |
| Import router | `backend/app/routers/import_source.py` |
| Version bump script | `scripts/bump-version.js` |

## Common Gotchas

- **DPAPI**: Windows-only. The cookie extraction uses Windows CryptUnprotectData. Won't work on macOS/Linux.
- **Chromium file lock**: Claude Desktop's Network Service holds an exclusive lock (no `FILE_SHARE_READ`) on the Cookies DB. The code kills the Network Service, copies the file, and Chromium auto-restarts it. Direct SQLite readonly mode and `shutil.copy2` both fail while the lock is held.
- **Claude Desktop path varies**: Different install methods (Store, MSI, enterprise) put data in different paths. The code searches 12 candidates across `%APPDATA%` and `%LOCALAPPDATA%`. If auto-detect fails, the browser login fallback bypasses this entirely.
- **`lastActiveOrg` cookie missing**: Some installs don't set this cookie. The API client auto-resolves the org ID from `GET /api/organizations` on first use.
- **Cloudflare TLS fingerprinting**: `httpx` gets 403'd by Cloudflare on claude.ai. The API client uses `urllib.request` (via `asyncio.to_thread`) which has a compatible TLS fingerprint.
- **File upload uses `/conversations/` not `/chat_conversations/`**: The wiggle upload endpoint path differs from all other conversation endpoints. Getting this wrong gives 400.
- **`convert_document` returns 415 for images**: Only call it for documents. Images are uploaded via wiggle only.
- **`file_size` must be integer in completion attachments**: Claude returns `size_bytes: null` from the upload response. Always fallback to `len(file_bytes)`.
- **SSE on completion endpoint**: The `/completion` endpoint returns Server-Sent Events, not JSON. Using `json.loads()` on the response silently breaks handover injection.
- **FastAPI trailing slashes**: Use `@router.get("")` not `@router.get("/")` — the prefix adds the path.
- **PyInstaller**: Must use `upx=False`. UPX corrupts DLLs on Windows.
- **Port 8020**: Chosen to avoid conflicts with Briefinator (8000), Sprintinator (8010).
- **Module-level state**: The connect router stores cookies and API client at module level. Single-user desktop app, so this is fine.
- **Session isolation**: Destination browser login must use ephemeral Electron partition to avoid sharing cookies with source login.

## Git

SSH remote uses `github.com-rahul` alias. Repo: `Rahul-999-alpha/claudexit`.
