"""
ImportSource — reads from a previous claudexit export folder
and presents the same async interface as ClaudeAPI (duck-typed).

Export directory layout (from exporter.py):
  export_dir/
    conversations.json          # list of conversation summaries
    projects.json               # list of project summaries
    memory.json                 # {"memory": "..."}
    memory.md
    <ProjectName>/
      knowledge/
        doc1.md
        doc2.md
      project_memory.json       # {"memory": "..."}
      project_memory.md
      json/<date>_<name>_<uuid8>.json   # full conversation
      markdown/<date>_<name>_<uuid8>.md
      files/<filename>
    _no_project/
      json/...
      markdown/...
      files/...
"""

import json
import logging
from pathlib import Path

from app.models import DashboardResponse, DashboardStats

logger = logging.getLogger(__name__)


class ImportSource:
    """Reads from a claudexit export directory.

    Implements the subset of ClaudeAPI's read interface used by the migrator:
    - list_projects, list_conversations, get_memory, get_project_memory,
      get_conversation, get_project_docs, download_file_best_variant
    """

    def __init__(self, export_dir: str):
        self.export_dir = Path(export_dir)
        self.org_id = "import"
        self.account_email = None
        self.account_name = None

        # Load indexes
        self._projects: list[dict] = self._load_json("projects.json", [])
        self._conversations: list[dict] = self._load_json("conversations.json", [])
        self._memory: dict = self._load_json("memory.json", {})

        # Build project name -> dir mapping
        self._project_dirs: dict[str, Path] = {}
        for p in self._projects:
            name = p.get("name", "")
            # Try to find the matching directory (sanitized name)
            for d in self.export_dir.iterdir():
                if d.is_dir() and d.name != "_no_project" and d.name != "json" and d.name != "markdown" and d.name != "files":
                    # Match by prefix (sanitize_filename truncates at 60 chars)
                    if d.name.lower().startswith(name[:30].lower().replace(" ", "_")[:30]) or d.name == name:
                        self._project_dirs[p["uuid"]] = d
                        break

        # Build conversation uuid -> json file mapping
        self._conv_json_files: dict[str, Path] = {}
        self._scan_conv_json_files()

        logger.info(
            "ImportSource: %d projects, %d conversations, memory=%s",
            len(self._projects), len(self._conversations),
            "yes" if self._memory.get("memory") else "no",
        )

    def _load_json(self, filename: str, default):
        path = self.export_dir / filename
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load %s: %s", path, e)
        return default

    def _scan_conv_json_files(self):
        """Scan all subdirectories for json/*.json conversation files."""
        for d in self.export_dir.rglob("json/*.json"):
            # Filename format: <date>_<name>_<uuid8>.json
            stem = d.stem
            # Extract the last 8 chars as uuid prefix
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                uuid_prefix = parts[-1]
                # Match against known conversation UUIDs
                for conv in self._conversations:
                    if conv["uuid"].startswith(uuid_prefix):
                        self._conv_json_files[conv["uuid"]] = d
                        break

    async def close(self):
        pass

    async def list_projects(self) -> list[dict]:
        return self._projects

    async def list_conversations(self) -> list[dict]:
        return self._conversations

    async def get_memory(self) -> dict:
        return self._memory

    async def get_project_memory(self, project_uuid: str) -> dict:
        proj_dir = self._project_dirs.get(project_uuid)
        if not proj_dir:
            return {}
        mem_file = proj_dir / "project_memory.json"
        if mem_file.exists():
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def get_conversation(self, uuid: str) -> dict:
        json_file = self._conv_json_files.get(uuid)
        if not json_file or not json_file.exists():
            raise FileNotFoundError(f"Conversation JSON not found for {uuid}")
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)

    async def get_project_docs(self, project_uuid: str) -> list[dict]:
        proj_dir = self._project_dirs.get(project_uuid)
        if not proj_dir:
            return []
        knowledge_dir = proj_dir / "knowledge"
        if not knowledge_dir.exists():
            return []
        docs = []
        for f in sorted(knowledge_dir.iterdir()):
            if f.is_file():
                try:
                    content = f.read_text(encoding="utf-8")
                    docs.append({"file_name": f.name, "content": content})
                except Exception:
                    pass
        return docs

    async def download_file_best_variant(self, file_info: dict) -> tuple[bytes, str] | None:
        """Try to find the file in the export's files/ directories."""
        file_name = file_info.get("file_name", "unknown")
        file_uuid = file_info.get("file_uuid") or file_info.get("uuid", "")

        # Search all files/ directories
        for files_dir in self.export_dir.rglob("files"):
            if not files_dir.is_dir():
                continue
            # Try exact name match
            candidate = files_dir / file_name
            if candidate.exists():
                return candidate.read_bytes(), file_name
            # Try uuid-prefixed match
            for f in files_dir.iterdir():
                if f.is_file() and (f.name == file_name or f.name.startswith(file_uuid[:8])):
                    return f.read_bytes(), f.name
        return None


def scan_export_dir(export_dir: str) -> DashboardResponse:
    """Scan an export directory and return a DashboardResponse for the dashboard."""
    source = ImportSource(export_dir)

    # Build project uuid set
    project_uuids = {p["uuid"] for p in source._projects}

    # Attach doc_count to projects
    for p in source._projects:
        proj_dir = source._project_dirs.get(p["uuid"])
        if proj_dir:
            knowledge_dir = proj_dir / "knowledge"
            p["doc_count"] = len(list(knowledge_dir.iterdir())) if knowledge_dir.exists() else 0
        else:
            p["doc_count"] = 0

    # Build project memories
    project_memories: dict[str, str] = {}
    for p in source._projects:
        proj_dir = source._project_dirs.get(p["uuid"])
        if proj_dir:
            mem_file = proj_dir / "project_memory.json"
            if mem_file.exists():
                try:
                    with open(mem_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    text = data.get("memory", "")
                    if text:
                        project_memories[p["uuid"]] = text
                except Exception:
                    pass

    # Standalone conversations
    standalone = [
        c for c in source._conversations
        if c.get("project_uuid") not in project_uuids
    ]

    global_memory = source._memory.get("memory") or None
    total_knowledge = sum(p.get("doc_count", 0) for p in source._projects)

    stats = DashboardStats(
        total_conversations=len(source._conversations),
        total_projects=len(source._projects),
        total_knowledge_docs=total_knowledge,
        total_files=0,  # can't easily count without scanning all files/ dirs
    )

    return DashboardResponse(
        global_memory=global_memory,
        project_memories=project_memories,
        projects=source._projects,
        standalone_conversations=standalone,
        all_conversation_uuids=[c["uuid"] for c in source._conversations],
        stats=stats,
    )
