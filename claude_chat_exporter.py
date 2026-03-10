"""
Claude Desktop Chat Exporter
=============================
Extracts all conversations, projects, knowledge files, and uploaded files
from the Claude Desktop app by reading session cookies and calling the
claude.ai API.

Requirements:
    pip install cryptography

Usage:
    python claude_chat_exporter.py                       # List all chats
    python claude_chat_exporter.py --export              # Export everything
    python claude_chat_exporter.py --export --format md  # Markdown only
    python claude_chat_exporter.py --export --format json # JSON only
    python claude_chat_exporter.py --chat <uuid>         # Export a single chat
    python claude_chat_exporter.py --no-files            # Skip file downloads
    python claude_chat_exporter.py --no-projects         # Skip project knowledge
    python claude_chat_exporter.py --migrate             # Generate migration prompt from export

Output:
    ./claude_export/
      ├── conversations.json               (index of all conversations)
      ├── projects.json                    (index of all projects)
      ├── _no_project/                     (chats not in any project)
      │   ├── json/
      │   ├── markdown/
      │   └── files/
      ├── FT/                              (project folder)
      │   ├── knowledge/                   (project knowledge docs)
      │   │   ├── hardware_decision_framework.md
      │   │   └── ...
      │   ├── json/                        (conversation JSON)
      │   ├── markdown/                    (conversation Markdown)
      │   └── files/                       (uploaded files from chats)
      └── Matrimony/
          └── ...

Notes:
    - Works on Windows only (uses DPAPI for cookie decryption)
    - The Claude Desktop app must have been logged in at least once
    - Session cookies expire — run while your session is active
    - Works even while the Claude Desktop app is running
"""

import argparse
import base64
import ctypes
import ctypes.wintypes
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


# ---------------------------------------------------------------------------
# DPAPI decryption (Windows only)
# ---------------------------------------------------------------------------

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def dpapi_decrypt(encrypted: bytes) -> bytes:
    blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
    blob_out = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise RuntimeError("DPAPI CryptUnprotectData failed")
    data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return data


# ---------------------------------------------------------------------------
# Chromium cookie decryption
# ---------------------------------------------------------------------------

def get_aes_key(claude_data_dir: str) -> bytes:
    """Read and decrypt the AES-GCM key from Chromium's Local State."""
    local_state_path = os.path.join(claude_data_dir, "Local State")
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)

    if not encrypted_key.startswith(b"DPAPI"):
        raise RuntimeError("Unexpected key format (missing DPAPI prefix)")

    return dpapi_decrypt(encrypted_key[5:])


def decrypt_cookie_value(encrypted_value: bytes, aes_key: bytes) -> str:
    """Decrypt a Chromium v10 encrypted cookie value."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if encrypted_value[:3] != b"v10":
        return dpapi_decrypt(encrypted_value).decode("utf-8")

    nonce = encrypted_value[3:15]
    ciphertext = encrypted_value[15:]
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    # Chromium prepends a 32-byte app-bound encryption header
    return plaintext[32:].decode("utf-8")


def get_claude_cookies(claude_data_dir: str) -> dict[str, str]:
    """Extract and decrypt all claude.ai cookies.

    Uses SQLite readonly URI mode to read the database without needing
    to copy it — works even while the Claude Desktop app is running.
    """
    aes_key = get_aes_key(claude_data_dir)

    cookies_db = os.path.join(claude_data_dir, "Network", "Cookies")
    # Use forward slashes for SQLite URI and readonly mode to avoid file locks
    db_uri = f"file:///{cookies_db.replace(os.sep, '/')}?mode=ro"

    conn = sqlite3.connect(db_uri, uri=True)
    cookies = {}
    try:
        for name, enc_val in conn.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"
        ):
            try:
                cookies[name] = decrypt_cookie_value(enc_val, aes_key)
            except Exception:
                pass
    finally:
        conn.close()

    if "sessionKey" not in cookies:
        raise RuntimeError(
            "No sessionKey cookie found. Is the Claude Desktop app logged in?"
        )

    return cookies


# ---------------------------------------------------------------------------
# Claude API client
# ---------------------------------------------------------------------------

class ClaudeAPI:
    BASE = "https://claude.ai/api"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.6613.186 Safari/537.36"
    )

    def __init__(self, cookies: dict[str, str]):
        self.cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.org_id = cookies.get("lastActiveOrg")
        if not self.org_id:
            raise RuntimeError("lastActiveOrg cookie not found")

    def _request(self, url: str, accept: str = "application/json") -> bytes:
        """Make an authenticated GET request, return raw bytes."""
        req = urllib.request.Request(url)
        req.add_header("Cookie", self.cookie_str)
        req.add_header("User-Agent", self.USER_AGENT)
        req.add_header("Accept", accept)
        req.add_header("Referer", "https://claude.ai/")
        req.add_header("Origin", "https://claude.ai")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def _get(self, path: str) -> dict | list:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        return json.loads(self._request(url))

    def list_conversations(self) -> list[dict]:
        """Return all conversations (metadata only, no messages)."""
        return self._get("chat_conversations")

    def get_conversation(self, uuid: str) -> dict:
        """Return a single conversation with all messages."""
        return self._get(
            f"chat_conversations/{uuid}?tree=True&rendering_mode=messages"
        )

    def list_projects(self) -> list[dict]:
        """Return all projects."""
        return self._get("projects")

    def get_project_docs(self, project_uuid: str) -> list[dict]:
        """Return knowledge documents for a project."""
        return self._get(f"projects/{project_uuid}/docs")

    def get_memory(self) -> dict:
        """Return the user's memory (markdown text + metadata)."""
        return self._get("memory")

    def download_file(self, file_uuid: str, variant: str = "document_pdf") -> bytes:
        """Download an uploaded file by UUID and variant.

        Common variants: document_pdf, preview, thumbnail
        """
        url = f"{self.BASE}/{self.org_id}/files/{file_uuid}/{variant}"
        return self._request(url, accept="*/*")


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, max_len: int = 50) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", "-", name.strip())
    return name[:max_len].rstrip("-.")


def message_to_text(msg: dict) -> str:
    """Extract plain text from a chat message's content field."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "thinking":
                    thinking = block.get("thinking", "")
                    if thinking:
                        parts.append(f"<details>\n<summary>Thinking...</summary>\n\n{thinking}\n\n</details>")
                elif btype == "tool_use":
                    parts.append(f"[Tool: {block.get('name', 'unknown')}]")
                elif btype == "tool_result":
                    parts.append("[Tool Result]")
                # Skip token_budget and other meta types
            elif isinstance(block, str):
                parts.append(block)
        return "\n\n".join(p for p in parts if p)
    return str(content)


def format_file_attachments(msg: dict) -> str:
    """Format file attachment info for markdown output."""
    files = msg.get("files_v2", [])
    if not files:
        return ""
    lines = ["", "**Attachments:**"]
    for f in files:
        name = f.get("file_name", "unknown")
        kind = f.get("file_kind", "file")
        lines.append(f"- {name} ({kind})")
    return "\n".join(lines)


def conversation_to_markdown(conv: dict, project_name: str = "") -> str:
    """Convert a full conversation (with messages) to Markdown."""
    lines = []
    name = conv.get("name", "Untitled")
    created = conv.get("created_at", "")[:19].replace("T", " ")
    model = conv.get("model", "unknown")
    summary = conv.get("summary", "")

    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"**Created:** {created}  ")
    lines.append(f"**Model:** {model}  ")
    lines.append(f"**UUID:** {conv.get('uuid', '')}  ")
    if project_name:
        lines.append(f"**Project:** {project_name}  ")
    if summary:
        lines.append("")
        lines.append(f"> {summary[:500]}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in conv.get("chat_messages", []):
        sender = msg.get("sender", "unknown")
        label = "Human" if sender == "human" else "Assistant"
        text = message_to_text(msg)
        attachments = format_file_attachments(msg)

        lines.append(f"### {label}")
        lines.append("")
        if attachments:
            lines.append(attachments)
            lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def collect_files_from_conversation(conv: dict) -> list[dict]:
    """Extract all file references from a conversation's messages."""
    files = []
    seen = set()
    for msg in conv.get("chat_messages", []):
        for f in msg.get("files_v2", []):
            fid = f.get("file_uuid") or f.get("uuid")
            if fid and fid not in seen:
                seen.add(fid)
                files.append(f)
    return files


def generate_migration_prompt(export_dir: str) -> str:
    """Generate a migration prompt from an existing claudexit export.

    Reads the export directory and produces a self-contained prompt that can
    be pasted into a new Claude account to recreate the project structure,
    upload knowledge documents, and provide conversation context.
    """
    export_path = Path(export_dir)

    # Load projects
    projects = []
    projects_file = export_path / "projects.json"
    if projects_file.exists():
        with open(projects_file, "r", encoding="utf-8") as f:
            projects = json.load(f)

    # Load conversations index
    conversations = []
    convs_file = export_path / "conversations.json"
    if convs_file.exists():
        with open(convs_file, "r", encoding="utf-8") as f:
            conversations = json.load(f)

    lines = []

    # --- Header ---
    lines.append("# Claude Account Migration")
    lines.append("")
    lines.append("I'm migrating from another Claude account. Below is my complete")
    lines.append("account structure — memory, projects, knowledge documents, and")
    lines.append("conversation history. Please help me recreate this setup on this")
    lines.append("new account.")
    lines.append("")

    # --- Memory ---
    memory_file = export_path / "memory.md"
    memory_json = export_path / "memory.json"
    if memory_file.exists():
        memory_text = memory_file.read_text(encoding="utf-8")
        # Strip the "# Claude Memory\n\n" header we added
        if memory_text.startswith("# Claude Memory"):
            memory_text = memory_text.split("\n", 2)[-1].strip()
        lines.append("## Memory from Previous Account")
        lines.append("")
        lines.append("Below is my complete memory from the previous account. Please")
        lines.append("internalize all of this as your memory about me — this is who")
        lines.append("I am, what I work on, and what we've discussed.")
        lines.append("")
        lines.append(memory_text)
        lines.append("")

    # --- Instructions ---
    lines.append("## What I Need You To Do")
    lines.append("")
    lines.append("1. **Absorb the memory above** as context about me")
    lines.append("2. **Create these projects** with their names and descriptions")
    lines.append("3. **Note the knowledge documents** listed below — I will upload")
    lines.append("   them as project knowledge files. The full content is included")
    lines.append("   so you have context even before I upload them.")
    lines.append("4. **Review the conversation summaries** so you have context about")
    lines.append("   what we've discussed previously.")
    lines.append("")

    # --- Projects ---
    lines.append("## Projects")
    lines.append("")
    if projects:
        for p in projects:
            name = p.get("name", "Untitled")
            desc = p.get("description", "")
            is_private = p.get("is_private", True)
            created = p.get("created_at", "")[:10]
            lines.append(f"### {name}")
            lines.append(f"- **Description:** {desc or '(none)'}")
            lines.append(f"- **Private:** {is_private}")
            lines.append(f"- **Created:** {created}")
            lines.append("")

            # Knowledge docs for this project
            proj_dir_name = sanitize_filename(name, 60)
            knowledge_dir = export_path / proj_dir_name / "knowledge"
            if knowledge_dir.is_dir():
                doc_files = sorted(knowledge_dir.iterdir())
                if doc_files:
                    lines.append(f"#### Knowledge Documents ({len(doc_files)} files)")
                    lines.append("")
                    for doc_path in doc_files:
                        lines.append(f"**`{doc_path.name}`**")
                        lines.append("")
                        try:
                            content = doc_path.read_text(encoding="utf-8")
                            # Include full content but wrap in collapsible block
                            lines.append("<details>")
                            lines.append(f"<summary>View content ({len(content)} chars)</summary>")
                            lines.append("")
                            lines.append(content)
                            lines.append("")
                            lines.append("</details>")
                        except Exception:
                            lines.append("*(content could not be read)*")
                        lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("*(No projects found)*")
        lines.append("")

    # --- Conversation History ---
    lines.append("## Conversation History")
    lines.append("")
    lines.append("Summary of past conversations for context. Grouped by project.")
    lines.append("")

    # Group conversations by project
    proj_uuid_to_name = {p["uuid"]: p["name"] for p in projects}
    grouped: dict[str, list] = {"(No Project)": []}
    for p in projects:
        grouped[p["name"]] = []
    for conv in conversations:
        proj_uuid = conv.get("project_uuid")
        if proj_uuid and proj_uuid in proj_uuid_to_name:
            grouped.setdefault(proj_uuid_to_name[proj_uuid], []).append(conv)
        else:
            grouped["(No Project)"].append(conv)

    for group_name, convs in grouped.items():
        if not convs:
            continue
        lines.append(f"### {group_name}")
        lines.append("")
        lines.append(f"| # | Date | Model | Title | Summary |")
        lines.append(f"|---|------|-------|-------|---------|")
        for i, c in enumerate(convs, 1):
            date = c.get("created_at", "")[:10]
            model = c.get("model", "?")
            # Shorten model name
            model_short = model.replace("claude-", "").replace("-20250929", "").replace("-20251001", "").replace("-20251101", "")
            name = c.get("name", "Untitled").replace("|", "/")
            summary = (c.get("summary", "") or "").replace("|", "/").replace("\n", " ")[:150]
            lines.append(f"| {i} | {date} | {model_short} | {name} | {summary} |")
        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append("*Generated by [claudexit](https://github.com/Rahul-999-alpha/claudexit)*")

    return "\n".join(lines)


def download_file_best_variant(api: ClaudeAPI, file_info: dict) -> tuple[bytes, str] | None:
    """Try to download a file using the best available variant."""
    file_uuid = file_info.get("file_uuid") or file_info.get("uuid")
    file_name = file_info.get("file_name", "unknown")
    kind = file_info.get("file_kind", "")

    # Determine the best variant to download based on file kind
    if kind == "document":
        variants = ["document_pdf"]
    elif kind == "image":
        variants = ["preview", "thumbnail"]
    else:
        variants = ["document_pdf", "preview", "thumbnail"]

    for variant in variants:
        try:
            data = api.download_file(file_uuid, variant)
            return data, file_name
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if sys.platform != "win32":
        print("Error: This script only works on Windows (requires DPAPI).")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Export conversations, projects, and files from Claude Desktop"
    )
    parser.add_argument(
        "--export", action="store_true",
        help="Export all conversations (default: just list them)",
    )
    parser.add_argument(
        "--chat", type=str, default=None,
        help="Export a single conversation by UUID",
    )
    parser.add_argument(
        "--format", choices=["json", "md", "both"], default="both",
        help="Export format (default: both)",
    )
    parser.add_argument(
        "--output", type=str, default="claude_export",
        help="Output directory (default: claude_export)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay between API requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--no-files", action="store_true",
        help="Skip downloading uploaded files (PDFs, images)",
    )
    parser.add_argument(
        "--no-projects", action="store_true",
        help="Skip exporting project knowledge documents",
    )
    parser.add_argument(
        "--no-thinking", action="store_true",
        help="Exclude thinking/reasoning blocks from markdown output",
    )
    parser.add_argument(
        "--migrate", action="store_true",
        help="Generate a migration prompt from an existing export (run --export first)",
    )
    args = parser.parse_args()

    # ---- Migration prompt mode (no API needed) ----
    if args.migrate:
        export_dir = Path(args.output)
        if not (export_dir / "conversations.json").exists():
            print(f"Error: No export found at {export_dir}/")
            print(f"Run --export first, then run --migrate.")
            sys.exit(1)
        print(f"Generating migration prompt from {export_dir}...")
        prompt = generate_migration_prompt(str(export_dir))
        out_path = export_dir / "MIGRATION_PROMPT.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"  Saved to {out_path}")
        print(f"  Size: {len(prompt):,} characters")
        print(f"\nPaste this file's contents into a new Claude account to recreate")
        print(f"your project structure and provide conversation context.")
        return

    # ---- Resolve Claude data directory ----
    claude_data_dir = os.path.join(os.environ.get("APPDATA", ""), "Claude")
    if not os.path.isdir(claude_data_dir):
        print(f"Error: Claude data directory not found at {claude_data_dir}")
        sys.exit(1)

    # ---- Extract cookies ----
    print("Extracting session cookies from Claude Desktop...")
    try:
        cookies = get_claude_cookies(claude_data_dir)
    except Exception as e:
        print(f"Error extracting cookies: {e}")
        sys.exit(1)
    print(f"  Session key: {cookies['sessionKey'][:15]}...")
    print(f"  Organization: {cookies.get('lastActiveOrg', 'N/A')}")

    api = ClaudeAPI(cookies)

    # ---- Fetch projects ----
    print("\nFetching projects...")
    try:
        projects = api.list_projects()
    except Exception:
        projects = []
    project_map = {p["uuid"]: p for p in projects}
    print(f"  Found {len(projects)} projects: {', '.join(p['name'] for p in projects) or '(none)'}")

    # ---- Fetch conversations ----
    print("\nFetching conversation list...")
    try:
        conversations = api.list_conversations()
    except urllib.error.HTTPError as e:
        print(f"API error: {e.code} {e.reason}")
        if e.code == 401:
            print("Session expired. Open Claude Desktop, then try again.")
        sys.exit(1)
    print(f"  Found {len(conversations)} conversations")

    # ---- Group conversations by project ----
    NO_PROJECT = "_no_project"
    conv_by_project: dict[str, list[dict]] = {NO_PROJECT: []}
    for p in projects:
        conv_by_project[p["name"]] = []

    for conv in conversations:
        proj_uuid = conv.get("project_uuid")
        if proj_uuid and proj_uuid in project_map:
            proj_name = project_map[proj_uuid]["name"]
            conv_by_project.setdefault(proj_name, []).append(conv)
        else:
            conv_by_project[NO_PROJECT].append(conv)

    if not args.export and not args.chat:
        # ---- List mode ----
        for proj_name, convs in conv_by_project.items():
            if not convs:
                continue
            label = proj_name if proj_name != NO_PROJECT else "(No Project)"
            print(f"\n  [{label}] — {len(convs)} conversations")
            for i, c in enumerate(convs, 1):
                date = c["created_at"][:10]
                model = c.get("model", "?")[:25]
                name = c.get("name", "Untitled")[:55]
                print(f"    {i:<3} {date}  {model:<27} {name}")
        print(f"\nTo export all: python {sys.argv[0]} --export")
        print(f"To export one: python {sys.argv[0]} --chat <uuid> --export")
        return

    # ---- Single chat mode ----
    if args.chat:
        conversations = [c for c in conversations if c["uuid"] == args.chat]
        if not conversations:
            conversations = [{"uuid": args.chat, "name": "Unknown", "created_at": ""}]
        # Rebuild grouping for single chat
        conv_by_project = {NO_PROJECT: []}
        for conv in conversations:
            proj_uuid = conv.get("project_uuid")
            if proj_uuid and proj_uuid in project_map:
                proj_name = project_map[proj_uuid]["name"]
                conv_by_project.setdefault(proj_name, []).append(conv)
            else:
                conv_by_project[NO_PROJECT].append(conv)

    # ---- Prepare output ----
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save indexes
    with open(out_dir / "conversations.json", "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2, ensure_ascii=False)
    if projects:
        with open(out_dir / "projects.json", "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)
    print(f"\nSaved indexes to {out_dir}")

    # ---- Export memory ----
    if not args.chat:
        try:
            memory_data = api.get_memory()
            memory_text = memory_data.get("memory", "")
            if memory_text:
                with open(out_dir / "memory.json", "w", encoding="utf-8") as f:
                    json.dump(memory_data, f, indent=2, ensure_ascii=False)
                with open(out_dir / "memory.md", "w", encoding="utf-8") as f:
                    f.write("# Claude Memory\n\n")
                    f.write(memory_text)
                print(f"  Memory exported ({len(memory_text)} chars)")
            else:
                print("  No memory found")
        except Exception as e:
            print(f"  Could not export memory: {e}")

    # ---- Export project knowledge docs ----
    if not args.no_projects and projects and not args.chat:
        print("\nExporting project knowledge documents...")
        for proj in projects:
            proj_dir = out_dir / sanitize_filename(proj["name"], 60)
            knowledge_dir = proj_dir / "knowledge"
            try:
                docs = api.get_project_docs(proj["uuid"])
                if docs:
                    knowledge_dir.mkdir(parents=True, exist_ok=True)
                    for doc in docs:
                        fname = doc.get("file_name", "untitled.md")
                        content = doc.get("content", "")
                        fpath = knowledge_dir / fname
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(content)
                    print(f"  {proj['name']}: {len(docs)} knowledge docs")
                else:
                    print(f"  {proj['name']}: no knowledge docs")
            except Exception as e:
                print(f"  {proj['name']}: error fetching docs - {e}")
            time.sleep(args.delay)

    # ---- Export conversations ----
    total = sum(len(v) for v in conv_by_project.values())
    exported = 0
    errors = []
    file_count = 0

    print(f"\nExporting {total} conversations...")

    for proj_name, convs in conv_by_project.items():
        if not convs:
            continue

        proj_dir = out_dir / sanitize_filename(proj_name, 60)
        json_dir = proj_dir / "json"
        md_dir = proj_dir / "markdown"
        files_dir = proj_dir / "files"

        if args.format in ("json", "both"):
            json_dir.mkdir(parents=True, exist_ok=True)
        if args.format in ("md", "both"):
            md_dir.mkdir(parents=True, exist_ok=True)

        display_name = proj_name if proj_name != NO_PROJECT else "(No Project)"
        print(f"\n  [{display_name}]")

        for conv in convs:
            uuid = conv["uuid"]
            name = conv.get("name", "Untitled")
            date = conv.get("created_at", "")[:10]
            safe_name = sanitize_filename(name)
            file_stem = f"{date}_{safe_name}_{uuid[:8]}"

            exported += 1
            print(f"    [{exported}/{total}] {name[:55]}...", end=" ", flush=True)

            try:
                full_conv = api.get_conversation(uuid)
                msg_count = len(full_conv.get("chat_messages", []))

                # Save JSON
                if args.format in ("json", "both"):
                    with open(json_dir / f"{file_stem}.json", "w", encoding="utf-8") as f:
                        json.dump(full_conv, f, indent=2, ensure_ascii=False)

                # Save Markdown
                if args.format in ("md", "both"):
                    md_text = conversation_to_markdown(
                        full_conv,
                        project_name=proj_name if proj_name != NO_PROJECT else "",
                    )
                    if args.no_thinking:
                        md_text = re.sub(
                            r"<details>\n<summary>Thinking\.\.\.</summary>\n\n.*?\n\n</details>",
                            "*[thinking omitted]*",
                            md_text,
                            flags=re.DOTALL,
                        )
                    with open(md_dir / f"{file_stem}.md", "w", encoding="utf-8") as f:
                        f.write(md_text)

                # Download attached files
                if not args.no_files:
                    conv_files = collect_files_from_conversation(full_conv)
                    if conv_files:
                        files_dir.mkdir(parents=True, exist_ok=True)
                        for file_info in conv_files:
                            try:
                                result = download_file_best_variant(api, file_info)
                                if result:
                                    data, fname = result
                                    fpath = files_dir / fname
                                    # Avoid overwriting — add uuid prefix if exists
                                    if fpath.exists():
                                        fid = (file_info.get("file_uuid") or file_info.get("uuid", ""))[:8]
                                        fpath = files_dir / f"{fid}_{fname}"
                                    with open(fpath, "wb") as f:
                                        f.write(data)
                                    file_count += 1
                            except Exception:
                                pass
                            time.sleep(0.2)

                print(f"OK ({msg_count} msgs" + (f", {len(conv_files)} files" if not args.no_files and conv_files else "") + ")")

            except Exception as e:
                errors.append((uuid, name, str(e)))
                print(f"FAILED: {e}")

            time.sleep(args.delay)

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"Export complete!")
    print(f"  Conversations: {total - len(errors)}/{total}")
    if not args.no_files:
        print(f"  Files downloaded: {file_count}")
    if not args.no_projects and projects:
        print(f"  Projects with knowledge: {len([p for p in projects])}")
    print(f"  Output: {out_dir.resolve()}")
    if errors:
        print(f"\n  Failed ({len(errors)}):")
        for uuid, name, err in errors:
            print(f"    {uuid}: {name[:40]} - {err}")


if __name__ == "__main__":
    main()
