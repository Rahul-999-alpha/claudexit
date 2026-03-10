"""
Async Claude API client using httpx.
"""

import httpx


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
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Cookie": self.cookie_str,
                "User-Agent": self.USER_AGENT,
                "Referer": "https://claude.ai/",
                "Origin": "https://claude.ai",
            },
        )

    async def close(self):
        await self._client.aclose()

    async def _request(self, url: str, accept: str = "application/json") -> bytes:
        """Make an authenticated GET request, return raw bytes."""
        resp = await self._client.get(url, headers={"Accept": accept})
        resp.raise_for_status()
        return resp.content

    async def _get(self, path: str) -> dict | list:
        url = f"{self.BASE}/organizations/{self.org_id}/{path}"
        data = await self._request(url)
        import json
        return json.loads(data)

    async def verify_session(self) -> dict:
        """Verify session is valid by fetching organizations."""
        data = await self._request(f"{self.BASE}/organizations")
        import json
        orgs = json.loads(data)
        return {"valid": True, "org_id": self.org_id, "organizations": orgs}

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
