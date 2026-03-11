"""
claudexit — FastAPI Backend
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── File logging ───────────────────────────────────────────────────────────────
_log_dir = os.path.join(os.environ.get("APPDATA", "."), "claudexit")
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "backend.log")

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

logging.getLogger().addHandler(_file_handler)
logging.getLogger().setLevel(logging.DEBUG)

from app.routers import connect, preview, export
from app.routers import dashboard, migrate_v2, import_source

app = FastAPI(
    title="claudexit API",
    description="Claude Desktop Chat Exporter",
    version="1.1.10",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connect.router, prefix="/api")
app.include_router(preview.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(migrate_v2.router, prefix="/api")
app.include_router(import_source.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "claudexit"}
