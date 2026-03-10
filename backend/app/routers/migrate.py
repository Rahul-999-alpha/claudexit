"""
POST /api/migrate — Generate migration prompt from an existing export.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models import MigrateRequest, MigrateResponse
from app.services.migration import generate_migration_prompt

router = APIRouter()


@router.post("/migrate", response_model=MigrateResponse)
async def migrate(req: MigrateRequest):
    export_dir = Path(req.output_dir)
    if not (export_dir / "conversations.json").exists():
        raise HTTPException(
            status_code=400,
            detail=f"No export found at {export_dir}. Run export first.",
        )

    prompt = generate_migration_prompt(str(export_dir))
    out_path = export_dir / "MIGRATION_PROMPT.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    return MigrateResponse(path=str(out_path), char_count=len(prompt))
