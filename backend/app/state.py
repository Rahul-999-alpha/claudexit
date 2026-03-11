# backend/app/state.py
"""Shared module-level state for source and destination API clients."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.importer import ImportSource

from app.services.claude_api import ClaudeAPI

source_api: ClaudeAPI | None = None
dest_api: ClaudeAPI | None = None

# Import mode: ImportSource replaces ClaudeAPI as the source
import_source: ImportSource | None = None
is_import_mode: bool = False

# Raw cookie dicts — kept so legacy callers (e.g. get_cookies()) still work.
source_cookies: dict[str, str] | None = None
dest_cookies: dict[str, str] | None = None

def set_source(api: ClaudeAPI): global source_api, is_import_mode, import_source; source_api = api; is_import_mode = False; import_source = None
def set_dest(api: ClaudeAPI): global dest_api; dest_api = api

def set_import_source(src: ImportSource):
    global import_source, is_import_mode, source_api
    import_source = src
    is_import_mode = True
    source_api = None

def get_source() -> ClaudeAPI | ImportSource | None:
    """Return the active source — ImportSource in import mode, ClaudeAPI otherwise."""
    if is_import_mode and import_source is not None:
        return import_source
    return source_api

def get_dest() -> ClaudeAPI | None: return dest_api
