"""
Pure utility functions for export operations.
"""

import re


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
                        parts.append(
                            f"<details>\n<summary>Thinking...</summary>\n\n{thinking}\n\n</details>"
                        )
                elif btype == "tool_use":
                    parts.append(f"[Tool: {block.get('name', 'unknown')}]")
                elif btype == "tool_result":
                    parts.append("[Tool Result]")
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
    """Extract all file references from a conversation's messages.

    Searches multiple locations where Claude API may store file references:
    - msg.files_v2 (primary)
    - msg.files (fallback)
    - content blocks with file attachments or images
    - top-level conv.files_v2 / conv.files
    """
    files = []
    seen: set[str] = set()

    def _add(f: dict) -> None:
        fid = f.get("file_uuid") or f.get("uuid")
        if fid and fid not in seen:
            seen.add(fid)
            files.append(f)

    for msg in conv.get("chat_messages", []):
        # Primary: files_v2
        for f in msg.get("files_v2", []):
            _add(f)
        # Fallback: files field
        for f in msg.get("files", []):
            if isinstance(f, dict):
                _add(f)
        # Fallback: content blocks with attachments
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                # tool_result blocks may contain nested file refs
                if btype == "tool_result":
                    for inner in block.get("content", []):
                        if isinstance(inner, dict) and inner.get("file_uuid"):
                            _add(inner)
                # Direct file reference in content block
                if block.get("file_uuid"):
                    _add(block)
        # Attachments array on message
        for f in msg.get("attachments", []):
            if isinstance(f, dict):
                _add(f)

    # Top-level conversation file references
    for f in conv.get("files_v2", []):
        _add(f)
    for f in conv.get("files", []):
        if isinstance(f, dict):
            _add(f)

    return files
