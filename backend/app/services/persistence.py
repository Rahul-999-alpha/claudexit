"""
Persist migration state to disk so completed migrations survive app restarts.

File location: %APPDATA%/claudexit/migration_state.json

Schema:
{
  "<source_org_id>:<dest_org_id>": {
    "memory:global": {"status": "done", "timestamp": "...", "dest_uuid": null},
    "project:<uuid>": {"status": "done", "timestamp": "...", "dest_uuid": "..."},
    "conv:<uuid>": {"status": "done", "timestamp": "...", "dest_uuid": "..."},
    ...
  }
}
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _state_file() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        # Fallback for non-Windows (shouldn't happen in production)
        appdata = Path.home() / ".claudexit"
    return Path(appdata) / "claudexit" / "migration_state.json"


def _read_all() -> dict:
    path = _state_file()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to read migration state: %s", e)
        return {}


def _write_all(data: dict) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to write migration state: %s", e)


def _pair_key(source_org: str, dest_org: str) -> str:
    return f"{source_org}:{dest_org}"


def load_history(source_org: str, dest_org: str) -> dict[str, dict]:
    """Load persisted migration states for a source→dest pair.

    Returns: {"memory:global": {"status": "done", ...}, "project:uuid": {...}, ...}
    """
    data = _read_all()
    return data.get(_pair_key(source_org, dest_org), {})


def save_item(source_org: str, dest_org: str, item_key: str, dest_uuid: str | None = None) -> None:
    """Mark an item as successfully migrated."""
    data = _read_all()
    pk = _pair_key(source_org, dest_org)
    if pk not in data:
        data[pk] = {}
    data[pk][item_key] = {
        "status": "done",
        "dest_uuid": dest_uuid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _write_all(data)


def remove_item(source_org: str, dest_org: str, item_key: str) -> None:
    """Remove an item's migration record (unmark)."""
    data = _read_all()
    pk = _pair_key(source_org, dest_org)
    if pk in data and item_key in data[pk]:
        del data[pk][item_key]
        _write_all(data)
