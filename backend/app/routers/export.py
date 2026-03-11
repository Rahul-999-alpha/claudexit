"""
POST /api/export/start — Start a full export job.
POST /api/export/conversation — Export a single conversation.
POST /api/export/project — Export a single project.
POST /api/export/batch — Export multiple items.
GET  /api/export/status/{job_id} — Poll export progress.
WS   /api/export/stream/{job_id} — WebSocket for live progress.
"""

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models import (
    ExportConfig,
    ExportStartResponse,
    ExportProgress,
    ExportConversationRequest,
    ExportProjectRequest,
    ExportBatchRequest,
)
from app.routers.connect import get_api
from app.services.exporter import run_export, export_single_conversation, export_single_project
import app.state as state

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job store (single-user desktop app, no persistence needed)
_jobs: dict[str, ExportProgress] = {}
_job_events: dict[str, asyncio.Event] = {}
_job_subscribers: dict[str, list[asyncio.Queue]] = {}


def _make_job(job_id: str, output_dir: str) -> ExportProgress:
    """Create a fresh ExportProgress object for a new job."""
    return ExportProgress(
        job_id=job_id,
        status="running",
        stage="exporting",
        current_item="Starting...",
        conversations_total=0,
        conversations_done=0,
        files_total=0,
        files_done=0,
        knowledge_total=0,
        knowledge_done=0,
        errors=[],
        output_dir=output_dir,
    )


def _register_job(job_id: str):
    """Register a job in the event/subscriber stores."""
    _job_events[job_id] = asyncio.Event()
    _job_subscribers[job_id] = []


async def _progress_callback(progress: ExportProgress):
    """Store latest progress and notify WebSocket subscribers."""
    _jobs[progress.job_id] = progress
    # Signal polling endpoint
    event = _job_events.get(progress.job_id)
    if event:
        event.set()
    # Push to WebSocket subscribers
    for queue in _job_subscribers.get(progress.job_id, []):
        try:
            queue.put_nowait(progress)
        except asyncio.QueueFull:
            pass


# ── Full export ───────────────────────────────────────────────────────────


@router.post("/export/start", response_model=ExportStartResponse)
async def export_start(config: ExportConfig):
    api = get_api()
    if not api:
        raise HTTPException(status_code=400, detail="Not connected. Call /api/connect first.")

    job_id = str(uuid.uuid4())[:8]
    _register_job(job_id)

    # Launch export as background task
    asyncio.create_task(run_export(api, config, job_id, _progress_callback))

    return ExportStartResponse(job_id=job_id)


# ── Per-item export ──────────────────────────────────────────────────────


async def _run_conversation_export(
    job_id: str,
    conversation_uuid: str,
    output_dir: str,
    fmt: str,
    download_files: bool,
    include_thinking: bool,
    file_uuids: list[str] | None = None,
):
    """Background task for single conversation export."""
    api = state.get_source()
    progress = _make_job(job_id, output_dir)
    progress.conversations_total = 1
    await _progress_callback(progress)

    try:
        # Fetch conversation summary to get name/date
        conv = await api.get_conversation(conversation_uuid)
        conv_dict = {
            "uuid": conversation_uuid,
            "name": conv.get("name", "Untitled"),
            "created_at": conv.get("created_at", ""),
        }

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        async def cb(status: str, _done: int, _total: int):
            progress.current_item = status
            await _progress_callback(progress)

        result = await export_single_conversation(
            api=api,
            conv_dict=conv_dict,
            output_dir=out,
            fmt=fmt,
            download_files=download_files,
            include_thinking=include_thinking,
            file_uuids=file_uuids,
            progress_cb=cb,
        )

        progress.conversations_done = result["conversations_done"]
        progress.files_done = result["files_done"]
        progress.files_total = result["files_total"]
        progress.errors = result["errors"]
        progress.stage = "done"
        progress.status = "complete"
        progress.current_item = "Export complete!"

    except Exception as e:
        progress.status = "error"
        progress.current_item = f"Export failed: {str(e)}"
        progress.errors.append({"item": conversation_uuid, "error": str(e)})

    await _progress_callback(progress)


async def _run_project_export(
    job_id: str,
    project_uuid: str,
    output_dir: str,
    fmt: str,
    download_files: bool,
    include_thinking: bool,
):
    """Background task for single project export."""
    api = state.get_source()
    progress = _make_job(job_id, output_dir)
    await _progress_callback(progress)

    try:
        # Find project info
        projects = await api.list_projects()
        project_dict = next((p for p in projects if p["uuid"] == project_uuid), None)
        if not project_dict:
            raise ValueError(f"Project {project_uuid} not found")

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        async def cb(status: str, done: int, total: int):
            progress.current_item = status
            progress.conversations_done = done
            progress.conversations_total = total
            await _progress_callback(progress)

        result = await export_single_project(
            api=api,
            project_dict=project_dict,
            output_dir=out,
            fmt=fmt,
            download_files=download_files,
            include_thinking=include_thinking,
            progress_cb=cb,
        )

        progress.conversations_done = result["conversations_done"]
        progress.conversations_total = result["conversations_total"]
        progress.files_done = result["files_done"]
        progress.files_total = result["files_total"]
        progress.knowledge_done = result["knowledge_done"]
        progress.knowledge_total = result["knowledge_total"]
        progress.errors = result["errors"]
        progress.stage = "done"
        progress.status = "complete"
        progress.current_item = "Export complete!"

    except Exception as e:
        progress.status = "error"
        progress.current_item = f"Export failed: {str(e)}"
        progress.errors.append({"item": project_uuid, "error": str(e)})

    await _progress_callback(progress)


async def _run_batch_export(
    job_id: str,
    item_keys: list[str],
    output_dir: str,
    fmt: str,
    download_files: bool,
    include_thinking: bool,
):
    """Background task for batch export of multiple items."""
    api = state.get_source()
    progress = _make_job(job_id, output_dir)
    progress.conversations_total = len(item_keys)
    await _progress_callback(progress)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Pre-fetch projects for lookup
    try:
        projects = await api.list_projects()
    except Exception:
        projects = []
    project_map = {p["uuid"]: p for p in projects}

    for i, key in enumerate(item_keys):
        parts = key.split(":", 1)
        if len(parts) != 2:
            progress.errors.append({"item": key, "error": "Invalid item key format"})
            progress.conversations_done += 1
            await _progress_callback(progress)
            continue

        item_type, item_uuid = parts

        try:
            if item_type == "conv":
                conv = await api.get_conversation(item_uuid)
                conv_dict = {
                    "uuid": item_uuid,
                    "name": conv.get("name", "Untitled"),
                    "created_at": conv.get("created_at", ""),
                }
                progress.current_item = f"[{i+1}/{len(item_keys)}] {conv_dict['name'][:50]}"
                await _progress_callback(progress)

                result = await export_single_conversation(
                    api=api,
                    conv_dict=conv_dict,
                    output_dir=out,
                    fmt=fmt,
                    download_files=download_files,
                    include_thinking=include_thinking,
                )
                progress.files_done += result["files_done"]
                progress.files_total += result["files_total"]
                progress.errors.extend(result["errors"])

            elif item_type == "project":
                project_dict = project_map.get(item_uuid)
                if not project_dict:
                    progress.errors.append({"item": key, "error": "Project not found"})
                else:
                    progress.current_item = f"[{i+1}/{len(item_keys)}] Project: {project_dict['name'][:40]}"
                    await _progress_callback(progress)

                    result = await export_single_project(
                        api=api,
                        project_dict=project_dict,
                        output_dir=out,
                        fmt=fmt,
                        download_files=download_files,
                        include_thinking=include_thinking,
                    )
                    progress.files_done += result["files_done"]
                    progress.files_total += result["files_total"]
                    progress.knowledge_done += result["knowledge_done"]
                    progress.knowledge_total += result["knowledge_total"]
                    progress.errors.extend(result["errors"])

        except Exception as e:
            progress.errors.append({"item": key, "error": str(e)})

        progress.conversations_done += 1
        await _progress_callback(progress)
        await asyncio.sleep(0.3)

    progress.stage = "done"
    progress.status = "complete"
    progress.current_item = "Export complete!"
    await _progress_callback(progress)


@router.post("/export/conversation", response_model=ExportStartResponse)
async def export_conversation(req: ExportConversationRequest):
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Not connected.")

    job_id = str(uuid.uuid4())[:8]
    _register_job(job_id)

    asyncio.create_task(_run_conversation_export(
        job_id=job_id,
        conversation_uuid=req.conversation_uuid,
        output_dir=req.config.output_dir,
        fmt=req.config.format,
        download_files=req.config.download_files,
        include_thinking=req.config.include_thinking,
        file_uuids=req.config.file_uuids,
    ))

    return ExportStartResponse(job_id=job_id)


@router.post("/export/project", response_model=ExportStartResponse)
async def export_project(req: ExportProjectRequest):
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Not connected.")

    job_id = str(uuid.uuid4())[:8]
    _register_job(job_id)

    asyncio.create_task(_run_project_export(
        job_id=job_id,
        project_uuid=req.project_uuid,
        output_dir=req.config.output_dir,
        fmt=req.config.format,
        download_files=req.config.download_files,
        include_thinking=req.config.include_thinking,
    ))

    return ExportStartResponse(job_id=job_id)


@router.post("/export/batch", response_model=ExportStartResponse)
async def export_batch(req: ExportBatchRequest):
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Not connected.")

    job_id = str(uuid.uuid4())[:8]
    _register_job(job_id)

    asyncio.create_task(_run_batch_export(
        job_id=job_id,
        item_keys=req.item_keys,
        output_dir=req.config.output_dir,
        fmt=req.config.format,
        download_files=req.config.download_files,
        include_thinking=req.config.include_thinking,
    ))

    return ExportStartResponse(job_id=job_id)


# ── Status + WebSocket ───────────────────────────────────────────────────


@router.get("/export/status/{job_id}", response_model=ExportProgress)
async def export_status(job_id: str):
    progress = _jobs.get(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Job not found")
    return progress


@router.websocket("/export/stream/{job_id}")
async def export_stream(websocket: WebSocket, job_id: str):
    await websocket.accept()

    queue: asyncio.Queue[ExportProgress] = asyncio.Queue(maxsize=50)
    if job_id not in _job_subscribers:
        _job_subscribers[job_id] = []
    _job_subscribers[job_id].append(queue)

    try:
        # Send current state immediately if job already started
        current = _jobs.get(job_id)
        if current:
            await websocket.send_json(current.model_dump())

        while True:
            try:
                progress = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(progress.model_dump())
                if progress.status in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"keepalive": True})
    except WebSocketDisconnect:
        pass
    finally:
        if job_id in _job_subscribers:
            try:
                _job_subscribers[job_id].remove(queue)
            except ValueError:
                pass
