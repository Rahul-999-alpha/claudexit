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
import app.state as state
from app.services import migrator

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


async def _run_job(job_id: str, item_type: str, item_name: str, coro) -> None:
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

    asyncio.create_task(_run_job(job_id, "memory", item_name, coro))
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

    job_id = _new_job_id()
    coro = lambda cb: migrator.migrate_project(
        src, dst, req.project_uuid,
        migrate_conversations=req.migrate_conversations,
        handover_options=req.handover_options,
        progress_cb=cb,
    )
    asyncio.create_task(_run_job(job_id, "project", req.project_uuid, coro))
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

    job_id = _new_job_id()
    coro = lambda cb: migrator.migrate_conversation(
        src, dst, req.conversation_uuid,
        dest_project_uuid=req.project_uuid,
        handover_options=req.handover_options,
        progress_cb=cb,
    )
    asyncio.create_task(_run_job(job_id, "conversation", req.conversation_uuid, coro))
    return MigrateJobResponse(job_id=job_id)


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
