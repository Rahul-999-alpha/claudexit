"""
POST /api/import/scan — Scan an export directory and load it as the source for migration.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import DashboardResponse
from app.services.importer import ImportSource, scan_export_dir
import app.state as state

router = APIRouter()


class ImportScanRequest(BaseModel):
    export_dir: str


@router.post("/import/scan", response_model=DashboardResponse)
async def import_scan(req: ImportScanRequest):
    """Scan an export directory and set it as the import source.

    Returns DashboardResponse so the frontend can display the dashboard
    with the imported data.
    """
    export_dir = Path(req.export_dir)

    if not export_dir.exists():
        raise HTTPException(status_code=400, detail=f"Directory not found: {req.export_dir}")
    if not export_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {req.export_dir}")

    # Check for at least conversations.json or projects.json
    has_convs = (export_dir / "conversations.json").exists()
    has_projects = (export_dir / "projects.json").exists()
    if not has_convs and not has_projects:
        raise HTTPException(
            status_code=400,
            detail="Not a valid claudexit export folder. Expected conversations.json or projects.json.",
        )

    try:
        import_source = ImportSource(req.export_dir)
        dashboard_data = scan_export_dir(req.export_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan export directory: {e}")

    # Store import source in state
    state.set_import_source(import_source)

    return dashboard_data
