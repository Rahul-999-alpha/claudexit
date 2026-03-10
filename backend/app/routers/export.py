"""
POST /api/export/start — Start an export job.
GET  /api/export/status/{job_id} — Poll export progress.
WS   /api/export/stream/{job_id} — WebSocket for live progress.
"""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models import ExportConfig, ExportStartResponse, ExportProgress
from app.routers.connect import get_api
from app.services.exporter import run_export

router = APIRouter()

# In-memory job store (single-user desktop app, no persistence needed)
_jobs: dict[str, ExportProgress] = {}
_job_events: dict[str, asyncio.Event] = {}
_job_subscribers: dict[str, list[asyncio.Queue]] = {}


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


@router.post("/export/start", response_model=ExportStartResponse)
async def export_start(config: ExportConfig):
    api = get_api()
    if not api:
        raise HTTPException(status_code=400, detail="Not connected. Call /api/connect first.")

    job_id = str(uuid.uuid4())[:8]
    _job_events[job_id] = asyncio.Event()
    _job_subscribers[job_id] = []

    # Launch export as background task
    asyncio.create_task(run_export(api, config, job_id, _progress_callback))

    return ExportStartResponse(job_id=job_id)


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
