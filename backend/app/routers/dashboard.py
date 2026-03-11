"""
GET /api/dashboard — Fetch full source account data for the migration dashboard.
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import DashboardResponse, DashboardStats
from app.utils import collect_files_from_conversation, message_to_text
import app.state as state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """Fetch all source account data needed for the dashboard:

    - Global memory
    - All projects (with their knowledge doc counts)
    - Project memory for each project
    - All conversations (tagged with project_uuid if applicable)
    - Stats
    """
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Source account not connected")

    # Fetch projects, conversations, and global memory in parallel.
    try:
        projects_result, conversations_result, memory_result = await asyncio.gather(
            api.list_projects(),
            api.list_conversations(),
            api.get_memory(),
            return_exceptions=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch account data: {e}")

    # Unpack results — each may be an exception if its individual call failed.
    projects: list[dict] = projects_result if not isinstance(projects_result, BaseException) else []
    conversations: list[dict] = conversations_result if not isinstance(conversations_result, BaseException) else []
    global_memory: str | None = None
    if not isinstance(memory_result, BaseException):
        global_memory = memory_result.get("memory") or None

    # Build project uuid set for fast lookup.
    project_uuids = {p["uuid"] for p in projects}

    # Fetch doc counts for all projects in parallel.
    if projects:
        doc_results = await asyncio.gather(
            *[api.get_project_docs(p["uuid"]) for p in projects],
            return_exceptions=True,
        )
        for proj, doc_result in zip(projects, doc_results):
            if isinstance(doc_result, BaseException):
                proj["doc_count"] = 0
            else:
                proj["doc_count"] = len(doc_result)
    total_knowledge_docs = sum(p.get("doc_count", 0) for p in projects)

    # Fetch project memories sequentially to avoid rate limiting.
    project_memories: dict[str, str] = {}
    for proj in projects:
        try:
            proj_memory_data = await api.get_project_memory(proj["uuid"])
            proj_memory_text = proj_memory_data.get("memory", "")
            if proj_memory_text:
                project_memories[proj["uuid"]] = proj_memory_text
        except Exception:
            pass
        await asyncio.sleep(0.2)

    # Standalone conversations = those not belonging to any known project.
    standalone_conversations = [
        conv for conv in conversations
        if conv.get("project_uuid") not in project_uuids
    ]

    stats = DashboardStats(
        total_conversations=len(conversations),
        total_projects=len(projects),
        total_knowledge_docs=total_knowledge_docs,
        total_files=sum(conv.get("num_files", 0) for conv in conversations),
    )

    return DashboardResponse(
        global_memory=global_memory,
        project_memories=project_memories,
        projects=projects,
        standalone_conversations=standalone_conversations,
        all_conversation_uuids=[c["uuid"] for c in conversations],
        stats=stats,
    )


class FileCountsRequest(BaseModel):
    uuids: list[str]

class FileCountsResponse(BaseModel):
    counts: dict[str, int]
    total: int

@router.post("/dashboard/file-counts", response_model=FileCountsResponse)
async def get_file_counts(req: FileCountsRequest):
    """Fetch file counts for conversations by fetching each one."""
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Source account not connected")

    counts: dict[str, int] = {}
    batch_size = 5
    logged_first = False

    for i in range(0, len(req.uuids), batch_size):
        batch = req.uuids[i:i + batch_size]
        results = await asyncio.gather(
            *[api.get_conversation(uuid) for uuid in batch],
            return_exceptions=True,
        )
        for uuid, result in zip(batch, results):
            if isinstance(result, BaseException):
                counts[uuid] = 0
            else:
                # Debug: log first conversation structure to diagnose file detection
                if not logged_first:
                    logged_first = True
                    msg_keys = []
                    for msg in result.get("chat_messages", [])[:2]:
                        msg_keys.append(list(msg.keys()))
                    top_keys = [k for k in result.keys() if "file" in k.lower()]
                    logger.info(
                        "file-counts debug: conv=%s top_file_keys=%s first_msg_keys=%s",
                        uuid[:8], top_keys, msg_keys,
                    )
                counts[uuid] = len(collect_files_from_conversation(result))
        if i + batch_size < len(req.uuids):
            await asyncio.sleep(0.3)

    logger.info("file-counts: scanned %d convs, total_files=%d", len(counts), sum(counts.values()))
    return FileCountsResponse(counts=counts, total=sum(counts.values()))


class ConversationMessage(BaseModel):
    sender: str
    text: str

class ConversationFile(BaseModel):
    file_uuid: str
    name: str
    kind: str

class ConversationDetailResponse(BaseModel):
    messages: list[ConversationMessage]
    files: list[ConversationFile]

@router.get("/dashboard/conversation/{uuid}", response_model=ConversationDetailResponse)
async def get_conversation_detail(uuid: str):
    """Fetch conversation messages and files for inline expansion."""
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Source account not connected")

    try:
        conv = await api.get_conversation(uuid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch conversation: {e}")

    messages = []
    for msg in conv.get("chat_messages", []):
        sender = msg.get("sender", "unknown")
        text = message_to_text(msg)
        # Truncate to ~80 chars
        if len(text) > 80:
            text = text[:80] + "…"
        messages.append(ConversationMessage(sender=sender, text=text))

    files = []
    for f in collect_files_from_conversation(conv):
        fid = f.get("file_uuid") or f.get("uuid") or ""
        files.append(ConversationFile(
            file_uuid=fid,
            name=f.get("file_name", "unknown"),
            kind=f.get("file_kind", "file"),
        ))

    return ConversationDetailResponse(messages=messages, files=files)


# ── Project detail ────────────────────────────────────────────────────────

class KnowledgeDoc(BaseModel):
    file_name: str
    content_preview: str  # first ~200 chars

class ProjectConversationSummary(BaseModel):
    uuid: str
    name: str
    created_at: str
    message_count: int

class ProjectDetailResponse(BaseModel):
    memory: str | None = None
    knowledge_docs: list[KnowledgeDoc] = []
    conversations: list[ProjectConversationSummary] = []

@router.get("/dashboard/project/{uuid}", response_model=ProjectDetailResponse)
async def get_project_detail(uuid: str):
    """Fetch project memory, knowledge docs, and conversations for inline expansion."""
    api = state.get_source()
    if not api:
        raise HTTPException(status_code=400, detail="Source account not connected")

    # Fetch memory, docs, and conversations in parallel
    memory_result, docs_result, convs_result = await asyncio.gather(
        api.get_project_memory(uuid),
        api.get_project_docs(uuid),
        api.list_conversations(),
        return_exceptions=True,
    )

    # Memory
    memory: str | None = None
    if not isinstance(memory_result, BaseException):
        memory = memory_result.get("memory") or None

    # Knowledge docs
    knowledge_docs: list[KnowledgeDoc] = []
    if not isinstance(docs_result, BaseException):
        for doc in docs_result:
            content = doc.get("content", "")
            preview = content[:200] + ("…" if len(content) > 200 else "")
            knowledge_docs.append(KnowledgeDoc(
                file_name=doc.get("file_name", "untitled"),
                content_preview=preview,
            ))

    # Conversations belonging to this project
    conversations: list[ProjectConversationSummary] = []
    if not isinstance(convs_result, BaseException):
        for conv in convs_result:
            if conv.get("project_uuid") == uuid:
                conversations.append(ProjectConversationSummary(
                    uuid=conv["uuid"],
                    name=conv.get("name", "Untitled"),
                    created_at=conv.get("created_at", ""),
                    message_count=conv.get("num_messages", 0),
                ))

    return ProjectDetailResponse(
        memory=memory,
        knowledge_docs=knowledge_docs,
        conversations=conversations,
    )
