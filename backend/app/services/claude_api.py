"""
Async Claude API client using urllib (Cloudflare-compatible TLS fingerprint).

Includes retry with exponential backoff for rate-limited (429/529) and
transient server errors (500/502/503).
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0  # seconds
RETRYABLE_CODES = {429, 529, 500, 502, 503}


class ClaudeAPI:
    BASE = "https://claude.ai/api"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.6613.186 Safari/537.36"
    )

    def __init__(self, cookies: dict[str, str]):
        self.cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.org_id = cookies.get("lastActiveOrg")
        self.account_email: str | None = None
        self.account_name: str | None = None
        # org_id will be resolved in verify_session if not in cookies

    async def close(self):
        pass

    async def _resolve_org_id(self) -> str:
        """Fetch the organization ID from the API and capture account identity."""
        import logging
        logger = logging.getLogger(__name__)

        data = await self._request(f"{self.BASE}/organizations")
        orgs = json.loads(data)
        if not orgs:
            raise RuntimeError("No organizations found for this account")

        org = orgs[0]
        logger.info("orgs response keys: %s", list(org.keys()))

        # Capture account identity — try common field names
        for field in ("email_address", "email"):
            val = org.get(field)
            if val:
                self.account_email = val
                break

        for field in ("name", "display_name", "full_name"):
            val = org.get(field)
            if val:
                self.account_name = val
                break

        return org["uuid"]

    def _request_sync(self, url: str, accept: str = "application/json") -> bytes:
        """Make an authenticated GET request with retry on rate-limit/server errors."""
        import time
        req = urllib.request.Request(url)
        req.add_header("Cookie", self.cookie_str)
        req.add_header("User-Agent", self.USER_AGENT)
        req.add_header("Accept", accept)
        req.add_header("Referer", "https://claude.ai/")
        req.add_header("Origin", "https://claude.ai")

        for attempt in range(MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    # Check for Retry-After header
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning("GET %s → %d, retry %d/%d in %.1fs", url[:80], e.code, attempt + 1, MAX_RETRIES, wait)
                    time.sleep(wait)
                    continue
                raise

    async def _request(self, url: str, accept: str = "application/json") -> bytes:
        """Make an authenticated GET request, return raw bytes."""
        return await asyncio.to_thread(self._request_sync, url, accept)

    async def _get(self, path: str) -> dict | list:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        data = await self._request(url)
        return json.loads(data)

    async def verify_session(self) -> dict:
        """Verify session is valid. Always resolves org info for identity capture."""
        self.org_id = await self._resolve_org_id()
        convos = await self._get("chat_conversations")
        return {"valid": True, "org_id": self.org_id, "conversation_count": len(convos)}

    async def list_conversations(self) -> list[dict]:
        return await self._get("chat_conversations")

    async def get_conversation(self, uuid: str) -> dict:
        return await self._get(
            f"chat_conversations/{uuid}?tree=True&rendering_mode=messages"
        )

    async def list_projects(self) -> list[dict]:
        return await self._get("projects")

    async def get_project_docs(self, project_uuid: str) -> list[dict]:
        return await self._get(f"projects/{project_uuid}/docs")

    async def get_memory(self) -> dict:
        return await self._get("memory")

    async def get_project_memory(self, project_uuid: str) -> dict:
        """Fetch memory scoped to a specific project."""
        return await self._get(f"memory?project_uuid={project_uuid}")

    async def download_file(self, file_uuid: str, variant: str = "document_pdf") -> bytes:
        url = f"{self.BASE}/{self.org_id}/files/{file_uuid}/{variant}"
        return await self._request(url, accept="*/*")

    async def download_file_best_variant(self, file_info: dict) -> tuple[bytes, str] | None:
        """Try to download a file using the best available variant."""
        file_uuid = file_info.get("file_uuid") or file_info.get("uuid")
        file_name = file_info.get("file_name", "unknown")
        kind = file_info.get("file_kind", "")

        if kind == "document":
            variants = ["document_pdf"]
        elif kind == "image":
            variants = ["preview", "thumbnail"]
        else:
            variants = ["document_pdf", "preview", "thumbnail"]

        for variant in variants:
            try:
                data = await self.download_file(file_uuid, variant)
                return data, file_name
            except Exception:
                continue
        return None

    # ── WRITE METHODS ──────────────────────────────────────────────────

    def _post_sync(self, url: str, body: dict | None = None, extra_headers: dict | None = None) -> bytes:
        """POST with JSON body, with retry on rate-limit/server errors."""
        import time
        data = json.dumps(body or {}).encode("utf-8")

        for attempt in range(MAX_RETRIES + 1):
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Cookie", self.cookie_str)
            req.add_header("User-Agent", self.USER_AGENT)
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("Referer", "https://claude.ai/")
            req.add_header("Origin", "https://claude.ai")
            if extra_headers:
                for k, v in extra_headers.items():
                    req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                if e.code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning("POST %s → %d, retry %d/%d in %.1fs body=%s", url[:80], e.code, attempt + 1, MAX_RETRIES, wait, error_body[:200])
                    time.sleep(wait)
                    continue
                logger.error("POST %s → %d FAILED: %s", url[:80], e.code, error_body[:300])
                raise

    async def _post(self, path: str, body: dict | None = None, extra_headers: dict | None = None) -> dict:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        data = await asyncio.to_thread(self._post_sync, url, body, extra_headers)
        return json.loads(data)

    def _put_sync(self, url: str, body: dict) -> bytes:
        """PUT with JSON body, with retry on rate-limit/server errors."""
        import time
        data = json.dumps(body).encode("utf-8")

        for attempt in range(MAX_RETRIES + 1):
            req = urllib.request.Request(url, data=data, method="PUT")
            req.add_header("Cookie", self.cookie_str)
            req.add_header("User-Agent", self.USER_AGENT)
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("Referer", "https://claude.ai/")
            req.add_header("Origin", "https://claude.ai")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning("PUT %s → %d, retry %d/%d in %.1fs", url[:80], e.code, attempt + 1, MAX_RETRIES, wait)
                    time.sleep(wait)
                    continue
                raise

    async def _put(self, path: str, body: dict) -> dict:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        data = await asyncio.to_thread(self._put_sync, url, body)
        return json.loads(data)

    # ── Project write methods ──────────────────────────────────────────

    async def create_project(self, name: str, description: str = "") -> dict:
        """Create a new project. Returns {"uuid": ..., "name": ...}"""
        return await self._post("projects", {"name": name, "description": description, "is_private": True})

    async def add_project_doc(self, project_uuid: str, file_name: str, content: str) -> dict:
        """Add a knowledge document to a project."""
        return await self._post(f"projects/{project_uuid}/docs", {"file_name": file_name, "content": content})

    async def sync_project(self, project_uuid: str) -> None:
        """Sync a project after adding docs."""
        await self._post(f"projects/{project_uuid}/sync", {"projectUuid": project_uuid})

    # ── Memory ────────────────────────────────────────────────────────

    async def set_memory_controls(self, controls: list[str], project_uuid: str | None = None) -> dict:
        """Write memory via controls array. Anthropic processes these into memory text (up to 24h).
        This is the same mechanism claude.com/import-memory uses.
        """
        path = "memory/controls"
        if project_uuid:
            path = f"memory/controls?project_uuid={project_uuid}"
        return await self._put(path, {"controls": controls})

    # ── Conversation write methods ────────────────────────────────────

    async def create_conversation(self, title: str = "", project_uuid: str | None = None, model: str | None = None) -> dict:
        """Create a new conversation, optionally inside a project. Returns the conversation dict with uuid."""
        import uuid as _uuid
        body: dict = {
            "uuid": str(_uuid.uuid4()),
            "name": title,
            "is_temporary": False,
        }
        if project_uuid:
            body["project_uuid"] = project_uuid
        if model:
            body["model"] = model
        return await self._post("chat_conversations", body)

    def _multipart_upload_sync(self, url: str, file_bytes: bytes, file_name: str, mime_type: str) -> bytes:
        """POST a file as multipart/form-data with retry. Matches chrome's exact format."""
        import uuid as _uuid
        import time as _time

        boundary = f"----WebKitFormBoundary{_uuid.uuid4().hex[:16]}"
        body_parts = []
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\nContent-Type: {mime_type}\r\n\r\n".encode())
        body_parts.append(file_bytes)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        for attempt in range(MAX_RETRIES + 1):
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Cookie", self.cookie_str)
            req.add_header("User-Agent", self.USER_AGENT)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("Accept", "*/*")
            req.add_header("Referer", "https://claude.ai/")
            req.add_header("Origin", "https://claude.ai")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                if e.code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning("UPLOAD %s → %d, retry %d/%d in %.1fs body=%s", file_name, e.code, attempt + 1, MAX_RETRIES, wait, error_body[:200])
                    _time.sleep(wait)
                    continue
                logger.error("UPLOAD %s → %d FAILED: %s", file_name, e.code, error_body[:300])
                raise RuntimeError(f"HTTP {e.code} uploading '{file_name}': {error_body[:200]}") from e

    async def upload_file_to_conversation(self, conversation_uuid: str, file_bytes: bytes, file_name: str) -> dict:
        """Upload a file to a conversation (two-step: upload + convert).

        Returns the attachment dict to include in the completion request:
        {"file_name": ..., "file_size": ..., "file_type": ..., "extracted_content": ..., "path": ...}
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Step 1: Upload raw file via wiggle endpoint (uses /conversations/, NOT /chat_conversations/)
        upload_url = f"{self.BASE}/organizations/{self.org_id}/conversations/{conversation_uuid}/wiggle/upload-file"
        logger.info("UPLOAD step1 wiggle: %s (%d bytes, %s)", file_name, len(file_bytes), mime_type)
        upload_data = await asyncio.to_thread(self._multipart_upload_sync, upload_url, file_bytes, file_name, mime_type)
        upload_result = json.loads(upload_data)
        logger.info("UPLOAD step1 result: %s", json.dumps(upload_result)[:300])

        file_kind = upload_result.get("file_kind", "")

        # Step 2: Convert document — only for documents, not images
        if file_kind != "image" and not mime_type.startswith("image/"):
            convert_url = f"{self.BASE}/organizations/{self.org_id}/convert_document"
            logger.info("UPLOAD step2 convert_document: %s", file_name)
            try:
                convert_data = await asyncio.to_thread(self._multipart_upload_sync, convert_url, file_bytes, file_name, mime_type)
                convert_result = json.loads(convert_data)
                # Ensure file_size is always an integer
                convert_result["file_size"] = convert_result.get("file_size") or len(file_bytes)
                logger.info("UPLOAD step2 result: file_type=%s content_len=%d", convert_result.get("file_type"), len(convert_result.get("extracted_content", "")))
                return convert_result
            except Exception as e:
                logger.warning("convert_document for '%s' failed: %s — using fallback", file_name, e)

        # For images or convert_document failures: build attachment from upload result
        logger.info("UPLOAD using image/fallback attachment for: %s", file_name)
        return {
            "file_name": upload_result.get("file_name", file_name),
            "file_size": upload_result.get("size_bytes") or len(file_bytes),
            "file_type": file_name.rsplit(".", 1)[-1] if "." in file_name else "",
            "extracted_content": "",
            "path": upload_result.get("path", ""),
        }

    async def send_handover_message(self, conversation_uuid: str, text: str, file_attachments: list[dict] | None = None) -> None:
        """Send the handover prompt as the first message in a new conversation.

        The /completion endpoint returns Server-Sent Events (SSE), not JSON.
        We stream the response and consume it until the server closes the connection.
        file_attachments: list of dicts from upload_file_to_conversation (convert_document format).
        """
        import time as _time

        body = {
            "prompt": text,
            "timezone": "UTC",
            "personalized_styles": [],
            "tools": [],
            "attachments": file_attachments or [],
            "files": [],
            "rendering_mode": "messages",
        }

        logger.info("COMPLETION request: conv=%s attachments=%d prompt_len=%d",
                     conversation_uuid[:8], len(file_attachments or []), len(text))
        if file_attachments:
            for att in file_attachments:
                logger.info("  attachment: file_name=%s file_type=%s file_size=%s content_len=%s",
                            att.get("file_name"), att.get("file_type"),
                            att.get("file_size"), len(att.get("extracted_content", "")))

        url = f"{self.BASE}/organizations/{self.org_id}/chat_conversations/{conversation_uuid}/completion"

        def _do_completion():
            for attempt in range(MAX_RETRIES + 1):
                data = json.dumps(body).encode("utf-8")
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Cookie", self.cookie_str)
                req.add_header("User-Agent", self.USER_AGENT)
                req.add_header("Content-Type", "application/json")
                req.add_header("Accept", "text/event-stream")
                req.add_header("Referer", "https://claude.ai/")
                req.add_header("Origin", "https://claude.ai")
                try:
                    with urllib.request.urlopen(req, timeout=180) as resp:
                        while True:
                            chunk = resp.read(4096)
                            if not chunk:
                                break
                        logger.info("COMPLETION %s → success", conversation_uuid[:8])
                        return
                except urllib.error.HTTPError as e:
                    error_body = ""
                    try:
                        error_body = e.read().decode("utf-8", errors="replace")[:500]
                    except Exception:
                        pass
                    logger.error("COMPLETION %s → %d body=%s", conversation_uuid[:8], e.code, error_body[:300])
                    if e.code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                        wait = INITIAL_BACKOFF * (2 ** attempt)
                        retry_after = e.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait = max(wait, float(retry_after))
                            except ValueError:
                                pass
                        logger.warning("COMPLETION %s → %d, retry %d/%d in %.1fs", conversation_uuid[:8], e.code, attempt + 1, MAX_RETRIES, wait)
                        _time.sleep(wait)
                        continue
                    raise

        await asyncio.to_thread(_do_completion)
