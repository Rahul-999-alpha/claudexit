# backend/app/state.py
"""Shared module-level state for source and destination API clients."""
from app.services.claude_api import ClaudeAPI

source_api: ClaudeAPI | None = None
dest_api: ClaudeAPI | None = None

# Raw cookie dicts — kept so legacy callers (e.g. get_cookies()) still work.
source_cookies: dict[str, str] | None = None
dest_cookies: dict[str, str] | None = None

def set_source(api: ClaudeAPI): global source_api; source_api = api
def set_dest(api: ClaudeAPI): global dest_api; dest_api = api
def get_source() -> ClaudeAPI | None: return source_api
def get_dest() -> ClaudeAPI | None: return dest_api
