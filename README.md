# claudexit

Export and migrate your Claude Desktop conversations, projects, knowledge files, memory, and uploaded files.

Available as both a **desktop app** (wizard-style GUI) and a **CLI script**.

## Desktop App

A polished Electron + React + FastAPI desktop app with a 5-step wizard. Designed for general Claude users who want a dead-simple one-click export experience.

### Features

- **One-click export** — Automatically detects your Claude Desktop installation and extracts session cookies
- **Full account export** — Conversations, projects, knowledge documents, memory, and uploaded files
- **Live progress** — Real-time WebSocket progress tracking during export
- **Multiple formats** — Export as JSON, Markdown, or both
- **Migration prompt** — Generate a self-contained prompt to recreate your account structure on a new Claude instance
- **Wizard UX** — 5-step guided flow: Connect, Preview, Configure, Export, Done

### Quick Start (Desktop)

**From installer:** Download the latest `claudexit Setup x.x.x.exe` from [Releases](https://github.com/Rahul-999-alpha/claudexit/releases), install, and run.

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
  │   ├── DPAPI cookie extraction
  │   ├── Async Claude API client (httpx)
  │   ├── Export pipeline with progress callbacks
  │   └── WebSocket streaming
  └── React 18 frontend (Vite)
      ├── 5-step wizard UI
      ├── Zustand state management
      └── WebSocket progress hook
```

### Tech Stack

- **Frontend:** React 18, TypeScript, Vite 6, Tailwind CSS, Zustand, Lucide Icons
- **Backend:** FastAPI, httpx (async), WebSocket, DPAPI, cryptography
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

claudexit can generate a migration prompt that helps recreate your account setup on a new Claude account.

1. **Export** your current account (via desktop app or `--export`)
2. **Generate** the migration prompt (via desktop app or `--migrate`)
3. **Open** `MIGRATION_PROMPT.md` and paste it into your new Claude account

The migration prompt includes your memory, project structure, knowledge document contents, and conversation summaries.

## What Gets Exported

| Data | Included | Notes |
|------|----------|-------|
| Memory | Yes | Full memory text and metadata |
| Conversations (all messages) | Yes | Full message history with metadata |
| Projects (metadata) | Yes | Name, description, timestamps |
| Project knowledge docs | Yes | Full markdown content |
| Uploaded files (PDFs, images) | Yes | Downloaded as original files |
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

1. **Cookie extraction**: Reads the AES-GCM encryption key from `%APPDATA%\Claude\Local State`, decrypts via Windows DPAPI, then opens the Chromium cookie database in SQLite readonly mode to decrypt the `sessionKey` cookie.

2. **API calls**: Uses the decrypted session cookie to authenticate against `claude.ai`'s internal API.

3. **Export**: Organizes everything by project into the output directory.

## Troubleshooting

- **"No sessionKey cookie found"** — Open the Claude Desktop app and make sure you're logged in.
- **"HTTP Error 401 / 403"** — Your session has expired. Open Claude Desktop to refresh it, then try again.
- **Not all conversations exported** — The API returns conversations visible in your sidebar. Deleted or auto-archived conversations are not retrievable.

## Portability

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows** | Supported | Uses DPAPI for Chromium cookie decryption |
| **macOS** | Coming Soon | Requires Keychain integration |
| **Linux** | Coming Soon | Requires libsecret/GNOME Keyring |

## Security Notes

- The script reads your Claude session cookie to make API calls. The cookie is only used locally and is not transmitted anywhere except to `claude.ai`.
- Exported data may contain sensitive conversation content. Store exports securely.
- No credentials or cookies are written to the export directory.

## License

MIT
