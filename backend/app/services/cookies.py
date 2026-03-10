"""
DPAPI cookie extraction for Claude Desktop (Windows only).
Reads session cookies from the Chromium-based Claude Desktop app.
"""

import base64
import ctypes
import ctypes.wintypes
import json
import os
import sqlite3


# ---------------------------------------------------------------------------
# DPAPI decryption (Windows only)
# ---------------------------------------------------------------------------

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def dpapi_decrypt(encrypted: bytes) -> bytes:
    blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
    blob_out = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise RuntimeError("DPAPI CryptUnprotectData failed")
    data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return data


# ---------------------------------------------------------------------------
# Chromium cookie decryption
# ---------------------------------------------------------------------------

def get_aes_key(claude_data_dir: str) -> bytes:
    """Read and decrypt the AES-GCM key from Chromium's Local State."""
    local_state_path = os.path.join(claude_data_dir, "Local State")
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)

    if not encrypted_key.startswith(b"DPAPI"):
        raise RuntimeError("Unexpected key format (missing DPAPI prefix)")

    return dpapi_decrypt(encrypted_key[5:])


def decrypt_cookie_value(encrypted_value: bytes, aes_key: bytes) -> str:
    """Decrypt a Chromium v10 encrypted cookie value."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if encrypted_value[:3] != b"v10":
        return dpapi_decrypt(encrypted_value).decode("utf-8")

    nonce = encrypted_value[3:15]
    ciphertext = encrypted_value[15:]
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    # Chromium prepends a 32-byte app-bound encryption header
    return plaintext[32:].decode("utf-8")


def get_claude_data_dir() -> str:
    """Return the Claude Desktop data directory path."""
    return os.path.join(os.environ.get("APPDATA", ""), "Claude")


def detect_claude_desktop() -> dict:
    """Check if Claude Desktop is installed and return status info."""
    data_dir = get_claude_data_dir()
    installed = os.path.isdir(data_dir)
    cookies_db = os.path.join(data_dir, "Network", "Cookies") if installed else ""
    has_cookies = os.path.isfile(cookies_db) if installed else False

    return {
        "installed": installed,
        "data_dir": data_dir,
        "has_cookies": has_cookies,
    }


def _open_cookies_db(cookies_db: str):
    """Open the Chromium cookies database.

    Tries SQLite URI readonly mode first (works while Claude Desktop is running).
    Falls back to copying to a temp file if URI mode isn't supported.
    """
    # Try URI readonly mode first
    try:
        db_uri = f"file:///{cookies_db.replace(os.sep, '/')}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        conn.execute("SELECT 1 FROM cookies LIMIT 1")
        return conn
    except Exception:
        pass

    # Fallback: copy to temp file (handles locked DB and URI-unsupported builds)
    import shutil
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(cookies_db, tmp.name)
    # Also copy WAL/SHM if they exist (needed for recent writes)
    for ext in ("-wal", "-shm"):
        src = cookies_db + ext
        if os.path.isfile(src):
            shutil.copy2(src, tmp.name + ext)
    return sqlite3.connect(tmp.name)


def get_claude_cookies() -> dict[str, str]:
    """Extract and decrypt all claude.ai cookies.

    Tries SQLite readonly URI mode first, falls back to copying the DB.
    """
    claude_data_dir = get_claude_data_dir()

    if not os.path.isdir(claude_data_dir):
        raise RuntimeError(
            f"Claude Desktop data directory not found at {claude_data_dir}. "
            "Is the Claude Desktop app installed?"
        )

    aes_key = get_aes_key(claude_data_dir)

    cookies_db = os.path.join(claude_data_dir, "Network", "Cookies")
    if not os.path.isfile(cookies_db):
        raise RuntimeError(
            f"Cookie database not found at {cookies_db}. "
            "Has Claude Desktop been logged in?"
        )

    conn = _open_cookies_db(cookies_db)
    cookies = {}
    try:
        for name, enc_val in conn.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"
        ):
            try:
                cookies[name] = decrypt_cookie_value(enc_val, aes_key)
            except Exception:
                pass
    finally:
        conn.close()

    if "sessionKey" not in cookies:
        raise RuntimeError(
            "No sessionKey cookie found. Is the Claude Desktop app logged in?"
        )

    return cookies
