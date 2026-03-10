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


def _copy_to_temp(cookies_db: str) -> str:
    """Copy the cookies database (and journal/WAL) to a temp file."""
    import shutil
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(cookies_db, tmp.name)
    for ext in ("-wal", "-shm", "-journal"):
        src = cookies_db + ext
        if os.path.isfile(src):
            shutil.copy2(src, tmp.name + ext)
    return tmp.name


def _find_network_service_pid() -> str | None:
    """Find the PID of the Chromium Network Service subprocess."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                (
                    "Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" "
                    "| Where-Object { $_.CommandLine -like '*network.mojom.NetworkService*' } "
                    "| Select-Object -ExpandProperty ProcessId"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.strip().split("\n"):
            pid = line.strip()
            if pid.isdigit():
                return pid
    except Exception:
        pass
    return None


def _kill_and_copy_cookies(cookies_db: str) -> str:
    """Kill the Chromium Network Service and immediately copy the Cookies file.

    Chromium opens the Cookies database with an exclusive lock (no FILE_SHARE_READ).
    The Network Service (--utility-sub-type=network.mojom.NetworkService) holds this
    lock. We kill it and copy the file as fast as possible before Chromium restarts it.

    Uses taskkill (fast) + shutil.copy2 (fast) with retries, rather than PowerShell
    cmdlets which have overhead.
    """
    import shutil
    import subprocess
    import tempfile
    import time

    pid = _find_network_service_pid()
    if not pid:
        raise RuntimeError(
            "Cannot access the Cookies database. Claude Desktop's Network Service "
            "could not be found. Try closing Claude Desktop and retrying."
        )

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = tmp.name

    # Kill the Network Service (taskkill is faster than Stop-Process)
    subprocess.run(
        ["taskkill", "/F", "/PID", pid],
        capture_output=True,
        timeout=5,
    )

    # Immediately try to copy — retry a few times in case of brief delay
    last_err = None
    for attempt in range(5):
        try:
            shutil.copy2(cookies_db, tmp_path)
            # Also copy journal/WAL if present
            for ext in ("-journal", "-wal", "-shm"):
                src = cookies_db + ext
                if os.path.isfile(src):
                    try:
                        shutil.copy2(src, tmp_path + ext)
                    except OSError:
                        pass
            return tmp_path
        except OSError as e:
            last_err = e
            time.sleep(0.05)  # 50ms between retries

    os.unlink(tmp_path)
    raise RuntimeError(f"Failed to copy Cookies database after killing Network Service: {last_err}")


def _open_cookies_db(cookies_db: str):
    """Open the Chromium cookies database.

    Strategy:
    1. Try direct SQLite connection (works if Claude Desktop is closed).
    2. Try copying the file (works if Claude Desktop is closed).
    3. Kill the Chromium Network Service to release its exclusive file lock,
       then immediately copy the file before Chromium restarts it.
    """
    # --- Attempt 1: direct connection (Claude Desktop not running) ---
    try:
        db_uri = f"file:///{cookies_db.replace(os.sep, '/')}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        conn.execute("SELECT 1 FROM cookies LIMIT 1")
        return conn
    except Exception:
        pass

    # --- Attempt 2: copy file (Claude Desktop not running, or non-exclusive lock) ---
    try:
        tmp_path = _copy_to_temp(cookies_db)
        conn = sqlite3.connect(tmp_path)
        conn.execute("SELECT 1 FROM cookies LIMIT 1")
        return conn
    except Exception:
        pass

    # --- Attempt 3: kill Network Service, copy file immediately ---
    tmp_path = _kill_and_copy_cookies(cookies_db)
    try:
        conn = sqlite3.connect(tmp_path)
        conn.execute("SELECT 1 FROM cookies LIMIT 1")
        return conn
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read Cookies database even after releasing the file lock: {exc}"
        ) from exc


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
