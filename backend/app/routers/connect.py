"""
POST /api/connect — Extract cookies and verify Claude session.
"""

from fastapi import APIRouter

from app.models import ConnectResponse
from app.services.cookies import detect_claude_desktop, get_claude_cookies
from app.services.claude_api import ClaudeAPI

router = APIRouter()

# Module-level state: active API client and cookies
_cookies: dict[str, str] | None = None
_api: ClaudeAPI | None = None


def get_api() -> ClaudeAPI | None:
    return _api


def get_cookies() -> dict[str, str] | None:
    return _cookies


@router.post("/connect", response_model=ConnectResponse)
async def connect():
    global _cookies, _api

    # Check installation
    status = detect_claude_desktop()
    if not status["installed"]:
        searched = status.get("searched", [])
        detail = f" Searched: {', '.join(searched)}" if searched else ""
        return ConnectResponse(
            status="error",
            error=f"Claude Desktop not found. Is it installed?{detail}",
        )
    if not status["has_cookies"]:
        return ConnectResponse(
            status="error",
            error="No cookie database found. Has Claude Desktop been logged in?",
        )

    # Extract cookies
    try:
        _cookies = get_claude_cookies()
    except Exception as e:
        _cookies = None
        return ConnectResponse(status="error", error=str(e))

    # Create API client and verify session
    try:
        _api = ClaudeAPI(_cookies)
        await _api.verify_session()
    except Exception as e:
        _api = None
        return ConnectResponse(
            status="error",
            error=f"Session verification failed: {e}. Try opening Claude Desktop first.",
        )

    return ConnectResponse(
        status="connected",
        org_id=_api.org_id,
        session_preview=_cookies["sessionKey"][:15] + "...",
    )
