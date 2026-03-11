"""
Pydantic request/response models for the API.
"""

from pydantic import BaseModel


class ConnectResponse(BaseModel):
    status: str  # "connected" | "error"
    org_id: str | None = None
    account_email: str | None = None
    account_name: str | None = None
    session_preview: str | None = None
    error: str | None = None


class ConnectWithCookiesRequest(BaseModel):
    cookies: dict[str, str]


class PreviewStats(BaseModel):
    total_conversations: int
    total_projects: int
    total_files_referenced: int


class PreviewResponse(BaseModel):
    memory: str | None = None
    projects: list[dict]
    conversations: list[dict]
    stats: PreviewStats


class ExportConfig(BaseModel):
    output_dir: str
    export_conversations: bool = True
    export_projects: bool = True
    download_files: bool = True
    include_thinking: bool = True
    export_memory: bool = True
    format: str = "both"  # "json" | "md" | "both"
    generate_migration: bool = False


class ExportStartResponse(BaseModel):
    job_id: str


class ExportProgress(BaseModel):
    job_id: str
    status: str  # "running" | "complete" | "error"
    stage: str  # "cookies" | "metadata" | "knowledge" | "conversations" | "files" | "done"
    current_item: str
    conversations_total: int
    conversations_done: int
    files_total: int
    files_done: int
    knowledge_total: int
    knowledge_done: int
    errors: list[dict]
    output_dir: str


# ── Dashboard ──────────────────────────────────────────────────

class ProjectMemoryMap(BaseModel):
    """Maps project_uuid -> memory text for all projects."""
    data: dict[str, str] = {}

class DashboardStats(BaseModel):
    total_conversations: int
    total_projects: int
    total_knowledge_docs: int
    total_files: int

class DashboardResponse(BaseModel):
    global_memory: str | None = None
    project_memories: dict[str, str] = {}   # project_uuid -> memory text
    projects: list[dict] = []
    standalone_conversations: list[dict] = []  # conversations not in any project
    all_conversation_uuids: list[str] = []     # all conv UUIDs for file count scan
    stats: DashboardStats

# ── Per-item Export ────────────────────────────────────────────

class ExportItemConfig(BaseModel):
    output_dir: str
    format: str = "both"          # "json" | "md" | "both"
    download_files: bool = True
    include_thinking: bool = True
    file_uuids: list[str] | None = None  # if set, only download these files

class ExportConversationRequest(BaseModel):
    conversation_uuid: str
    config: ExportItemConfig

class ExportProjectRequest(BaseModel):
    project_uuid: str
    config: ExportItemConfig

class ExportBatchRequest(BaseModel):
    item_keys: list[str]          # "conv:{uuid}", "project:{uuid}"
    config: ExportItemConfig

# ── Migration ──────────────────────────────────────────────────

class HandoverOptions(BaseModel):
    template: str  # The full handover message text (user-editable)
    include_files: bool = True

class MigrateMemoryRequest(BaseModel):
    scope: str = "global"         # "global" | "project"
    project_uuid: str | None = None

class MigrateProjectRequest(BaseModel):
    project_uuid: str
    migrate_conversations: bool = True
    handover_options: HandoverOptions | None = None  # None = don't resume conversations

class MigrateConversationRequest(BaseModel):
    conversation_uuid: str
    project_uuid: str | None = None          # dest project UUID to link to (already migrated)
    handover_options: HandoverOptions

class MigrateJobResponse(BaseModel):
    job_id: str

class MigrateProgress(BaseModel):
    job_id: str
    status: str          # "running" | "complete" | "error"
    item_type: str       # "memory" | "project" | "conversation"
    item_name: str
    stage: str           # e.g. "creating_project" | "uploading_docs" | "sending_handover" etc.
    current_step: str    # human-readable status string
    steps_total: int
    steps_done: int
    errors: list[dict] = []
    result: dict = {}    # e.g. {"dest_project_uuid": "...", "dest_conv_uuid": "..."}

class ItemMigrationStatus(BaseModel):
    """Per-item status stored in the JSON state persistence file."""
    item_uuid: str
    item_type: str
    item_name: str
    status: str          # "pending" | "migrating" | "done" | "failed"
    dest_uuid: str | None = None
    error: str | None = None
