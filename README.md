# claudexit

Export and migrate your Claude Desktop conversations, projects, knowledge files, memory, and uploaded files.

Available as both a **desktop app** (dashboard GUI) and a **CLI script**.

## Desktop App

An Electron + React + FastAPI desktop app with an interactive dashboard. Designed for general Claude users who want full control over their data — browse, select, export, and migrate individual items or everything at once.

### Features

- **Dashboard view** — Browse all your projects and conversations in an interactive, expandable card-based dashboard
- **Per-item export** — Export individual conversations or projects with a folder picker
- **Selective file picking** — Preview files attached to conversations and deselect the ones you don't need
- **Batch export** — Select multiple items and export them all at once
- **Select All** — Per-section (Projects, Conversations) and global Select All with a selection queue sidebar
- **Project viewer** — Expand project cards to see memory, knowledge docs, and conversations inline
- **Conversation viewer** — Expand conversation cards to see messages and attached files
- **Account-to-account migration** — Connect a source and destination account, then migrate memory, projects, conversations, and uploaded files directly
- **Import from export folder** — Lost access to your source account? Import from a previous claudexit export folder and migrate to a new account
- **Enriched handover prompt** — Migration injects a context-rich handover message with conversation summary, model, time range, last messages, and file list
- **Model passthrough** — Migrated conversations preserve the original model (e.g. Claude Opus, Sonnet, Haiku)
- **File transfer** — Uploaded files (PDFs, images, documents) are transferred to the destination account during migration
- **Session isolation** — Source and destination logins use separate Electron sessions so you can connect two different accounts
- **Migration tracking** — Mark/unmark items as migrated, persistent across app restarts
- **Auto-detect cookies** — Automatically extracts session cookies from your Claude Desktop installation via DPAPI
- **Browser login fallback** — If auto-detect fails, log in through a browser window instead
- **Account identity** — Shows your email/name (not raw org ID) in the dashboard and connect screens
- **Multiple formats** — Export as JSON, Markdown, or both
- **Live progress** — Real-time WebSocket progress tracking during export and migration
- **Rate limiting** — Exponential backoff with retry on API throttling — slow but reliable
- **File logging** — Backend logs to `%APPDATA%/claudexit/backend.log` for troubleshooting
- **Legacy wizard mode** — Full-account export with the original 5-step wizard (Connect, Preview, Configure, Export, Done)

### Quick Start (Desktop)

**From installer:** Download the latest `claudexit.Setup.x.x.x.exe` from [Releases](https://github.com/Rahul-999-alpha/claudexit/releases), install, and run.

**From source:**
```bash
npm install
cd backend && pip install -r requirements.txt && cd ..
npm run dev
```

### Build

```bash
# Full build pipeline
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
# Output: release/claudexit Setup {version}.exe
```

### Architecture

```
Electron 34 (main process)
  ├── FastAPI backend (subprocess, port 8020)
  │   ├── DPAPI cookie extraction (Windows)
  │   ├── Async Claude API client (urllib, Cloudflare-compatible)
  │   ├── Dashboard data aggregation
  │   ├── Per-item + batch export pipeline
  │   ├── Account-to-account migration (files, handover prompt, model passthrough)
  │   ├── Import from export folder (duck-typed read interface)
  │   ├── Migration state persistence (%APPDATA%/claudexit/)
  │   ├── Rate limiting with exponential backoff
  │   ├── File logging (%APPDATA%/claudexit/backend.log)
  │   └── WebSocket progress streaming
  └── React 18 frontend (Vite)
      ├── Dashboard with expandable cards
      ├── Selection queue sidebar
      ├── Per-item export with file picker
      ├── Handover preview modal (editable before migration)
      ├── Import mode (from previous export folder)
      ├── Session-isolated source/destination login
      ├── Zustand state management
      └── WebSocket progress hooks
```

### Tech Stack

- **Frontend:** React 18, TypeScript, Vite 6, Tailwind CSS, Zustand, Lucide Icons
- **Backend:** FastAPI, urllib (async via thread pool), WebSocket, DPAPI, cryptography
- **Desktop:** Electron 34, electron-vite, electron-builder (NSIS)
- **Build:** PyInstaller (backend binary), electron-builder (installer)

---

## CLI Script

Single-file Python script for users who prefer the command line.

### Quick Start (CLI)

```bash
pip install -r requirements.txt

python claude_chat_exporter.py              # List all chats (grouped by project)
python claude_chat_exporter.py --export     # Export everything
python claude_chat_exporter.py --migrate    # Generate migration prompt for a new account
```

### Usage

```bash
# Export all conversations, project knowledge, and uploaded files
python claude_chat_exporter.py --export

# Export as Markdown only (skip JSON)
python claude_chat_exporter.py --export --format md

# Export as JSON only (skip Markdown)
python claude_chat_exporter.py --export --format json

# Export a single conversation by UUID
python claude_chat_exporter.py --chat <uuid> --export

# Skip downloading uploaded files (faster)
python claude_chat_exporter.py --export --no-files

# Skip project knowledge documents
python claude_chat_exporter.py --export --no-projects

# Exclude thinking/reasoning blocks from Markdown
python claude_chat_exporter.py --export --no-thinking

# Custom output directory
python claude_chat_exporter.py --export --output my_backup

# Adjust delay between API requests (default: 0.5s)
python claude_chat_exporter.py --export --delay 1.0

# Generate migration prompt from an existing export
python claude_chat_exporter.py --migrate
```

---

## Requirements

- **Windows 10/11** (uses DPAPI for cookie decryption)
- **Claude Desktop app** installed and logged in at least once
- Active session (open Claude Desktop before exporting if session expired)
- Desktop app: Node.js 20+, Python 3.10+
- CLI: Python 3.10+, `cryptography` package

## Output Structure

```
claude_export/
  ├── conversations.json               # Index of all conversations
  ├── projects.json                     # Index of all projects
  ├── memory.json                       # Full memory with metadata
  ├── memory.md                         # Memory as readable Markdown
  ├── MIGRATION_PROMPT.md               # Account migration prompt (optional)
  ├── _no_project/                      # Chats not assigned to any project
  │   ├── json/
  │   ├── markdown/
  │   └── files/
  ├── ProjectName/                      # Project folder
  │   ├── knowledge/                    # Project knowledge docs
  │   ├── json/                         # Conversation JSON
  │   ├── markdown/                     # Conversation Markdown
  │   └── files/                        # Uploaded files (PDFs, images)
  └── ...
```

## Account Migration

claudexit supports two migration approaches:

### 1. Direct migration (Desktop app, v1.0.0+)
Connect both source and destination Claude accounts. Then migrate individual items — memory, projects, or conversations — directly from one account to the other through the dashboard. Files are transferred, the original model is preserved, and an enriched handover message is injected with context (summary, model, time range, recent messages, file list) so your new conversation starts with full context.

### 2. Import and migrate (Desktop app, v1.1.0+)
Lost access to your source account? If you have a previous claudexit export folder, use **Import from Export Folder** on the source connect screen. The app reads from disk instead of the API, loads the dashboard, and lets you migrate everything to a new destination account.

### 3. Migration prompt (Desktop app or CLI)
1. **Export** your current account
2. **Generate** the migration prompt
3. **Open** `MIGRATION_PROMPT.md` and paste it into your new Claude account

The migration prompt includes your memory, project structure, knowledge document contents, and conversation summaries.

## What Gets Exported

| Data | Included | Notes |
|------|----------|-------|
| Memory | Yes | Full memory text and metadata |
| Conversations (all messages) | Yes | Full message history with metadata |
| Projects (metadata) | Yes | Name, description, timestamps |
| Project knowledge docs | Yes | Full markdown content |
| Uploaded files (PDFs, images) | Yes | Downloaded as original files. Selectable per-conversation in desktop app |
| Thinking/reasoning blocks | Yes | Can exclude with `--no-thinking` or toggle in desktop app |
| File attachments metadata | Yes | File names, types, UUIDs |
| Conversation summaries | Yes | Auto-generated summaries |
| Model used per conversation | Yes | e.g. `claude-opus-4-6`, `claude-sonnet-4-5` |

### What Cannot Be Exported

| Data | Reason |
|------|--------|
| **Artifacts** (interactive code, HTML, React components) | API strips artifact source code server-side. No known endpoint returns the original. |
| **Deleted conversations** | Not returned by the API |
| **Older conversations** | The API returns conversations visible in your sidebar. There may be a server-side cap. |

## How It Works

1. **Cookie extraction**: Reads the AES-GCM encryption key from `%APPDATA%\Claude\Local State`, decrypts via Windows DPAPI. Since Claude Desktop holds an exclusive lock on the Cookies database, the app temporarily kills the Chromium Network Service subprocess, copies the database, and lets Chromium auto-restart the service (~1 second, no user impact). The copied database is then opened with SQLite to decrypt the `sessionKey` cookie.

2. **API calls**: Uses the decrypted session cookie to authenticate against `claude.ai`'s internal API.

3. **Export**: Organizes everything by project into the output directory.

## Troubleshooting

- **"Claude Desktop not found"** — Your install path may be non-standard. Use the **Login with Browser** button instead — it bypasses local cookie extraction entirely.
- **"No sessionKey cookie found"** — Open the Claude Desktop app and make sure you're logged in, or use **Login with Browser**.
- **"Session verification failed"** — Your session may have expired, or the `lastActiveOrg` cookie may be missing (claudexit auto-resolves this, but if it still fails, try **Login with Browser**).
- **"HTTP Error 401 / 403"** — Your session has expired. Open Claude Desktop to refresh it, then try again. Or use **Login with Browser** for a fresh session.
- **Migration file upload fails** — Check `%APPDATA%/claudexit/backend.log` for detailed error messages. Common causes: expired session, rate limiting (the app retries automatically), or unsupported file types.
- **Not all conversations exported** — The API returns conversations visible in your sidebar. Deleted or auto-archived conversations are not retrievable.

## Portability

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows** | Supported | Uses DPAPI for Chromium cookie decryption |
| **macOS** | Coming Soon | Requires Keychain integration |
| **Linux** | Coming Soon | Requires libsecret/GNOME Keyring |

## Security Notes

- The app reads your Claude session cookie to make API calls. The cookie is only used locally and is not transmitted anywhere except to `claude.ai`.
- Exported data may contain sensitive conversation content. Store exports securely.
- No credentials or cookies are written to the export directory.

## License

MIT
