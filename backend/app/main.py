"""
claudexit — FastAPI Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import connect, preview, export, migrate

app = FastAPI(
    title="claudexit API",
    description="Claude Desktop Chat Exporter",
    version="1.0.0",
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
app.include_router(migrate.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "claudexit"}
