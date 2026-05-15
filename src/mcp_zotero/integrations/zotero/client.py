"""Klien async untuk Zotero Web API v3."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from mcp_zotero.config.settings import Settings


class ZoteroClient:
    def __init__(self, settings: Settings, timeout: float = 120.0) -> None:
        self._settings = settings
        self._timeout = timeout
        self._base = "https://api.zotero.org"
        self._prefix = self._library_prefix()

    def _library_prefix(self) -> str:
        t = self._settings.zotero_library_type
        lid = self._settings.zotero_library_id
        if t == "group":
            return f"/groups/{lid}"
        return f"/users/{lid}"

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {
            "Zotero-API-Key": self._settings.zotero_api_key,
            "Zotero-API-Version": "3",
            "User-Agent": "mcp-zotero/0.1 (Zotero MCP)",
        }
        if extra:
            h.update(extra)
        return h

    async def _request_raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        url = f"{self._base}{path}"
        if params:
            q = urlencode(params, doseq=True)
            url = f"{url}?{q}"
        hdrs = self._headers(headers)
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            for attempt in range(6):
                resp = await client.request(method, url, headers=hdrs, json=json_body)
                rh = dict(resp.headers)
                bo = rh.get("Backoff")
                if bo and str(bo).isdigit():
                    await asyncio.sleep(min(float(bo), 30.0))
                if resp.status_code == 429:
                    ra = rh.get("Retry-After")
                    wait = float(ra) if ra and str(ra).isdigit() else 2.0 * (attempt + 1)
                    await asyncio.sleep(min(wait, 60.0))
                    continue
                return resp.status_code, rh, resp.content
        return 429, {}, b""

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        status, rh, body = await self._request_raw(
            method, path, params=params, json_body=json_body, headers=headers
        )
        if not body:
            return status, rh, None
        try:
            return status, rh, json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return status, rh, body.decode("utf-8", errors="replace")

    async def library_version(self) -> int:
        status, headers, _ = await self._request_raw(
            "GET",
            f"{self._prefix}/items",
            params={"limit": 1},
        )
        if status >= 400:
            raise RuntimeError(f"Gagal membaca versi pustaka Zotero: HTTP {status}")
        # httpx normalizes header names to lowercase
        v = headers.get("last-modified-version")
        if v and str(v).isdigit():
            return int(v)
        # Fallback: gunakan 0 jika header tidak ada (Zotero akan tolak jika versi salah)
        return 0

    async def get_items(
        self,
        *,
        subpath: str = "/items",
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        p = params.copy() if params else {}
        return await self.request_json("GET", f"{self._prefix}{subpath}", params=p)

    async def get_item(self, item_key: str, *, params: dict[str, Any] | None = None) -> Any:
        p = params.copy() if params else {}
        status, _, data = await self.request_json(
            "GET", f"{self._prefix}/items/{quote(item_key)}", params=p
        )
        if status >= 400:
            raise RuntimeError(f"Item {item_key}: HTTP {status} — {data}")
        return data

    async def get_item_bibtex(self, item_key: str) -> str:
        status, _, body = await self._request_raw(
            "GET",
            f"{self._prefix}/items/{quote(item_key)}",
            params={"format": "bibtex"},
        )
        if status >= 400:
            raise RuntimeError(f"BibTeX {item_key}: HTTP {status}")
        return body.decode("utf-8", errors="replace")

    async def get_children(self, item_key: str) -> Any:
        status, _, data = await self.request_json(
            "GET", f"{self._prefix}/items/{quote(item_key)}/children"
        )
        if status >= 400:
            raise RuntimeError(f"Children {item_key}: HTTP {status} — {data}")
        return data

    async def get_fulltext(self, item_key: str) -> Any:
        status, _, data = await self.request_json(
            "GET", f"{self._prefix}/items/{quote(item_key)}/fulltext"
        )
        if status == 404:
            return None
        if status >= 400:
            raise RuntimeError(f"Fulltext {item_key}: HTTP {status} — {data}")
        return data

    async def get_collections(self, *, top: bool = False) -> Any:
        sub = "/collections/top" if top else "/collections"
        status, _, data = await self.request_json("GET", f"{self._prefix}{sub}")
        if status >= 400:
            raise RuntimeError(f"Collections: HTTP {status} — {data}")
        return data

    async def get_tags(self, *, params: dict[str, Any] | None = None) -> Any:
        p = params.copy() if params else {}
        status, _, data = await self.request_json("GET", f"{self._prefix}/tags", params=p)
        if status >= 400:
            raise RuntimeError(f"Tags: HTTP {status} — {data}")
        return data

    async def download_file_bytes(self, item_key: str) -> bytes:
        path = f"{self._prefix}/items/{quote(item_key)}/file"
        status, _, body = await self._request_raw("GET", path)
        if status >= 400:
            raise RuntimeError(f"Unduh berkas {item_key}: HTTP {status}")
        return body

    async def write_items(
        self,
        items: list[dict[str, Any]],
        *,
        library_version: int | None = None,
    ) -> Any:
        ver = library_version if library_version is not None else await self.library_version()
        status, _, data = await self.request_json(
            "POST",
            f"{self._prefix}/items",
            json_body=items,
            headers={"If-Unmodified-Since-Version": str(ver)},
        )
        if status >= 400:
            raise RuntimeError(f"POST items: HTTP {status} — {data}")
        return data

    async def post_collections(self, rows: list[dict[str, Any]]) -> Any:
        ver = await self.library_version()
        status, _, data = await self.request_json(
            "POST",
            f"{self._prefix}/collections",
            json_body=rows,
            headers={"If-Unmodified-Since-Version": str(ver)},
        )
        if status >= 400:
            raise RuntimeError(f"POST collections: HTTP {status} — {data}")
        return data

    async def patch_item(
        self,
        item_key: str,
        body: dict[str, Any],
    ) -> Any:
        ver = await self.library_version()
        status, _, data = await self.request_json(
            "PATCH",
            f"{self._prefix}/items/{quote(item_key)}",
            json_body=body,
            headers={"If-Unmodified-Since-Version": str(ver)},
        )
        if status >= 400:
            raise RuntimeError(f"PATCH item {item_key}: HTTP {status} — {data}")
        return data

    async def delete_item(self, item_key: str) -> None:
        try:
            ver = await self.library_version()
        except Exception:
            ver = 0
        status, _, data = await self.request_json(
            "DELETE",
            f"{self._prefix}/items/{quote(item_key)}",
            headers={"If-Unmodified-Since-Version": str(ver)},
        )
        if status not in (204, 200):
            raise RuntimeError(f"DELETE item {item_key}: HTTP {status} — {data}")

    async def new_item_template(self, item_type: str) -> dict[str, Any]:
        status, _, data = await self.request_json(
            "GET",
            f"{self._prefix}/items/new",
            params={"itemType": item_type},
        )
        if status >= 400:
            raise RuntimeError(f"Template {item_type}: HTTP {status} — {data}")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        if isinstance(data, dict):
            return data
        raise RuntimeError("Template item tidak valid.")

    async def create_collection(
        self,
        name: str,
        *,
        parent_collection: str | None = None,
    ) -> Any:
        row: dict[str, Any] = {"name": name}
        if parent_collection:
            row["parentCollection"] = parent_collection
        else:
            row["parentCollection"] = False
        return await self.post_collections([row])

    async def add_items_to_collection(
        self,
        collection_key: str,
        item_keys: list[str],
    ) -> None:
        """Menambahkan item ke koleksi via PATCH setiap item (field collections)."""
        for key in item_keys:
            item = await self.get_item(key)
            data = item.get("data", item) if isinstance(item, dict) else item
            if not isinstance(data, dict):
                continue
            cols = list(data.get("collections") or [])
            if collection_key not in cols:
                cols.append(collection_key)
            await self.patch_item(key, {"collections": cols})

    async def remove_items_from_collection(
        self,
        collection_key: str,
        item_keys: list[str],
    ) -> None:
        for key in item_keys:
            item = await self.get_item(key)
            data = item.get("data", item) if isinstance(item, dict) else item
            if not isinstance(data, dict):
                continue
            cols = [c for c in (data.get("collections") or []) if c != collection_key]
            await self.patch_item(key, {"collections": cols})
