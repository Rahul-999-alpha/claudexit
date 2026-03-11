"""
Migration service — moves data from source to destination Claude account.

Uses the internal claude.ai API via ClaudeAPI write methods.
Migrations are per-item (memory, project, conversation) and report progress
via a callback. Errors per sub-item are captured and do not abort the whole run.
"""

import asyncio
from typing import Callable, Awaitable

from app.services.claude_api import ClaudeAPI


# ── Type alias ─────────────────────────────────────────────────────────────────

ProgressCB = Callable[[str, str, int, int], Awaitable[None]]
# progress_cb(stage: str, current_step: str, steps_done: int, steps_total: int)


# ── Memory migration ───────────────────────────────────────────────────────────

async def migrate_global_memory(
    source: ClaudeAPI,
    dest: ClaudeAPI,
    progress_cb: ProgressCB,
) -> dict:
    """Migrate global account memory to the destination account.

    Fetches memory text from source, splits into individual paragraph controls,
    and writes them to the destination via PUT memory/controls.
    Anthropic processes the controls into memory text within 24h
    (same mechanism as claude.com/import-memory).

    Returns {"controls_sent": N}
    """
    await progress_cb("memory", "Fetching global memory from source...", 0, 3)

    memory_data = await source.get_memory()
    memory_text = memory_data.get("memory", "") or ""

    await progress_cb("memory", "Splitting memory into controls...", 1, 3)
    controls = memory_text_to_controls(memory_text)

    if not controls:
        await progress_cb("memory", "No memory content found — skipping.", 2, 3)
        return {"controls_sent": 0}

    await progress_cb("memory", f"Writing {len(controls)} memory controls to destination...", 2, 3)
    await asyncio.sleep(0.3)
    await dest.set_memory_controls(controls)

    await progress_cb("memory", f"Global memory migrated ({len(controls)} controls).", 3, 3)
    return {"controls_sent": len(controls)}


async def migrate_project_memory(
    source: ClaudeAPI,
    dest: ClaudeAPI,
    source_project_uuid: str,
    dest_project_uuid: str,
    progress_cb: ProgressCB,
) -> dict:
    """Migrate project-scoped memory from source project to destination project.

    Returns {"controls_sent": N}
    """
    await progress_cb("project_memory", "Fetching project memory from source...", 0, 3)

    memory_data = await source.get_project_memory(source_project_uuid)
    memory_text = memory_data.get("memory", "") or ""

    await progress_cb("project_memory", "Splitting project memory into controls...", 1, 3)
    controls = memory_text_to_controls(memory_text)

    if not controls:
        await progress_cb("project_memory", "No project memory found — skipping.", 2, 3)
        return {"controls_sent": 0}

    await progress_cb("project_memory", f"Writing {len(controls)} project memory controls...", 2, 3)
    await asyncio.sleep(0.3)
    await dest.set_memory_controls(controls, project_uuid=dest_project_uuid)

    await progress_cb("project_memory", f"Project memory migrated ({len(controls)} controls).", 3, 3)
    return {"controls_sent": len(controls)}


# ── Project migration ──────────────────────────────────────────────────────────

async def migrate_project(
    source: ClaudeAPI,
    dest: ClaudeAPI,
    source_project: dict,
    migrate_conversations: bool,
    handover_options,  # HandoverOptions | None
    progress_cb: ProgressCB,
) -> dict:
    """Migrate a full project from source to destination account.

    Steps:
    1. Create the project on dest (same name + description)
    2. Upload all knowledge documents
    3. Sync the project
    4. Migrate project-scoped memory
    5. (Optional) Migrate all conversations belonging to the project

    If handover_options is None, conversation migration is skipped even
    when migrate_conversations is True.

    Returns {
        "dest_project_uuid": str,
        "docs_migrated": int,
        "conversations_migrated": int,
    }
    """
    project_name = source_project.get("name", "Untitled Project")
    source_project_uuid = source_project["uuid"]
    description = source_project.get("description", "") or ""

    # Count steps: create(1) + docs(N) + sync(1) + memory(1) + conversations(M)
    # We compute steps_total dynamically as we discover counts.

    # ── Step 1: Create project on destination ──────────────────────────────────
    await progress_cb("creating_project", f"Creating project '{project_name}'...", 0, 1)
    await asyncio.sleep(0.3)
    dest_project = await dest.create_project(name=project_name, description=description)
    dest_project_uuid = dest_project["uuid"]
    await progress_cb("creating_project", f"Project created: {dest_project_uuid}", 1, 1)

    docs_migrated = 0
    conversations_migrated = 0

    # ── Step 2: Fetch and upload knowledge documents ───────────────────────────
    docs = []
    try:
        await progress_cb("fetching_docs", "Fetching knowledge documents from source...", 0, 1)
        docs = await source.get_project_docs(source_project_uuid)
    except Exception as e:
        await progress_cb("fetching_docs", f"Warning: Could not fetch docs — {e}", 0, 1)

    steps_total = len(docs)
    for i, doc in enumerate(docs):
        file_name = doc.get("file_name", f"doc_{i}.md")
        content = doc.get("content", "")
        try:
            await progress_cb(
                "uploading_docs",
                f"Uploading doc {i + 1}/{steps_total}: {file_name}",
                i,
                steps_total,
            )
            await asyncio.sleep(0.3)
            await dest.add_project_doc(
                project_uuid=dest_project_uuid,
                file_name=file_name,
                content=content,
            )
            docs_migrated += 1
        except Exception as e:
            await progress_cb(
                "uploading_docs",
                f"Warning: Failed to upload '{file_name}' — {e}",
                i,
                steps_total,
            )

    # ── Step 3: Sync project ───────────────────────────────────────────────────
    if docs_migrated > 0:
        try:
            await progress_cb("syncing_project", "Syncing project on destination...", 0, 1)
            await asyncio.sleep(0.3)
            await dest.sync_project(dest_project_uuid)
            await progress_cb("syncing_project", "Project synced.", 1, 1)
        except Exception as e:
            await progress_cb("syncing_project", f"Warning: Sync failed — {e}", 1, 1)

    # ── Step 4: Migrate project memory ────────────────────────────────────────
    try:
        await migrate_project_memory(
            source=source,
            dest=dest,
            source_project_uuid=source_project_uuid,
            dest_project_uuid=dest_project_uuid,
            progress_cb=progress_cb,
        )
    except Exception as e:
        await progress_cb("project_memory", f"Warning: Project memory migration failed — {e}", 0, 1)

    # ── Step 5: Migrate conversations (optional) ───────────────────────────────
    if migrate_conversations and handover_options is not None:
        try:
            all_convs = await source.list_conversations()
        except Exception as e:
            await progress_cb(
                "fetching_conversations",
                f"Warning: Could not list conversations — {e}",
                0, 1,
            )
            all_convs = []

        # Filter to conversations belonging to this project
        project_convs = [
            c for c in all_convs
            if c.get("project_uuid") == source_project_uuid
        ]

        total_convs = len(project_convs)
        for j, conv in enumerate(project_convs):
            conv_name = conv.get("name", "Untitled")
            await progress_cb(
                "migrating_conversations",
                f"Migrating conversation {j + 1}/{total_convs}: {conv_name[:60]}",
                j,
                total_convs,
            )
            try:
                await asyncio.sleep(0.3)
                result = await migrate_conversation(
                    source=source,
                    dest=dest,
                    source_conv=conv,
                    handover_options=handover_options,
                    dest_project_uuid=dest_project_uuid,
                    progress_cb=progress_cb,
                )
                if result.get("dest_conv_uuid"):
                    conversations_migrated += 1
            except Exception as e:
                await progress_cb(
                    "migrating_conversations",
                    f"Warning: Failed to migrate '{conv_name[:40]}' — {e}",
                    j,
                    total_convs,
                )

    await progress_cb(
        "project_done",
        f"Project '{project_name}' migrated. Docs: {docs_migrated}, Conversations: {conversations_migrated}.",
        1, 1,
    )

    return {
        "dest_project_uuid": dest_project_uuid,
        "docs_migrated": docs_migrated,
        "conversations_migrated": conversations_migrated,
    }


# ── Conversation migration ─────────────────────────────────────────────────────

async def migrate_conversation(
    source: ClaudeAPI,
    dest: ClaudeAPI,
    source_conv: dict,
    handover_options,  # HandoverOptions
    dest_project_uuid: str | None,
    progress_cb: ProgressCB,
) -> dict:
    """Migrate a single conversation via handover prompt injection.

    Steps:
    1. Fetch full conversation from source
    2. Create a new conversation on dest (linked to dest_project_uuid if given)
    3. (Optional) Download files from source and re-upload to the new conversation
    4. Send the handover message with file UUIDs attached

    Returns {"dest_conv_uuid": str, "files_migrated": int}
    """
    source_conv_uuid = source_conv["uuid"]
    conv_title = source_conv.get("name", "Untitled")

    # ── Step 1: Fetch full conversation ───────────────────────────────────────
    await progress_cb("fetching_conversation", f"Fetching full conversation: {conv_title[:60]}...", 0, 4)
    full_conv = await source.get_conversation(source_conv_uuid)

    # ── Step 2: Create conversation on destination ────────────────────────────
    await progress_cb("creating_conversation", f"Creating conversation on destination...", 1, 4)
    await asyncio.sleep(0.3)
    dest_conv = await dest.create_conversation(
        title=conv_title,
        project_uuid=dest_project_uuid,
    )
    dest_conv_uuid = dest_conv["uuid"]

    # ── Step 3: Upload files (if enabled) ─────────────────────────────────────
    files_migrated = 0
    uploaded_file_uuids: list[str] = []

    if handover_options.include_files:
        file_infos = collect_files_from_conv(full_conv)
        total_files = len(file_infos)

        if total_files > 0:
            await progress_cb(
                "uploading_files",
                f"Uploading {total_files} file(s) to destination conversation...",
                2, 4,
            )

        for file_info in file_infos:
            file_name = file_info.get("file_name", "attachment")
            try:
                result = await source.download_file_best_variant(file_info)
                if result is not None:
                    file_bytes, fname = result
                    await asyncio.sleep(0.3)
                    upload_result = await dest.upload_file_to_conversation(
                        conversation_uuid=dest_conv_uuid,
                        file_bytes=file_bytes,
                        file_name=fname,
                    )
                    fuid = upload_result.get("file_uuid")
                    if fuid:
                        uploaded_file_uuids.append(fuid)
                        files_migrated += 1
            except Exception as e:
                await progress_cb(
                    "uploading_files",
                    f"Warning: Could not migrate file '{file_name}' — {e}",
                    2, 4,
                )

    # ── Step 4: Send handover message ─────────────────────────────────────────
    await progress_cb("sending_handover", "Sending handover message...", 3, 4)
    await asyncio.sleep(0.3)
    await dest.send_handover_message(
        conversation_uuid=dest_conv_uuid,
        text=handover_options.template,
        file_uuids=uploaded_file_uuids if uploaded_file_uuids else None,
    )

    await progress_cb(
        "conversation_done",
        f"Conversation '{conv_title[:50]}' migrated.",
        4, 4,
    )

    return {
        "dest_conv_uuid": dest_conv_uuid,
        "files_migrated": files_migrated,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def memory_text_to_controls(memory_text: str) -> list[str]:
    """Split memory text into individual control strings.

    Splits on double newlines (paragraph boundaries), strips whitespace from
    each item, filters out blanks, and caps the result at 50 items.
    Each returned string is a single memory fact or paragraph.
    """
    if not memory_text:
        return []
    paragraphs = memory_text.split("\n\n")
    controls = [p.strip() for p in paragraphs]
    controls = [c for c in controls if c]
    return controls[:50]


def extract_last_messages(full_conv: dict, n: int = 3) -> list[dict]:
    """Extract the last N messages from a conversation.

    Looks in full_conv["chat_messages"]. Each message has a "sender" field
    ("human" or "assistant") and a "content" field (list of content blocks or str).
    Extracts plain text from content blocks where type == "text".

    Returns list of {"role": "human"|"assistant", "text": "..."} dicts
    (last N messages total, not N pairs).
    """
    messages = full_conv.get("chat_messages", [])
    if not messages:
        return []

    last_n = messages[-n:]
    result = []
    for msg in last_n:
        sender = msg.get("sender", "")
        role = "human" if sender == "human" else "assistant"
        content = msg.get("content", "")

        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    part = block.get("text", "").strip()
                    if part:
                        text_parts.append(part)
            text = "\n\n".join(text_parts)
        else:
            text = str(content).strip()

        result.append({"role": role, "text": text})

    return result


def collect_files_from_conv(full_conv: dict) -> list[dict]:
    """Collect all unique file attachments referenced in a conversation.

    Looks in each message's "files_v2" field for file info dicts.
    Also checks content blocks for items with a "file_uuid" field,
    covering tool_result and document-type blocks.

    Returns a deduplicated list of file_info dicts containing at minimum
    "file_uuid" (or "uuid") and "file_name".
    """
    files: list[dict] = []
    seen: set[str] = set()

    for msg in full_conv.get("chat_messages", []):
        # Primary source: files_v2 field on the message
        for f in msg.get("files_v2", []):
            fid = f.get("file_uuid") or f.get("uuid")
            if fid and fid not in seen:
                seen.add(fid)
                files.append(f)

        # Secondary source: content blocks that carry a file_uuid directly
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")
                # tool_result or document blocks may embed file references
                if block_type in ("tool_result", "document"):
                    fid = block.get("file_uuid")
                    if fid and fid not in seen:
                        seen.add(fid)
                        files.append({
                            "file_uuid": fid,
                            "file_name": block.get("file_name", "attachment"),
                            "file_kind": block.get("file_kind", ""),
                        })
                # Any block with a top-level file_uuid not covered above
                elif "file_uuid" in block:
                    fid = block["file_uuid"]
                    if fid and fid not in seen:
                        seen.add(fid)
                        files.append({
                            "file_uuid": fid,
                            "file_name": block.get("file_name", "attachment"),
                            "file_kind": block.get("file_kind", ""),
                        })

        # Tertiary source: legacy "attachments" field
        for attachment in msg.get("attachments", []):
            if not isinstance(attachment, dict):
                continue
            fid = attachment.get("file_uuid") or attachment.get("uuid")
            if fid and fid not in seen:
                seen.add(fid)
                files.append(attachment)

    return files
