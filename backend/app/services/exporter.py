"""
Export pipeline with progress tracking.
Runs as an async background task, reports progress via callback.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Callable, Awaitable

from app.models import ExportConfig, ExportProgress
from app.services.claude_api import ClaudeAPI
from app.utils import (
    sanitize_filename,
    conversation_to_markdown,
    collect_files_from_conversation,
)

NO_PROJECT = "_no_project"


# ── Reusable single-item export functions ─────────────────────────────────


async def export_single_conversation(
    api: ClaudeAPI,
    conv_dict: dict,
    output_dir: Path,
    fmt: str = "both",
    download_files: bool = True,
    include_thinking: bool = True,
    project_name: str = "",
    file_uuids: list[str] | None = None,
    progress_cb: Callable[[str, int, int], Awaitable[None]] | None = None,
) -> dict:
    """Export a single conversation to output_dir.

    Args:
        api: Authenticated Claude API client
        conv_dict: Conversation summary dict (from list_conversations or dashboard)
        output_dir: Root directory to export into
        fmt: "json", "md", or "both"
        download_files: Whether to download file attachments
        include_thinking: Whether to include thinking blocks in markdown
        project_name: Optional project name for markdown header
        file_uuids: If set, only download these specific file UUIDs
        progress_cb: Optional async callback(status_text, files_done, files_total)

    Returns:
        dict with keys: conversations_done, files_done, files_total, errors
    """
    uuid = conv_dict["uuid"]
    name = conv_dict.get("name", "Untitled")
    date = conv_dict.get("created_at", "")[:10]
    safe_name = sanitize_filename(name)
    file_stem = f"{date}_{safe_name}_{uuid[:8]}"

    json_dir = output_dir / "json"
    md_dir = output_dir / "markdown"
    files_dir = output_dir / "files"

    result = {"conversations_done": 0, "files_done": 0, "files_total": 0, "errors": []}

    try:
        if progress_cb:
            await progress_cb(f"Fetching: {name[:60]}", 0, 0)

        full_conv = await api.get_conversation(uuid)

        # Save JSON
        if fmt in ("json", "both"):
            json_dir.mkdir(parents=True, exist_ok=True)
            with open(json_dir / f"{file_stem}.json", "w", encoding="utf-8") as f:
                json.dump(full_conv, f, indent=2, ensure_ascii=False)

        # Save Markdown
        if fmt in ("md", "both"):
            md_dir.mkdir(parents=True, exist_ok=True)
            md_text = conversation_to_markdown(full_conv, project_name=project_name)
            if not include_thinking:
                md_text = re.sub(
                    r"<details>\n<summary>Thinking\.\.\.</summary>\n\n.*?\n\n</details>",
                    "*[thinking omitted]*",
                    md_text,
                    flags=re.DOTALL,
                )
            with open(md_dir / f"{file_stem}.md", "w", encoding="utf-8") as f:
                f.write(md_text)

        # Download attached files
        if download_files:
            conv_files = collect_files_from_conversation(full_conv)
            if file_uuids is not None:
                allowed = set(file_uuids)
                conv_files = [
                    f for f in conv_files
                    if (f.get("file_uuid") or f.get("uuid")) in allowed
                ]
            result["files_total"] = len(conv_files)
            if conv_files:
                files_dir.mkdir(parents=True, exist_ok=True)
                for file_info in conv_files:
                    try:
                        dl_result = await api.download_file_best_variant(file_info)
                        if dl_result:
                            data, fname = dl_result
                            fpath = files_dir / fname
                            if fpath.exists():
                                fid = (file_info.get("file_uuid") or file_info.get("uuid", ""))[:8]
                                fpath = files_dir / f"{fid}_{fname}"
                            with open(fpath, "wb") as f:
                                f.write(data)
                            result["files_done"] += 1
                    except Exception:
                        pass
                    await asyncio.sleep(0.15)

        result["conversations_done"] = 1

    except Exception as e:
        result["errors"].append({"item": f"{uuid}: {name[:40]}", "error": str(e)})
        result["conversations_done"] = 1

    return result


async def export_single_project(
    api: ClaudeAPI,
    project_dict: dict,
    output_dir: Path,
    fmt: str = "both",
    download_files: bool = True,
    include_thinking: bool = True,
    progress_cb: Callable[[str, int, int], Awaitable[None]] | None = None,
) -> dict:
    """Export a single project: knowledge docs, project memory, and all conversations.

    Returns:
        dict with keys: conversations_done, conversations_total, files_done, files_total,
                        knowledge_done, knowledge_total, errors
    """
    proj_uuid = project_dict["uuid"]
    proj_name = project_dict.get("name", "Untitled Project")
    proj_dir = output_dir / sanitize_filename(proj_name, 60)
    proj_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "conversations_done": 0, "conversations_total": 0,
        "files_done": 0, "files_total": 0,
        "knowledge_done": 0, "knowledge_total": 0,
        "errors": [],
    }

    # Export knowledge docs
    if progress_cb:
        await progress_cb(f"Knowledge: {proj_name}", 0, 0)
    try:
        docs = await api.get_project_docs(proj_uuid)
        if docs:
            knowledge_dir = proj_dir / "knowledge"
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            result["knowledge_total"] = len(docs)
            for doc in docs:
                fname = doc.get("file_name", "untitled.md")
                content = doc.get("content", "")
                with open(knowledge_dir / fname, "w", encoding="utf-8") as f:
                    f.write(content)
                result["knowledge_done"] += 1
    except Exception as e:
        result["errors"].append({"item": f"knowledge:{proj_name}", "error": str(e)})

    # Export project memory
    try:
        proj_memory_data = await api.get_project_memory(proj_uuid)
        proj_memory_text = proj_memory_data.get("memory", "")
        if proj_memory_text:
            with open(proj_dir / "project_memory.md", "w", encoding="utf-8") as f:
                f.write(f"# Project Memory: {proj_name}\n\n")
                f.write(proj_memory_text)
            with open(proj_dir / "project_memory.json", "w", encoding="utf-8") as f:
                json.dump(proj_memory_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        result["errors"].append({"item": f"project_memory:{proj_name}", "error": str(e)})

    # Fetch project conversations
    try:
        all_conversations = await api.list_conversations()
        proj_conversations = [c for c in all_conversations if c.get("project_uuid") == proj_uuid]
    except Exception as e:
        proj_conversations = []
        result["errors"].append({"item": f"conversations:{proj_name}", "error": str(e)})

    result["conversations_total"] = len(proj_conversations)

    # Export each conversation
    for conv in proj_conversations:
        if progress_cb:
            await progress_cb(
                f"Exporting: {conv.get('name', 'Untitled')[:50]}",
                result["conversations_done"],
                result["conversations_total"],
            )

        conv_result = await export_single_conversation(
            api=api,
            conv_dict=conv,
            output_dir=proj_dir,
            fmt=fmt,
            download_files=download_files,
            include_thinking=include_thinking,
            project_name=proj_name,
        )
        result["conversations_done"] += conv_result["conversations_done"]
        result["files_done"] += conv_result["files_done"]
        result["files_total"] += conv_result["files_total"]
        result["errors"].extend(conv_result["errors"])
        await asyncio.sleep(0.3)

    return result


# ── Full export pipeline (existing) ──────────────────────────────────────


async def run_export(
    api: ClaudeAPI,
    config: ExportConfig,
    job_id: str,
    progress_callback,
):
    """Run the full export pipeline, calling progress_callback with ExportProgress updates."""

    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    progress = ExportProgress(
        job_id=job_id,
        status="running",
        stage="metadata",
        current_item="Fetching account data...",
        conversations_total=0,
        conversations_done=0,
        files_total=0,
        files_done=0,
        knowledge_total=0,
        knowledge_done=0,
        errors=[],
        output_dir=config.output_dir,
    )
    await progress_callback(progress)

    try:
        # --- Fetch projects ---
        projects = []
        if config.export_projects:
            try:
                projects = await api.list_projects()
            except Exception:
                projects = []
        project_map = {p["uuid"]: p for p in projects}

        # --- Fetch conversations ---
        conversations = []
        if config.export_conversations:
            progress.current_item = "Fetching conversation list..."
            await progress_callback(progress)
            conversations = await api.list_conversations()

        progress.conversations_total = len(conversations)

        # --- Save indexes ---
        with open(out_dir / "conversations.json", "w", encoding="utf-8") as f:
            json.dump(conversations, f, indent=2, ensure_ascii=False)
        if projects:
            with open(out_dir / "projects.json", "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=2, ensure_ascii=False)

        # --- Export memory ---
        if config.export_memory:
            progress.current_item = "Exporting memory..."
            progress.stage = "metadata"
            await progress_callback(progress)
            try:
                memory_data = await api.get_memory()
                memory_text = memory_data.get("memory", "")
                if memory_text:
                    with open(out_dir / "memory.json", "w", encoding="utf-8") as f:
                        json.dump(memory_data, f, indent=2, ensure_ascii=False)
                    with open(out_dir / "memory.md", "w", encoding="utf-8") as f:
                        f.write("# Claude Memory\n\n")
                        f.write(memory_text)
            except Exception as e:
                progress.errors.append({"item": "memory", "error": str(e)})

        # --- Export project knowledge ---
        if config.export_projects and projects:
            progress.stage = "knowledge"
            for proj in projects:
                progress.current_item = f"Knowledge: {proj['name']}"
                await progress_callback(progress)
                proj_dir = out_dir / sanitize_filename(proj["name"], 60)
                knowledge_dir = proj_dir / "knowledge"
                try:
                    docs = await api.get_project_docs(proj["uuid"])
                    if docs:
                        knowledge_dir.mkdir(parents=True, exist_ok=True)
                        progress.knowledge_total += len(docs)
                        for doc in docs:
                            fname = doc.get("file_name", "untitled.md")
                            content = doc.get("content", "")
                            with open(knowledge_dir / fname, "w", encoding="utf-8") as f:
                                f.write(content)
                            progress.knowledge_done += 1
                        await progress_callback(progress)
                except Exception as e:
                    progress.errors.append({"item": f"knowledge:{proj['name']}", "error": str(e)})
                # After saving docs for a project, also fetch project memory
                try:
                    proj_memory_data = await api.get_project_memory(proj["uuid"])
                    proj_memory_text = proj_memory_data.get("memory", "")
                    if proj_memory_text:
                        proj_dir.mkdir(parents=True, exist_ok=True)
                        with open(proj_dir / "project_memory.md", "w", encoding="utf-8") as f:
                            f.write(f"# Project Memory: {proj['name']}\n\n")
                            f.write(proj_memory_text)
                        with open(proj_dir / "project_memory.json", "w", encoding="utf-8") as f:
                            json.dump(proj_memory_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    progress.errors.append({"item": f"project_memory:{proj['name']}", "error": str(e)})
                await asyncio.sleep(0.3)

        # --- Group conversations by project ---
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

        # --- Export conversations ---
        if config.export_conversations:
            progress.stage = "conversations"
            for proj_name, convs in conv_by_project.items():
                if not convs:
                    continue

                proj_dir = out_dir / sanitize_filename(proj_name, 60)

                for conv in convs:
                    name = conv.get("name", "Untitled")
                    progress.current_item = f"Exporting: {name[:60]}"
                    await progress_callback(progress)

                    display_name = proj_name if proj_name != NO_PROJECT else ""
                    conv_result = await export_single_conversation(
                        api=api,
                        conv_dict=conv,
                        output_dir=proj_dir,
                        fmt=config.format,
                        download_files=config.download_files,
                        include_thinking=config.include_thinking,
                        project_name=display_name,
                    )

                    progress.conversations_done += conv_result["conversations_done"]
                    progress.files_done += conv_result["files_done"]
                    progress.files_total += conv_result["files_total"]
                    progress.errors.extend(conv_result["errors"])

                    await progress_callback(progress)
                    await asyncio.sleep(0.3)

        # --- Done ---
        progress.stage = "done"
        progress.status = "complete"
        progress.current_item = "Export complete!"
        await progress_callback(progress)

    except Exception as e:
        progress.status = "error"
        progress.current_item = f"Export failed: {str(e)}"
        progress.errors.append({"item": "export", "error": str(e)})
        await progress_callback(progress)
