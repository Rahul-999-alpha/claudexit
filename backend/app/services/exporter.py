"""
Export pipeline with progress tracking.
Runs as an async background task, reports progress via callback.
"""

import asyncio
import json
import re
from pathlib import Path

from app.models import ExportConfig, ExportProgress
from app.services.claude_api import ClaudeAPI
from app.utils import (
    sanitize_filename,
    conversation_to_markdown,
    collect_files_from_conversation,
)

NO_PROJECT = "_no_project"


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
                json_dir = proj_dir / "json"
                md_dir = proj_dir / "markdown"
                files_dir = proj_dir / "files"

                if config.format in ("json", "both"):
                    json_dir.mkdir(parents=True, exist_ok=True)
                if config.format in ("md", "both"):
                    md_dir.mkdir(parents=True, exist_ok=True)

                for conv in convs:
                    uuid = conv["uuid"]
                    name = conv.get("name", "Untitled")
                    date = conv.get("created_at", "")[:10]
                    safe_name = sanitize_filename(name)
                    file_stem = f"{date}_{safe_name}_{uuid[:8]}"

                    progress.current_item = f"Exporting: {name[:60]}"
                    await progress_callback(progress)

                    try:
                        full_conv = await api.get_conversation(uuid)

                        # Save JSON
                        if config.format in ("json", "both"):
                            with open(json_dir / f"{file_stem}.json", "w", encoding="utf-8") as f:
                                json.dump(full_conv, f, indent=2, ensure_ascii=False)

                        # Save Markdown
                        if config.format in ("md", "both"):
                            display_name = proj_name if proj_name != NO_PROJECT else ""
                            md_text = conversation_to_markdown(full_conv, project_name=display_name)
                            if not config.include_thinking:
                                md_text = re.sub(
                                    r"<details>\n<summary>Thinking\.\.\.</summary>\n\n.*?\n\n</details>",
                                    "*[thinking omitted]*",
                                    md_text,
                                    flags=re.DOTALL,
                                )
                            with open(md_dir / f"{file_stem}.md", "w", encoding="utf-8") as f:
                                f.write(md_text)

                        # Download attached files
                        if config.download_files:
                            conv_files = collect_files_from_conversation(full_conv)
                            progress.files_total += len(conv_files)
                            if conv_files:
                                files_dir.mkdir(parents=True, exist_ok=True)
                                for file_info in conv_files:
                                    try:
                                        result = await api.download_file_best_variant(file_info)
                                        if result:
                                            data, fname = result
                                            fpath = files_dir / fname
                                            if fpath.exists():
                                                fid = (file_info.get("file_uuid") or file_info.get("uuid", ""))[:8]
                                                fpath = files_dir / f"{fid}_{fname}"
                                            with open(fpath, "wb") as f:
                                                f.write(data)
                                            progress.files_done += 1
                                    except Exception:
                                        pass
                                    await asyncio.sleep(0.15)

                        progress.conversations_done += 1

                    except Exception as e:
                        progress.errors.append({"item": f"{uuid}: {name[:40]}", "error": str(e)})
                        progress.conversations_done += 1

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
