"""
POST /api/connect          — Extract cookies via DPAPI and verify source session.
POST /api/connect/cookies  — Accept cookies directly for source (browser login fallback).
POST /api/connect/destination — Accept cookies directly for destination account.
"""

from fastapi import APIRouter

from app.models import ConnectResponse, ConnectWithCookiesRequest
from app.services.cookies import detect_claude_desktop, get_claude_cookies
from app.services.claude_api import ClaudeAPI
import app.state as state

router = APIRouter()


def get_api() -> ClaudeAPI | None:
    """Backwards-compatible accessor — returns the source API client."""
    return state.get_source()


def get_cookies() -> dict[str, str] | None:
    """Backwards-compatible accessor — returns source cookies stored on the state module."""
    return state.source_cookies


@router.post("/connect", response_model=ConnectResponse)
async def connect():
    """Connect the source account via DPAPI cookie extraction from Claude Desktop."""
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
        cookies = get_claude_cookies()
    except Exception as e:
        return ConnectResponse(status="error", error=str(e))

    # Create API client and verify session
    try:
        api = ClaudeAPI(cookies)
        await api.verify_session()
    except Exception as e:
        return ConnectResponse(
            status="error",
            error=f"Session verification failed: {e}. Try opening Claude Desktop first.",
        )

    state.set_source(api)
    state.source_cookies = cookies

    return ConnectResponse(
        status="connected",
        org_id=api.org_id,
        session_preview=cookies["sessionKey"][:15] + "...",
    )


@router.post("/connect/cookies", response_model=ConnectResponse)
async def connect_with_cookies(req: ConnectWithCookiesRequest):
    """Connect the source account using cookies provided directly (browser login)."""
    cookies = req.cookies

    if "sessionKey" not in cookies:
        return ConnectResponse(
            status="error",
            error="No sessionKey found in browser cookies. Please log in fully.",
        )

    try:
        api = ClaudeAPI(cookies)
        await api.verify_session()
    except Exception as e:
        return ConnectResponse(
            status="error",
            error=f"Session verification failed: {e}",
        )

    state.set_source(api)
    state.source_cookies = cookies

    return ConnectResponse(
        status="connected",
        org_id=api.org_id,
        session_preview=cookies["sessionKey"][:15] + "...",
    )


@router.post("/connect/destination", response_model=ConnectResponse)
async def connect_destination(req: ConnectWithCookiesRequest):
    """Connect the destination (new) account via browser login cookies.

    Destination is always a fresh account without Claude Desktop — no DPAPI path.
    """
    cookies = req.cookies

    if "sessionKey" not in cookies:
        return ConnectResponse(
            status="error",
            error="No sessionKey found in browser cookies. Please log in fully.",
        )

    try:
        api = ClaudeAPI(cookies)
        await api.verify_session()
    except Exception as e:
        return ConnectResponse(
            status="error",
            error=f"Session verification failed: {e}",
        )

    state.set_dest(api)
    state.dest_cookies = cookies

    return ConnectResponse(
        status="connected",
        org_id=api.org_id,
        session_preview=cookies["sessionKey"][:15] + "...",
    )
