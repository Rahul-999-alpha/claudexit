"""
Pydantic request/response models for the API.
"""

from pydantic import BaseModel


class ConnectResponse(BaseModel):
    status: str  # "connected" | "error"
    org_id: str | None = None
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


class MigrateRequest(BaseModel):
    output_dir: str


class MigrateResponse(BaseModel):
    path: str
    char_count: int
