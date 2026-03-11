"""
Migration endpoints for v1.0.0.

POST /api/migrate/memory        — Migrate global or project memory.
POST /api/migrate/project       — Migrate a project (docs + optional conversations).
POST /api/migrate/conversation  — Migrate a single conversation.
GET  /api/migrate/status/{job_id} — Poll current MigrateProgress for a job.
WS   /api/migrate/stream/{job_id} — Stream MigrateProgress as JSON until job completes.
"""

import asyncio
import uuid as _uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models import (
    MigrateMemoryRequest,
    MigrateProjectRequest,
    MigrateConversationRequest,
    MigrateJobResponse,
    MigrateProgress,
)
from pydantic import BaseModel

import app.state as state
from app.services import migrator
from app.services import persistence

router = APIRouter()

# In-memory job store: job_id -> MigrateProgress
_jobs: dict[str, MigrateProgress] = {}

# WebSocket connections waiting for updates: job_id -> list[WebSocket]
_ws_connections: dict[str, list[WebSocket]] = {}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _new_job_id() -> str:
    return _uuid.uuid4().hex


async def _broadcast(job_id: str, progress: MigrateProgress) -> None:
    """Send the current progress snapshot to all WebSocket listeners for a job."""
    sockets = _ws_connections.get(job_id, [])
    for ws in list(sockets):
        try:
            await ws.send_text(progress.model_dump_json())
        except Exception:
            pass


async def _run_job(job_id: str, item_type: str, item_name: str, coro, item_key: str | None = None) -> None:
    """Execute a migration coroutine as a tracked background job.

    The coroutine receives a single argument: an async progress_cb(stage,
    current_step, steps_done, steps_total) callable that it should invoke
    whenever its progress changes.
    """
    progress = MigrateProgress(
        job_id=job_id,
        status="running",
        item_type=item_type,
        item_name=item_name,
        stage="starting",
        current_step="Starting...",
        steps_total=0,
        steps_done=0,
    )
    _jobs[job_id] = progress

    async def progress_cb(stage: str, current_step: str, steps_done: int, steps_total: int) -> None:
        progress.stage = stage
        progress.current_step = current_step
        progress.steps_done = steps_done
        progress.steps_total = steps_total
        await _broadcast(job_id, progress)

    try:
        result = await coro(progress_cb)
        progress.result = result or {}
        progress.status = "complete"
        progress.current_step = "Done"

        # Persist successful migration to disk
        if item_key:
            src = state.get_source()
            dst = state.get_dest()
            src_org = getattr(src, "org_id", None) or "unknown"
            dst_org = getattr(dst, "org_id", None) or "unknown"
            dest_uuid = (result or {}).get("dest_project_uuid") or (result or {}).get("dest_conv_uuid")
            persistence.save_item(src_org, dst_org, item_key, dest_uuid)
    except Exception as e:
        progress.status = "error"
        progress.errors.append({"error": str(e)})
    finally:
        # Send the final state to all connected WebSockets, then close them.
        sockets = _ws_connections.pop(job_id, [])
        for ws in sockets:
            try:
                await ws.send_text(progress.model_dump_json())
                await ws.close()
            except Exception:
                pass


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/migrate/memory", response_model=MigrateJobResponse)
async def migrate_memory(req: MigrateMemoryRequest):
    """Start a background job to migrate global or project memory."""
    src = state.get_source()
    dst = state.get_dest()
    if not src:
        raise HTTPException(status_code=400, detail="Source account not connected")
    if not dst:
        raise HTTPException(status_code=400, detail="Destination account not connected")

    job_id = _new_job_id()
    item_name = f"project:{req.project_uuid}" if req.project_uuid else "global"

    if req.scope == "project" and req.project_uuid:
        coro = lambda cb: migrator.migrate_project_memory(src, dst, req.project_uuid, cb)
    else:
        coro = lambda cb: migrator.migrate_global_memory(src, dst, cb)

    item_key = f"memory:{req.project_uuid}" if req.project_uuid else "memory:global"
    asyncio.create_task(_run_job(job_id, "memory", item_name, coro, item_key=item_key))
    return MigrateJobResponse(job_id=job_id)


@router.post("/migrate/project", response_model=MigrateJobResponse)
async def migrate_project(req: MigrateProjectRequest):
    """Start a background job to migrate a project."""
    src = state.get_source()
    dst = state.get_dest()
    if not src:
        raise HTTPException(status_code=400, detail="Source account not connected")
    if not dst:
        raise HTTPException(status_code=400, detail="Destination account not connected")

    # Fetch the source project dict so migrator gets the full object
    projects = await src.list_projects()
    source_project = next((p for p in projects if p["uuid"] == req.project_uuid), None)
    if not source_project:
        raise HTTPException(status_code=404, detail=f"Project {req.project_uuid} not found")

    job_id = _new_job_id()
    coro = lambda cb: migrator.migrate_project(
        src, dst, source_project,
        migrate_conversations=req.migrate_conversations,
        handover_options=req.handover_options,
        progress_cb=cb,
    )
    item_key = f"project:{req.project_uuid}"
    asyncio.create_task(_run_job(job_id, "project", source_project.get("name", req.project_uuid), coro, item_key=item_key))
    return MigrateJobResponse(job_id=job_id)


@router.post("/migrate/conversation", response_model=MigrateJobResponse)
async def migrate_conversation(req: MigrateConversationRequest):
    """Start a background job to migrate a single conversation."""
    src = state.get_source()
    dst = state.get_dest()
    if not src:
        raise HTTPException(status_code=400, detail="Source account not connected")
    if not dst:
        raise HTTPException(status_code=400, detail="Destination account not connected")

    # Build source_conv dict — list_conversations may be expensive, try to get directly
    try:
        full_conv = await src.get_conversation(req.conversation_uuid)
        source_conv = {
            "uuid": req.conversation_uuid,
            "name": full_conv.get("name", "Untitled"),
            "created_at": full_conv.get("created_at", ""),
            "project_uuid": full_conv.get("project_uuid"),
        }
    except Exception:
        source_conv = {"uuid": req.conversation_uuid, "name": "Untitled"}

    job_id = _new_job_id()
    coro = lambda cb: migrator.migrate_conversation(
        src, dst, source_conv,
        dest_project_uuid=req.project_uuid,
        handover_options=req.handover_options,
        progress_cb=cb,
    )
    item_key = f"conv:{req.conversation_uuid}"
    asyncio.create_task(_run_job(job_id, "conversation", source_conv.get("name", req.conversation_uuid), coro, item_key=item_key))
    return MigrateJobResponse(job_id=job_id)


@router.get("/migrate/handover-preview")
async def handover_preview(conversation_uuid: str):
    """Build and return the enriched handover template for a conversation.

    The frontend shows this in the modal so the user can review/edit before migrating.
    """
    src = state.get_source()
    if not src:
        raise HTTPException(status_code=400, detail="Source account not connected")

    try:
        full_conv = await src.get_conversation(conversation_uuid)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch conversation: {e}")

    conv_title = full_conv.get("name", "Untitled")
    template = migrator.build_handover_template(full_conv, conv_title)
    return {"template": template}


class MarkMigratedRequest(BaseModel):
    item_key: str
    dest_uuid: str | None = None


@router.get("/migrate/history")
async def get_migrate_history():
    """Load persisted migration states for the current source→dest pair."""
    src = state.get_source()
    dst = state.get_dest()
    if not src or not dst:
        return {"items": {}}
    src_org = getattr(src, "org_id", None) or "unknown"
    dst_org = getattr(dst, "org_id", None) or "unknown"
    items = persistence.load_history(src_org, dst_org)
    return {"items": items}


@router.post("/migrate/mark")
async def mark_migrated(req: MarkMigratedRequest):
    """Manually mark an item as migrated (for pre-persistence migrations)."""
    src = state.get_source()
    dst = state.get_dest()
    if not src or not dst:
        raise HTTPException(status_code=400, detail="Both accounts must be connected")
    src_org = getattr(src, "org_id", None) or "unknown"
    dst_org = getattr(dst, "org_id", None) or "unknown"
    persistence.save_item(src_org, dst_org, req.item_key, req.dest_uuid)
    return {"ok": True}


@router.post("/migrate/unmark")
async def unmark_migrated(req: MarkMigratedRequest):
    """Remove an item's migration record (allow re-migration)."""
    src = state.get_source()
    dst = state.get_dest()
    if not src or not dst:
        raise HTTPException(status_code=400, detail="Both accounts must be connected")
    src_org = getattr(src, "org_id", None) or "unknown"
    dst_org = getattr(dst, "org_id", None) or "unknown"
    persistence.remove_item(src_org, dst_org, req.item_key)
    return {"ok": True}


@router.get("/migrate/status/{job_id}", response_model=MigrateProgress)
async def get_migrate_status(job_id: str):
    """Poll the current progress of a migration job."""
    progress = _jobs.get(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return progress


@router.websocket("/migrate/stream/{job_id}")
async def stream_migrate_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint that streams MigrateProgress as JSON until the job completes.

    Clients should connect and listen for messages. The background task pushes
    updates via _broadcast(); this handler also sends the current snapshot
    immediately on connect so the client doesn't have to wait for the next event.
    """
    await websocket.accept()

    # Register connection.
    _ws_connections.setdefault(job_id, []).append(websocket)

    # If the job already exists, send its current state immediately.
    progress = _jobs.get(job_id)
    if progress:
        try:
            await websocket.send_text(progress.model_dump_json())
            # If the job is already terminal, close right away.
            if progress.status in ("complete", "error"):
                await websocket.close()
                _ws_connections.get(job_id, []).remove(websocket)
                return
        except Exception:
            return

    # Keep the connection open; the background task will push updates and
    # eventually close the socket when the job completes.
    try:
        while True:
            # Yield to the event loop so background tasks can send messages.
            # We also watch for a client-initiated close.
            await asyncio.sleep(0.5)
            current = _jobs.get(job_id)
            if current and current.status in ("complete", "error"):
                # Job finished — the _run_job finalizer already closed the socket.
                break
    except WebSocketDisconnect:
        pass
    finally:
        connections = _ws_connections.get(job_id, [])
        if websocket in connections:
            connections.remove(websocket)
