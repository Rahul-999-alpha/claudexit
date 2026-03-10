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
        if not self.org_id:
            raise RuntimeError("lastActiveOrg cookie not found")

    async def close(self):
        pass

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
        """Verify session is valid by fetching the conversation list."""
        # Use chat_conversations instead of /organizations — more reliable
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
