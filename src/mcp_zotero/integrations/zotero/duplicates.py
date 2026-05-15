"""Deteksi duplikat sederhana (DOI / judul ternormalisasi)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from mcp_zotero.integrations.zotero.client import ZoteroClient


def _norm_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t[:200]


def _doi_from_data(data: dict[str, Any]) -> str | None:
    d = (data.get("DOI") or "").strip()
    if d:
        return d.lower()
    extra = data.get("extra") or ""
    if isinstance(extra, str):
        for line in extra.splitlines():
            if line.lower().startswith("doi:"):
                return line.split(":", 1)[1].strip().lower()
    return None


async def scan_items_top(
    client: ZoteroClient,
    *,
    max_scan: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    limit = 100
    seen = 0
    while seen < max_scan:
        status, _, items = await client.get_items(
            subpath="/items/top",
            params={"limit": min(limit, max_scan - seen), "start": start, "format": "json"},
        )
        if status >= 400 or not isinstance(items, list) or not items:
            break
        for it in items:
            if seen >= max_scan:
                break
            seen += 1
            if isinstance(it, dict) and it.get("key") and isinstance(it.get("data"), dict):
                rows.append(it)
        if len(items) < limit:
            break
        start += limit
    return rows


async def find_duplicate_groups(
    client: ZoteroClient,
    *,
    by: str,
    max_scan: int,
) -> dict[str, Any]:
    by_l = {x.strip().lower() for x in by.split(",") if x.strip()}
    items = await scan_items_top(client, max_scan=max_scan)
    doi_groups: dict[str, list[str]] = defaultdict(list)
    title_groups: dict[str, list[str]] = defaultdict(list)
    for it in items:
        key = str(it.get("key"))
        data = it.get("data") or {}
        if not isinstance(data, dict):
            continue
        itype = data.get("itemType")
        if itype in ("attachment", "note", "annotation"):
            continue
        if "doi" in by_l:
            d = _doi_from_data(data)
            if d:
                doi_groups[d].append(key)
        if "title" in by_l:
            title = (data.get("title") or "").strip()
            if title:
                title_groups[_norm_title(title)].append(key)
    dup_doi = {k: v for k, v in doi_groups.items() if len(v) > 1}
    dup_title = {k: v for k, v in title_groups.items() if len(v) > 1}
    return {
        "scanned": len(items),
        "duplicate_doi_groups": dup_doi,
        "duplicate_title_groups": dup_title,
    }


async def merge_items_into_master(
    client: ZoteroClient,
    *,
    master_key: str,
    duplicate_keys: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    plan: list[dict[str, Any]] = []
    dup_keys = [k for k in duplicate_keys if k and k != master_key]
    for dk in dup_keys:
        children = await client.get_children(dk)
        child_list = children if isinstance(children, list) else []
        moves = []
        for ch in child_list:
            if not isinstance(ch, dict):
                continue
            ck = ch.get("key")
            if not ck:
                continue
            moves.append({"child_key": ck, "from_parent": dk, "to_parent": master_key})
        plan.append({"duplicate_key": dk, "child_moves": moves, "delete_duplicate_after": True})
    if dry_run:
        return {"dry_run": True, "plan": plan}
    summary: list[str] = []
    for step in plan:
        dk = step["duplicate_key"]
        for mv in step["child_moves"]:
            body = {"parentItem": master_key}
            await client.patch_item(str(mv["child_key"]), body)
            summary.append(f"pindah {mv['child_key']} ke bawah {master_key}")
        await client.delete_item(dk)
        summary.append(f"hapus duplikat {dk}")
    return {"dry_run": False, "done": True, "actions": summary}
