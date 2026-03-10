# claudexit

Export all conversations, projects, knowledge files, and uploaded files from the **Claude Desktop app** on Windows. Includes account migration support.

Works by reading the session cookies from the Electron app's local Chromium storage and calling the `claude.ai` internal API.

## Quick Start

```bash
pip install -r requirements.txt

python claude_chat_exporter.py              # List all chats (grouped by project)
python claude_chat_exporter.py --export     # Export everything
python claude_chat_exporter.py --migrate    # Generate migration prompt for a new account
```

## Requirements

- **Windows** (uses DPAPI for Chromium cookie decryption)
- **Python 3.10+**
- **Claude Desktop app** installed and logged in (at least once)
- Active session (cookies expire — run while your session is valid)

## Usage

```bash
# List all conversations grouped by project
python claude_chat_exporter.py

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
python claude_chat_exporter.py --migrate --output my_backup
```

## Output Structure

```
claude_export/
  ├── conversations.json               # Index of all conversations
  ├── projects.json                     # Index of all projects
  ├── MIGRATION_PROMPT.md               # Account migration prompt (--migrate)
  │
  ├── _no_project/                      # Chats not assigned to any project
  │   ├── json/
  │   │   └── 2026-01-15_Chat-title_abc12345.json
  │   ├── markdown/
  │   │   └── 2026-01-15_Chat-title_abc12345.md
  │   └── files/
  │       └── screenshot.png
  │
  ├── My-Project/                       # Project folder
  │   ├── knowledge/                    # Project knowledge documents
  │   │   ├── design_spec.md
  │   │   └── api_reference.md
  │   ├── json/                         # Full conversation JSON
  │   ├── markdown/                     # Readable Markdown
  │   └── files/                        # Uploaded files (PDFs, images)
  │
  └── Another-Project/
      └── ...
```

## Account Migration

claudexit can generate a migration prompt that helps you recreate your account setup on a new Claude account.

### How it works

1. **Export** your current account:
   ```bash
   python claude_chat_exporter.py --export
   ```

2. **Generate** the migration prompt:
   ```bash
   python claude_chat_exporter.py --migrate
   ```

3. **Open** `claude_export/MIGRATION_PROMPT.md` and paste it into your new Claude account.

### What the migration prompt includes

- **Project structure** — names, descriptions, and settings for each project
- **Knowledge documents** — full content of every knowledge doc, so the new account has complete context even before you re-upload them
- **Conversation summaries** — a table of all past conversations with dates, models used, titles, and auto-generated summaries grouped by project
- **Setup instructions** — tells Claude exactly what to create and in what order

### What you'll need to do manually

- **Re-upload knowledge files** to each project (the prompt tells Claude which files go where)
- **Re-upload any files** referenced in conversations (PDFs, images — they're in the `files/` directories)
- Artifacts cannot be migrated (see limitations below)

## What Gets Exported

| Data | Included | Notes |
|------|----------|-------|
| Conversations (all messages) | Yes | Full message history with metadata |
| Projects (metadata) | Yes | Name, description, timestamps |
| Project knowledge docs | Yes | Full markdown content of uploaded knowledge |
| Uploaded files (PDFs, images) | Yes | Downloaded as original files |
| Thinking/reasoning blocks | Yes | Can exclude with `--no-thinking` |
| File attachments metadata | Yes | File names, types, UUIDs in message data |
| Conversation summaries | Yes | Auto-generated summaries |
| Model used per conversation | Yes | e.g. `claude-opus-4-6`, `claude-sonnet-4-5` |

### What Cannot Be Exported

| Data | Reason |
|------|--------|
| **Artifacts** (interactive code, HTML, React components) | The API strips artifact source code server-side and replaces it with a placeholder. No known endpoint returns the original source. Artifacts are only rendered in the web app during the live session. |
| **Deleted conversations** | Not returned by the API |
| **Older conversations** | The API returns conversations visible in your sidebar. There may be a server-side cap on how many are returned — not yet confirmed. Deleted or auto-archived conversations are not retrievable. |

## How It Works

1. **Cookie extraction**: Reads the AES-GCM encryption key from `%APPDATA%\Claude\Local State`, decrypts it via Windows DPAPI, then opens the Chromium cookie database (`%APPDATA%\Claude\Network\Cookies`) in SQLite readonly mode to decrypt the `sessionKey` cookie.

2. **API calls**: Uses the decrypted session cookie to authenticate against `claude.ai`'s internal API:
   - `GET /api/organizations/{org}/chat_conversations` — list conversations
   - `GET /api/organizations/{org}/chat_conversations/{id}?tree=True&rendering_mode=messages` — full conversation with messages
   - `GET /api/organizations/{org}/projects` — list projects
   - `GET /api/organizations/{org}/projects/{id}/docs` — project knowledge documents
   - `GET /api/{org}/files/{id}/{variant}` — download uploaded files

3. **Export**: Organizes everything by project into the output directory.

## Troubleshooting

### "No sessionKey cookie found"
- Open the Claude Desktop app and make sure you're logged in
- The app stores cookies after first login — if you've never opened it, there are no cookies

### "HTTP Error 401 / 403"
- Your session has expired. Open the Claude Desktop app (it refreshes the session), then run the script again.

### "unable to open database file"
- The SQLite readonly mode should work even while the app is running. If you still get this error, try closing the Claude Desktop app first.

### Not all conversations exported
- The API returns conversations visible in your sidebar. There may be a server-side cap — not yet confirmed. Deleted or auto-archived conversations are not retrievable.

## Portability

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows** | Supported | Uses DPAPI for Chromium cookie decryption |
| **macOS** | Coming Soon | Requires Keychain integration for cookie decryption |
| **Linux** | Coming Soon | Requires libsecret/GNOME Keyring for cookie decryption |

**Windows requirements:**
- Python 3.10+
- The `cryptography` package
- Claude Desktop app installed and logged in

## Security Notes

- The script reads your Claude session cookie to make API calls. The cookie is only used locally and is not transmitted anywhere except to `claude.ai`.
- Exported data may contain sensitive conversation content. Store exports securely.
- No credentials or cookies are written to the export directory.
