"""
Async Claude API client using urllib (Cloudflare-compatible TLS fingerprint).
"""

import asyncio
import json
import urllib.request


class ClaudeAPI:
    BASE = "https://claude.ai/api"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.6613.186 Safari/537.36"
    )

    def __init__(self, cookies: dict[str, str]):
        self.cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.org_id = cookies.get("lastActiveOrg")
        # org_id will be resolved in verify_session if not in cookies

    async def close(self):
        pass

    async def _resolve_org_id(self) -> str:
        """Fetch the organization ID from the API."""
        data = await self._request(f"{self.BASE}/organizations")
        orgs = json.loads(data)
        if not orgs:
            raise RuntimeError("No organizations found for this account")
        # Use the first org (most accounts have one)
        return orgs[0]["uuid"]

    def _request_sync(self, url: str, accept: str = "application/json") -> bytes:
        """Make an authenticated GET request (sync, runs in thread pool)."""
        req = urllib.request.Request(url)
        req.add_header("Cookie", self.cookie_str)
        req.add_header("User-Agent", self.USER_AGENT)
        req.add_header("Accept", accept)
        req.add_header("Referer", "https://claude.ai/")
        req.add_header("Origin", "https://claude.ai")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    async def _request(self, url: str, accept: str = "application/json") -> bytes:
        """Make an authenticated GET request, return raw bytes."""
        return await asyncio.to_thread(self._request_sync, url, accept)

    async def _get(self, path: str) -> dict | list:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        data = await self._request(url)
        return json.loads(data)

    async def verify_session(self) -> dict:
        """Verify session is valid. Resolves org_id if missing."""
        if not self.org_id:
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
        """POST with JSON body (sync, runs in thread pool)."""
        import urllib.error
        data = json.dumps(body or {}).encode("utf-8")
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    async def _post(self, path: str, body: dict | None = None, extra_headers: dict | None = None) -> dict:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        data = await asyncio.to_thread(self._post_sync, url, body, extra_headers)
        return json.loads(data)

    def _put_sync(self, url: str, body: dict) -> bytes:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Cookie", self.cookie_str)
        req.add_header("User-Agent", self.USER_AGENT)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("Referer", "https://claude.ai/")
        req.add_header("Origin", "https://claude.ai")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

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

    async def create_conversation(self, title: str = "", project_uuid: str | None = None) -> dict:
        """Create a new conversation, optionally inside a project. Returns the conversation dict with uuid."""
        import uuid as _uuid
        body: dict = {
            "uuid": str(_uuid.uuid4()),
            "name": title,
            "is_temporary": False,
        }
        if project_uuid:
            body["project_uuid"] = project_uuid
        return await self._post("chat_conversations", body)

    async def upload_file_to_conversation(self, conversation_uuid: str, file_bytes: bytes, file_name: str) -> dict:
        """Upload a file to a conversation via multipart form. Returns {"file_uuid": ..., "file_name": ...}"""
        import uuid as _uuid
        boundary = f"----WebKitFormBoundary{_uuid.uuid4().hex[:16]}"
        body_parts = []
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
        body_parts.append(file_bytes)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        url = f"{self.BASE}/organizations/{self.org_id}/conversations/{conversation_uuid}/wiggle/upload-file"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Cookie", self.cookie_str)
        req.add_header("User-Agent", self.USER_AGENT)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("Referer", "https://claude.ai/")
        req.add_header("Origin", "https://claude.ai")

        def _do():
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()

        data = await asyncio.to_thread(_do)
        return json.loads(data)

    async def send_handover_message(self, conversation_uuid: str, text: str, file_uuids: list[str] | None = None) -> None:
        """Send the handover prompt as the first message in a new conversation.
        Uses the completion endpoint with streaming=False to get a response.
        file_uuids: list of UUIDs from upload_file_to_conversation, to attach to the message.
        """
        attachments = []
        if file_uuids:
            for fuid in file_uuids:
                attachments.append({"type": "tool_result", "file_uuid": fuid})

        body = {
            "prompt": text,
            "timezone": "UTC",
            "personalized_styles": [],
            "tools": [],
            "attachments": attachments,
            "files": file_uuids or [],
            "rendering_mode": "messages",
            "stream": False,
        }
        await self._post(f"chat_conversations/{conversation_uuid}/completion", body)
