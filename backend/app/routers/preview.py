"""
GET /api/preview — Fetch account summary (projects, conversations, memory).
"""

from fastapi import APIRouter, HTTPException

from app.models import PreviewResponse, PreviewStats
from app.routers.connect import get_api
from app.utils import collect_files_from_conversation

router = APIRouter()


@router.get("/preview", response_model=PreviewResponse)
async def preview():
    api = get_api()
    if not api:
        raise HTTPException(status_code=400, detail="Not connected. Call /api/connect first.")

    # Fetch all data in parallel-ish (sequential for rate limiting)
    memory_text = None
    try:
        memory_data = await api.get_memory()
        memory_text = memory_data.get("memory", "")
    except Exception:
        pass

    projects = []
    try:
        projects = await api.list_projects()
    except Exception:
        pass

    conversations = []
    try:
        conversations = await api.list_conversations()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch conversations: {e}")

    # Count total file references (estimate from conversation metadata)
    # We don't fetch full conversations here — just count from metadata if available
    total_files = 0
    for conv in conversations:
        # Conversation list items may have a file count or we estimate 0
        total_files += conv.get("num_files", 0)

    stats = PreviewStats(
        total_conversations=len(conversations),
        total_projects=len(projects),
        total_files_referenced=total_files,
    )

    return PreviewResponse(
        memory=memory_text,
        projects=projects,
        conversations=conversations,
        stats=stats,
    )
